## Детекция дефектов дорожного полотна (MVP)

Минимальный прототип сервиса для детекции дефектов дорожного полотна с помощью модели YOLO, доступный через REST API и Jupyter Notebook.

---

### 1. Описание проекта

Проект представляет собой микросервис на FastAPI с одним endpoint'ом `/api/v1/test/detect`, который принимает изображение дороги в формате base64 и возвращает список обнаруженных дефектов с координатами и уверенностью модели.  
Для наглядной демонстрации предусмотрен Jupyter-ноутбук, который отправляет запросы к API, визуализирует результаты детекции и выводит базовые метрики времени обработки.

### 2. Структура репозитория

#### Текущее состояние (`road_monitoring/`)

Сейчас в репозитории реализовано следующее.

```text
road_monitoring/
├── main.py
├── config.yaml
├── requirements.txt
├── Readme.md
├── models/                # в .gitignore; локально, напр. epoch50.pt (см. config.yaml)
├── api/
│   └── rest_api.py
├── pipeline/
│   ├── core.py
│   └── stages.py
├── inference/
│   └── yolo_detector.py
├── core/
│   └── frame_packet.py
├── sensors/
│   ├── ffmpeg_camera.py
│   └── rtsp_streamer.py
├── scripts/
│   ├── start_mediamtx_rtsp.ps1
│   ├── start_mediamtx_rtsp.sh
│   ├── rtsp_view.ps1
│   └── rtsp_view.sh
├── test_videos/
│   └── download_link.md
└── training/                  # ноутбуки обучения, не обязательны для деплоя
```

**Ключевые компоненты:**

- `main.py` — точка входа: конфигурация, захват RTSP, пайплайн, REST API, при необходимости выходной RTSP.
- `api/rest_api.py` — FastAPI, в т.ч. `/api/v1/test/detect`.
- `pipeline/` — сборка стадий обработки видео (`core.py`, `stages.py`).
- `inference/yolo_detector.py` — загрузка YOLO и инференс.
- `core/frame_packet.py` — контейнер кадра для пайплайна.
- `sensors/` — захват RTSP через FFmpeg и публикация превью-потока.
- `scripts/` — вспомогательные сценарии для MediaMTX и просмотра RTSP.
- `models/` — веса модели (каталог в `.gitignore`).
- `training/` — ноутбуки обучения; для деплоя edge не обязательны.

#### Планируемые дополнения (`road-damage-edge`)

К полноценной edge-версии планируется **дописать** (ниже — только новые или меняющиеся части; `api/`, `pipeline/`, `inference/`, `core/`, актуальные модули `sensors/` и остальное из дерева выше сохраняются и развиваются).

```text
road-damage-edge/  (дополнения к road_monitoring/)
├── models/
│   └── yolo8.rknn              # YOLOv8 в формате RKNN для NPU
├── storage/
│   ├── minio_client.py         # медиа и GeoJSON в S3/MinIO
│   └── sqlite_db.py            # локальная БД events.db
├── messenger/
│   └── mqtt_client.py          # события в MQTT-брокер
├── sensors/
│   ├── gnss.py                 # ГНСС
│   └── imu.py                  # ИИБ
├── road-damage.service         # systemd на SoC RK3588
└── test_videos/
    └── video_1.mkv             # тестовый материал для RTSP
```

Кратко: `storage/` — SQLite и MinIO; `messenger/` — MQTT; датчики — ГНСС и ИИБ; развёртывание — unit-файл systemd; модель на edge — RKNN.

```text
Интерфейсы ввода
Рабочий режим:
├── Камера: RTSP:// (H.264 1080p30)
├── IMU
└── GNSS


Интерфейсы вывода - критические события  
Критические события (Риск высокий/критический): 
├── MQTT 5.0: road-damage/{vehicle_id}/evt-{event_id}-GeoJSON 
└── MinIO S3: ┬── s3://events/{vehicle_id}/evt-{event_id}.mp4
  └── s3://events/{vehicle_id}/evt-{event_id}.jpg


 4.3.3 Интерфейсы вывода - обычные события
 Обычные события. Синхронизация ежедневно или по запросу:
└── REST sync: POST /api/v1/sync 
├── MinIO S3://events/{vehicle_id}/evt-{event_id}.mp4
├── MinIO S3://events/{vehicle_id}/evt-{event_id}.jpg
└── MinIO S3://events/{vehicle_id}/evt-{event_id}-GeoJSON


4.3.4 Архитектура REST API Endpoints

REST API endpoints (http://edge.local:8080/api/v1/):
├── GET /api/v1/status 
├── GET /api/v1/config 
├── PUT /api/v1/config 
├── GET /api/v1/events
├── POST /api/v1/sync
└── POST /api/v1/test/detect 

REST API сервиса road‑damage‑edge предоставляет базовый набор endpoint’ов (базовый URL http://edge.local:8080/api/v1/), используемых внешними системами для мониторинга и интеграци:
GET /status — мониторинг состояния системы (CPU/FPS/MinIO/MQTT).
GET /config — получение актуальной конфигурации сервиса (параметры модели, источники данных, пороги срабатывания);
PUT /config — обновление конфигурации без перезагрузки устройства;
GET /events — получение списка зафиксированных событий из локальной БД SQLite с возможностью фильтрации по времени и уровню риска;
POST /sync — инициирование синхронизации событий и связанных медиафайлов (видео, кадры, GeoJSON) с хранилищем MinIO;
POST /test/detect — тестовый endpoint для детекции по одиночному изображению (base64), используемый в MVP‑прототипе и для отладки модели.
```

#### Основная задача MVP

Показать сквозной сценарий: от входного изображения до JSON-ответа сервиса и визуализации детекций.

