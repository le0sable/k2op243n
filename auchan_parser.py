"""
Парсер каталога auchan.ru для магазина АШАН Симферополь (merchantId=729).

Собирает по категории максимально полную карточку каждого товара:
цены и скидки, остаток, бренд, состав, масса, КБЖУ, все характеристики,
описание, изображения, рейтинг с разбивкой по звёздам и сами отзывы.

Работает через внутренний JSON API /v3/ — браузер не нужен.
HTML-страницы сайта закрыты Qrator, но API отдаётся напрямую
и разрешён в robots.txt (Allow: */v3/).

Использование:
    python auchan_parser.py moloko
    python auchan_parser.py moloko --no-reviews
    python auchan_parser.py syry -o output/syry.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://www.auchan.ru/v3"

# Симферополь — единственный магазин Ашана в Крыму (regionId=9).
MERCHANT_ID = 729
REGION_ID = 9
MERCHANT_NAME = "АШАН Симферополь"

# Листинг категории отдаёт только товары В НАЛИЧИИ у конкретного мерчанта.
# Чтобы захватить и отсутствующие в Симферополе позиции, коды товаров
# собираются объединением листингов нескольких мерчантов, а карточка
# каждого кода затем запрашивается уже под Симферополь.
DISCOVERY_MERCHANTS = [729, 3]  # Симферополь + Москва (самый широкий ассортимент)

PER_PAGE = 100  # жёсткий потолок API, больше не отдаёт
REVIEWS_PER_PAGE = 100

# Замер на живом API: 6 потоков дают ~9.6 карточек/с, 16 — ~19.6, 20 — уже 17.1,
# а 32 без паузы проваливаются до 4.6 (сервер начинает придерживать соединения).
# 16/0.05 — верхняя точка перед деградацией, ошибок на ней не было.
WORKERS = 16
THROTTLE = 0.05  # пауза между запросами внутри воркера, сек

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class AuchanAPI:
    """Тонкий клиент вокруг /v3/ с ретраями и троттлингом."""

    def __init__(self, merchant_id: int = MERCHANT_ID):
        self.merchant_id = merchant_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Content-Type": "application/json",
                "Origin": "https://www.auchan.ru",
                "Referer": "https://www.auchan.ru/",
            }
        )
        retry = Retry(
            total=4,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=WORKERS * 2)
        self.session.mount("https://", adapter)
        self._lock = threading.Lock()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        time.sleep(THROTTLE)
        resp = self.session.request(method, f"{BASE}{path}", timeout=30, **kwargs)
        if resp.status_code == 401:
            # Qrator включил челлендж — значит темп запросов слишком высокий.
            raise RuntimeError(
                "401 от Qrator — API временно закрылось. Снизьте WORKERS / увеличьте THROTTLE."
            )
        resp.raise_for_status()
        return resp.json()

    # --- каталог -----------------------------------------------------------

    def list_category(self, category: str, merchant_id: int) -> list[dict]:
        """Все товары категории, доступные у данного мерчанта."""
        items: list[dict] = []
        page = 1
        while True:
            data = self._request(
                "POST",
                "/catalog/products/",
                params={"merchantId": merchant_id, "page": page, "perPage": PER_PAGE},
                json={"filter": {"category": category}},
            )
            batch = data.get("items") or []
            items.extend(batch)
            total = data.get("range") or 0
            if len(items) >= total or not batch:
                break
            page += 1
        return items

    def product_detail(self, code: str) -> dict | None:
        """Полная карточка товара в разрезе выбранного мерчанта."""
        try:
            return self._request(
                "GET",
                "/catalog/product-detail/",
                params={"code": code, "merchantId": self.merchant_id},
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise

    def reviews(self, code: str, limit: int | None = None) -> list[dict]:
        """Все отзывы о товаре (offset-пагинация)."""
        collected: list[dict] = []
        offset = 0
        while True:
            data = self._request(
                "POST",
                "/reviews/reviews/",
                json={
                    "code": code,
                    "pagination": {
                        "type": "offset",
                        "limit": REVIEWS_PER_PAGE,
                        "offset": offset,
                    },
                },
            )
            batch = (data.get("data") or {}).get("reviews") or []
            collected.extend(batch)
            total = ((data.get("meta") or {}).get("pagination") or {}).get("total", 0)
            offset += REVIEWS_PER_PAGE
            if not batch or offset >= total:
                break
            if limit and len(collected) >= limit:
                return collected[:limit]
        return collected


# Характеристики, вынесенные в отдельные поля записи. Из `characteristics`
# они удаляются: на срезе продуктов дублировались 1:1 у 100% товаров и давали
# около 9 МБ лишнего объёма. «Масса брутто» и «ДxШxВ» отдельными полями не
# выносятся и остаются здесь.
FLATTENED_CHARS = {
    "Состав",
    "Масса нетто, кг",
    "Объем, л",
    "Срок хранения",
    "Температурный режим",
    "Производитель",
    "Страна производства",
    "Калорийность",
    "Белки на 100 г, г",
    "Жиры на 100 г, г",
    "Углеводы на 100 г, г",
}


def characteristics_to_dict(chars: list[dict]) -> dict[str, Any]:
    """[{title, value}] -> {title: value}, дубли схлопываются в список."""
    out: dict[str, Any] = {}
    for c in chars or []:
        title, value = c.get("title"), c.get("value")
        if title is None:
            continue
        if title in out:
            existing = out[title]
            out[title] = existing + [value] if isinstance(existing, list) else [existing, value]
        else:
            out[title] = value
    return out


def dump_json(payload: Any) -> str:
    """Компактный JSON: отступы удваивали размер файлов, а читают их программы."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def write_json(path: Path, payload: Any) -> None:
    """Записать JSON, сжимая gzip'ом, если путь оканчивается на .gz.

    Сжатие даёт восьмикратную экономию (62 МБ → 7.6 МБ на пищевом срезе)
    и ничего не стоит: gzip.open читается так же прозрачно.
    """
    data = dump_json(payload)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
            f.write(data)
    else:
        path.write_text(data, encoding="utf-8")


