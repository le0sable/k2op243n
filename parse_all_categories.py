"""
Полный обход каталога auchan.ru для магазина АШАН Симферополь.

Проходит все категории товарного дерева и сохраняет каждую в отдельный
JSON-файл внутри папки с текущей датой:

    output/2026-08-11/moloko.json
    output/2026-08-11/syry.json
    ...
    output/2026-08-11/_manifest.json

Надстройка над auchan_parser.py — использует его клиент API и сборку карточки.

Ключевые отличия от одиночного парсера:
  * дерево категорий берётся из /v3/categories/;
  * карточка каждого товара запрашивается ОДИН раз и кэшируется — один
    и тот же SKU лежит в нескольких категориях, без кэша это лишние часы;
  * прогон возобновляемый: уже готовые файлы категорий пропускаются.

Использование:
    python parse_all_categories.py                  # всё товарное дерево, без отзывов
    python parse_all_categories.py --reviews        # добавить тексты отзывов (долго)
    python parse_all_categories.py --limit 5        # прогнать 5 категорий для проверки
    python parse_all_categories.py --include-hidden # + Коллекции, опт, B2B-разделы
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

from auchan_parser import (
    MERCHANT_ID,
    MERCHANT_NAME,
    REGION_ID,
    WORKERS,
    AuchanAPI,
    build_record,
    category_files,
    read_json,
    write_json,
)

# Категории с hiddenMenu=False — это ровно меню каталога на сайте (49 корневых).
# Остальные корневые узлы — маркетинговые подборки («Коллекции», «Чёрная пятница»)
# и B2B-разделы («Продукты оптом», «Гостиницам и отелям»), собранные из тех же
# товаров. По умолчанию они пропускаются, чтобы не плодить дубли.
def fetch_tree(api: AuchanAPI, include_hidden: bool) -> list[dict]:
    tree = api._request(
        "GET",
        "/categories/",
        params={
            "merchant_id": api.merchant_id,  # именно snake_case, camelCase не принимается
            "active_only": 1,
            "show_hidden": 1,
        },
    )
    return tree if include_hidden else [n for n in tree if not n.get("hiddenMenu")]


def iter_leaves(nodes: list[dict], path: list[str] | None = None):
    """Листовые категории дерева вместе с их путём."""
    path = path or []
    for node in nodes:
        here = path + [node.get("name") or node.get("code")]
        children = node.get("items") or []
        if children:
            yield from iter_leaves(children, here)
        else:
            yield node, here


def safe_name(code: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", code)[:120]


def resolve_out_dir(expected: int, explicit: str | None) -> Path:
    """Папка вывода: незавершённый прогон продолжается, даже если сменилась дата.

    Обход длится десятки минут и легко переезжает через полночь. Привязка к
    сегодняшней дате в этом случае завела бы новую папку и начала каталог
    заново, поэтому берётся самая свежая папка, которая ещё не доведена
    до конца.
    """
    if explicit:
        return Path(explicit)

    root = Path("output")
    dated = sorted(
        (p for p in root.glob("*") if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    for candidate in dated:
        done = len(category_files(candidate))
        if 0 < done < expected:
            print(f"Найден незавершённый прогон в {candidate} ({done} из {expected}) — продолжаю.")
            return candidate

    return root / date.today().isoformat()


class Collector:
    """Обход категорий с общим кэшем карточек товаров."""

    def __init__(self, api: AuchanAPI, with_reviews: bool, max_reviews: int | None):
        self.api = api
        self.with_reviews = with_reviews
        self.max_reviews = max_reviews
        self.cache: dict[str, dict | None] = {}
        self.lock = threading.Lock()
        self.requests_saved = 0

    def get_product(self, code: str) -> dict | None:
        with self.lock:
            if code in self.cache:
                self.requests_saved += 1
                return self.cache[code]

        detail = self.api.product_detail(code)
        record = None
        if detail:
            reviews = []
            if self.with_reviews and (detail.get("rate") or {}).get("reviews_qnt"):
                try:
                    reviews = self.api.reviews(code, limit=self.max_reviews)
                except Exception as exc:
                    print(f"    ! отзывы {code}: {exc}", file=sys.stderr)
            record = build_record(detail, reviews)

        with self.lock:
            self.cache[code] = record
        return record

    def _fetch_products(self, codes) -> tuple[list[dict], list[str]]:
        records: list[dict] = []
        failed: list[str] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(self.get_product, c): c for c in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    record = future.result()
                    records.append(record) if record else failed.append(code)
                except Exception as exc:
                    failed.append(code)
                    print(f"    ! {code}: {exc}", file=sys.stderr)
        return records, failed

    def collect_category(self, category_code: str) -> tuple[list[dict], list[str]]:
        # Листинги Симферополя и Москвы тянутся параллельно: на мелких категориях
        # именно эти два запроса, а не карточки, определяют время обхода.
        codes: dict[str, None] = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            listings = pool.map(
                lambda m: self.api.list_category(category_code, m), (MERCHANT_ID, 3)
            )
            for listing in listings:
                for item in listing:
                    if item.get("code"):
                        codes[item["code"]] = None

        records, failed = self._fetch_products(codes)
        if failed:
            # то же самое временное дребезжание, что и на уровне категорий —
            # одна короткая пауза и повтор именно упавших карточек.
            time.sleep(5)
            retried, failed = self._fetch_products(failed)
            records.extend(retried)

        records.sort(key=lambda r: (not r["in_stock"], r["title"] or ""))
        return records, failed


def _harvest_category(collector: Collector, node: dict, path: list[str], out_dir: Path) -> dict:
    """Собрать одну категорию и записать файл. Бросает исключение при неудаче."""
    code = node["code"]
    out_path = out_dir / f"{safe_name(code)}.json.gz"
    records, failed = collector.collect_category(code)

    in_stock = sum(1 for r in records if r["in_stock"])
    meta = {
        "category": code,
        "category_name": node.get("name"),
        "category_path": path,
        "merchant_id": MERCHANT_ID,
        "merchant_name": MERCHANT_NAME,
        "region_id": REGION_ID,
        "currency": "RUB",
        "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "products_total": len(records),
        "products_in_stock": in_stock,
        "products_out_of_stock": len(records) - in_stock,
        "reviews_total": sum(len(r.get("reviews") or []) for r in records),
        "failed_codes": failed,
    }
    write_json(out_path, {"meta": meta, "products": records})
    return meta | {"file": out_path.name}


def write_by_category(
    collector: Collector,
    leaves: list[tuple[dict, list[str]]],
    out_dir: Path,
    resume: bool,
    with_reviews: bool,
    started: float,
) -> int:
    """Обойти категории, каждую записать отдельным файлом, собрать манифест.

    Общая часть для полного каталога и для пищевого среза — оба раскладывают
    результат одинаково, отличаются только набором категорий и папкой.

    Категория, упавшая целиком (а не отдельными карточками — это уже
    разбирается в Collector), почти всегда падает вместе с соседями от
    одного и того же временного сбоя. Поэтому такие категории не отбрасываются
    молча, а собираются в список и обходятся вторым проходом в конце —
    так же, как устроен повтор в snapshot_prices.py."""
    manifest: list[dict] = []
    total_products = 0
    skipped = 0
    failed_categories: list[tuple[dict, list[str]]] = []

    for index, (node, path) in enumerate(leaves, 1):
        code = node.get("code")
        if not code:
            continue
        out_path = out_dir / f"{safe_name(code)}.json.gz"
        label = " / ".join(path)

        # прогон, начатый до включения сжатия, продолжается без перезапроса
        done_path = next((p for p in (out_path, out_path.with_suffix("")) if p.exists()), None)
        if done_path and resume:
            skipped += 1
            try:
                existing = read_json(done_path)
                manifest.append(existing["meta"] | {"file": done_path.name})
                total_products += existing["meta"]["products_total"]
            except Exception:
                pass
            continue

        try:
            entry = _harvest_category(collector, node, path, out_dir)
        except Exception as exc:
            print(f"[{index}/{len(leaves)}] {label} — ОШИБКА: {exc}", file=sys.stderr)
            failed_categories.append((node, path))
            continue

        manifest.append(entry)
        total_products += entry["products_total"]
        elapsed = time.time() - started
        eta = elapsed / index * (len(leaves) - index)
        print(
            f"[{index}/{len(leaves)}] {label[:60]} — {entry['products_total']} тов. "
            f"(в наличии {entry['products_in_stock']}) | уник. карточек {len(collector.cache)} "
            f"| осталось ~{eta / 60:.0f} мин"
        )

    if failed_categories:
        preview = ", ".join((n.get("code") or "?") for n, _ in failed_categories[:10])
        print(f"\n! не удалось обойти категорий с первой попытки: {len(failed_categories)} "
              f"({preview}) — повторяю через 30 секунд", file=sys.stderr)
        time.sleep(30)

        still_failed: list[tuple[dict, list[str], str]] = []
        for node, path in failed_categories:
            label = " / ".join(path)
            try:
                entry = _harvest_category(collector, node, path, out_dir)
            except Exception as exc:
                print(f"  повтор {label} — ОШИБКА: {exc}", file=sys.stderr)
                still_failed.append((node, path, str(exc)))
                continue
            manifest.append(entry)
            total_products += entry["products_total"]
            print(f"  повтор {label} — собрано {entry['products_total']} тов.")

        # категория, не собравшаяся и со второй попытки, остаётся в манифесте
        # явной пометкой "failed" — вместо того чтобы просто выпасть из него.
        # Так следующий прогон (в течение дня/на следующий день, см.
        # weekly-full.yml) видит, что именно осталось дособрать, а не гадает
        # по разнице с ожидаемым числом категорий.
        for node, path, error in still_failed:
            manifest.append({
                "category": node.get("code"),
                "category_name": node.get("name"),
                "category_path": path,
                "failed": True,
                "error": error,
            })

        recovered = len(failed_categories) - len(still_failed)
        if recovered:
            print(f"  повтор дособрал {recovered} из {len(failed_categories)} категорий", file=sys.stderr)
        if still_failed:
            codes = ", ".join((n.get("code") or "?") for n, _, _ in still_failed)
            print(f"::error::полный срез: {len(still_failed)} категорий не собрались "
                  f"даже после повторного прогона — {codes}", file=sys.stderr)

    # манифест намеренно не сжимается — он маленький, и в него удобно заглянуть
    write_json(
        out_dir / "_manifest.json",
        {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "merchant_id": MERCHANT_ID,
            "merchant_name": MERCHANT_NAME,
            "with_reviews": with_reviews,
            "categories_total": len(manifest),
            "unique_products": len(collector.cache),
            "product_rows_total": total_products,
            "categories": manifest,
        },
    )

    failed_final = sum(1 for c in manifest if c.get("failed"))
    print(f"\nГотово за {(time.time() - started) / 60:.1f} мин")
    print(f"  категорий:        {len(manifest)}" + (f" (пропущено готовых {skipped})" if skipped else "")
          + (f" (не собралось {failed_final})" if failed_final else ""))
    print(f"  уникальных SKU:   {len(collector.cache)}")
    print(f"  строк в файлах:   {total_products} (товар может быть в нескольких категориях)")
    print(f"  сэкономлено запросов кэшем: {collector.requests_saved}")
    print(f"  папка:            {out_dir}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Полный обход каталога АШАН Симферополь")
    parser.add_argument("--out-dir", help="папка вывода (по умолчанию output/ГГГГ-ММ-ДД)")
    parser.add_argument("--reviews", action="store_true", help="собирать тексты отзывов")
    parser.add_argument("--max-reviews", type=int, default=None, help="лимит отзывов на товар")
    parser.add_argument("--limit", type=int, default=None, help="обработать только N категорий")
    parser.add_argument(
        "--include-hidden", action="store_true", help="включить Коллекции, опт и B2B-разделы"
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="не пропускать уже готовые файлы категорий"
    )
    args = parser.parse_args()

    api = AuchanAPI()
    collector = Collector(api, args.reviews, args.max_reviews)
    started = time.time()

    print(f"Магазин: {MERCHANT_NAME} (merchantId={MERCHANT_ID})")
    print(f"Отзывы:  {'да' if args.reviews else 'нет (только рейтинг и разбивка по звёздам)'}")
    print("\nЗагружаю дерево категорий...")

    tree = fetch_tree(api, args.include_hidden)
    leaves = list(iter_leaves(tree))
    if args.limit:
        leaves = leaves[: args.limit]
    print(f"Корневых разделов: {len(tree)} | категорий к обходу: {len(leaves)}")

    # папка определяется после дерева: нужно знать, сколько категорий считать полным прогоном
    out_dir = resolve_out_dir(len(leaves), args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Папка:   {out_dir}\n")

    return write_by_category(
        collector, leaves, out_dir, not args.no_resume, args.reviews, started
    )


if __name__ == "__main__":
    sys.exit(main())
