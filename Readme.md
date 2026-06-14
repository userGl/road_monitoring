# Детекция дефектов дорожного полотна — MVP

Минимально рабочий прототип сервиса детекции дефектов дорожного полотна с захватом RTSP-видеопотока, трекингом объектов, локальным хранилищем и REST API управления.

---

## Реализованные функции

- Захват входного RTSP-видеопотока (FFmpeg) с автоматическим восстановлением соединения
- Детектирование дефектов моделью YOLO (YOLOv8/v9/v11)
- Трекинг дефектов между кадрами с компенсацией движения камеры (оптический поток Lucas–Kanade)
- Сохранение результатов в локальную SQLite-базу и файловое хранилище кропов
- Трансляция аннотированного выходного RTSP-потока для визуального контроля
- Управление параметрами системы через REST API без перезапуска
- CLI-утилита для запуска, настройки и отладки
- Пакетная обработка директории изображений (режим `test_images`)

---

## Быстрый старт

### 1. Клонировать репозиторий и перейти в ветку vkr

```bash
git clone https://github.com/userGl/road_monitoring
cd road_monitoring
git checkout vkr
```

### 2. Создать и активировать виртуальное окружение

```bash
# Создать
python3.12 -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\activate
```

### 3. Установить зависимости


```bash
ffmpeg -h
ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
built with gcc 13 (Ubuntu 13.2.0-23ubuntu3)
```

Для работы RTSP-потоками необходим MediaMTX, программа установится в Docker контейнер автоматически, проверьте работу Docker


```bash
$ docker -v
Docker version 29.4.0, build 9d7ad9f
```

Сначала установите PyTorch с нужной версией CUDA (см. [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)), например:

```bash
$ pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

Проверка:

```bash
$ nvidia-smi
Sun Jun 14 15:28:57 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.159.03             Driver Version: 580.159.03     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 4070 ...    Off |   00000000:01:00.0 Off |                  N/A |
| N/A   43C    P0             15W /  115W |      15MiB /   8188MiB |      9%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            2056      G   /usr/lib/xorg/Xorg                        4MiB |
+-----------------------------------------------------------------------------------------+

```

Затем установите зависимости:

```bash
pip install -r requirements.txt
```

### 4. Скачать веса модели

Скачайте файл весов ссылка находится в файле:  

`models/download_link.md`


Поместите файл в папку `models/`.

Скачайте видеофайл, ссылка находится в файле: `test_videos/download_link.md` и поместите в папку  `test_videos/`


### 5. Запустить через CLI-утилиту


```bash
# Linux
bash scripts/01_manage.sh

