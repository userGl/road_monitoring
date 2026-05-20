road_monitoring/  
├── storage/  
│   ├── __init__.py  
│   ├── files.py  
│   ├── sqlite_db.py  
│   └── repository.py  
└── data/  
    ├── events.db  
    └── crops/  

В проекте код хранения и сами данные разделены.  

storage/ — Python-модули для работы с хранилищем.  

data/ — реальные данные: база SQLite и сохранённые crop-изображения.  

Что где находится:  
 - storage/files.py — сохраняет crop-изображения в data/crops/ и возвращает относительный путь к файлу.  

 - storage/sqlite_db.py — создаёт подключение к SQLite и инициализирует data/events.db.  

 - storage/repository.py — содержит методы для записи и чтения данных о треках из БД.  

 - data/events.db — хранит метаданные confirmed tracks: класс, bbox, confidence, позицию и путь к crop.  

 - data/crops/ — хранит сами crop-изображения дефектов.  

После завершения confirmed track приложение сохраняет лучший crop в data/crops/..., а затем записывает в events.db метаданные и путь к файлу.