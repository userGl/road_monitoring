# Тестовые изображения

Эта папка содержит тестовые изображения для проверки работы API детекции дефектов дорожного полотна.

## Форматы изображений

Поддерживаемые форматы:
- `.jpg` / `.jpeg`
- `.png`
- `.bmp`

## Использование

В ноутбуке `manual_test.ipynb` можно загрузить изображение из этой папки:

```python
image_path = "test_images/your_image.jpg"
image_base64 = load_image_from_file(image_path)
```

## Структура (рекомендуется)

```
test_images/
├── README.md
├── sample_road_1.jpg
├── sample_road_2.jpg
└── defects/
    ├── d00_crack.jpg
    ├── d40_pothole.jpg
    └── ...
```

