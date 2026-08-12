"""
Экспорт готовых выгрузок в Parquet — формат для анализа.

Берёт JSON, собранный любым из парсеров, и раскладывает товары в плоскую
таблицу. Замер на пищевом срезе (21 567 товаров):

    JSON     62.0 МБ   чтение 0.85 с
    JSON.gz   7.6 МБ
    CSV      43.9 МБ   чтение 1.22 с
    Parquet   6.1 МБ   чтение 0.46 с, а если нужны 3 колонки — 0.01 с

Выигрыш даёт колоночное хранение: имена полей занимали пятую часть JSON и
повторялись у каждого товара, а бренды и страны кодируются словарём.

Использование:
    python export_parquet.py output/food-2026-08-12            # папка категорий
    python export_parquet.py output/food_simferopol.json.gz    # один файл
    python export_parquet.py output/food-2026-08-12 -o data.parquet

Требует pandas и pyarrow:  pip install pandas pyarrow
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auchan_parser import category_files, read_json

# Поля-контейнеры: в таблицу они не ложатся как есть и разбираются отдельно.
NESTED = {
    "nutrition_per_100g",
    "rating_breakdown",
    "categories",
    "images",
    "badges",
    "characteristics",
    "reviews",
}

LIST_SEP = "|"


def scalar(value):
    """Привести значение к скаляру: таблица не хранит вложенные структуры.

    Списки (схлопнутые дубли характеристик) склеиваются разделителем, словари
    сериализуются — так читаются и старые выгрузки, где скидка и кэшбэк лежали
    объектами.
    """
    if isinstance(value, list):
        return LIST_SEP.join(json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def flatten(product: dict) -> dict:
    row = {k: scalar(v) for k, v in product.items() if k not in NESTED}

    nutrition = product.get("nutrition_per_100g") or {}
    for key in ("calories", "proteins", "fats", "carbohydrates"):
        row[f"nutrition_{key}"] = nutrition.get(key)

    for stars, count in (product.get("rating_breakdown") or {}).items():
        row[f"rating_{stars}"] = count

    # дерево категорий раскладывается по уровням: раздел / подраздел / категория
    cats = product.get("categories") or []
    for level in range(3):
        row[f"category_{level + 1}"] = cats[level]["name"] if level < len(cats) else None
    row["category_codes"] = LIST_SEP.join(c.get("code") or "" for c in cats)

    row["images"] = LIST_SEP.join(product.get("images") or [])
    row["badges"] = LIST_SEP.join(b.get("code") or "" for b in product.get("badges") or [])
    row["reviews_collected"] = len(product.get("reviews") or [])

    # каждая характеристика — своя колонка; таблица разреженная, но Parquet
    # хранит пропуски почти бесплатно
    for key, value in (product.get("characteristics") or {}).items():
        row[f"ch_{key}"] = scalar(value)

    return row


def load_products(source: Path) -> list[dict]:
    if source.is_dir():
        files = category_files(source)
        if not files:
            raise SystemExit(f"В {source} нет файлов категорий.")
        by_code: dict[str, dict] = {}
        for path in files:
            for product in read_json(path).get("products") or []:
                by_code.setdefault(product["code"], product)
        return list(by_code.values())

    if not source.exists():
        raise SystemExit(f"Не найдено: {source}")
    return read_json(source).get("products") or []


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Экспорт выгрузки АШАН в Parquet")
    parser.add_argument("source", help="папка с категориями или один JSON (можно .gz)")
    parser.add_argument("-o", "--output", help="путь к .parquet")
    parser.add_argument(
        "--compression", default="zstd", choices=["zstd", "snappy", "gzip", "none"]
    )
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("Нужны pandas и pyarrow:  pip install pandas pyarrow")

    source = Path(args.source)
    print(f"Читаю {source} ...")
    products = load_products(source)
    if not products:
        raise SystemExit("В источнике нет товаров.")

    frame = pd.DataFrame([flatten(p) for p in products])

    # Повторяющиеся строки — в словарь: бренды, страны, категории занимают
    # в разы меньше, когда хранятся как коды, а не как текст в каждой строке.
    for column in frame.columns:
        if frame[column].dtype != object:
            continue
        try:
            if frame[column].nunique(dropna=True) < len(frame) // 3:
                frame[column] = frame[column].astype("category")
        except TypeError:
            # значение неожиданного типа — оставляем колонку как есть
            frame[column] = frame[column].map(scalar)

    name = source.name.split(".")[0] if source.is_file() else source.name
    out_path = Path(args.output or f"output/{name}.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(
        out_path,
        compression=None if args.compression == "none" else args.compression,
        index=False,
    )

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nГотово")
    print(f"  товаров:  {len(frame)}")
    print(f"  колонок:  {len(frame.columns)}")
    print(f"  файл:     {out_path} ({size_mb:.1f} МБ, сжатие {args.compression})")
    print(f"\nЧитать так:\n  import pandas as pd\n  df = pd.read_parquet('{out_path.as_posix()}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
