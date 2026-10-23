# Парсер каталога АШАН Симферополь

Ежедневный снимок цен и еженедельный полный срез каталога auchan.ru по магазину
АШАН Симферополь — через внутренний JSON API, без браузера.

- `output/snapshots/ГГГГ-ММ-ДД.parquet` — снимок цен за день (коммитит GitHub Actions);
- релиз [`weekly-full`](../../releases/tag/weekly-full) — полный срез пищевых категорий (состав, КБЖУ, характеристики), Parquet;
- [API.md](API.md) — как устроен API; [CLAUDE.md](CLAUDE.md) — скрипты и устройство сбора.

```bash
pip install -r requirements.txt
python snapshot_prices.py       # снимок цен за сегодня (~30 с)
```
