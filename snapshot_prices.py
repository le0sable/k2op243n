"""
Снимок цен: только то, что меняется за день.

Полный пищевой срез обходит карточку каждого товара (19 тысяч GET-запросов,
около 19 минут) ради состава, КБЖУ и характеристик. Но всё это неделями не
меняется, а цена, скидка и остаток — меняются, и они целиком лежат уже
в листинге категории. Отсюда дешёвый ежедневный режим: один POST на страницу
категории, около 40 секунд на весь пищевой каталог.

Такой снимок и есть источник истории цен — `build_site_data.py` читает его
наравне с полными срезами. Полный срез нужен реже, раз в неделю, чтобы
подтянуть состав новых товаров.

Использование:
    python snapshot_prices.py                   # output/snapshots/ГГГГ-ММ-ДД.parquet
    python snapshot_prices.py --no-alcohol
    python snapshot_prices.py -o путь.parquet

Требует pandas и pyarrow:  pip install pandas pyarrow
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from auchan_parser import MERCHANT_ID, MERCHANT_NAME, WORKERS, AuchanAPI
from parse_all_categories import fetch_tree, iter_leaves
from parse_food import ALCOHOL_ROOT, FOOD_ROOTS


def snapshot_record(item: dict) -> dict:
    """Плоская запись из элемента листинга.

    Поля читаются ровно так же, как в `build_record` для карточки товара,
    иначе история цен склеится из несопоставимых значений. Цена 0 у API
    означает «в этом магазине товар не продаётся», а не «бесплатно».
    """
    price = item.get("price") or {}
    old_price = item.get("oldPrice") or {}
    stock = item.get("stock") or {}
    discount = item.get("discount") or {}

    return {
        "code": item.get("code"),
        "price": price.get("value") or None,
        "old_price": old_price.get("value") or None,
        "price_per": price.get("per"),
        "in_stock": not stock.get("not_available", True) and bool(stock.get("qty")),
        "stock_qty": stock.get("qty"),
        "discount_percent": discount.get("size"),
        "discount_start": discount.get("date_start"),
        "discount_end": discount.get("date_end"),
    }


def collect(api: AuchanAPI, leaves: list, verbose: bool = True) -> dict[str, dict]:
    """Обход листингов в потоках. Товар встречается в нескольких категориях —
    остаётся первая запись, они по цене и остатку совпадают."""
    records: dict[str, dict] = {}
    failed: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(api.list_category, node["code"], MERCHANT_ID): node
            for node, _ in leaves
        }
        for future in as_completed(futures):
            node = futures[future]
            done += 1
            try:
                items = future.result()
            except Exception as exc:  # сеть, 5xx после ретраев — категория пропускается
                failed.append(node.get("code") or "?")
                print(f"  ! {node.get('code')}: {exc}", file=sys.stderr)
                continue
            for item in items:
                code = item.get("code")
                if code and code not in records:
                    records[code] = snapshot_record(item)
            if verbose and done % 50 == 0:
                print(f"  [{done}/{len(futures)}] уникальных товаров: {len(records)}")

    if failed:
        print(f"\n! не удалось обойти категорий: {len(failed)} ({', '.join(failed[:10])})",
              file=sys.stderr)
    return records


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Снимок цен пищевого каталога АШАН Симферополь")
    parser.add_argument("-o", "--out", help="файл вывода (по умолчанию output/snapshots/ГГГГ-ММ-ДД.parquet)")
    parser.add_argument("--no-alcohol", action="store_true", help="исключить раздел «Алкоголь»")
    parser.add_argument("--date", help="дата снимка ГГГГ-ММ-ДД (по умолчанию сегодня)")
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError:
        sys.exit("нужен pandas: pip install pandas pyarrow")

    day = args.date or date.today().isoformat()
    out = Path(args.out) if args.out else Path("output/snapshots") / f"{day}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)

    roots = set(FOOD_ROOTS)
    if not args.no_alcohol:
        roots.add(ALCOHOL_ROOT)

    api = AuchanAPI()
    started = time.time()
    print(f"Магазин: {MERCHANT_NAME} (merchantId={MERCHANT_ID})")
    print(f"Снимок:  {day} | разделов: {len(roots)}" + (" (без алкоголя)" if args.no_alcohol else ""))
    print("\nЗагружаю дерево категорий...")

    tree = [n for n in fetch_tree(api, include_hidden=False) if n.get("code") in roots]
    missing = roots - {n.get("code") for n in tree}
    if missing:
        print(f"  ! в дереве не найдены разделы: {', '.join(sorted(missing))}", file=sys.stderr)

    leaves = list(iter_leaves(tree))
    print(f"Категорий к обходу: {len(leaves)}\n")

    records = collect(api, leaves)
    if not records:
        sys.exit("не собрано ни одного товара — снимок не записан")

    df = pd.DataFrame(list(records.values()))
    df.insert(1, "date", day)
    df.to_parquet(out, index=False, compression="zstd")

    priced = int(df.price.notna().sum())
    in_stock = int(df.in_stock.sum())
    on_sale = int(df.discount_percent.notna().sum())
    print(f"\nГотово за {(time.time() - started) / 60:.1f} мин")
    print(f"  товаров:      {len(df)} (с ценой {priced}, в наличии {in_stock}, со скидкой {on_sale})")
    print(f"  файл:         {out} ({out.stat().st_size / 1024:.0f} КБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
