# Парсер каталога АШАН — Симферополь

Выгрузка каталога auchan.ru в JSON по магазину **АШАН Симферополь**
(`merchantId=729`, регион Крым `regionId=9`).

## Скрипты

| файл | охват | раскладка |
|---|---|---|
| [auchan_parser.py](auchan_parser.py) | одна категория | один файл |
| [parse_all_categories.py](parse_all_categories.py) | весь каталог | файл на категорию |
| [parse_food_categories.py](parse_food_categories.py) | только пищевые | файл на категорию |
| [parse_food.py](parse_food.py) | только пищевые | всё одним файлом |

```bash
python auchan_parser.py moloko                     # одна категория
python parse_all_categories.py                     # всё товарное дерево
python parse_food_categories.py                    # пищевой срез по категориям
python parse_food.py                               # пищевой срез одним файлом
python parse_food.py --from-dir output/ГГГГ-ММ-ДД  # пищевой срез из готовой выгрузки
python parse_all_categories.py --reviews           # + тексты отзывов (долго и тяжело)
```

Куда пишется результат:

| скрипт | путь |
|---|---|
| `auchan_parser.py` | `output/<категория>_simferopol.json` |
| `parse_all_categories.py` | `output/ГГГГ-ММ-ДД/<категория>.json` + `_manifest.json` |
| `parse_food_categories.py` | `output/food-ГГГГ-ММ-ДД/<категория>.json` + `_manifest.json` |
| `parse_food.py` | `output/food_simferopol_ГГГГ-ММ-ДД.json` |

Пищевой срез — 19 продуктовых разделов каталога, список в `FOOD_ROOTS`
(`parse_food.py`), алкоголь отключается флагом `--no-alcohol`.

Полный обход возобновляемый: прерванный прогон продолжается с той же точки,
даже если за это время сменилась дата.

Зависимости: `pip install -r requirements.txt` (только `requests`).

## Как это работает

Данные берутся из внутреннего JSON API сайта `/v3/` обычными HTTP-запросами.
**Браузер не нужен** и в зависимостях его нет: HTML сайта закрыт защитой Qrator,
а API — нет, и он разрешён в `robots.txt`.

По каждому товару собирается всё, что отдаёт API: цены и скидки, наличие, бренд,
состав, масса, КБЖУ, все характеристики, описание, изображения, кэшбэк, рейтинг
с разбивкой по звёздам и при необходимости сами отзывы.

## Документация

Перед любыми правками читать **[docs/auchan-api.md](docs/auchan-api.md)** — там
эндпоинты, схемы запросов и подводные камни API.
