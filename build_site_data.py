# -*- coding: utf-8 -*-
"""Сборка данных для PWA-помощника покупок из накопленных выгрузок.

Читает все дневные срезы (output/food-*.parquet и output/ГГГГ-ММ-ДД.parquet),
считает оценки состава и историю цен, пишет компактные JSON в web/data/:

  meta.json            — дата, счётчики, список категорий
  index.json           — колоночный индекс всех пищевых товаров (для поиска/списков)
  details/NN.json      — тяжёлые поля (состав, история цен) шардами по коду

Запуск:  python build_site_data.py
"""
import glob
import json
import math
import os
import re
import statistics
import sys

import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "data")
SHARDS = 32

# Классы вредности Е-добавок: 0 безвредна … 3 избегать.
# Источники: классификации Codex/Роспотребнадзор + открытые справочники добавок.
E_HAZARD = {
    3: {102, 104, 110, 122, 124, 129, 131, 142, 151, 154, 155, 173, 180,
        214, 215, 216, 217, 219, 226, 227, 230, 231, 233, 239, 249, 250,
        251, 252, 310, 320, 321, 407, 425, 512, 621, 622, 627, 631, 635,
        924, 926, 951, 952, 954, 957},
    2: {100, 120, 127, 128, 133, 150, 153, 160, 200, 201, 202, 203, 210,
        211, 212, 213, 220, 221, 222, 223, 224, 228, 234, 235, 242, 261,
        262, 280, 281, 282, 283, 338, 339, 340, 341, 385, 405, 412, 413,
        414, 420, 421, 422, 430, 431, 432, 433, 434, 435, 436, 442, 444,
        445, 450, 451, 452, 459, 460, 461, 463, 465, 466, 471, 472, 473,
        475, 476, 477, 481, 482, 483, 491, 492, 493, 494, 495, 950, 955,
        965, 967},
    1: {101, 106, 140, 141, 160, 161, 162, 163, 170, 171, 172, 260, 270,
        290, 296, 300, 301, 302, 306, 307, 322, 325, 326, 330, 331, 332,
        333, 334, 335, 336, 341, 400, 401, 402, 406, 410, 415, 416, 417,
        440, 500, 501, 503, 504, 507, 508, 509, 511, 513, 514, 524, 525,
        526, 527, 528, 530, 570, 575, 640, 900, 901, 902, 903, 904, 920,
        938, 941, 948, 960, 1400, 1404, 1410, 1412, 1414, 1420, 1422,
        1442, 1450},
}
E_LEVEL = {}
for lvl in (1, 2, 3):
    for code in E_HAZARD[lvl]:
        E_LEVEL[code] = max(E_LEVEL.get(code, 0), lvl)

E_RE = re.compile(r"[EЕ]\s?-?\s?(\d{3,4})", re.IGNORECASE)
SUGAR_RE = re.compile(r"сахар|глюкозн|фруктозн|патока|мальтодекстрин|инвертн", re.I)
PALM_RE = re.compile(r"пальмов|растительн\w+ жир|заменитель молочного жира|гидрогенизир", re.I)
FLAVOR_RE = re.compile(r"усилитель вкуса|глутамат|инозинат|гуанилат", re.I)
SWEET_RE = re.compile(r"аспартам|сукралоза|ацесульфам|цикламат|сахарин", re.I)

NONFOOD_CATS = {
    "Все для учебы", "Кухня", "Спорт и отдых", "Уборка и бытовая химия",
    "Аптека", "Красота и гигиена", "Дом и интерьер", "Дача, сад",
    "Товары для животных", "Бытовая техника", "Текстиль", "Одежда и обувь",
}


def parse_qty(row):
    """Количество в кг или л для цены за единицу."""
    for col, unit in (("net_weight_kg", "кг"), ("volume_l", "л")):
        v = row.get(col)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        try:
            q = float(str(v).replace(",", "."))
        except ValueError:
            continue
        if 0 < q < 100:
            return q, unit
    return None, None


def score_composition(comp):
    """Оценка состава 0..100 (в вакууме) + флаги."""
    if not comp or not isinstance(comp, str) or len(comp) < 3:
        return None, [], []
    e_codes = sorted({int(m) for m in E_RE.findall(comp) if int(m) < 2000})
    penalty = 0.0
    for c in e_codes:
        penalty += {0: 1, 1: 2, 2: 6, 3: 12}[E_LEVEL.get(c, 0)]
    ingredients = [p.strip() for p in re.split(r"[,;]", comp) if p.strip()]
    n_ing = len(ingredients)
    penalty += max(0, n_ing - 5) * 0.8  # длинный состав
    flags = []
    head = ", ".join(ingredients[:3])
    if SUGAR_RE.search(head):
        flags.append("sugar_first")
        penalty += 8
    if PALM_RE.search(comp):
        flags.append("palm")
        penalty += 10
    if FLAVOR_RE.search(comp):
        flags.append("flavor_enh")
        penalty += 8
    if SWEET_RE.search(comp):
        flags.append("sweetener")
        penalty += 5
    score = max(0.0, 100.0 - penalty)
    return round(score, 1), e_codes, flags


def collect_history():
    """История цен по всем срезам: code -> [(date, price, old_price, in_stock)]."""
    hist = {}
    files = {}
    for p in glob.glob("output/food-????-??-??.parquet"):
        files[os.path.basename(p)[5:15]] = p
    for p in glob.glob("output/????-??-??.parquet"):
        files.setdefault(os.path.basename(p)[:10], p)
    # Снимки цен (snapshot_prices.py) — только листинги, без карточек. Они
    # дешёвые и потому ежедневные, но полный срез за ту же дату богаче:
    # в снимке нет товаров, которых сейчас нет в наличии.
    for p in glob.glob("output/snapshots/????-??-??.parquet"):
        files.setdefault(os.path.basename(p)[:10], p)
    for date in sorted(files):
        df = pd.read_parquet(files[date], columns=["code", "price", "old_price", "in_stock"])
        for code, price, old, stock in df.itertuples(index=False):
            if price is None or (isinstance(price, float) and math.isnan(price)):
                continue
            hist.setdefault(code, []).append(
                (date, round(float(price), 2),
                 None if old is None or (isinstance(old, float) and math.isnan(old)) else round(float(old), 2),
                 bool(stock)))
    return hist