def read_json(path: Path) -> Any:
    """Прочитать выгрузку — сжатую или обычную, чтобы старые файлы тоже открывались."""
    if Path(path).suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def category_files(directory: Path) -> list[Path]:
    """Файлы категорий в папке выгрузки: и сжатые, и старые несжатые."""
    return sorted(
        p
        for p in directory.glob("*.json*")
        if p.suffix in (".json", ".gz") and not p.name.startswith("_manifest")
    )


def build_record(detail: dict, reviews: list[dict]) -> dict:
    """Собирает плоскую и удобную для анализа запись из ответа API."""
    chars = characteristics_to_dict(detail.get("characteristics") or [])
    stock = detail.get("stock") or {}
    price = detail.get("price") or {}
    old_price = detail.get("oldPrice") or {}

    # Для товаров, которых нет в ассортименте Симферополя, API отдаёт цену 0.
    # Это не «бесплатно», а «цены для этого магазина нет» — пишем null.
    price_value = price.get("value") or None
    old_price_value = old_price.get("value") or None
    energy = detail.get("energy_value") or {}
    rate = detail.get("rate") or {}
    brand = detail.get("brand") or {}
    discount = detail.get("discount") or {}

    record = {
        # идентификаторы; ссылка на товар — https://www.auchan.ru/product/<code>/
        "code": detail.get("code"),
        "product_id": detail.get("productId"),
        "article": detail.get("gimaId"),  # артикул, он же на карточке товара
        "title": detail.get("title"),
        # бренд и происхождение
        "brand": brand.get("name"),
        "manufacturer": chars.get("Производитель"),
        "country": chars.get("Страна производства"),
        # цены
        "price": price_value,
        "old_price": old_price_value,
        # товар вообще продаётся в этом магазине (цена известна), даже если сейчас 0 остаток
        "sold_in_region": price_value is not None,
        # item / weight_kg / weight_100g — без этого цены весовых товаров
        # несопоставимы с штучными
        "price_per": price.get("per"),
        "discount_percent": discount.get("size"),
        "discount_start": discount.get("date_start"),
        "discount_end": discount.get("date_end"),
        # Кэшбэк баллами — это не скидка с цены. В product-detail поле
        # cashbackPercent всегда null, реальный процент лежит внутри cashback.
        "cashback_percent": (detail.get("cashback") or {}).get("percent")
        or detail.get("cashbackPercent"),
        # наличие в Симферополе
        "in_stock": not stock.get("not_available", True) and bool(stock.get("qty")),
        "stock_qty": stock.get("qty"),
        "basket_step": detail.get("basketStep"),
        # состав и вес
        "composition": chars.get("Состав"),
        "net_weight_kg": chars.get("Масса нетто, кг"),
        "volume_l": chars.get("Объем, л"),
        "shelf_life": chars.get("Срок хранения"),
        "storage_temp": chars.get("Температурный режим"),
        # КБЖУ на 100 г
        "nutrition_per_100g": {
            "calories": energy.get("calories"),
            "proteins": energy.get("proteins"),
            "fats": energy.get("fats"),
            "carbohydrates": energy.get("carbohydrates"),
        },
        # оценки
        "rating": rate.get("rating"),
        "reviews_count": rate.get("reviews_qnt"),
        "rating_breakdown": {
            "5": rate.get("rate5"),
            "4": rate.get("rate4"),
            "3": rate.get("rate3"),
            "2": rate.get("rate2"),
            "1": rate.get("rate1"),
        },
        # тексты и медиа (первое изображение — то же, что на карточке каталога)
        "description": (detail.get("description") or {}).get("content"),
        "images": detail.get("mediaUrls") or [],
        # категории и прочее
        "categories": [
            {"code": c.get("code"), "name": c.get("name")}
            for c in detail.get("categoryCodes") or []
        ],
        # бейджи-плашки на карточке: discount, cashback, private_label, first_price...
        "badges": [
            {
                "code": b.get("code"),
                "type": b.get("type"),
                "description": b.get("description"),
                "value_text": b.get("value_text"),
            }
            for b in detail.get("badges") or []
        ],
        "is_adult": detail.get("isAdult"),
        "is_new": detail.get("is_new"),
        # остальные характеристики: те, что вынесены в поля выше, отсюда убраны,
        # чтобы не хранить одно и то же дважды
        "characteristics": {k: v for k, v in chars.items() if k not in FLATTENED_CHARS},
    }
    if reviews:
        record["reviews"] = reviews
    return record


