# training/src/train.py
import argparse
import os
import sys
from pathlib import Path
import yaml
import torch
from ultralytics import YOLO, settings
import time
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_DIR = PROJECT_ROOT / "training"

def print_env_info() -> None:
    print(f"PyTorch версия: {torch.__version__}")
    print(f"CUDA доступна: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA версия: {torch.version.cuda}")
        print(f"Количество GPU: {torch.cuda.device_count()}")
        print(f"Текущее GPU: {torch.cuda.get_device_name(0)}")
        mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"Память GPU: {mem_gb:.2f} GB")
    else:
        print("CUDA недоступна, будет использоваться CPU (тренировка будет медленнее)")


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"YAML-конфиг не найден: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_cfg(
    train_cfg_path: Path,
    data_cfg_path: Path,
    model_path: Path,
    run_name: str,
    dataset_name: str,
    batch: int | None = None,
) -> dict:
    cfg = load_yaml(train_cfg_path)

    cfg.update(
        {
            "model": str(model_path),
            "data": str(data_cfg_path),
            "device": 0 if torch.cuda.is_available() else "cpu",
            "project": str(TRAINING_DIR / "runs" / dataset_name),
            "name": run_name,
            # "resume": True,
        }
    )

    if batch is not None:
        cfg["batch"] = batch

    print("\nИспользуемые ключевые параметры:")
    keys = [
        "model",
        "data",
        "epochs",
        "lr0",
        "patience",
        "batch",
        "imgsz",
        "mosaic",
        "mixup",
        "copy_paste",
        "box",
        "cls",
        "dfl",
        "project",
        "name",
    ]
    for k in keys:
        val = cfg.get(k, "<нет в конфиге>")
        print(f"{k}: {val}")

    return cfg


def train_yolo(cfg: dict) -> Path:
    model = YOLO(cfg["model"])
    results = model.train(**cfg)

    # фактическая папка (с учётом суффиксов)
    run_dir = Path(results.save_dir)
    best_path = run_dir / "weights" / "best.pt"

    print("\nТРЕНИРОВКА ЗАВЕРШЕНА!")
    print(f"Результаты: {run_dir}")
    if best_path.is_file():
        print(f"Лучшие веса: {best_path}")
    else:
        print("Внимание: best.pt не найден, возможно обучение завершилось некорректно.")

    return best_path


def eval_on_test(
    best_model_path: Path,
    data_cfg_path: Path,
    base_run_name: str,
    imgsz: int = 640,
    batch: int = 24,
    device: int | str = 0,
) -> None:
    """Прогоняет лучшую модель по test split и логирует метрики."""
    if not best_model_path.is_file():
        print(f"\n[eval] best.pt не найден, пропускаем тестовую оценку: {best_model_path}")
        return

    print("\n------ ТЕСТОВАЯ ОЦЕНКА МОДЕЛИ ------")
    print(f"Модель: {best_model_path}")
    print(f"Data YAML: {data_cfg_path}")

    model = YOLO(str(best_model_path))

    metrics = model.val(
        data=str(data_cfg_path),
        split="test",
        imgsz=imgsz,
        batch=batch,
        device=device,
        save_json=True,
        project=str(TRAINING_DIR / "runs" / "test_eval"),
        name=f"{base_run_name}_test",
    )

    print("\nРезультаты тестовой оценки:")
    print(f"mAP@0.5-0.95: {metrics.box.map:.4f}")
    print(f"mAP@0.5:      {metrics.box.map50:.4f}")
    print(f"per-class AP: {metrics.box.maps}")


def check_mlflow_server(tracking_uri: str, timeout: float = 2.0) -> bool:
    if not tracking_uri.startswith(("http://", "https://")):
        return True

    candidates = [
        tracking_uri.rstrip("/") + "/health",
        tracking_uri.rstrip("/") + "/",
    ]

    for url in candidates:
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code < 500:
                return True
        except requests.RequestException:
            pass

    return False


def wait_for_mlflow_server(tracking_uri: str) -> None:
    while not check_mlflow_server(tracking_uri):
        print(f"\n[MLflow] Сервер недоступен: {tracking_uri}")
        print("[MLflow] Запустите MLflow server и нажмите Enter...")
        input()
        time.sleep(0.5)

    print(f"[MLflow] Сервер доступен: {tracking_uri}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Обучение YOLO-модели на RDD-датасете (training/src/train.py)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="yolo12n.pt",
        help="Имя файла предобученной модели в training/pretrained_models",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="yolo12n_rdd_default_run",
        help="Имя запуска (name в Ultralytics, подкаталог в runs/DATASET_NAME).",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="road_damage_yolo",
        help="Имя MLflow-эксперимента.",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="RDD_SPLIT",
        help="Имя поддиректории датасета (используется для имени папки runs/DATASET_NAME).",
    )
    parser.add_argument(
        "--data-config",
        type=str,
        default="rdd_split.yaml",
        help="Файл конфигурации датасета из training/configs/data/.",
    )
    parser.add_argument(
        "--train-config",
        type=str,
        default="args.yaml",
        help="Файл train-конфига из training/configs/train/.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=32,
        help="Размер batch (переопределяет значение из train-конфига).",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Не запускать оценку на test split после обучения.",
    )

    return parser.parse_args()


def main() -> None:
    os.chdir(PROJECT_ROOT)
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"Текущая директория: {Path.cwd()}")

    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    print_env_info()

    args = parse_args()

    # Включаем Ultralytics + MLflow и настраиваем окружение
    settings.update({"mlflow": True})
    os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5000"
    os.environ["MLFLOW_EXPERIMENT_NAME"] = args.experiment
    os.environ["MLFLOW_RUN"] = args.run_name
    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    wait_for_mlflow_server(tracking_uri)

    train_cfg_path = TRAINING_DIR / "configs" / "train" / args.train_config
    data_cfg_path = TRAINING_DIR / "configs" / "data" / args.data_config
    raw_model_path = Path(args.model)

    if raw_model_path.is_file():
        # Явно указан путь к .pt (best.pt/last.pt и т.п.)
        model_path = raw_model_path
    else:
        # Иначе ищем в training/pretrained_models
        model_path = TRAINING_DIR / "pretrained_models" / args.model

    if not model_path.is_file():
        raise FileNotFoundError(f"Предобученная модель не найдена: {model_path}")

    cfg = build_cfg(
        train_cfg_path=train_cfg_path,
        data_cfg_path=data_cfg_path,
        model_path=model_path,
        run_name=args.run_name,
        dataset_name=args.dataset_name,
        batch=args.batch,
    )

    best_model_path = train_yolo(cfg)

    if not args.no_test:
        eval_on_test(
            best_model_path=best_model_path,
            data_cfg_path=data_cfg_path,
            base_run_name=args.run_name,
            imgsz=cfg.get("imgsz", 640),
            batch=min(args.batch, 24),
            device=cfg.get("device", 0),
        )
    else:
        print("\nТестовая оценка (--no-test) отключена.")

if __name__ == "__main__":
    main()