"""Сборка дизайн-кита «Корзинка» для Claude Design.

Каждая карточка — самодостаточный HTML: стили из web/style.css вшиваются inline,
данные захардкожены, ни одного сетевого запроса (фото — inline-SVG-муляжи).
Разметка карточек скопирована с шаблонов web/app.js.

    python build_design_kit.py            # → design/

Первая строка каждого файла — маркер <!-- @dsCard group="…" -->, по нему
Claude Design строит индекс карточек.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
WEB = ROOT / "web"
OUT = ROOT / "design"

STYLE = (WEB / "style.css").read_text(encoding="utf-8")

# ---------------------------------------------------------------- обвязка кита

KIT_CSS = """
/* --- обвязка превью, в приложение не попадает --- */
body.ds{background:#F0EFEC;padding:20px;font:14px/1.4 Inter,-apple-system,"Segoe UI",Roboto,sans-serif}
.ds-h{margin:0 0 14px}
.ds-h b{display:block;font-size:15px;font-weight:700;color:#212120}
.ds-h span{display:block;font-size:12px;color:#8A8880;margin-top:2px}
.ds-frame{background:#FFFFFF;border-radius:18px;overflow:hidden;
  box-shadow:0 2px 14px rgba(33,32,31,.10)}
.ds-frame.pad{padding:16px}
.ds-sec{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:#8A8880;margin:22px 0 8px}
.ds-sec:first-child{margin-top:0}
.ds-note{font-size:12px;color:#8A8880;margin:6px 0 0}
.ds-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}
.ds-col{display:grid;gap:10px}
/* внутри превью «залипание» и фиксация только мешают */
.ds-frame #top{position:static}
.ds-frame #tabs{position:static;max-width:none;margin:0}
.ds-frame #to-top{position:static;opacity:1;visibility:visible;transform:none}
.ds-frame .toast{position:static;transform:none;max-width:none;display:inline-block}
.ds-frame main,.ds-frame .page{padding-bottom:16px}
/* экраны целиком — «телефон» 393×873 */
.ds-phone{width:393px;height:873px;overflow:hidden;position:relative;
  background:#FFFFFF;border-radius:22px;box-shadow:0 2px 18px rgba(33,32,31,.14)}
/* #app в приложении position:relative — гасим, иначе таб-бар цепляется за него,
   а не за «телефон», и уезжает вниз вместе с лентой */
.ds-phone #app{max-width:none;position:static;height:100%}
.ds-phone .ds-scroll{height:100%;overflow:hidden}
.ds-phone #tabs{position:absolute;bottom:0;left:0;right:0;max-width:none}
/* муляжи фото вместо сетевых картинок */
.ph-wrap.mock .ph{background:#FFFFFF}
.ph-wrap.mock .ph svg{width:76%;height:76%;stroke:none}
.tile .tim svg{width:100%;height:100%}
/* палитра */
.sw{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.sw div{border-radius:12px;padding:10px 12px;font-size:12px;line-height:1.35;
  box-shadow:inset 0 0 0 1px rgba(33,32,31,.08)}
.sw b{display:block;font-size:12px;font-weight:700}
.sw i{font-style:normal;opacity:.75;font-variant-numeric:tabular-nums}
.ds-scale{display:grid;gap:8px}
.ds-scale div{display:flex;align-items:baseline;gap:12px}
.ds-scale u{text-decoration:none;font-size:11px;color:#8A8880;min-width:112px;flex:0 0 auto;
  font-variant-numeric:tabular-nums}
.ds-box{background:var(--chip);display:inline-block}
"""


def page(group, title, subtitle, body, extra_css="", cls="ds"):
    """Самодостаточная страница-карточка."""
    return (
        f'<!-- @dsCard group="{group}" -->\n'
        '<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{title} — Корзинка</title>\n"
        f"<style>\n{STYLE}\n</style>\n"
        f"<style>{KIT_CSS}{extra_css}</style>\n"
        f'</head>\n<body class="{cls}">\n'
        f'<div class="ds-h"><b>{title}</b><span>{subtitle}</span></div>\n'
        f"{body}\n</body>\n</html>\n"
    )


# ------------------------------------------------------------ иконки из app.js

ICON_BOX = ('<svg viewBox="0 0 24 24"><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5v-9Z"/>'
            '<path d="M3 7.5 12 12l9-4.5M12 12v9"/></svg>')
ICON_SEARCH = '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 21 21"/></svg>'
ICON_CART = '<svg viewBox="0 0 24 24"><path d="M4 8h16l-1.6 11H5.6L4 8ZM9 8V5a3 3 0 0 1 6 0v3"/></svg>'
ICON_HEART = ('<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.6-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 '
              '7-2.8c0 4.6-7 14.8-7 14.8Z"/></svg>')
ICON_EYE = ('<svg viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 '
            '18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/><path d="M4 20 20 4"/></svg>')
ICON_WARN = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.4v.2"/></svg>'
ICON_SORT = '<svg viewBox="0 0 24 24"><path d="M4 7h16M7 12h10M10 17h4"/></svg>'
ICON_UP = '<svg viewBox="0 0 24 24"><path d="M12 19V6M6 12l6-6 6 6"/></svg>'

# ------------------------------------------------- муляжи фото (без сети)

MOCKS = {
    "milk": '<svg viewBox="0 0 100 100"><path d="M32 34h36v50a4 4 0 0 1-4 4H36a4 4 0 0 1-4-4V34Z" fill="#DCE9F5"/>'
            '<path d="M32 34 42 16h16l10 18H32Z" fill="#B9D4EC"/><rect x="38" y="52" width="24" height="16" rx="3" fill="#4E7FB0"/></svg>',
    "cheese": '<svg viewBox="0 0 100 100"><path d="M16 68 74 30l12 12v26H16Z" fill="#F2CE5C"/>'
              '<circle cx="42" cy="58" r="6" fill="#E0B63C"/><circle cx="62" cy="52" r="4" fill="#E0B63C"/>'
              '<circle cx="30" cy="62" r="3" fill="#E0B63C"/></svg>',
    "cookie": ('<svg viewBox="0 0 100 100"><rect x="20" y="30" width="60" height="42" rx="6" fill="#D9A45B"/>'
               '<circle cx="38" cy="46" r="4" fill="#8A5A2B"/><circle cx="56" cy="42" r="3.5" fill="#8A5A2B"/>'
               '<circle cx="50" cy="60" r="4" fill="#8A5A2B"/><circle cx="66" cy="58" r="3" fill="#8A5A2B"/></svg>'),
    "tomato": '<svg viewBox="0 0 100 100"><circle cx="50" cy="58" r="28" fill="#E4574B"/>'
              '<path d="M50 30c-6-8-14-10-20-8 4 6 10 10 20 8Zm0 0c6-8 14-10 20-8-4 6-10 10-20 8Z" fill="#5A9E4B"/></svg>',
    "pack": '<svg viewBox="0 0 100 100"><rect x="24" y="26" width="52" height="50" rx="6" fill="#C9A27A"/>'
            '<rect x="24" y="26" width="52" height="14" rx="6" fill="#A67F58"/>'
            '<rect x="34" y="50" width="32" height="4" rx="2" fill="#F0E2D2"/>'
            '<rect x="34" y="58" width="22" height="4" rx="2" fill="#F0E2D2"/></svg>',
    "bottle": '<svg viewBox="0 0 100 100"><path d="M44 14h12v12l8 10v50a4 4 0 0 1-4 4H40a4 4 0 0 1-4-4V36l8-10V14Z" fill="#CBE3D6"/>'
              '<rect x="36" y="52" width="28" height="18" rx="3" fill="#2E8B62"/>'
              '<rect x="43" y="10" width="14" height="8" rx="2" fill="#2E8B62"/></svg>',
    "meat": '<svg viewBox="0 0 100 100"><ellipse cx="50" cy="56" rx="30" ry="22" fill="#E0857F"/>'
            '<ellipse cx="50" cy="56" rx="18" ry="12" fill="#C4635C"/></svg>',
    "bread": '<svg viewBox="0 0 100 100"><path d="M22 46a14 14 0 0 1 14-14h28a14 14 0 0 1 14 14v22a6 6 0 0 1-6 6H28a6 6 0 0 1-6-6V46Z" fill="#DCAF6E"/>'
             '<path d="M34 40c4-4 10-4 14 0m4 0c4-4 10-4 14 0" stroke="#B98A4B" stroke-width="3" fill="none" stroke-linecap="round"/></svg>',
}

def photo(mock=None, extra="", cls=""):
    """Копия photoHTML() из app.js: муляж вместо <img>."""
    inner = f'<div class="ph">{MOCKS[mock] if mock else ICON_BOX}</div>'
    wrap_cls = " ".join(x for x in ["ph-wrap", "mock" if mock else "", cls] if x)
    return f'<div class="{wrap_cls}">{inner}{extra}</div>'


# --------------------------------------------------------------- мок-товары

def card(t, p, *, old=None, ppk=None, rate=None, rc=None, score=None, mock="pack",
         deal=None, oos=False, fav=False, qty=0, flag=None):
    """Карточка ленты — разметка itemHTML() из app.js."""
    corner = ""
    if oos:
        corner = '<span class="oos-abs">нет в наличии</span>'
    elif deal:
        corner = f'<span class="badge-abs">{deal}</span>'
    s_abs = ""
    if score is not None:
        cls = "good" if score >= 67 else "mid" if score >= 34 else "bad"
        s_abs = f'<span class="s-abs {cls}">{score}</span>'
    heart = (f'<button type="button" class="heart{" on" if fav else ""}">'
             f'{"♥" if fav else "♡"}</button>{corner}{s_abs}')
    rate_html = (f'<div class="rate"><span class="st">★</span>{rate} · {rc}</div>'
                 if rate else '<div class="rate"></div>')
    price = (f'<div class="price{" sale" if old else ""}"><span>{p} ₽</span>'
             + (f'<span class="old">{old} ₽</span>' if old else "") + "</div>")
    if qty:
        act = (f'<span class="qty"><button type="button">−</button>'
               f'<span class="n">{qty}</span><button type="button">+</button></span>')
    else:
        act = '<button type="button" class="add">+ В список</button>'
    return (f'<article class="card{"" if not oos else " oos"}">'
            f'{photo(mock, heart)}{rate_html}'
            f'<div class="name">{t}</div>{price}'
            f'<div class="ppk">{f"{ppk} ₽/кг" if ppk else ""}</div>'
            f'<div class="act">{act}</div></article>')


P_MILK = dict(t="Молоко Домик в деревне отборное 3,7%, 930 мл", p="98,90", ppk="106,30",
              rate="4,7", rc="312", score=82, mock="milk", qty=0)
P_CHEESE = dict(t="Сыр Ламбер 50%, 460 г", p="449,00", old="589,00", ppk="976,10",
                rate="4,8", rc="1 204", score=71, mock="cheese",
                deal='<span class="badge good">−24%</span>')
P_COOKIE = dict(t="Печенье Юбилейное витаминизированное, 313 г", p="89,90", ppk="287,20",
                rate="4,5", rc="86", score=24, mock="cookie", qty=2)
P_TOMATO = dict(t="Помидоры розовые, 1 кг", p="219,00", ppk="219,00", rate="4,2", rc="41",
                score=95, mock="tomato", fav=True)
P_OIL = dict(t="Масло подсолнечное Слобода рафинированное, 1 л", p="139,00", ppk="139,00",
             score=88, mock="bottle", oos=True)
P_MEAT = dict(t="Филе бедра куриное охлаждённое, 1 кг", p="329,00", old="359,00", ppk="329,00",
              rate="4,6", rc="510", score=91, mock="meat",
              deal='<span class="badge small">−8%</span>')
P_BREAD = dict(t="Хлеб Бородинский нарезка, 390 г", p="52,90", ppk="135,60", rate="4,4",
               rc="128", score=64, mock="bread")
P_PACK = dict(t="Хлопья овсяные Ясно Солнышко, 500 г", p="74,50", ppk="149,00", rate="4,3",
              rc="67", score=79, mock="pack")


def grid(*items):
    return '<div class="grid">' + "".join(card(**i) for i in items) + "</div>"


# ============================================================ карточки кита

FILES = {}

# ---------------------------------------------------------------- 1. Токены

def _swatches():
    groups = [
        ("Поверхности", [("--bg / --card", "#FFFFFF", "#212120", "фон приложения и карточек"),
                         ("--sunken", "#F5F4F2", "#212120", "утопленные блоки, заглушка фото"),
                         ("--line", "#EBEAE7", "#212120", "разделители, границы"),
                         ("--chip", "rgba(101,92,78,.1)", "#212120", "чипы, кнопки, поля")]),
        ("Текст", [("--ink", "#212120", "#FFFFFF", "основной"),
                   ("--ink2", "#5C5B58", "#FFFFFF", "вторичный, подписи на плашках"),
                   ("--muted", "#999999", "#FFFFFF", "третичный: цена за кг, хинты"),
                   ("--chip-on", "#212120", "#FFFFFF", "активный чип")]),
        ("Акцент", [("--accent", "#009860", "#FFFFFF", "хорошая оценка, прогресс, график"),
                    ("--accent-ink", "#00794C", "#FFFFFF", "текст акцентом на светлом"),
                    ("--accent-soft", "#E4F4EC", "#00794C", "безопасные Е-добавки"),
                    ("--on-accent", "#FFFFFF", "#009860", "текст на акценте")]),
        ("Скидка и тревога", [("--deal", "#EF544A", "#FFFFFF", "бейдж выгоды, цена по акции"),
                              ("--deal-soft", "#FDE9E5", "#D1552E", "легенда «только скидки»"),
                              ("--danger", "#EF544A", "#FFFFFF", "превышение бюджета, ♥"),
                              ("--bad", "#D1552E", "#FFFFFF", "низкая оценка состава")]),
        ("Предупреждение", [("--warn", "#C07A12", "#FFFFFF", "средняя оценка"),
                            ("--warn-soft", "#FBEFD9", "#C07A12", "«цена как обычно»"),
                            ("--star", "#F5A623", "#212120", "звезда рейтинга")]),
        ("Фоны плиток-«прилавков»", [("Свежее", "#ECF5D3", "#212120", "овощи, молочное, мясо, рыба"),
                                     ("Каждый день", "#FFECB2", "#212120", "хлеб, бакалея, заморозка"),
                                     ("К чаю и перекус", "#FFF6ED", "#212120", "сладости, снеки, напитки"),
                                     ("Остальное", "#E7EEFB", "#212120", "всё, что не попало выше"),
                                     ("Скидки", "#FDE9E5", "#EF544A", "плитка «Скидки» первой строкой")]),
    ]
    out = []
    for name, rows in groups:
        out.append(f'<div class="ds-sec">{name}</div><div class="sw">')
        for label, val, ink, note in rows:
            out.append(f'<div style="background:{val};color:{ink}"><b>{label}</b>'
                       f'<i>{val}</i><br><i>{note}</i></div>')
        out.append("</div>")
    return "".join(out)


FILES["tokens/colors.html"] = page(
    "Токены", "Палитра", "Светлая тема, ориентир — Яндекс Лавка. Тёмной темы нет.",
    f'<div class="ds-frame pad">{_swatches()}</div>')

FILES["tokens/type-space.html"] = page(
    "Токены", "Типографика, радиусы, отступы",
    "Inter / системный стек, tabular-nums на всех числах",
    '<div class="ds-frame pad">'
    '<div class="ds-sec">Шрифтовая шкала</div><div class="ds-scale">'
    '<div><u>20 / 800 · h1, h2</u><span style="font-size:20px;font-weight:800;letter-spacing:-.01em">Список покупок</span></div>'
    '<div><u>20 / 800 · .grp-h</u><span class="grp-h" style="margin:0">Свежее</span></div>'
    '<div><u>20 / 800 · .price</u><span style="font-size:20px;font-weight:800;letter-spacing:-.02em">449,00 ₽</span></div>'
    '<div><u>26 / 800 · .price-now</u><span class="price-now">449,00 ₽</span></div>'
    '<div><u>18 / 700 · #card h2</u><span style="font-size:18px;font-weight:700">Сыр Ламбер 50%, 460 г</span></div>'
    '<div><u>15 / 700 · .sec-h</u><span class="sec-h" style="margin:0">Похожие</span></div>'
    '<div><u>14 / 400 · body</u><span>Базовый текст интерфейса</span></div>'
    '<div><u>13 / 400 · .name</u><span style="font-size:13px">Название товара в ленте</span></div>'
    '<div><u>13 / 500 · .chip</u><span style="font-size:13px;font-weight:500">Молоко, сыр, яйцо</span></div>'
    '<div><u>12 / 400 · .hint</u><span class="hint">Пояснение под блоком</span></div>'
    '<div><u>11 / 700 · .badge</u><span class="badge good">−24%</span></div>'
    "</div>"
    '<div class="ds-sec">Радиусы</div><div class="ds-row">'
    '<div class="ds-box" style="width:96px;height:56px;border-radius:16px"></div>'
    '<div class="ds-box" style="width:96px;height:56px;border-radius:8px"></div>'
    '<div class="ds-box" style="width:56px;height:56px;border-radius:50%"></div></div>'
    '<p class="ds-note">--r 16px — плитки, чипы, кнопки, шторки. --r-s 8px — бейджи и мелкие поля. '
    '50% — круглые кнопки «✕» и «назад».</p>'
    '<div class="ds-sec">Отступы</div><div class="ds-row" style="align-items:flex-end">'
    '<div class="ds-box" style="width:16px;height:16px"></div>'
    '<div class="ds-box" style="width:12px;height:12px"></div>'
    '<div class="ds-box" style="width:8px;height:8px"></div>'
    '<div class="ds-box" style="width:20px;height:20px"></div></div>'
    '<p class="ds-note">--pad 16px — поля экрана. 20/8 — зазоры сетки карточек (по вертикали больше, '
    'чтобы строки читались как ряды). 8px — сетка плиток и чипов. Тени нет нигде, кроме «наверх» и тоста.</p>'
    "</div>")

# ---------------------------------------------------------------- 2. Каталог

def _tile(name, n, bg, mock, wide=False, deals=False):
    cls = "tile" + (" wide" if wide else "") + (" deals" if deals else "")
    img = (f'<span class="tim shown" style="display:flex;align-items:flex-end;justify-content:flex-end">'
           f'{MOCKS[mock]}</span>')
    return (f'<button type="button" class="{cls}" style="background:{bg}">'
            f'<span class="tt">{name}</span><span class="tn">{n}</span>{img}</button>')


TILES_BODY = (
    '<div class="tgrid first">'
    + _tile("Скидки", "412", "#FDE9E5", "cheese", wide=True, deals=True) +
    "</div>"
    '<h2 class="grp-h">Свежее</h2><div class="tgrid">'
    + _tile("Овощи, фрукты, орехи", "1 284", "#ECF5D3", "tomato", wide=True)
    + _tile("Молочные продукты, яйца", "976", "#ECF5D3", "milk")
    + _tile("Сыр", "512", "#ECF5D3", "cheese")
    + _tile("Птица, мясо", "438", "#ECF5D3", "meat")
    + _tile("Рыба, икра, морепродукты", "301", "#ECF5D3", "pack") +
    "</div>"
    '<h2 class="grp-h">Каждый день</h2><div class="tgrid">'
    + _tile("Хлеб и выпечка", "264", "#FFECB2", "bread", wide=True)
    + _tile("Бакалея", "1 902", "#FFECB2", "pack")
    + _tile("Замороженные продукты", "588", "#FFECB2", "pack") +
    "</div>"
    '<h2 class="grp-h">К чаю и перекус</h2><div class="tgrid">'
    + _tile("Сладости", "1 340", "#FFF6ED", "cookie", wide=True)
    + _tile("Вода, соки, напитки", "812", "#FFF6ED", "bottle") +
    "</div>")

FILES["catalog/tiles.html"] = page(
    "Каталог", "Плитки разделов", "Группы-«прилавки»: один пастельный цвет на группу, первая плитка широкая",
    f'<div class="ds-frame pad" style="width:393px">{TILES_BODY}</div>'
    '<p class="ds-note" style="width:393px">Ряды фиксированной высоты 114px, сетка 3 колонки, '
    'широкая плитка занимает 2. Число товаров прижато к низу — общая базовая линия. '
    'Картинка — правый нижний угол, mix-blend-mode: multiply.</p>')

HEADER_ROOT = (
    '<div id="top" style="position:static">'
    '<div class="srch"><svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/>'
    '<path d="M16.5 16.5 21 21"/></svg>'
    '<input id="q" type="text" placeholder="Найти товар…"></div></div>')

HEADER_CAT = (
    '<div id="top" class="stuck" style="position:static">'
    '<div class="cat-head"><button id="back" type="button">‹</button>'
    '<h1 id="cat-title">Молочные продукты, яйца</h1></div>'
    '<div class="srch"><svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/>'
    '<path d="M16.5 16.5 21 21"/></svg>'
    '<input id="q" type="text" value="молоко"><button id="q-clear" type="button">✕</button></div>'
    '<div class="chips">'
    '<button type="button" class="chip">Все</button>'
    '<button type="button" class="chip on">Молоко</button>'
    '<button type="button" class="chip">Сыр творожный</button>'
    '<button type="button" class="chip">Яйцо</button>'
    '<button type="button" class="chip">Сливки</button></div>'
    '<div class="toolbar"><button class="sort-btn" type="button">' + ICON_SORT +
    '<span>Сортировка · 2</span></button>'
    '<label class="chk"><input type="checkbox" checked><span>В наличии</span></label></div></div>')

FILES["catalog/header.html"] = page(
    "Каталог", "Шапка", "Корневой экран — только поиск; внутри раздела — назад, чипы подкатегорий и фильтры",
    '<div class="ds-sec">Корень каталога</div>'
    f'<div class="ds-frame" style="width:393px">{HEADER_ROOT}</div>'
    '<div class="ds-sec">Внутри раздела, состояние stuck</div>'
    f'<div class="ds-frame" style="width:393px">{HEADER_CAT}</div>'
    '<p class="ds-note" style="max-width:393px">Шапка липкая; волосок снизу проявляется только когда '
    'под неё что-то уехало. Правый край ленты чипов растворяется маской — намёк на горизонтальный скролл.</p>')

FILES["catalog/toolbar.html"] = page(
    "Каталог", "Чипы, сортировка, «в наличии»", "Состояния управляющих элементов ленты",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">Чипы подкатегорий</div>'
    '<div class="ds-row"><button class="chip" type="button">Все</button>'
    '<button class="chip on" type="button">Молоко</button>'
    '<button class="chip" type="button">Очень длинное название подкатегории</button></div>'
    '<div class="ds-sec">Кнопка сортировки</div>'
    '<div class="ds-col">'
    '<button class="sort-btn" type="button">' + ICON_SORT + '<span>Выгода</span></button>'
    '<button class="sort-btn" type="button">' + ICON_SORT + '<span>Сортировка · 3</span></button></div>'
    '<p class="ds-note">Один критерий — его название; несколько — счётчик.</p>'
    '<div class="ds-sec">«В наличии»</div>'
    '<div class="ds-row"><label class="chk"><input type="checkbox"><span>В наличии</span></label>'
    '<label class="chk"><input type="checkbox" checked><span>В наличии</span></label></div>'
    '<div class="ds-sec">Легенда скидок</div>'
    '<p class="legend">Только скидки, подтверждённые историей цен · 128 фейковых скрыто</p>'
    "</div>")

# ---------------------------------------------------------------- 3. Товар

FILES["product/card.html"] = page(
    "Товар", "Карточка в ленте", "Сетка 2 колонки: обычная, со скидкой, в списке, нет в наличии",
    f'<div class="ds-frame pad" style="width:393px">{grid(P_MILK, P_CHEESE, P_COOKIE, P_OIL)}</div>'
    '<p class="ds-note" style="max-width:393px">Карточка без рамки — разделение сеткой и отступами. '
    'Колонка на всю высоту строки, кнопка всегда внизу, поэтому цены и кнопки соседей стоят на одной линии. '
    'У «нет в наличии» гасится само фото, а не сердечко с меткой.</p>')

FILES["product/badges.html"] = page(
    "Товар", "Бейджи и оценка состава", "Выгода, честность скидки, флаги состава, Е-добавки",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">Выгода</div><div class="ds-row">'
    '<span class="badge good">−24%</span><span class="badge small">−8%</span>'
    '<span class="badge fake">цена как обычно</span></div>'
    '<p class="ds-note">Красный — скидка подтверждена историей (rel ≤ −5%). Тёмный — есть, но слабая. '
    'Охряный — ярлык магазина без реального снижения.</p>'
    '<div class="ds-sec">Оценка состава — угол на фото</div><div class="ds-row">'
    '<span class="s-abs good" style="position:static">82</span>'
    '<span class="s-abs mid" style="position:static">51</span>'
    '<span class="s-abs bad" style="position:static">24</span></div>'
    '<p class="ds-note">good ≥ 67, mid ≥ 34, bad — ниже. Абсолютная шкала 0–100.</p>'
    '<div class="ds-sec">Флаги состава</div><div class="e-list">'
    '<span class="badge flag">сахар в первых 3 ингредиентах</span>'
    '<span class="badge flag">пальмовое масло</span>'
    '<span class="badge flag">усилители вкуса</span>'
    '<span class="badge flag">подсластители</span></div>'
    '<div class="ds-sec">Е-добавки по классам вредности</div><div class="e-list">'
    '<span class="e h0">Е300 · безопасная</span><span class="e h1">Е322 · нейтральная</span>'
    '<span class="e h2">Е471 · сомнительная</span><span class="e h3">Е621 · нежелательная</span>'
    '<span class="e more-e">ещё 4</span></div>'
    '<p class="hint" style="margin:-4px 0 12px">Сомнительных и нежелательных добавок: 2 из 10</p>'
    '<div class="ds-sec">Отсутствие товара</div><div class="ds-row">'
    '<span class="oos-abs" style="position:static">нет в наличии</span></div>'
    '<div class="oos-banner" style="margin-top:10px">' + ICON_WARN +
    '<span>Сейчас нет в магазине — можно оставить в списке на потом</span></div>'
    "</div>")

HEART_CSS = """
/* «грязный» фон — на нём видно, зачем сердечку световой ореол */
.ds-busy .ph{background:linear-gradient(135deg,#8FA9C4 0 40%,#E8DCC8 40% 70%,#6E7F63 70%)}
.ds-busy .ph svg{opacity:0}
.ds-pin{position:relative;width:120px;height:120px;flex:0 0 auto}
"""

HEART_OFF = '<button type="button" class="heart">♡</button>'
HEART_ON = '<button type="button" class="heart on">♥</button>'

FILES["product/heart-button.html"] = page(
    "Товар", "Кнопка ♡ «в любимое»", "Глиф на фото и в подвале шторки, два состояния",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">На фото карточки — правый верхний угол</div>'
    '<div class="ds-row">'
    f'<div class="ds-pin">{photo("cheese", HEART_OFF)}</div>'
    f'<div class="ds-pin">{photo("cheese", HEART_ON)}</div>'
    "</div>"
    '<div class="ds-sec">На пёстром фото — ореол вместо плашки</div>'
    '<div class="ds-row">'
    f'<div class="ds-pin ds-busy">{photo("cheese", HEART_OFF)}</div>'
    f'<div class="ds-pin ds-busy">{photo("cheese", HEART_ON)}</div>'
    "</div>"
    '<p class="ds-note">Кнопка 44×44 без фона: контраст держит двойная белая тень '
    '(text-shadow 0 0 6px #fff, 0 0 3px #fff). Во включённом состоянии тень снимается — '
    'красный ♥ читается сам.</p>'
    '<div class="ds-sec">В подвале шторки — .fav-btn 48×48</div>'
    '<div class="ds-row">'
    '<button class="fav-btn" type="button">♡</button>'
    '<button class="fav-btn on" type="button">♥</button></div>'
    '<p class="ds-note">Здесь наоборот — квадрат с фоном: выключенный на --chip, включённый '
    'на --danger-soft, чтобы стоять в ряд с кнопкой «В список».</p>'
    '<div class="ds-sec">Цвета</div><div class="sw">'
    '<div style="background:#B9B7B2;color:#FFFFFF"><b>Выключено</b><i>#B9B7B2</i><br>'
    '<i>серее --muted, чтобы не спорить с оценкой состава</i></div>'
    '<div style="background:#EF544A;color:#FFFFFF"><b>Включено</b><i>--danger #EF544A</i><br>'
    '<i>тот же красный, что у бейджа выгоды</i></div></div>'
    '<div class="ds-sec">В карточке ленты</div>'
    + grid(dict(P_TOMATO, fav=True), P_CHEESE) +
    "</div>", extra_css=HEART_CSS)

FILES["product/actions.html"] = page(
    "Товар", "Кнопка «в список» и степпер", "Полная и компактная раскладка, кнопки шторки",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">В ленте — во всю ширину карточки</div>'
    '<div class="ds-row"><span style="flex:1"><button class="add" type="button">+ В список</button></span>'
    '<span style="flex:1"><span class="qty"><button type="button">−</button>'
    '<span class="n">2</span><button type="button">+</button></span></span></div>'
    '<div class="ds-sec">Компактно — строка списка покупок</div>'
    '<div class="ds-row"><span class="qty compact"><button type="button">+</button></span>'
    '<span class="qty compact"><button type="button">−</button><span class="n">3</span>'
    '<button type="button">+</button></span></div>'
    '<div class="ds-sec">Подвал шторки товара</div>'
    '<div class="card-foot" style="border-radius:12px;border:1px solid var(--line)">'
    '<button class="fav-btn" type="button">♡</button>'
    '<button class="cta" type="button">' + ICON_CART + '<span>В список</span></button></div>'
    '<div class="card-foot" style="border-radius:12px;border:1px solid var(--line);margin-top:8px">'
    '<button class="fav-btn on" type="button">♥</button>'
    '<span class="qty compact" style="min-width:120px"><button type="button">−</button>'
    '<span class="n">2</span><button type="button">+</button></span>'
    '<button class="cta in" type="button">В списке · 897,80 ₽</button></div>'
    '<div class="ds-sec">Прочие кнопки</div><div class="ds-col">'
    '<button class="rowbtn" type="button">' + ICON_EYE + '<span>Скрыть товар</span></button>'
    '<button class="rowbtn" type="button">' + ICON_EYE + '<span>Скрыть все товары бренда «Ламбер»</span></button>'
    '<button class="ghost wide" type="button" style="margin-top:0">Очистить список</button>'
    '<button class="ghost wide danger" type="button" style="margin-top:0">Точно очистить?</button></div>'
    "</div>")

# ---------------------------------------------------------------- 4. Шторки

SPARK = ('<div class="blk"><div class="spark-h"><span class="sec-h" style="margin:0">Цена за 34 дн.</span>'
         '<span class="rng">419,00 – 589,00 ₽</span></div>'
         '<svg class="spark" viewBox="0 0 300 60">'
         '<polyline points="6,14 30,15 54,12 78,20 102,19 126,32 150,31 174,30 198,44 222,43 246,45 270,46 294,46" '
         'fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
         '<circle cx="294" cy="46" r="3.5" fill="var(--accent)"/></svg></div>')

SIM = ('<div class="sim">'
       + "".join(f'<div class="s-card">{photo(m, f"<span class=\'s-abs {c}\'>{s}</span>")}'
                 f'<div class="st">{t}</div><div class="sp">{p} ₽{o}</div></div>'
                 for m, c, s, t, p, o in [
                     ("cheese", "good", 74, "Сыр Российский Стародуб 50%, 250 г", "199,00",
                      '<span class="old">239,00 ₽</span>'),
                     ("cheese", "mid", 58, "Сыр Голландский Брест-Литовск, 200 г", "179,00", ""),
                     ("milk", "good", 81, "Сыр творожный Hochland, 220 г", "159,00", ""),
                     ("pack", "bad", 31, "Продукт сырный плавленый, 400 г", "119,00", ""),
                 ])
       + "</div>")

SHEET_BODY = (
    '<div class="handle-row"><div class="handle"></div><button class="dots" type="button">✕</button></div>'
    '<div id="card-body" style="overflow:visible">'
    + photo("cheese", "", "c-photo") +
    '<h2>Сыр Ламбер 50%, 460 г</h2>'
    '<div class="c-sub">Lamber · Россия · Сыр твёрдый</div>'
    '<div class="price-row"><span class="price-now sale">449,00 ₽</span>'
    '<span class="price-old">589,00 ₽</span><span class="badge good">−24%</span></div>'
    '<div class="blk score-big"><div class="top"><span class="n c-good">71</span>'
    '<span class="track"><i class="fill s-good" style="display:block;width:71%"></i></span></div>'
    '<div class="hint" style="margin-top:10px">Оценка состава · лучше 84% товаров в категории</div></div>'
    '<div class="e-list"><span class="badge flag">пальмовое масло</span></div>'
    '<div class="e-list"><span class="e h0">Е300 · безопасная</span>'
    '<span class="e h1">Е322 · нейтральная</span><span class="e h2">Е471 · сомнительная</span>'
    '<span class="e more-e">ещё 3</span></div>'
    '<p class="hint" style="margin:-4px 0 12px">Сомнительных и нежелательных добавок: 1 из 6</p>'
    + SPARK +
    '<div class="kvs"><div class="kv">Цена за кг<b>976,10 ₽</b></div>'
    '<div class="kv">Обычная цена<b>589,00 ₽</b></div>'
    '<div class="kv wide">КБЖУ на 100 г<b>377 ккал · Б 26 · Ж 30 · У 0,1</b></div>'
    '<div class="kv wide">Скидка действует до<b>19 августа 2026</b></div></div>'
    '<div class="blk comp"><b>Состав:</b> <span class="txt clip">молоко нормализованное, '
    'закваска молочнокислых культур, молокосвёртывающий ферментный препарат микробного происхождения, '
    'соль поваренная пищевая, уплотнитель кальция хлорид, консервант калия нитрат, '
    'краситель аннато</span>'
    '<button class="more" type="button">Показать полностью</button></div>'
    '<div class="sec-h">Похожие в «Сыр твёрдый» — качество за рубль</div>'
    + SIM +
    '<div class="sec-h">Меньше видеть</div>'
    '<button class="rowbtn" type="button">' + ICON_EYE + '<span>Скрыть товар</span></button>'
    '<button class="rowbtn" type="button">' + ICON_EYE +
    '<span>Скрыть все товары бренда «Lamber»</span></button>'
    "</div>"
    '<div class="card-foot"><button class="fav-btn" type="button">♡</button>'
    '<button class="cta" type="button">' + ICON_CART + '<span>В список</span></button></div>')

FILES["sheets/product.html"] = page(
    "Шторки", "Шторка товара", "Фото, оценка состава, история цены, КБЖУ, состав, похожие, «меньше видеть»",
    f'<div class="ds-frame" style="width:393px"><div id="card" style="max-height:none">{SHEET_BODY}</div></div>')

SORT_ROWS = [("Выгода", "скидка от обычной цены", True),
             ("Оценка покупателей", "с поправкой на число отзывов", False),
             ("Чистота состава", "меньше добавок и флагов", True),
             ("Качество за рубль", "оценка состава на рубль", False),
             ("Дешевле за кг", "цена за килограмм или литр", False),
             ("Дешевле", "цена за упаковку", False)]

FILES["sheets/sort.html"] = page(
    "Шторки", "Шторка сортировки", "Комбинатор: несколько критериев усредняются по рангу",
    '<div class="ds-frame" style="width:393px"><div id="sort-sheet" style="animation:none">'
    '<div class="handle-row"><div class="handle"></div><button class="dots" type="button">✕</button></div>'
    '<div class="sheet-body"><h2>Сортировка</h2>'
    '<p class="hint" style="margin-bottom:12px">Можно включить несколько — товары встанут по среднему '
    'месту в каждом из выбранных рейтингов.</p><div>'
    + "".join(f'<label class="srow"><input type="checkbox"{" checked" if on else ""}>'
              f'<span class="sr-t">{t}<i>{d}</i></span><span class="sr-box"></span></label>'
              for t, d, on in SORT_ROWS)
    + "</div></div></div></div>"
    '<p class="ds-note" style="max-width:393px">Хотя бы один критерий всегда остаётся включённым — '
    'иначе порядок ленты становится случайным.</p>')

# ---------------------------------------------------------------- 5. Список

def citem(t, sum_, mock, n=1, oos=False, gone=False):
    if gone:
        return (f'<div class="citem gone">{photo(mock)}'
                f'<div><div class="ti">{t}</div><div class="crow">'
                f'<span class="undo-t">убрали из списка</span>'
                f'<button class="undo" type="button">Вернуть</button></div></div>'
                f'<i class="undo-bar" style="animation:none;width:62%"></i></div>')
    return (f'<div class="citem{"" if not oos else " oos"}">{photo(mock)}'
            f'<div><div class="ti">{t}</div><div class="crow">'
            f'<span class="act-c"><span class="qty compact"><button type="button">−</button>'
            f'<span class="n">{n}</span><button type="button">+</button></span></span>'
            f'<span class="cright"><span class="sum">{sum_} ₽</span>'
            + ('<span class="oos">нет в наличии</span>' if oos else "")
            + "</span></div></div></div>")


CART_ITEMS = (citem("Сыр Ламбер 50%, 460 г", "898,00", "cheese", 2)
              + citem("Молоко Домик в деревне отборное 3,7%, 930 мл", "296,70", "milk", 3)
              + citem("Масло подсолнечное Слобода рафинированное, 1 л", "139,00", "bottle", 1, oos=True)
              + citem("Печенье Юбилейное витаминизированное, 313 г", "", "cookie", gone=True))

FILES["list/budget.html"] = page(
    "Список", "Бюджет", "Три состояния полосы: в рамках, близко к пределу, превышение",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">Бюджет не задан</div>'
    '<div class="budget-card"><div class="budget-row">'
    '<label class="bl">Бюджет <span class="bfield"><input id="budget" type="number" placeholder="—"></span></label>'
    '<div class="total">Итого 1 333,70 ₽</div></div>'
    '<p class="hint" style="margin-top:10px">Задайте бюджет, чтобы видеть прогресс</p></div>'
    '<div class="ds-sec">В рамках</div>'
    '<div class="budget-card"><div class="budget-row">'
    '<label class="bl">Бюджет <span class="bfield"><input type="number" value="2500"></span></label>'
    '<div class="total">Итого 1 333,70 ₽</div></div>'
    '<div class="bar-track"><div class="bar-fill" style="width:53%"></div></div>'
    '<p class="hint">53% бюджета · остаток 1 166,30 ₽</p></div>'
    '<div class="ds-sec">Почти предел — от 85%</div>'
    '<div class="budget-card"><div class="budget-row">'
    '<label class="bl">Бюджет <span class="bfield"><input type="number" value="1500"></span></label>'
    '<div class="total">Итого 1 333,70 ₽</div></div>'
    '<div class="bar-track"><div class="bar-fill warn" style="width:89%"></div></div>'
    '<p class="hint">89% бюджета · остаток 166,30 ₽</p></div>'
    '<div class="ds-sec">Превышение</div>'
    '<div class="budget-card"><div class="budget-row">'
    '<label class="bl">Бюджет <span class="bfield"><input type="number" value="1000"></span></label>'
    '<div class="total over">Итого 1 333,70 ₽</div></div>'
    '<div class="bar-track"><div class="bar-fill over" style="width:100%"></div></div>'
    '<p class="hint over">Превышение на 333,70 ₽</p></div>'
    "</div>")

FILES["list/items.html"] = page(
    "Список", "Строки списка покупок", "Обычная, нет в наличии, «убрали» с окном возврата на 5 с",
    f'<div class="ds-frame pad" style="width:393px">{CART_ITEMS}</div>'
    '<p class="ds-note" style="max-width:393px">Убрали последнюю штуку — строка не исчезает мгновенно, '
    'а висит приглушённой с кнопкой «Вернуть»; полоска внизу отсчитывает 5 секунд. '
    'Промах по «−» перестал быть необратимым.</p>')

# ---------------------------------------------------------------- 6. Моё

FILES["prefs/blacklist.html"] = page(
    "Моё", "Скрытое и «о данных»", "Аккордеоны чёрных списков, инфо-карточка",
    '<div class="ds-frame pad" style="width:393px">'
    '<button class="acc" type="button" aria-expanded="true"><span>Скрытые бренды (3)</span>'
    '<span class="acc-x">Скрыть</span></button>'
    '<div class="acc-body">'
    '<span class="bl-chip">Каждый день<button type="button">✕</button></span>'
    '<span class="bl-chip">Красная цена<button type="button">✕</button></span>'
    '<span class="bl-chip">Слобода<button type="button">✕</button></span>'
    '<button class="mini-clear" type="button">вернуть все</button></div>'
    '<button class="acc" type="button" aria-expanded="false"><span>Скрытые товары (1)</span>'
    '<span class="acc-x">Показать</span></button>'
    '<div class="info-card"><h3>О данных</h3>'
    '<p class="hint">Данные от 13 августа 2026 · 24 318 товаров · история 34 дн.</p>'
    '<p class="hint">Цены и состав — из каталога АШАН Симферополь. «Выгода» считается сравнением '
    'с типичной ценой товара по истории, поэтому ярлык скидки на ценнике сюда не попадает '
    'автоматически. Оценка состава — по Е-добавкам, флагам и длине состава.</p></div>'
    "</div>")

# ---------------------------------------------------------------- 7. Навигация

def tabbar(active="catalog", badge=None):
    items = [("catalog", "Каталог", '<svg viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="7" height="7" rx="2"/>'
              '<rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/>'
              '<rect x="13.5" y="13.5" width="7" height="7" rx="2"/></svg>'),
             ("cart", "Список", ICON_CART),
             ("fav", "Любимое", ICON_HEART),
             ("prefs", "Моё", '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.4"/>'
              '<path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>')]
    out = []
    for key, label, icon in items:
        b = f'<b id="cart-n">{badge}</b>' if key == "cart" and badge else ""
        cls = ' class="active"' if key == active else ""
        out.append(f'<button type="button"{cls}>{icon}<span>{label}</span>{b}</button>')
    return '<nav id="tabs">' + "".join(out) + "</nav>"


FILES["nav/tabbar.html"] = page(
    "Навигация", "Нижняя навигация", "Четыре вкладки, счётчик списка, активное состояние",
    '<div class="ds-frame" style="width:393px">' + tabbar("catalog", 6) + "</div>"
    '<div class="ds-frame" style="width:393px;margin-top:12px">' + tabbar("cart", 6) + "</div>"
    '<div class="ds-frame" style="width:393px;margin-top:12px">' + tabbar("fav") + "</div>")

FILES["nav/overlays.html"] = page(
    "Навигация", "Тост и «наверх»", "Единственные два элемента с тенью",
    '<div class="ds-frame pad" style="width:393px;background:#F5F4F2">'
    '<div class="ds-sec">Тост</div><div class="ds-col" style="justify-items:center">'
    '<div class="toast" style="animation:none">Добавлено в список</div>'
    '<div class="toast" style="animation:none">Бренд «Слобода» скрыт</div></div>'
    '<div class="ds-sec">Кнопка «наверх»</div>'
    '<button id="to-top" class="on" type="button">' + ICON_UP + "</button>"
    '<p class="ds-note">Появляется после 800 px прокрутки, слева над таб-баром.</p>'
    "</div>")

# ---------------------------------------------------------------- 8. Состояния

SKELETON = ('<div class="grid">' + '<div class="sk"><i class="b"></i><i class="l1"></i>'
            '<i class="l3"></i><i class="l2"></i></div>' * 4 + "</div>")

FILES["states/loading-empty.html"] = page(
    "Состояния", "Загрузка и пустые экраны", "Скелетоны ленты и четыре пустых состояния",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">Скелетоны первой загрузки</div>' + SKELETON +
    '<div class="ds-sec">Ничего не нашлось</div>'
    '<div class="empty">' + ICON_SEARCH + '<h3>Ничего не нашлось</h3>'
    '<p>Проверьте написание или уберите фильтры</p>'
    '<button class="ghost" type="button">Сбросить фильтры</button></div>'
    '<div class="ds-sec">Список пуст</div>'
    '<div class="empty">' + ICON_CART + '<h3>Список пуст</h3>'
    '<p>Добавляйте товары кнопкой «+ В список»</p>'
    '<button class="ghost" type="button">В каталог</button></div>'
    '<div class="ds-sec">Нет любимого</div>'
    '<div class="empty">' + ICON_HEART + '<h3>Пока нет любимого</h3>'
    '<p>Отмечайте товары ♡ на карточке</p></div>'
    '<div class="ds-sec">Нет подтверждённых скидок</div>'
    '<div class="empty"><h3>Сейчас нет проверенных скидок</h3>'
    '<p>Список обновляется вместе с ценами каждый день</p></div>'
    "</div>")

# ---------------------------------------------------------------- 9. Экраны

def screen(inner, active, badge=None):
    return ('<div class="ds-phone"><div id="app"><div class="ds-scroll">'
            + inner + "</div>" + tabbar(active, badge) + "</div></div>")


FILES["screens/catalog.html"] = page(
    "Экраны", "Каталог — корень", "393×873, плитки разделов группами",
    screen(HEADER_ROOT + f'<main><div class="tiles">{TILES_BODY}</div></main>', "catalog", 6))

FILES["screens/category.html"] = page(
    "Экраны", "Лента раздела", "Шапка с чипами и фильтрами, сетка карточек",
    screen(HEADER_CAT + "<main>" + grid(P_MILK, P_CHEESE, P_TOMATO, P_COOKIE, P_MEAT, P_OIL) + "</main>",
           "catalog", 6))

FILES["screens/cart.html"] = page(
    "Экраны", "Список покупок", "Бюджет с прогрессом и строки товаров",
    screen('<section class="page"><h2>Список покупок</h2>'
           '<div class="budget-card"><div class="budget-row">'
           '<label class="bl">Бюджет <span class="bfield"><input type="number" value="1500"></span></label>'
           '<div class="total">Итого 1 333,70 ₽</div></div>'
           '<div class="bar-track"><div class="bar-fill warn" style="width:89%"></div></div>'
           '<p class="hint">89% бюджета · остаток 166,30 ₽</p></div>'
           + CART_ITEMS +
           '<button class="ghost wide" type="button">Очистить список</button></section>', "cart", 6))

FILES["screens/fav.html"] = page(
    "Экраны", "Любимое", "Группировка по разделам каталога",
    screen('<section class="page"><div class="head-row"><h2>Любимое (5)</h2>'
           '<button class="mini-clear" type="button">очистить всё</button></div>'
           '<h3 class="grp-h fav-grp" style="margin-top:4px">Молочные продукты, яйца</h3>'
           + grid(dict(P_MILK, fav=True), dict(P_CHEESE, fav=True))
           + '<h3 class="grp-h fav-grp">Овощи, фрукты, орехи</h3>'
           + grid(P_TOMATO) + "</section>", "fav", 6))

FILES["screens/prefs.html"] = page(
    "Экраны", "Моё", "Чёрные списки и происхождение данных",
    screen('<section class="page"><h2>Моё</h2>'
           '<button class="acc" type="button" aria-expanded="true"><span>Скрытые бренды (3)</span>'
           '<span class="acc-x">Скрыть</span></button>'
           '<div class="acc-body">'
           '<span class="bl-chip">Каждый день<button type="button">✕</button></span>'
           '<span class="bl-chip">Красная цена<button type="button">✕</button></span>'
           '<span class="bl-chip">Слобода<button type="button">✕</button></span>'
           '<button class="mini-clear" type="button">вернуть все</button></div>'
           '<button class="acc" type="button" aria-expanded="false"><span>Скрытые товары (1)</span>'
           '<span class="acc-x">Показать</span></button>'
           '<div class="info-card"><h3>О данных</h3>'
           '<p class="hint">Данные от 13 августа 2026 · 24 318 товаров · история 34 дн.</p>'
           '<p class="hint">Цены и состав — из каталога АШАН Симферополь. «Выгода» считается сравнением '
           'с типичной ценой товара по истории, поэтому ярлык скидки на ценнике сюда не попадает '
           'автоматически. Оценка состава — по Е-добавкам, флагам и длине состава.</p></div>'
           "</section>", "prefs"))

FILES["screens/product-sheet.html"] = page(
    "Экраны", "Шторка товара поверх ленты", "Затемнение + лист снизу",
    '<div class="ds-phone">'
    '<div id="app" style="filter:blur(0)">' + HEADER_CAT + "<main>" + grid(P_MILK, P_CHEESE) + "</main></div>"
    '<div style="position:absolute;inset:0;background:rgba(33,32,31,.45)"></div>'
    '<div style="position:absolute;left:0;right:0;bottom:0;max-height:92%;background:#fff;'
    'border-radius:16px 16px 0 0;overflow:hidden;display:flex;flex-direction:column">'
    + SHEET_BODY.replace('overflow:visible', 'overflow-y:auto') +
    "</div></div>")


# ------------------------------------------------------------- 10. Иконка ♥

HEART_D = "M12 20s-7-4.6-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 7-2.8c0 4.6-7 14.8-7 14.8Z"

# отдельный файл-ассет: обводка вшита в атрибуты, чтобы SVG жил вне стилей приложения
HEART_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"\n'
             '     fill="none" stroke="currentColor" stroke-width="1.8"\n'
             '     stroke-linecap="round" stroke-linejoin="round">\n'
             f'  <path d="{HEART_D}"/>\n'
             "</svg>\n")

ICON_CSS = """
.ic-demo{display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap}
.ic-demo figure{margin:0;text-align:center}
.ic-demo svg{fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;display:block}
.ic-demo figcaption{font-size:11px;color:#8A8880;margin-top:8px;font-variant-numeric:tabular-nums}
.ic-grid{background:
  repeating-linear-gradient(0deg,#EBEAE7 0 1px,transparent 1px 10px),
  repeating-linear-gradient(90deg,#EBEAE7 0 1px,transparent 1px 10px);
  background-size:10px 10px;border:1px solid var(--line);border-radius:8px}
.ic-code{background:var(--sunken);border-radius:8px;padding:12px;font:11px/1.5 ui-monospace,
  SFMono-Regular,Consolas,monospace;color:var(--ink2);overflow-x:auto;white-space:pre-wrap;
  word-break:break-all;margin:0}
"""


def heart(size, color, sw):
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" '
            f'style="color:{color};stroke-width:{sw}"><path d="{HEART_D}"/></svg>')


FILES["icons/heart.html"] = page(
    "Иконки", "Сердце", "Контурная иконка: таб «Любимое» и пустое состояние. Файл — icons/heart.svg",
    '<div class="ds-frame pad" style="width:393px">'
    '<div class="ds-sec">Размеры в интерфейсе</div>'
    '<div class="ic-demo">'
    f'<figure>{heart(22, "#999999", 1.8)}<figcaption>22 · таб</figcaption></figure>'
    f'<figure>{heart(22, "#212120", 1.8)}<figcaption>22 · таб активен</figcaption></figure>'
    f'<figure>{heart(44, "#999999", 1.5)}<figcaption>44 · пусто</figcaption></figure>'
    f'<figure class="ic-grid">{heart(120, "#212120", 1.8)}'
    '<figcaption>120 · сетка 10px</figcaption></figure>'
    "</div>"
    '<p class="ds-note">viewBox 0 0 24 24, fill: none, stroke: currentColor, скругления на концах '
    'и стыках. В таб-баре обводка 1.8 и цвет наследуется от состояния вкладки '
    '(--muted → --ink), в пустом состоянии — 1.5 и --muted.</p>'
    '<div class="ds-sec">В таб-баре</div>'
    + tabbar("fav") +
    '<div class="ds-sec">В пустом состоянии</div>'
    '<div class="empty">' + ICON_HEART + '<h3>Пока нет любимого</h3>'
    '<p>Отмечайте товары ♡ на карточке</p></div>'
    '<div class="ds-sec">Геометрия</div>'
    f'<pre class="ic-code">&lt;path d="{HEART_D}"/&gt;</pre>'
    '<p class="ds-note">Не путать с глифом ♡/♥ — им нарисована кнопка «в любимое» '
    'на фото товара, это отдельная карточка.</p>'
    "</div>", extra_css=ICON_CSS)

ASSETS = {"icons/heart.svg": HEART_SVG}

# ------------------------------------------------------------------- запись

README = """# Дизайн-кит «Корзинка» для Claude Design

Сгенерирован `build_design_kit.py` из живых `web/style.css` и шаблонов `web/app.js`.
**Руками не править** — правки затрутся следующей сборкой; менять надо генератор
или сам `web/`.

Каждый файл — самодостаточная страница: стили вшиты inline, данные захардкожены,
фотографии заменены inline-SVG-муляжами. Ни одного сетевого запроса.
Первая строка — маркер `<!-- @dsCard group="…" -->`, по нему Claude Design строит
индекс карточек.

## Как залить

Закинуть содержимое папки `design/` целиком в проект Claude Design
(тип проекта — design system). Структура папок сохраняет группировку карточек.

## Группы

| папка | группа в панели |
|---|---|
| `tokens/` | Токены — палитра, шрифтовая шкала, радиусы, отступы |
| `catalog/` | Каталог — плитки разделов, шапка, фильтры |
| `product/` | Товар — карточка ленты, бейджи, кнопки |
| `sheets/` | Шторки — товар, сортировка |
| `list/` | Список — бюджет, строки |
| `prefs/` | Моё — чёрные списки |
| `icons/` | Иконки — `heart.html` (карточка) и `heart.svg` (сам ассет) |
| `nav/` | Навигация — таб-бар, тост, «наверх» |
| `states/` | Состояния — скелетоны, пустые экраны |
| `screens/` | Экраны — 6 полных экранов в рамке 393×873 |

## Пересборка

    python build_design_kit.py

Запускать после любой правки `web/style.css`, иначе кит разойдётся с приложением.
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, content in {**FILES, **ASSETS}.items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    (OUT / "README.md").write_text(README, encoding="utf-8")
    print(f"{len(FILES)} card(s) + {len(ASSETS)} asset(s) -> {OUT}")
    for rel in sorted({**FILES, **ASSETS}):
        print("  ", rel)


if __name__ == "__main__":
    main()