def discover_codes(api: AuchanAPI, category: str) -> list[str]:
    """Коды товаров категории: объединение листингов нескольких мерчантов."""
    codes: dict[str, None] = {}
    for merchant_id in DISCOVERY_MERCHANTS:
        items = api.list_category(category, merchant_id)
        new = [i["code"] for i in items if i.get("code") and i["code"] not in codes]
        for c in (i["code"] for i in items if i.get("code")):
            codes[c] = None
        label = "Симферополь" if merchant_id == MERCHANT_ID else f"merchantId={merchant_id}"
        print(f"  {label}: {len(items)} товаров в наличии (+{len(new)} новых кодов)")
    return list(codes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Парсер каталога АШАН Симферополь")
    parser.add_argument("category", help="код категории, например moloko")
    parser.add_argument("-o", "--output", help="путь к итоговому JSON")
    parser.add_argument("--no-reviews", action="store_true", help="не собирать тексты отзывов")
    parser.add_argument(
        "--max-reviews", type=int, default=None, help="ограничить число отзывов на товар"
    )
    args = parser.parse_args()

    api = AuchanAPI()
    started = time.time()

    print(f"Категория: {args.category} | магазин: {MERCHANT_NAME} (merchantId={MERCHANT_ID})")
    print("Собираю список товаров...")
    codes = discover_codes(api, args.category)
    if not codes:
        print("Товаров не найдено — проверьте код категории.", file=sys.stderr)
        return 1
    print(f"Итого уникальных товаров: {len(codes)}\n")

    records: list[dict] = []
    failed: list[str] = []
    done = 0
    lock = threading.Lock()

    def fetch(code: str) -> dict | None:
        detail = api.product_detail(code)
        if not detail:
            return None
        reviews: list[dict] = []
        if not args.no_reviews and (detail.get("rate") or {}).get("reviews_qnt"):
            try:
                reviews = api.reviews(code, limit=args.max_reviews)
            except Exception as exc:  # отзывы не должны ронять сбор карточки
                print(f"  ! отзывы для {code}: {exc}", file=sys.stderr)
        return build_record(detail, reviews)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch, c): c for c in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                record = future.result()
                if record:
                    records.append(record)
                else:
                    failed.append(code)
            except Exception as exc:
                failed.append(code)
                print(f"  ! {code}: {exc}", file=sys.stderr)
            with lock:
                done += 1
                if done % 20 == 0 or done == len(codes):
                    print(f"  обработано {done}/{len(codes)}")

    records.sort(key=lambda r: (not r["in_stock"], r["title"] or ""))

    out_path = Path(args.output or f"output/{args.category}_simferopol.json.gz")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    in_stock = sum(1 for r in records if r["in_stock"])
    payload = {
        "meta": {
            "category": args.category,
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
        },
        "products": records,
    }
    write_json(out_path, payload)

    print(f"\nГотово за {time.time() - started:.0f} с")
    print(f"  товаров:      {len(records)} (в наличии {in_stock}, нет {len(records) - in_stock})")
    print(f"  отзывов:      {payload['meta']['reviews_total']}")
    if failed:
        print(f"  не удалось:   {len(failed)} — {', '.join(failed[:5])}")
    print(f"  файл:         {out_path} ({out_path.stat().st_size / 1024:.0f} КБ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