#### Технологическая схема обработки видеоданных для выявления дефектов дорожного покрытия и классификации по степени риска

```text
Кадр с камеры
   ↓
Изменение размера / нормализация
   ↓
Маска области дороги
   ↓
Обнаружение дефектов (YOLO)
   ↓
Постобработка обнаружений
   ├─ фильтрация по уверенности, размеру, зоне дороги
   └─ подавление пересечений (NMS) между рамками
   ↓
Простое сопровождение (трекер) и временное подтверждение
   ├─ сопоставление рамок между кадрами
   ├─ обновление траекторий дефектов
   └─ подтверждение устойчивых дефектов
   ↓
Быстрое вычисление признаков
   ├─ выбоины: площадь рамки, форма, положение
   ├─ трещины: диагональ рамки, отношение сторон, направление
   └─ усреднение по нескольким кадрам
   ↓
Классификация по степени риска
   ├─ однозначный случай → сохранить как есть
   └─ пограничный случай → уточняющая обработка области дефекта → обновлённый риск
   ↓
Проверка конфиденциальности по сохраняемой области
   ├─ поиск людей, транспорта, лиц, номеров
   └─ размывание / маскирование при необходимости
   ↓
Сохранение только пакета данных о дефекте
   (обрезанное изображение дефекта, класс, риск, координаты, признаки)
```
---

### 3. Скриншоты и демонстрация

 To be done

---

### 4. Установка и зависимости

#### 4.1. Требования

- Поддерживаемая ОС: Linux / Windows
- Python 3.12
- Установленный Git
- Желательно наличие GPU (CUDA) для ускорения детекции, но MVP может работать и на CPU.

#### 4.2. Виртуальное окружение и зависимости

1. Создайте папку проекта.
2. В папке проекта откройте терминал командной строки.
3. Клонируйте репозиторий:

```bash
git clone https://github.com/userGl/road_monitoring
cd road_monitoring
```

1. Создайте виртуальное окружение:

```bash
python3.12 -m venv .venv
```

1. Активируйте виртуальное окружение:

```bash
# Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

1. Установите зависимости:
  **Установите PyTorch с нужной версией CUDA:**
   **Важно:** 
  - Сначала установите PyTorch, затем остальные зависимости
  - Для актуальной информации о совместимых версиях используйте официальный сайт: [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)

```bash
pip install -r requirements.txt
```

#### 4.3. Веса модели

Необходимо скачать веса модели по ссылке:  
[https://cloud.mail.ru/public/1WAH/jp92kHqw2](https://cloud.mail.ru/public/1WAH/jp92kHqw2)

и поместить файл в папку `models` проекта.

---

### 5. Запуск сервиса

1. В папке проекта откройте терминал командной строки.
2. Активируйте виртуальное окружение:

```bash
# Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

1. Запустите сервис:

```bash
python main.py
```

---

### 6. Использование API

#### 6.1. Endpoint детекции

```text
POST /api/v1/test/detect
```

Тест детекции дефектов дорожного полотна.

**Тело запроса (JSON):**

```json
{
  "image": "<base64-строка JPEG/PNG изображения>",
  "confidence_threshold": 0.6
}
```

**Параметры:**

- `image` — строка с изображением в base64 без префикса или в формате `data:image/jpeg;base64,...` (префикс будет автоматически отброшен).
- `confidence_threshold` — необязательный порог уверенности детекции (по умолчанию 0.6).

**Пример запроса с curl (Linux/macOS):**

```bash
IMAGE_B64=$(python - << 'EOF'
import base64
from pathlib import Path

with open("test_images/Czech_002942.jpg", "rb") as f:
    print(base64.b64encode(f.read()).decode("utf-8"))
EOF
)

curl -X POST "http://localhost:8080/api/v1/test/detect" \
  -H "Content-Type: application/json" \
  -d "{\"image\": \"${IMAGE_B64}\", \"confidence_threshold\": 0.4}"
```

**Пример ответа:**

```json
{
  "success": true,
  "timestamp": "2025-01-31T12:00:00.000000",
  "image_shape":,[^3]
  "detections": [
    {
      "class_id": 0,
      "class_name": "pothole",
      "confidence": 0.87,
      "bbox": [100.5, 200.3, 300.7, 400.9]
    }
  ],
  "processing_time_ms": 45.21,
  "message": "Обнаружено дефектов: 1"
}
```

**Структура ответа** задаётся моделью `DetectionResponse`:

- `success` — флаг успешной обработки;
- `timestamp` — время обработки запроса;
- `image_shape` — размеры входного изображения `[height, width, channels]`;
- `detections` — список детекций (`class_id`, `class_name`, `confidence`, `bbox`);
- `processing_time_ms` — время обработки в миллисекундах;
- `message` — текстовое сообщение, в т.ч. с количеством найденных дефектов.

---

### 7. Демонстрация в Jupyter Notebook

В репозитории предусмотрен демонстрационный ноутбук `jupyter.ipynb`, который:

- загружает тестовое изображение дороги из `test_images/`;
- отображает исходное изображение;
- конвертирует его в base64 и отправляет POST-запрос на `/api/v1/test/detect`;
- выводит в консоль число найденных дефектов, время обработки и подробности по каждому `bbox`;
- визуализирует все детекции поверх исходного изображения с подписями классов и уверенностью.

**Запуск (пример):**

```bash
# В активированном виртуальном окружении в папке проекта выполните:
jupyter lab

```

Затем откройте `jupyter.ipynb`, убедитесь, что:

```python
API_URL = "http://localhost:8080/api/v1/test/detect"
```

и выполните все ячейки.

---

### 8. Тестирование и метрики

Пайплайн обучения и тестирования модели находится в папке `training` 