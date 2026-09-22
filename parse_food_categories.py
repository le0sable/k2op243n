"""
Пищевые категории АШАН Симферополь — КАЖДАЯ В ОТДЕЛЬНЫЙ ФАЙЛ.

Тот же срез продуктов питания и напитков, что и в parse_food.py, но результат
не сводится в один файл, а раскладывается по категориям — как в
parse_all_categories.py, только без непищевых разделов:

    output/food-2026-08-12/moloko.json
    output/food-2026-08-12/syry.json
    ...
    output/food-2026-08-12/_manifest.json

Три варианта выгрузки, чтобы не путаться:
    parse_all_categories.py  — весь каталог,      файл на категорию
    parse_food_categories.py — только пищевые,    файл на категорию   (этот)
    parse_food.py            — только пищевые,    всё одним файлом

Использование:
    python parse_food_categories.py
    python parse_food_categories.py --no-alcohol
    python parse_food_categories.py --reviews
"""

from __future__ import annotations

import argparse
import sys
import time

from auchan_parser import MERCHANT_ID, MERCHANT_NAME, AuchanAPI
from parse_all_categories import (
    Collector,
    fetch_tree_checked,
    resolve_out_dir,
    write_by_category,
)
from parse_food import ALCOHOL_ROOT, FOOD_ROOTS

# Папки этого скрипта отделены префиксом, чтобы пищевой срез не смешивался
# с полной выгрузкой и не подхватывался её механизмом возобновления.
DIR_PREFIX = "food-"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Пищевые категории АШАН Симферополь, файл на категорию"
    )
    parser.add_argument("--out-dir", help="папка вывода (по умолчанию output/food-ГГГГ-ММ-ДД)")
    parser.add_argument("--no-alcohol", action="store_true", help="исключить раздел «Алкоголь»")
    parser.add_argument("--reviews", action="store_true", help="собирать тексты отзывов")
    parser.add_argument("--max-reviews", type=int, default=None, help="лимит отзывов на товар")
    parser.add_argument("--limit", type=int, default=None, help="обработать только N категорий")
    parser.add_argument(
        "--no-resume", action="store_true", help="не пропускать уже готовые файлы категорий"
    )
    args = parser.parse_args()

    roots = set(FOOD_ROOTS)
    if not args.no_alcohol:
        roots.add(ALCOHOL_ROOT)

    api = AuchanAPI()
    collector = Collector(api, args.reviews, args.max_reviews)
    started = time.time()

    print(f"Магазин: {MERCHANT_NAME} (merchantId={MERCHANT_ID})")
    print(f"Срез:    пищевые категории, {len(roots)} разделов" + (" (без алкоголя)" if args.no_alcohol else ""))
    print(f"Отзывы:  {'да' if args.reviews else 'нет (только рейтинг и разбивка по звёздам)'}")
    print("\nЗагружаю дерево категорий...")

    typical = not args.no_alcohol and not args.limit
    tree, leaves = fetch_tree_checked(api, False, "food", roots, typical=typical)
    if args.limit:
        leaves = leaves[: args.limit]
    print(f"Разделов: {len(tree)} | категорий к обходу: {len(leaves)}")

    out_dir = resolve_out_dir(len(leaves), args.out_dir, DIR_PREFIX, not args.no_resume)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Папка:   {out_dir}\n")

    return write_by_category(
        collector, leaves, out_dir, not args.no_resume, args.reviews, started
    )


if __name__ == "__main__":
    sys.exit(main())
