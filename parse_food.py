"""
Выгрузка только пищевых категорий АШАН Симферополь в ОДИН файл.

В отличие от parse_all_categories.py здесь результат не разбивается по
категориям: все продукты питания и напитки складываются в единый JSON с
дедупликацией по SKU. Принадлежность к категориям сохраняется внутри каждого
товара в поле `categories`.

Использование:
    python parse_food.py                       # собрать с сайта
    python parse_food.py --no-alcohol          # без раздела «Алкоголь»
    python parse_food.py --reviews             # + тексты отзывов (долго)
    python parse_food.py --from-dir output/2026-08-11   # пересобрать из готовой выгрузки
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from auchan_parser import MERCHANT_ID, MERCHANT_NAME, REGION_ID, AuchanAPI, dump_json
from parse_all_categories import Collector, fetch_tree, iter_leaves

# Состав списка выверен по данным полной выгрузки: для каждого корневого раздела
# считалась доля товаров с заполненным КБЖУ. У разделов ниже она 88–100 %,
# у непищевых — нулевая, промежуточных значений почти нет, поэтому граница
# однозначная.
FOOD_ROOTS = [
    "moloko-syr-yayca",  # Молочные продукты, яйца
    "ptica-myaso",  # Птица, мясо
    "ryba-ikra-moreprodukty",  # Рыба, икра, морепродукты
    "syry",  # Сыр
    "ovoschi-frukty-zelen-griby-yagody",  # Овощи, фрукты, орехи
    "zamorozhennye-produkty",  # Замороженные продукты
    "kolbasnye-izdeliya",  # Колбасные изделия
    "kulinariya",  # Готовая еда
    "hlebnaya-vypechka",  # Хлеб и выпечка
    "bakaleya",  # Бакалея
    "konditerskie_izdeliya",  # Сладости
    "orehi-suhofrukty-sneki",  # Чипсы, снеки, сухофрукты
    "voda-soki-napitki",  # Вода, соки, напитки
    "fermerskie_produkty_5",  # Фермерские продукты
    "sdelano_v_ashan",  # Собственное производство
    "zdorovyy-vybor",  # Здоровый выбор
    "nastoyashchaya_aziya",  # Настоящая Азия
    "regiony_rossii",  # Сокровища России
]

# Исключены сознательно: «Чай, кофе, горячие напитки» и «Спортивное питание
# и БАДы» — у них доля товаров с КБЖУ 52 % и 65 %, это заварка, зёрна и добавки,
# а не продукты питания в чистом виде.

# Алкоголь — тоже продуктовый раздел (97 % товаров с КБЖУ), но его часто нужно
# исключать отдельно, поэтому он вынесен под флаг.
ALCOHOL_ROOT = "alkogol"


def collect_from_dir(source: Path, roots: set[str]) -> list[dict]:
    """Пересобрать пищевой срез из готовой поcategory-выгрузки, без запросов к сайту."""
    by_code: dict[str, dict] = {}
    files = [f for f in glob.glob(str(source / "*.json")) if not f.endswith("_manifest.json")]
    if not files:
        raise SystemExit(f"В {source} нет файлов категорий.")

    for path in files:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        # Фильтруем по «родным» категориям самого товара, а не по файлу, в
        # котором он лежит: один SKU попадает и в пищевые, и в тематические
        # подборки, а его categoryCodes всегда указывают на настоящее место.
        for product in payload.get("products") or []:
            cats = {c.get("code") for c in product.get("categories") or []}
            if cats & roots:
                by_code.setdefault(product["code"], product)
    return list(by_code.values())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Пищевые категории АШАН Симферополь в один файл")
    parser.add_argument("-o", "--output", help="путь к итоговому JSON")
    parser.add_argument("--no-alcohol", action="store_true", help="исключить раздел «Алкоголь»")
    parser.add_argument("--reviews", action="store_true", help="собирать тексты отзывов")
    parser.add_argument("--max-reviews", type=int, default=None, help="лимит отзывов на товар")
    parser.add_argument(
        "--from-dir", help="собрать из готовой выгрузки parse_all_categories.py, без запросов"
    )
    parser.add_argument("--limit", type=int, default=None, help="обойти только N категорий")
    args = parser.parse_args()

    roots = set(FOOD_ROOTS)
    if not args.no_alcohol:
        roots.add(ALCOHOL_ROOT)

    started = time.time()
    out_path = Path(args.output or f"output/food_simferopol_{date.today().isoformat()}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Магазин: {MERCHANT_NAME} (merchantId={MERCHANT_ID})")
    print(f"Разделов в пищевом срезе: {len(roots)}" + ("" if not args.no_alcohol else " (без алкоголя)"))

    if args.from_dir:
        print(f"Источник: готовая выгрузка {args.from_dir}\n")
        products = collect_from_dir(Path(args.from_dir), roots)
        categories_used = sorted(roots)
    else:
        api = AuchanAPI()
        collector = Collector(api, args.reviews, args.max_reviews)
        print(f"Отзывы:  {'да' if args.reviews else 'нет (рейтинг и разбивка по звёздам собираются всегда)'}")
        print("\nЗагружаю дерево категорий...")

        tree = [n for n in fetch_tree(api, include_hidden=False) if n.get("code") in roots]
        missing = roots - {n.get("code") for n in tree}
        if missing:
            print(f"  ! в дереве не найдены разделы: {', '.join(sorted(missing))}", file=sys.stderr)

        leaves = list(iter_leaves(tree))
        if args.limit:
            leaves = leaves[: args.limit]
        print(f"Разделов: {len(tree)} | категорий к обходу: {len(leaves)}\n")

        by_code: dict[str, dict] = {}
        for index, (node, path) in enumerate(leaves, 1):
            code = node.get("code")
            if not code:
                continue
            try:
                records, _failed = collector.collect_category(code)
            except Exception as exc:
                print(f"[{index}/{len(leaves)}] {' / '.join(path)} — ОШИБКА: {exc}", file=sys.stderr)
                continue
            new = 0
            for record in records:
                if record["code"] not in by_code:
                    by_code[record["code"]] = record
                    new += 1
            elapsed = time.time() - started
            eta = elapsed / index * (len(leaves) - index)
            print(
                f"[{index}/{len(leaves)}] {' / '.join(path)[:58]} — {len(records)} тов. "
                f"(+{new} новых) | всего {len(by_code)} | осталось ~{eta / 60:.0f} мин"
            )
        products = list(by_code.values())
        categories_used = sorted(roots)

    products.sort(key=lambda r: (not r["in_stock"], r["title"] or ""))
    in_stock = sum(1 for p in products if p["in_stock"])
    with_nutrition = sum(1 for p in products if p["nutrition_per_100g"]["calories"] is not None)

    payload = {
        "meta": {
            "scope": "пищевые категории",
            "merchant_id": MERCHANT_ID,
            "merchant_name": MERCHANT_NAME,
            "region_id": REGION_ID,
            "currency": "RUB",
            "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "root_categories": categories_used,
            "alcohol_included": not args.no_alcohol,
            "products_total": len(products),
            "products_in_stock": in_stock,
            "products_out_of_stock": len(products) - in_stock,
            "products_with_nutrition": with_nutrition,
            "reviews_total": sum(len(p.get("reviews") or []) for p in products),
        },
        "products": products,
    }
    out_path.write_text(dump_json(payload), encoding="utf-8")

    print(f"\nГотово за {(time.time() - started) / 60:.1f} мин")
    print(f"  товаров:    {len(products)} (в наличии {in_stock}, нет {len(products) - in_stock})")
    print(f"  с КБЖУ:     {with_nutrition} ({100 * with_nutrition // max(len(products), 1)}%)")
    print(f"  отзывов:    {payload['meta']['reviews_total']}")
    print(f"  файл:       {out_path} ({out_path.stat().st_size / 1024 / 1024:.0f} МБ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