# Windows (PowerShell)
.\scripts\01_manage.ps1
```

Скрипт автоматически активирует виртуальное окружение и открывает интерактивное меню управления.

**Типичная последовательность в меню:**

1. `1) Управление процессами` → `1) Запустить симуляцию видеокамеры` — запускает MediaMTX RTSP-сервер с тестовым видео
2. `1) Управление процессами` → `2) Запустить приложение` — запускает `main.py` в отдельном окне терминала
3. `2) Режим приложения` → `2) Включить режим rtsp` — переключает приложение в рабочий режим
4. `1) Управление процессами` → `3) Вкл/выкл RTSP output` — включает выходной поток для просмотра
5. `1) Управление процессами` → `4) Запустить просмотр потока` — открывает mpv/VLC

---

## Запуск вручную

```bash
# В активированном виртуальном окружении
python main.py
```

После запуска приложение загружает `config.yaml`, запускает REST API сервер на порту `8081` и переходит в основной цикл обработки.

---

## Режимы работы

Переключаются через REST API или CLI-утилиту:


| Режим         | Описание                                                  |
| ------------- | --------------------------------------------------------- |
| `rtsp`        | Непрерывная обработка входящего RTSP-видеопотока          |
| `test_images` | Однократная пакетная обработка директории с изображениями |
| `idle`        | Ожидание команды, обработка приостановлена                |


---

## Структура репозитория

```text
road_monitoring/
├── main.py                     # Точка входа в приложение
├── config.yaml                 # Конфигурация прототипа
├── requirements.txt            # Зависимости Python-проекта
├── manual_test.ipynb           # Ноутбук для ручной отладки детекций
│
├── api/
│   └── rest_api.py             # REST API (FastAPI, порт 8081)
│
├── core/                       # Ядро системы
│   ├── frame_packet.py         # Датакласс пакета кадра (FramePacket)
│   ├── runtime_config.py       # Runtime-конфигурация
│   └── runtime_state.py        # Текущее состояние системы
│
├── data/                       # Данные, формируемые в ходе работы
│   ├── events.db               # SQLite-база результатов детекции
│   └── crops/                  # Фрагменты изображений дефектов
│       └── run_<id>/
│
├── inference/
│   └── yolo_detector.py        # Инференс модели YOLO
│
├── models/                     # Веса моделей (в .gitignore)
│
├── pipeline/                   # Конвейер обработки кадра
│   ├── core.py                 # Базовая логика конвейера
│   └── stages.py               # Стадии конвейера
│
├── sensors/                    # Модули получения видеоданных
│   ├── ffmpeg_camera.py        # Захват RTSP-потока через FFmpeg
│   ├── image_folder_camera.py  # Чтение директории изображений
│   └── rtsp_streamer.py        # Трансляция выходного RTSP-потока
│
├── services/                   # Служебные модули
│   ├── images_batch.py         # Пакетная обработка изображений
│   ├── pipeline_builder.py     # Сборка конвейера
│   └── rtsp_session.py         # Управление RTSP-сессией
│
├── storage/                    # Хранилище данных
│   ├── files.py                # Сохранение изображений (FileStorage)
│   ├── repository.py           # Репозиторий доступа к данным
│   ├── sqlite_db.py            # Инициализация SQLite
│   └── storage_stage.py        # Стадия конвейера сохранения
│
├── tracking/                   # Трекер дефектов RDDTracker
│   ├── rdd_tracker.py          # Основная реализация трекера
│   ├── geometry.py             # Геометрические вычисления
│   ├── matching.py             # Сопоставление детекций и треков
│   ├── models.py               # Внутренние структуры данных
│   ├── motion.py               # Оценка движения (оптический поток)
│   └── tracker_stage.py        # Стадия конвейера трекинга
│
├── scripts/                    # CLI-утилита и вспомогательные скрипты
│   ├── 01_manage.sh / .ps1     # Скрипты запуска CLI
│   ├── manage.py               # Точка входа CLI
│   ├── manage/                 # Модули CLI
│   │   ├── actions.py          # Бизнес-логика действий меню
│   │   ├── api.py              # HTTP-клиент к REST API
│   │   ├── cli.py              # Точка входа интерактивного меню
│   │   ├── paths.py            # Пути и URL (BASE_URL через env)
│   │   ├── runtime.py          # Управление дочерними процессами
│   │   └── ui.py               # Отображение меню, обработка ввода
│   ├── start_mediamtx_rtsp.sh / .ps1   # Запуск RTSP-сервера MediaMTX
│   ├── rtsp_view.sh / .ps1             # Просмотр RTSP-потока (mpv)
│   └── start_vlc_rtsp.sh / .ps1        # Просмотр RTSP-потока (VLC)
│
├── test_images/                # Тестовые изображения
├── training/                   # Ноутбуки обучения моделей
└── dev/                        # Вспомогательные скрипты разработки
```

---

## REST API

Сервер запускается на `http://127.0.0.1:8081/api/v1`.  
Адрес CLI-утилиты переопределяется через переменную окружения `BASE_URL`.

### GET /api/v1/config

Получить текущую конфигурацию.

```json
{
  "stream": { "enable_output_stream": false },
  "detector": {
    "confidence_threshold": 0.05,
    "model_path": "models/YOLOv8_Small_RDD.pt"
  }
}
```

### PATCH /api/v1/config

Изменить конфигурацию без перезапуска. Все поля опциональны.

```json
{
  "detector": {
    "confidence_threshold": 0.3,
    "model_path": "models/YOLOv8_Small_RDD.pt"
  },
  "stream": { "enable_output_stream": true }
}
```

### GET /api/v1/control

Получить текущий статус системы: режим работы, готовность YOLO-стадии.

```json
{
  "mode": "rtsp",
  "yolo_stage_ready": true,
  "test_input_dir": null,
  "test_output_dir": null,
  "test_fps": null
}
```

### POST /api/v1/control

Переключить режим работы.

```json
{ "mode": "idle" }
```

### POST /api/v1/test/images

Запустить пакетную обработку директории изображений.

```json
{
  "input_dir": "test_images/japan",
  "output_dir": "test_images/japan/output_1714550400",
  "fps": 10
}
```

### POST /api/v1/test/detect

Одиночная детекция по base64-изображению.

**Запрос:**

