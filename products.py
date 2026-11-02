"""
Справочник товаров: код → название, бренд, фасовка, категория.

В снимках цен хранится только код товара, а чтобы узнать, что за ним стоит,
пришлось бы каждый раз запрашивать карточку. Справочник `output/products.csv`
решает это: он хранится в git рядом со снимками и пополняется ежедневным
снимком бесплатно — название, бренд и категория лежат в том же листинге,
из которого снимаются цены.

Формат — CSV, отсортированный по коду: файл меняется только при появлении
новых товаров или смене названия, и в git такие правки видны построчно.
Если название товара поменялось, в справочнике остаётся последнее.

Использование:
    python products.py --backfill   # дописать коды из старых снимков (карточками)

В анализе:
    from products import load_products
    df = snapshot.merge(load_products(), on="code", how="left")
"""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PRODUCTS_PATH = Path("output/products.csv")

FIELDS = [
    "code",           # ключ, тот же, что в снимках; ссылка — https://www.auchan.ru/product/<code>/
    "title",
    "brand",
    "package",        # фасовка как на витрине: «720 г», «1 шт»
    "category",       # самая глубокая категория товара (код)
    "category_name",
    "article",        # артикул (gimaId)
    "product_id",
    "first_seen",     # первая дата, когда товар попал в снимок
]

# Поля, которые обновляются у уже известного товара (first_seen — никогда).
UPDATABLE = [f for f in FIELDS if f not in ("code", "first_seen")]


def catalog_record(item: dict) -> dict:
    """Описательные поля товара. Годится и для элемента листинга, и для карточки:
    ключи у них общие (в карточке нет только `package_display`)."""
    categories = item.get("categoryCodes") or []
    leaf = categories[-1] if categories else {}
    return {
        "code": item.get("code"),
        "title": _clean(item.get("title")),
        "brand": _clean((item.get("brand") or {}).get("name")),
        "package": _clean(item.get("package_display")),
        "category": leaf.get("code"),
        "category_name": _clean(leaf.get("name")),
        "article": item.get("gimaId"),
        "product_id": item.get("productId"),
    }


def _clean(value):
    """API помечает отсутствие бренда как «-», а фасовки — как пробел."""
    if isinstance(value, str):
        value = value.strip()
        return None if value in ("", "-") else value
    return value


def load(path: Path = PRODUCTS_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["code"]: row for row in csv.DictReader(f)}


def save(rows: dict[str, dict], path: Path = PRODUCTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for code in sorted(rows):
            writer.writerow({k: "" if rows[code].get(k) is None else rows[code][k] for k in FIELDS})
    tmp.replace(path)


def merge(rows: dict[str, dict], records: list[dict], day: str) -> tuple[int, int]:
    """Вливает свежие записи в справочник. Возвращает (новых, изменившихся).

    Пустое значение из API не затирает известное: листинг, например, иногда
    приходит без бренда, а карточка — всегда без фасовки."""
    added = changed = 0
    for rec in records:
        code = rec.get("code")
        if not code:
            continue
        fresh = {k: "" if rec.get(k) is None else str(rec[k]) for k in UPDATABLE}
        row = rows.get(code)
        if row is None:
            rows[code] = {"code": code, **fresh, "first_seen": day}
            added += 1
            continue
        diff = {k: v for k, v in fresh.items() if v and v != row.get(k, "")}
        if diff:
            row.update(diff)
            changed += 1
    return added, changed


def update(records: list[dict], day: str, path: Path = PRODUCTS_PATH) -> tuple[int, int]:
    rows = load(path)
    added, changed = merge(rows, records, day)
    if added or changed or not path.exists():
        save(rows, path)
    return added, changed


def load_products(path: Path = PRODUCTS_PATH):
    """Справочник как DataFrame — для merge со снимками по `code`."""
    import pandas as pd

    return pd.read_csv(path, dtype=str, keep_default_na=False).replace("", None)


# --- досбор из истории снимков --------------------------------------------


def backfill(snapshots: Path, path: Path = PRODUCTS_PATH) -> int:
    """Дописывает в справочник коды из всех снимков, которых в нём нет, и
    выставляет first_seen по самому раннему снимку. Названия недостающих
    товаров берутся из карточек — это нужно один раз, дальше справочник
    пополняет сам снимок."""
    import pandas as pd

    from auchan_parser import WORKERS, AuchanAPI

    first_seen: dict[str, str] = {}
    files = sorted(snapshots.glob("????-??-??.parquet"))
    for file in files:
        for code in pd.read_parquet(file, columns=["code"]).code:
            first_seen.setdefault(code, file.stem)
    print(f"снимков: {len(files)}, кодов в них: {len(first_seen)}")

    rows = load(path)
    for code, day in first_seen.items():
        if code in rows and day < rows[code]["first_seen"]:
            rows[code]["first_seen"] = day

    missing = sorted(set(first_seen) - set(rows))
    print(f"нет в справочнике: {len(missing)} — запрашиваю карточки")
    api = AuchanAPI()
    not_found = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(api.product_detail, code): code for code in missing}
        for done, future in enumerate(as_completed(futures), 1):
            code = futures[future]
            try:
                detail = future.result()
            except Exception as exc:
                print(f"  ! {code}: {exc}", file=sys.stderr)
                continue
            # Карточки нет (товар снят с сайта) — код всё равно записывается,
            # чтобы было видно, когда он появлялся; название остаётся пустым.
            rec = catalog_record(detail) if detail else {"code": code}
            if not detail:
                not_found += 1
            rec["code"] = code  # ключ — код из снимка, даже если карточка отдала другой
            merge(rows, [rec], first_seen[code])
            if done % 500 == 0:
                print(f"  [{done}/{len(missing)}]")

    save(rows, path)
    untitled = sum(1 for r in rows.values() if not r.get("title"))
    print(f"справочник: {len(rows)} товаров, без названия {untitled} (карточка не найдена: {not_found})")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Справочник товаров: код → название")
    parser.add_argument("--backfill", action="store_true",
                        help="дописать коды из всех снимков в output/snapshots")
    parser.add_argument("--snapshots", default="output/snapshots", help="папка со снимками")
    args = parser.parse_args()
    if args.backfill:
        return backfill(Path(args.snapshots))
    rows = load()
    print(f"{PRODUCTS_PATH}: {len(rows)} товаров")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
