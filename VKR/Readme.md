Схема ПО проекта:
road-damage-edge/
├── main.py                 # Главный цикл
├── config.yaml             # Конфигурация
├── models/
│   └── yolo2.rknn   # YOLOv8
├── api/
│   └── rest_api.py         # FastAPI endpoints
├── storage/
│   ├── minio_client.py     # S3 upload
│   └── sqlite_db.py        # events.db
├── messenger/
│   ├── mqqt_client.py     # отправка сообщений через MQQT
│── sensors/
│   ├── camera.py           # RTSP 
│   ├── gnss.py             #
│   └── imu.py              # 
├── road-damage.service     # systemd
└── requirements.txt
Установкп ПО
1. Установка (RK3588 Yocto)
sudo mkdir -p /opt/road-damage
sudo cp -r road-damage-edge/* /opt/road-damage/
cd /opt/road-damage
2. Зависимости
sudo pip3 install opencv-python rknn-toolkit2 paho-mqtt pyyaml boto3 fastapi uvicorn
3. Разрешения
sudo chown -R root:root /opt/road-damage
sudo chmod +x main.py
4. Systemd
sudo cp road-damage.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable road-damage-edge
sudo systemctl start road-damage-edge
5. Мониторинг
sudo journalctl -u road-damage-edge -f
sudo systemctl status road-damage-edge

Паплайн обработки видеопотока (черновик)
Видеопоток RTSP 1080p@30fps
↓
Предобработка (OpenCV+RGA, RK3588)
├── Resize 1080p→640x640 (аппаратно)
├── Нормализация RGB [0,1]
└── Изменчивость освещения (CLAHE)
Сегментация сцены (Cityscapes U-Net)  
└── Маска дороги (mIoU≥0.82) → ROI
Детекция дефектов (YOLOv8-Seg, RDD2022)
├── Input: кадр × маска дороги
├── Output: bbox + маска дефекта + класс (D00-D40)
└── Фильтр confidence ≥0.6
Классификация риска (FR-2)
├── Размер: bbox → метры (калибровка Cityscapes)
├── Тип: трещина/яма → риск
└── Коэффициент: IMU тряска × геометрия
Геопривязка (FR-3)
├── GPS WGS84 (RTK ≤3м RMS)
├── IMU offset для центра bbox
└── Timestamp синхронизация
Событие (SQLite + MQTT/MinIO)
└── Критический: немедленная отправка
Критический: ежедневная синхронизация
Блок-схема (черновик):
RTSP → [Предобработка] → [Cityscapes: маска дороги] → [YOLOv8: дефекты]
↓                                        ↓
GPS/IMU ← [Геопривязка] ← [Классификация] ← [Метрики дефекта]
↓
[SQLite/MQTT/MinIO]
Ограничения и интерфейсы
Система по умолчанию работает в автономном режиме. Одноплатный компьютер самостоятельно захватывает видеопоток (RTSP 1080p30fps), получает данные от ИИБ и ГНСС, выполняет детекцию и классификацию дефектов с помощью нейросети и автоматически генерирует и логирует события.
События высокой и критической важности сразу отправляются на сервер с помощью протокола MQTT 5.0 в формате GeoJSON. Фото и видео таких событий так же сразу отправляется на сервер с помощью протокола MinIO.
Протокол RestAPI используется для мониторинга состояния системы, настройки, тестирование работы нейросети и синхронизации событий с сервером.
Интерфейсы ввода
Рабочий режим:
├── Камера: RTSP://  (H.264 1080p30)
├── IMU
└── GNSS
Интерфейсы вывода
Критические события (Риск высокий/критический):
├── MQTT 5.0: road-damage/{vehicle_id}/evt-{event_id}-GeoJSON
└── MinIO S3:   ┬── s3://events/{vehicle_id}/evt-{event_id}.mp4
└── s3://events/{vehicle_id}/evt-{event_id}.jpg
Обычные события. Синхронизация ежедневно или по запросу:
└── REST sync: POST /api/v1/sync
├── MinIO S3://events/{vehicle_id}/evt-{event_id}.mp4
├── MinIO S3://events/{vehicle_id}/evt-{event_id}.jpg
└── MinIO S3://events/{vehicle_id}/evt-{event_id}-GeoJSON
Архитектура    REST API Endpoints
REST API endpoints (Базовый URL: http://edge.local:8080/api/v1/):
├── GET /api/v1/status — мониторинг работы системы (CPU/FPS/MinIO/MQTT)
├── GET /api/v1/config — текущая конфигурация системы
├── PUT /api/v1/config — обновление конфигурации системы
├── GET /api/v1/events — список событий SQLite (фильтр по времени/риску)
├── POST /api/v1/sync — синхронизация обычных событий с MinIO
└── POST /api/v1/test/detect — тест детекции (POST base64 image)