```json
{
  "image": "<base64-строка JPEG/PNG>",
  "confidence_threshold": 0.3
}
```

**Ответ:**

```json
{
  "success": true,
  "timestamp": "2026-04-01T12:00:00.123456",
  "image_shape": [720, 1280, 3],
  "detections": [
    {
      "class_id": 1,
      "class_name": "D10",
      "confidence": 0.82,
      "bbox": [120.5, 340.2, 280.1, 410.7]
    }
  ],
  "processing_time_ms": 45.3,
  "message": "Обнаружено дефектов: 1"
}
```

**Пример с curl (Linux/macOS):**

```bash
IMAGE_B64=$(python - << 'EOF'
import base64
with open("test_images/08_Japan_003154.jpg", "rb") as f:
    print(base64.b64encode(f.read()).decode())
EOF
)

curl -X POST "http://localhost:8081/api/v1/test/detect" \
  -H "Content-Type: application/json" \
  -d "{\"image\": \"${IMAGE_B64}\", \"confidence_threshold\": 0.3}"
```

---

## CLI-утилита

Интерактивное меню управления прототипом. Взаимодействует с приложением через REST API.

```
CLI (manage.py)
│
├── [API недоступно] → Управление процессами (автоматически)
│
└── [API доступно] → Главное меню
    │
    ├── 1) Управление процессами
    │   ├── 1) Запустить симуляцию видеокамеры  → start_mediamtx_rtsp.sh/.ps1
    │   ├── 2) Запустить приложение             → main.py (.venv)
    │   ├── 3) Вкл/выкл RTSP output             → PATCH /api/v1/config
    │   ├── 4) Запустить просмотр потока         → rtsp_view.sh/.ps1
    │   ├── 5) Остановить симуляцию видеокамеры
    │   ├── 6) Остановить приложение
    │   └── 0) Назад
    │
    ├── 2) Режим приложения
    │   ├── 1) Включить режим idle              → POST /api/v1/control
    │   ├── 2) Включить режим rtsp              → POST /api/v1/control
    │   ├── 3) Запустить пакетную обработку     → POST /api/v1/test/images
    │   └── 0) Назад
    │
    ├── 3) Изменить confidence_threshold        → PATCH /api/v1/config
    ├── 4) Изменить model_path                  → PATCH /api/v1/config
    ├── 5) Показать полный JSON конфигурации    → GET /api/v1/config
    └── 0) Выход
```

---

## Ручная отладка через Jupyter

Ноутбук `manual_test.ipynb` позволяет:

- загрузить изображение из `test_images/`
- отправить POST-запрос на `/api/v1/test/detect`
- визуализировать детекции поверх изображения

```bash
jupyter lab
```

Убедитесь, что в ноутбуке указан правильный адрес:

```python
API_URL = "http://localhost:8081/api/v1/test/detect"
```

---

## Конфигурация

Параметры по умолчанию задаются в `config.yaml`:


| Параметр                        | Значение по умолчанию           | Описание                     |
| ------------------------------- | ------------------------------- | ---------------------------- |
| `stream.input_rtsp_url`         | `rtsp://127.0.0.1:8554/live`    | Адрес входного RTSP-потока   |
| `stream.output_rtsp_url`        | `rtsp://127.0.0.1:8554/preview` | Адрес выходного RTSP-потока  |
| `stream.enable_output_stream`   | `false`                         | Включить выходную трансляцию |
| `detector.model_path`           | `models/YOLOv8_Small_RDD.pt`    | Путь к весам модели          |
| `detector.confidence_threshold` | `0.05`                          | Порог уверенности детектора  |


Параметры могут быть изменены через REST API во время работы без перезапуска.

---

## Системные требования

- ОС: Linux / Windows
- Python 3.12
- GPU с поддержкой CUDA (рекомендуется; работает и на CPU)
- FFmpeg (для захвата и трансляции RTSP)
- MediaMTX (для симуляции входного потока в тестовом режиме)

---

## Обучение моделей

Ноутбуки обучения находятся в папке `training/`. Для работы прототипа не требуются.

Краткие результаты экспериментов:

- На полном датасете RDD (Czech, India, Japan, Norway, US): средний Recall ≈ 0,60, Precision ≈ 0,68–0,69
- На подвыборке Japan (100 эпох, YOLOv8s): Recall ≥ 94%, Precision ≥ 95%

Результаты указывают на выраженный доменный сдвиг между поднаборами RDD и необходимость обучения на локальных данных.