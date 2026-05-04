# tracking/motion.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from .models import ShiftEstimate


@dataclass(slots=True)
class MotionEstimator:
    """Оценка глобального межкадрового сдвига по оптическому потоку.

    Класс отвечает только за оценку движения фона между двумя соседними
    grayscale-кадрами. Результат (dx, dy) используется трекером для
    motion compensation при предсказании bbox треков.
    """

    # ROI задаётся в долях от ширины/высоты кадра.
    # Здесь выбирается центрально-нижняя часть кадра, где обычно находится дорога.
    roi_x1_rel: float = 0.20
    roi_x2_rel: float = 0.80
    roi_y1_rel: float = 0.50
    roi_y2_rel: float = 0.85

    # Параметры выбора характерных точек (углов), для последующего отслеживания LK.
    max_corners: int = 200
    quality_level: float = 0.01
    min_distance: int = 10
    block_size: int = 7

    # Параметры pyramidal LK.
    lk_win_size: tuple[int, int] = (21, 21)
    lk_max_level: int = 3

    # Пороги для фильтрации и устойчивости оценки.
    max_magnitude: float = 60.0
    min_features: int = 20
    min_tracked: int = 20
    min_after_mag_filter: int = 12
    min_inliers: int = 12
    residual_inlier_threshold: float = 5.0
    max_spread: float = 12.0
    clip_dx: float = 30.0
    clip_dy: float = 30.0
    smooth_alpha: float = 0.7

    def get_motion_roi_rect(self, h: int, w: int) -> tuple[int, int, int, int]:
        """Возвращает прямоугольник ROI для оценки движения.

        ROI ограничивает область, по которой считается оптический поток.
        Это снижает вычислительную нагрузку и уменьшает влияние неба,
        краёв кадра и других нерелевантных областей.
        """
        x1 = int(w * self.roi_x1_rel)
        x2 = int(w * self.roi_x2_rel)
        y1 = int(h * self.roi_y1_rel)
        y2 = int(h * self.roi_y2_rel)

        x1 = max(0, min(x1, w - 1))
        x2 = max(x1 + 1, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(y1 + 1, min(y2, h))

        return x1, y1, x2, y2

    def estimate_global_shift(
        self,
        prev_gray: Optional[np.ndarray],
        curr_gray: np.ndarray,
        last_shift: Optional[ShiftEstimate] = None,
    ) -> ShiftEstimate:
        """Оценивает глобальный сдвиг между двумя ROI-патчами.

        Сначала на предыдущем ROI выбираются corner features, затем они
        отслеживаются методом Lucas–Kanade на текущем ROI. Итоговый dx/dy
        вычисляется по медианному сдвигу inlier-точек с несколькими
        фильтрами для отсечения шума и выбросов.
        """
        if prev_gray is None:
            return ShiftEstimate(reason="no_prev_frame")

        if prev_gray.shape != curr_gray.shape:
            return ShiftEstimate(reason="shape_mismatch")

        # Выбираем устойчивые точки (углы) на предыдущем ROI.
        features = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=self.max_corners,
            qualityLevel=self.quality_level,
            minDistance=self.min_distance,
            blockSize=self.block_size,
        )
        if features is None:
            return ShiftEstimate(reason="no_features")

        num_features = len(features)
        if num_features < self.min_features:
            return ShiftEstimate(num_features=num_features, reason="too_few_features")

        # Отслеживаем выбранные точки на текущем ROI с помощью pyramidal LK.
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray,
            curr_gray,
            features,
            None,
            winSize=self.lk_win_size,
            maxLevel=self.lk_max_level,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )
        if next_pts is None or status is None:
            return ShiftEstimate(num_features=num_features, reason="lk_failed")

        status = status.reshape(-1).astype(bool)
        p0 = features.reshape(-1, 2)[status]
        p1 = next_pts.reshape(-1, 2)[status]

        num_tracked = len(p0)
        if num_tracked < self.min_tracked:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                reason="too_few_tracked",
            )

        flow = p1 - p0
        dx_all = flow[:, 0]
        dy_all = flow[:, 1]
        mag = np.sqrt(dx_all**2 + dy_all**2)

        # Сначала убираем явно нереалистические сдвиги по модулю.
        valid_mag = mag <= self.max_magnitude
        dx_all = dx_all[valid_mag]
        dy_all = dy_all[valid_mag]

        if len(dx_all) < self.min_after_mag_filter:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                reason="too_few_after_mag_filter",
            )

        # Медианный сдвиг по всем векторим — первая грубая оценка движения.
        dx_med = float(np.median(dx_all))
        dy_med = float(np.median(dy_all))

        # Оцениваем согласованность векторов с медианной оценкой и оставляем inliers.
        residual = np.sqrt((dx_all - dx_med) ** 2 + (dy_all - dy_med) ** 2)
        inliers = residual < self.residual_inlier_threshold
        num_inliers = int(np.sum(inliers))

        if num_inliers < self.min_inliers:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                num_inliers=num_inliers,
                reason="too_few_inliers",
            )

        dx = float(np.median(dx_all[inliers]))
        dy = float(np.median(dy_all[inliers]))
        spread = float(np.median(residual[inliers])) if num_inliers > 0 else 9999.0

        # Если inlier-вектора слишком разнонаправленные, оценку считаем
        # ненадёжной и не используем её в трекере.
        if spread > self.max_spread:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                num_inliers=num_inliers,
                spread=spread,
                reason="spread_too_large",
            )

        # Жёстко ограничиваем максимальный сдвиг по обеим осям.
        dx = float(np.clip(dx, -self.clip_dx, self.clip_dx))
        dy = float(np.clip(dy, -self.clip_dy, self.clip_dy))

        # Сглаживание по времени для снижения дрожания между кадрами.
        if last_shift is not None and last_shift.ok:
            dx = self.smooth_alpha * dx + (1.0 - self.smooth_alpha) * last_shift.dx
            dy = self.smooth_alpha * dy + (1.0 - self.smooth_alpha) * last_shift.dy

        return ShiftEstimate(
            dx=dx,
            dy=dy,
            ok=True,
            num_features=num_features,
            num_tracked=num_tracked,
            num_inliers=num_inliers,
            spread=spread,
            reason="ok",
        )