def typical_price(entries):
    """Типичная (не акционная) цена: медиана old_price-или-price по дням."""
    vals = [(old if old else price) for _, price, old, _ in entries]
    return round(statistics.median(vals), 2) if vals else None


def main():
    food_files = sorted(glob.glob("output/food-????-??-??.parquet"))
    if not food_files:
        sys.exit("нет файлов output/food-*.parquet — сначала запустить парсер и export_parquet")
    latest = food_files[-1]
    date = os.path.basename(latest)[5:15]
    df = pd.read_parquet(latest)
    df = df[~df.category_1.isin(NONFOOD_CATS)].copy()

    print(f"срез {date}: {len(df)} товаров; собираю историю…")
    hist = collect_history()

    rows, details = [], {}
    for r in df.to_dict("records"):
        code = r["code"]
        score, e_codes, flags = score_composition(r.get("composition"))
        qty, unit = parse_qty(r)
        price = r.get("price")
        if price is None or (isinstance(price, float) and math.isnan(price)):
            continue
        price = float(price)
        ppu = round(price / qty, 2) if qty else None

        h = hist.get(code, [])
        typ = typical_price(h)
        # умная скидка: цена ниже типичной минимум на 5%
        deal = None
        if typ and typ > 0:
            rel = (price - typ) / typ * 100
            deal = round(rel, 1)

        def f(x, nd=2):
            if x is None:
                return None
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return None if math.isnan(x) else round(x, nd)

        def s(key):
            v = r.get(key)
            return v if isinstance(v, str) and v.strip(" -–—") else None

        rows.append({
            "c": code, "t": s("title"), "b": s("brand"),
            "k1": s("category_1"), "k2": s("category_2"),
            "p": round(price, 2), "op": f(r.get("old_price")),
            "d": f(r.get("discount_percent"), 0),
            "de": r.get("discount_end") if isinstance(r.get("discount_end"), str) else None,
            "pk": ppu, "un": unit,
            "r": f(r.get("rating"), 1), "rc": f(r.get("reviews_count"), 0),
            "s": score, "fl": flags, "st": bool(r.get("in_stock")),
            "kc": f(r.get("nutrition_calories"), 0), "pr": f(r.get("nutrition_proteins"), 1),
            "typ": typ, "rel": deal,
            # в parquet images — все URL через "|"; для карточки нужен первый
            "im": (r["images"].split("|", 1)[0] or None)
                  if isinstance(r.get("images"), str) and r["images"] else None,
        })
        details[code] = {
            "comp": r.get("composition") if isinstance(r.get("composition"), str) else None,
            "e": e_codes,
            "eh": {str(c): E_LEVEL.get(c, 0) for c in e_codes},
            "hist": [[d_, p_, o_, int(s_)] for d_, p_, o_, s_ in h],
            "fat": f(r.get("nutrition_fats"), 1),
            "carb": f(r.get("nutrition_carbohydrates"), 1),
            "descr": (r["description"][:600] if isinstance(r.get("description"), str) else None),
            "country": r.get("country") if isinstance(r.get("country"), str) else None,
        }

    # относительная оценка: перцентиль score внутри category_2 (мин. 8 товаров, иначе category_1)
    for key in ("k2", "k1"):
        groups = {}
        for row in rows:
            if row["s"] is not None:
                groups.setdefault(row[key], []).append(row["s"])
        for row in rows:
            if row.get("sp") is not None or row["s"] is None:
                continue
            g = sorted(groups.get(row[key], []))
            if len(g) >= 8:
                import bisect
                # средний ранг: у максимума в однородной группе перцентиль ~50, а не 0
                mid = (bisect.bisect_left(g, row["s"]) + bisect.bisect_right(g, row["s"])) / 2
                row["sp"] = round(mid / len(g) * 100)
    for row in rows:
        row.setdefault("sp", None)
        # ценность: качество за рубль (относительно категории считается на клиенте)
        if row["s"] is not None and row["pk"]:
            row["v"] = round(row["s"] / row["pk"] * 10, 1)
        else:
            row["v"] = None

    os.makedirs(os.path.join(OUT_DIR, "details"), exist_ok=True)
    cols = list(rows[0].keys())
    index = {"cols": cols, "rows": [[row[c] for c in cols] for row in rows]}
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))

    # стабильный шардинг (встроенный hash() меняется между запусками)
    shards = {i: {} for i in range(SHARDS)}
    for code, det in details.items():
        shards[sum(ord(ch) for ch in str(code)) % SHARDS][str(code)] = det
    for i, data in shards.items():
        with open(os.path.join(OUT_DIR, "details", f"{i}.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    dates = sorted({d_ for h in hist.values() for d_, *_ in h})
    meta = {
        "date": date, "products": len(rows), "days": len(dates), "dates": dates,
        "shards": SHARDS,
        "cats": sorted({row["k1"] for row in rows if row["k1"]}),
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)

    size = os.path.getsize(os.path.join(OUT_DIR, "index.json")) / 1e6
    print(f"готово: {len(rows)} товаров, индекс {size:.1f} МБ, история за {len(dates)} дн.")


if __name__ == "__main__":
    main()
