/* Корзинка — помощник покупок. Данные: web/data/* из build_site_data.py */
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const LS = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { localStorage.setItem(k, JSON.stringify(v)); },
};
let META = null, ROWS = [], BYCODE = new Map();
let cart = LS.get('cart', {});          // code -> qty
let blP = new Set(LS.get('blP', []));   // чёрный список товаров
let blB = new Set(LS.get('blB', []));   // чёрный список брендов
let fav = new Set(LS.get('fav', []));
let tab = 'catalog', cat = '', sub = '', onlyDeals = false, curCode = null;
const shardCache = {};

const fmt = n => n == null || isNaN(n) ? '—' : (Math.round(n * 100) / 100).toLocaleString('ru-RU');
/* «2026-08-12» → «12 августа»: ISO-дата в интерфейсе не читается */
const MON = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
function fmtDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
  if (!m) return s || '';
  return `${+m[3]} ${MON[+m[2] - 1]}`;
}
const esc = s => (s ?? '').toString().replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const qty = c => cart[String(c)] || 0;
const isFav = c => fav.has(String(c));

/* иконки-заглушки без сетевых запросов */
const ICON_BOX = '<svg viewBox="0 0 24 24"><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5v-9Z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/></svg>';
const ICON_SEARCH = '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 21 21"/></svg>';
const ICON_CART = '<svg viewBox="0 0 24 24"><path d="M4 8h16l-1.6 11H5.6L4 8ZM9 8V5a3 3 0 0 1 6 0v3"/></svg>';
const ICON_HEART = '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.6-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 7-2.8c0 4.6-7 14.8-7 14.8Z"/></svg>';
const ICON_EYE = '<svg viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/><path d="M4 20 20 4"/></svg>';
const ICON_WARN = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.4v.2"/></svg>';

/* пастельные фоны плиток разделов (палитра Лавки) */
const TILE_BG = ['#E1F8FA', '#FFECB2', '#ECF5D3', '#FEF0D5', '#FFF6ED',
  '#E7EEFB', '#F3E8FB', '#FBE4EC', '#E4F6E9'];
const DEAL_BG = '#FDE9E5';

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.hidden = true, 1800);
}

async function boot() {
  skeletons();
  META = await (await fetch('data/meta.json')).json();
  const idx = await (await fetch('data/index.json')).json();
  const cols = idx.cols;
  ROWS = idx.rows.map(a => { const o = {}; cols.forEach((c, i) => o[c] = a[i]); return o; });
  ROWS.forEach(r => BYCODE.set(String(r.c), r));
  buildTiles();
  renderHead();
  $('#meta-info').textContent = `Данные от ${fmtDate(META.date)} · ${fmt(META.products)} товаров · история ${META.days} дн.`;
  render();
  updateCartBadge();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
}

function skeletons() {
  $('#list').innerHTML = Array(6).fill(
    '<div class="sk"><i class="b"></i><i class="l1"></i><i class="l3"></i><i class="l2"></i></div>').join('');
}

/* ---------- экран плиток разделов ---------- */
let TILES = [];
/* по каждому разделу: сколько товаров и фото самого «популярного» — для картинки плитки */
function buildTiles() {
  const by = new Map();
  for (const r of ROWS) {
    if (!r.k1) continue;
    let t = by.get(r.k1);
    if (!t) by.set(r.k1, t = { name: r.k1, n: 0, im: '', rc: -1 });
    t.n++;
    const rc = r.rc || 0;
    if (r.im && r.st && rc > t.rc) { t.rc = rc; t.im = r.im; }
  }
  TILES = [...by.values()].sort((a, b) => b.n - a.n);
  // крупные разделы занимают две клетки — граница по медиане числа товаров
  const big = TILES.length ? TILES[Math.max(0, Math.floor(TILES.length / 3) - 1)].n : 0;
  TILES.forEach((t, i) => { t.wide = t.n >= big && i < Math.ceil(TILES.length / 3); t.bg = TILE_BG[i % TILE_BG.length]; });
}

function tileHTML(t) {
  const img = t.im ? `<img class="tim" loading="lazy" src="${esc(t.im)}" alt="" onerror="this.style.display='none'">` : '';
  const attr = t.deals ? 'data-deals="1"' : `data-tile="${esc(t.name)}"`;
  return `<button type="button" class="tile${t.wide ? ' wide' : ''}${t.deals ? ' deals' : ''}" ${attr}
    style="background:${t.bg}"><span class="tt">${esc(t.name)}</span>
    <span class="tn">${fmt(t.n)}</span>${img}</button>`;
}

function renderTiles() {
  const deals = ROWS.filter(r => visible(r) && r.st && isDeal(r));
  const dim = deals.slice().sort((a, b) => (b.rc || 0) - (a.rc || 0)).find(r => r.im);
  const dealTile = tileHTML({ name: 'Скидки', n: deals.length, im: dim ? dim.im : '', wide: true, bg: DEAL_BG, deals: 1 });
  $('#tiles').innerHTML = dealTile + TILES.map(tileHTML).join('');
}

/* шапка: на корневом экране — только поиск, внутри раздела — назад, чипы k2 и сортировка */
function renderHead() {
  const root = isRoot();
  $('#cat-head').hidden = root;
  $('#cats').hidden = root;
  $('#toolbar').hidden = root;
  $('#top').style.top = '0px';
  if (root) return;
  $('#cat-title').textContent = onlyDeals ? 'Скидки' : (cat || 'Поиск');
  const subs = cat ? [...new Set(ROWS.filter(r => r.k1 === cat && r.k2).map(r => r.k2))].sort() : [];
  $('#cats').hidden = !subs.length;
  if (!subs.length) { $('#cats').innerHTML = ''; return; }
  $('#cats').innerHTML = [`<button type="button" class="chip${!sub ? ' on' : ''}" data-sub="">Все</button>`]
    .concat(subs.map(c => `<button type="button" class="chip${sub === c ? ' on' : ''}" data-sub="${esc(c)}">${esc(c)}</button>`)).join('');
  // заголовок и поиск уезжают вверх, чипы подкатегорий и сортировка залипают
  $('#top').style.top = -$('#cats').offsetTop + 'px';
}

const isRoot = () => !cat && !onlyDeals && !$('#q').value.trim();
/* возврат на экран плиток */
function toRoot() {
  cat = ''; sub = ''; onlyDeals = false;
  $('#q').value = ''; $('#q-clear').hidden = true;
  renderHead(); render(); scrollTo(0, 0);
}

/* ---------- выборка ---------- */
function visible(r) { return !blP.has(String(r.c)) && !(r.b && blB.has(r.b)); }
const isDeal = r => r.d > 0 && r.rel != null && r.rel <= -5;

function filterRows() {
  const q = $('#q').value.trim().toLowerCase();
  let rs = ROWS.filter(visible);
  if ($('#stock').checked) rs = rs.filter(r => r.st);
  if (cat) rs = rs.filter(r => r.k1 === cat);
  if (sub) rs = rs.filter(r => r.k2 === sub);
  // «Выгода» — только скидки, подтверждённые историей цен
  if (onlyDeals) rs = rs.filter(isDeal);
  if (q) {
    const terms = q.split(/\s+/);
    rs = rs.filter(r => {
      const hay = (r.t + ' ' + (r.b || '')).toLowerCase();
      return terms.every(t => hay.includes(t));
    });
  }
  const key = $('#sort').value;
  const dir = (key === 's' || key === 'v') ? -1 : 1;
  rs.sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (x - y) * dir;
  });
  return rs;
}

/* ---------- элементы ---------- */
/* заглушка лежит под фото, но показывается только классом .noimg —
   иначе её серый фон торчал по бокам вытянутых картинок */
function photoHTML(r, extra, cls) {
  const ph = `<div class="ph">${ICON_BOX}</div>`;
  // заглушка видна, пока фото грузится (и остаётся, если не загрузилось),
  // но исчезает после load — иначе её серый фон торчал по бокам вытянутых картинок
  const img = r.im ? `<img loading="lazy" src="${esc(r.im)}" alt="">` : '';
  return `<div class="ph-wrap ${cls || ''}">${ph}${img}${extra || ''}</div>`;
}

/* отметка «фото приехало» — снимает серую заглушку под картинкой */
function markPhoto(img) {
  if (!img.complete || !img.naturalWidth) return;
  img.closest('.ph-wrap')?.classList.add('ok');
}
addEventListener('load', e => { if (e.target.tagName === 'IMG') markPhoto(e.target); }, true);
addEventListener('error', e => { if (e.target.tagName === 'IMG') e.target.remove(); }, true);
// картинки из кэша и lazy-загрузка могут завершиться без события в наш адрес —
// фоновый досмотр раз в секунду, пока есть неотмеченные фото
setInterval(() => $$('.ph-wrap:not(.ok) img').forEach(markPhoto), 1000);

// один бейдж на карточку
function dealBadge(r) {
  if (!(r.d > 0)) return '';
  const d = Math.round(r.d);
  if (r.rel != null && r.rel <= -5) return `<span class="badge good">−${d}%</span>`;
  if (r.rel == null || r.rel >= -1) return `<span class="badge fake">цена как обычно</span>`;
  return `<span class="badge small">−${d}%</span>`;
}

function scoreCls(s) { return s >= 67 ? 'good' : s >= 34 ? 'mid' : 'bad'; }

function scoreHTML(r) {
  if (r.s == null) return '';
  const s = Math.max(0, Math.min(100, Math.round(r.s))), k = scoreCls(s);
  return `<span class="score ${k}"><span class="lbl">состав</span>${s}</span>`;
}

/* кнопка «+ В список» превращается в степпер */
function actHTML(code, compact) {
  const n = qty(code);
  if (!n) return compact ? `<span class="qty compact"><button type="button" data-inc="${esc(code)}" aria-label="Добавить">+</button></span>`
    : `<button type="button" class="add" data-inc="${esc(code)}">+ В список</button>`;
  return `<span class="qty${compact ? ' compact' : ''}">
    <button type="button" data-dec="${esc(code)}" aria-label="Убрать">−</button>
    <span class="n">${n}</span>
    <button type="button" data-inc="${esc(code)}" aria-label="Добавить">+</button></span>`;
}

function rateHTML(r) {
  if (!r.r) return '<div class="rate"></div>';
  return `<div class="rate"><span class="st">★</span>${fmt(r.r)}${r.rc ? ` · ${fmt(r.rc)}` : ''}</div>`;
}

function itemHTML(r) {
  const b = dealBadge(r);
  // на карточке либо бейдж выгоды, либо метка отсутствия — вместе они бессмысленны
  const corner = !r.st ? '<span class="oos-abs">нет в наличии</span>'
    : (b ? `<span class="badge-abs">${b}</span>` : '');
  const heart = `<button type="button" class="heart${isFav(r.c) ? ' on' : ''}" data-fav="${esc(r.c)}" aria-label="Любимое">${isFav(r.c) ? '♥' : '♡'}</button>` + corner;
  return `<article class="card${r.st ? '' : ' oos'}" data-c="${esc(r.c)}">
    ${photoHTML(r, heart)}
    ${rateHTML(r)}
    <div class="name">${esc(r.t)}</div>
    <div class="price${r.op && r.op > r.p ? ' sale' : ''}"><span>${fmt(r.p)} ₽</span>${r.op && r.op > r.p ? `<span class="old">${fmt(r.op)} ₽</span>` : ''}</div>
    <div class="ppk">${r.pk ? `${fmt(r.pk)} ₽/${esc(r.un || 'кг')}` : ''}</div>
    <div class="score-row">${scoreHTML(r)}</div>
    <div class="act">${actHTML(r.c)}</div></article>`;
}

function emptyHTML(icon, h, p, btn) {
  return `${icon}<h3>${h}</h3><p>${p}</p>${btn || ''}`;
}

/* ---------- лента ---------- */
let shown = 0, curRows = [];
function render() {
  // корневой экран каталога — плитки разделов вместо ленты товаров
  if (isRoot()) {
    curRows = []; shown = 0;
    $('#tiles').hidden = false;
    $('#list').innerHTML = '';
    $('#empty').hidden = true;
    $('#legend').hidden = true;
    renderTiles();
    return;
  }
  $('#tiles').hidden = true;
  curRows = filterRows();
  shown = Math.min(60, curRows.length);
  $('#list').innerHTML = curRows.slice(0, shown).map(itemHTML).join('');
  const e = $('#empty');
  e.hidden = curRows.length > 0;
  if (!e.hidden) {
    e.innerHTML = onlyDeals
      ? emptyHTML('', 'Сейчас нет проверенных скидок', 'Список обновляется вместе с ценами каждый день')
      : emptyHTML(ICON_SEARCH, 'Ничего не нашлось', 'Проверьте написание или уберите фильтры',
        '<button type="button" class="ghost" id="reset-f">Сбросить фильтры</button>');
  }
  if (onlyDeals) {
    const fake = ROWS.filter(r => visible(r) && r.d > 0 && (r.rel == null || r.rel >= -1)).length;
    $('#legend').hidden = false;
    $('#legend').textContent = 'Только скидки, подтверждённые историей цен'
      + (fake ? ` · ${fmt(fake)} фейковых скрыто` : '');
  } else $('#legend').hidden = true;
}
function more() {
  if (shown >= curRows.length) return;
  const next = curRows.slice(shown, shown + 60);
  shown += next.length;
  $('#list').insertAdjacentHTML('beforeend', next.map(itemHTML).join(''));
}
addEventListener('scroll', () => {
  if (tab !== 'catalog') return;
  // волосок под залипшей шапкой появляется только когда под неё что-то уехало
  $('#top').classList.toggle('stuck', scrollY > 4 && !isRoot());
  if (innerHeight + scrollY > document.body.scrollHeight - 600) more();
});

/* обновить счётчики в уже отрисованном DOM, не перерисовывая ленту */
function syncQty(code) {
  const n = qty(code);
  const upd = (el, compact) => {
    // если степпер уже есть и остаётся — меняем только число, не пересоздавая кнопки
    const num = el.querySelector('.qty .n');
    if (num && n > 0) { num.textContent = n; return; }
    el.innerHTML = actHTML(code, compact);
  };
  $$(`[data-c="${CSS.escape(String(code))}"] .act`).forEach(el => upd(el, false));
  $$(`[data-c="${CSS.escape(String(code))}"] .act-c`).forEach(el => upd(el, true));
  updateCartBadge();
}
function addToCart(code, delta) {
  const k = String(code);
  const n = (cart[k] || 0) + delta;
  if (n <= 0) delete cart[k]; else cart[k] = n;
  LS.set('cart', cart);
  syncQty(k);
  if (tab === 'cart') renderCart();
  if (curCode === k) renderFoot();
}
function toggleFav(code) {
  const k = String(code);
  fav.has(k) ? fav.delete(k) : fav.add(k);
  LS.set('fav', [...fav]);
  $$(`[data-fav="${CSS.escape(k)}"]`).forEach(b => {
    b.classList.toggle('on', fav.has(k)); b.textContent = fav.has(k) ? '♥' : '♡';
  });
  if (curCode === k) renderFoot();
  toast(fav.has(k) ? 'В любимом' : 'Убрано из любимого');
}

/* ---------- карточка товара ---------- */
async function loadDetail(code) {
  const shard = [...String(code)].reduce((s, ch) => s + ch.charCodeAt(0), 0) % META.shards;
  if (!shardCache[shard]) shardCache[shard] = await (await fetch(`data/details/${shard}.json`)).json();
  return shardCache[shard][String(code)] || {};
}

/* график цены. Плоскую историю (2 точки или одна цена) не рисуем:
   получался пустой серый блок с линией по нижнему краю и наехавшей подписью */
function spark(hist) {
  if (!hist || hist.length < 3) return '';
  const ps = hist.map(h => h[1]).filter(p => typeof p === 'number');
  if (ps.length < 3) return '';
  const min = Math.min(...ps), max = Math.max(...ps);
  if (max - min < 0.01) return '';
  const pad = max - min;
  const W = 300, H = 60, T = 8, B = 10;
  const pts = ps.map((p, i) => `${(i / (ps.length - 1) * (W - 12) + 6).toFixed(1)},${(H - B - (p - min) / pad * (H - T - B)).toFixed(1)}`);
  const last = pts.at(-1).split(',');
  return `<div class="blk"><div class="spark-h"><span class="sec-h" style="margin:0">Цена за ${ps.length} дн.</span>
      <span class="rng">${fmt(min)} – ${fmt(max)} ₽</span></div>
    <svg class="spark" viewBox="0 0 ${W} ${H}">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="var(--accent)"/></svg></div>`;
}

function similar(r) {
  return ROWS.filter(x => x.c !== r.c && visible(x) && x.st && x.k2 && x.k2 === r.k2)
    .sort((a, b) => (b.v ?? -1) - (a.v ?? -1)).slice(0, 8);
}

const FLAGS = { sugar_first: 'сахар в начале состава', palm: 'пальмовое масло', flavor_enh: 'усилители вкуса', sweetener: 'подсластители' };
const E_NAMES = { 0: 'безопасная', 1: 'нейтральная', 2: 'сомнительная', 3: 'нежелательная' };

/* Е-добавки: сначала самые нежелательные, длинный хвост прячем под «ещё N»,
   иначе карточка превращалась в стену из полутора десятков одинаковых плашек */
const E_SHOWN = 6;
function eListHTML(d) {
  if (!d.e || !d.e.length) return '';
  const harm = c => (d.eh && d.eh[c]) ?? 0;
  const all = d.e.slice().sort((a, b) => harm(b) - harm(a) || String(a).localeCompare(String(b)));
  const chip = c => `<span class="e h${harm(c)}" title="${E_NAMES[harm(c)]}">Е${esc(c)} · ${E_NAMES[harm(c)]}</span>`;
  const head = all.slice(0, E_SHOWN).map(chip).join('');
  const tail = all.slice(E_SHOWN);
  const bad = all.filter(c => harm(c) >= 2).length;
  return `<div class="e-list" id="e-list" data-open="0">${head}
    ${tail.length ? `<span class="e more-e" id="e-more" role="button" tabindex="0">ещё ${tail.length}</span>
      <span hidden id="e-rest">${tail.map(chip).join('')}</span>` : ''}
    </div>${bad ? `<p class="hint" style="margin:-4px 0 12px">Сомнительных и нежелательных добавок: ${bad} из ${all.length}</p>` : ''}`;
}

function renderFoot() {
  const r = BYCODE.get(String(curCode));
  if (!r) return;
  const n = qty(r.c), f = isFav(r.c);
  $('#card-foot').innerHTML = `
    <button type="button" class="fav-btn ${f ? 'on' : ''}" id="c-fav" aria-label="Любимое">${f ? '♥' : '♡'}</button>
    ${n ? `<span class="qty compact" style="min-width:120px">
        <button type="button" data-dec="${esc(r.c)}">−</button><span class="n">${n}</span>
        <button type="button" data-inc="${esc(r.c)}">+</button></span>
      <button type="button" class="cta in" id="c-add">В списке · ${fmt(r.p * n)} ₽</button>`
      : `<button type="button" class="cta" id="c-add">${ICON_CART}<span>В список</span></button>`}`;
}

async function openCard(code) {
  const r = BYCODE.get(String(code));
  if (!r) return;
  curCode = String(code);
  $('#card-overlay').hidden = false;
  $('#card-body').innerHTML = `<div class="c-photo"></div><div class="sk" style="border:0;background:none;padding:12px 0">
    <i class="l1"></i><i class="l2"></i></div>`;
  renderFoot();
  const d = await loadDetail(code) || {};
  if (curCode !== String(code)) return; // успели открыть другой товар
  const s = r.s == null ? null : Math.max(0, Math.min(100, Math.round(r.s)));
  const sk = s == null ? '' : scoreCls(s);
  const sim = similar(r);
  $('#card-body').innerHTML = `
    ${photoHTML(r, '', 'c-photo')}
    <h2>${esc(r.t)}</h2>
    <div class="c-sub">${[r.b, d.country, r.k2 || r.k1].filter(Boolean).map(esc).join(' · ') || '—'}</div>
    <div class="price-row"><span class="price-now${r.op && r.op > r.p ? ' sale' : ''}">${fmt(r.p)} ₽</span>
      ${r.op && r.op > r.p ? `<span class="price-old">${fmt(r.op)} ₽</span>` : ''}
      ${dealBadge(r)}</div>
    ${!r.st ? `<div class="oos-banner">${ICON_WARN}<span>Сейчас нет в магазине — можно оставить в списке на потом</span></div>` : ''}
    ${s == null ? '' : `<div class="blk score-big"><div class="top"><span class="n c-${sk}">${s}</span>
      <span class="track"><i class="fill s-${sk}" style="display:block;width:${s}%"></i></span></div>
      <div class="hint" style="margin-top:10px">Оценка состава${r.sp != null ? ` · лучше ${r.sp}% товаров в категории` : ''}</div></div>`}
    ${(r.fl || []).length ? `<div class="e-list">${r.fl.map(f => `<span class="badge flag">${esc(FLAGS[f] || f)}</span>`).join('')}</div>` : ''}
    ${eListHTML(d)}
    ${spark(d.hist)}
    <div class="kvs">
      ${r.pk ? `<div class="kv">Цена за ${esc(r.un || 'кг')}<b>${fmt(r.pk)} ₽</b></div>` : ''}
      ${r.typ && Math.abs(r.typ - r.p) > 0.01 ? `<div class="kv">Обычная цена<b>${fmt(r.typ)} ₽</b></div>` : ''}
      ${r.kc ? `<div class="kv wide">КБЖУ на 100 г<b>${fmt(r.kc)} ккал · Б ${fmt(r.pr)} · Ж ${fmt(d.fat)} · У ${fmt(d.carb)}</b></div>` : ''}
      ${r.de && r.d ? `<div class="kv">Скидка действует до<b>${esc(fmtDate(r.de))}</b></div>` : ''}
    </div>
    ${d.comp ? `<div class="blk comp"><b>Состав:</b> <span class="txt${d.comp.length > 160 ? ' clip' : ''}" id="comp-txt">${esc(d.comp)}</span>
      ${d.comp.length > 160 ? '<button type="button" class="more" id="comp-more">Показать полностью</button>' : ''}</div>`
      : '<p class="hint">Состав не указан</p>'}
    <div class="sec-h">Похожие в «${esc(r.k2 || r.k1 || 'категории')}» — качество за рубль</div>
    ${sim.length ? `<div class="sim">${sim.map(x => `<div class="s-card" data-c="${esc(x.c)}">
        ${photoHTML(x, x.s != null ? `<span class="badge-abs">${scoreHTML(x)}</span>` : '')}
        <div class="st">${esc(x.t)}</div>
        <div class="sp">${fmt(x.p)} ₽${x.op && x.op > x.p ? `<span class="old">${fmt(x.op)} ₽</span>` : ''}</div></div>`).join('')}</div>`
      : '<p class="hint">нет похожих в наличии</p>'}
    <div class="sec-h">Меньше видеть</div>
    <button type="button" class="rowbtn" data-menu="p">${ICON_EYE}<span>Скрыть товар</span></button>
    ${r.b ? `<button type="button" class="rowbtn" data-menu="b">${ICON_EYE}<span>Скрыть все товары бренда «${esc(r.b)}»</span></button>` : ''}`;
  $('#card-body').scrollTop = 0;
}
function closeCard() { $('#card-overlay').hidden = true; curCode = null; }

$('#card-overlay').addEventListener('click', e => { if (e.target.id === 'card-overlay') closeCard(); });
addEventListener('keydown', e => { if (e.key === 'Escape') closeCard(); });

// клики внутри шторки — одна делегация
$('#card').addEventListener('click', e => {
  const t = e.target;
  if (t.closest('#c-close')) return closeCard();
  if (t.closest('#e-more')) {
    const rest = $('#e-rest');
    if (rest) { rest.hidden = false; rest.style.display = 'contents'; }
    $('#e-more').remove();
    return;
  }
  if (t.closest('#comp-more')) {
    const txt = $('#comp-txt'), on = txt.classList.toggle('clip');
    $('#comp-more').textContent = on ? 'Показать полностью' : 'Свернуть';
    return;
  }
  const dec = t.closest('[data-dec]'), inc = t.closest('[data-inc]');
  if (dec) return addToCart(dec.dataset.dec, -1);
  if (inc) return addToCart(inc.dataset.inc, 1);
  if (t.closest('#c-add')) { addToCart(curCode, 1); toast('Добавлено в список'); return; }
  if (t.closest('#c-fav')) return toggleFav(curCode);
  const sc = t.closest('.s-card');
  if (sc) { openCard(sc.dataset.c); return; }
  const mp = t.closest('[data-menu]');
  if (mp) {
    const r = BYCODE.get(String(curCode));
    if (!r) return;
    if (mp.dataset.menu === 'p') { blP.add(String(r.c)); LS.set('blP', [...blP]); toast('Товар скрыт'); }
    else { blB.add(r.b); LS.set('blB', [...blB]); toast(`Бренд «${r.b}» скрыт`); }
    closeCard(); render();
  }
});

/* ---------- список покупок ---------- */
function cartTotal() {
  return Object.keys(cart).reduce((s, c) => { const r = BYCODE.get(c); return s + (r ? r.p * cart[c] : 0); }, 0);
}
function updateCartBadge() {
  const n = Object.values(cart).reduce((a, b) => a + b, 0);
  $('#cart-n').hidden = !n;
  $('#cart-n').textContent = n;
}
function renderCart() {
  const codes = Object.keys(cart);
  const total = cartTotal();
  $('#cart-items').innerHTML = codes.map(c => {
    const r = BYCODE.get(c);
    if (!r) return '';
    return `<div class="citem${r.st ? '' : ' oos'}" data-c="${esc(c)}">
      ${photoHTML(r)}
      <div><div class="ti">${esc(r.t)}</div>
        <div class="crow"><span class="act-c">${actHTML(c, true)}</span>
          <span class="cright"><span class="sum">${fmt(r.p * cart[c])} ₽</span>${!r.st ? '<span class="oos">нет в наличии</span>' : ''}</span>
        </div></div></div>`;
  }).join('') || `<div class="empty">${emptyHTML(ICON_CART, 'Список пуст', 'Добавляйте товары кнопкой «+ В список»',
    '<button type="button" class="ghost" id="to-search">В каталог</button>')}</div>`;
  $('#cart-clear').hidden = !codes.length;
  // для пустого списка бюджет — шум, показываем только сам призыв набрать корзину
  $('.budget-card').hidden = !codes.length;
  const budget = LS.get('budget', null);
  if (document.activeElement !== $('#budget')) $('#budget').value = budget ?? '';
  const over = budget && total > budget;
  $('#cart-total').textContent = `Итого ${fmt(total)} ₽`;
  $('#cart-total').className = 'total' + (over ? ' over' : '');
  const pct = budget ? Math.min(100, total / budget * 100) : 0;
  const bar = $('#budget-bar');
  // без бюджета пустая полоса выглядела как сломанный элемент — просто прячем её
  $('#bar-track').hidden = !budget;
  bar.style.width = pct + '%';
  bar.className = 'bar-fill' + (over ? ' over' : pct >= 85 ? ' warn' : '');
  const hint = $('#budget-hint');
  hint.textContent = !budget ? 'Задайте бюджет, чтобы видеть прогресс'
    : over ? `Превышение на ${fmt(total - budget)} ₽` : `${Math.round(pct)}% бюджета · остаток ${fmt(budget - total)} ₽`;
  hint.className = 'hint' + (over ? ' over' : '');
  hint.style.marginTop = budget ? '' : '10px';
  updateCartBadge();
}
$('#budget').addEventListener('input', e => { LS.set('budget', +e.target.value || null); renderCart(); });
$('#cart-clear').addEventListener('click', e => {
  const b = e.currentTarget;
  if (b.dataset.sure) { cart = {}; LS.set('cart', cart); renderCart(); updateCartBadge(); return; }
  b.dataset.sure = '1'; b.textContent = 'Точно очистить?'; b.classList.add('danger');
  setTimeout(() => { delete b.dataset.sure; b.textContent = 'Очистить список'; b.classList.remove('danger'); }, 3000);
});

/* ---------- любимое ---------- */
function renderFav() {
  const rows = [...fav].map(c => BYCODE.get(c)).filter(Boolean);
  $('#fav-h').textContent = `Любимое (${rows.length})`;
  const cb = $('#fav-clear');
  cb.hidden = !rows.length;
  cb.textContent = 'очистить всё'; delete cb.dataset.sure;
  $('#fav-items').innerHTML = rows.map(itemHTML).join('')
    || `<div class="empty">${emptyHTML(ICON_HEART, 'Пока нет любимого', 'Отмечайте товары ♡ на карточке')}</div>`;
}
$('#fav-view').addEventListener('click', e => {
  const clr = e.target.closest('[data-clear]');
  if (clr) {
    if (!clr.dataset.sure) { clr.dataset.sure = '1'; clr.textContent = 'точно?'; setTimeout(() => { delete clr.dataset.sure; clr.textContent = 'очистить всё'; }, 3000); return; }
    fav.clear(); LS.set('fav', []); renderFav();
    return;
  }
  if (handleCardClicks(e)) return;
});

/* ---------- моё ---------- */
function renderPrefs() {
  $('#bl-brands-h').textContent = `Скрытые бренды (${blB.size})`;
  $('#bl-products-h').textContent = `Скрытые товары (${blP.size})`;
  const clearBtn = k => ` <button type="button" class="mini-clear" data-clear="${k}">вернуть все</button>`;
  $('#bl-brands').innerHTML = ([...blB].map(b => `<span class="bl-chip">${esc(b)}<button type="button" data-unb="${esc(b)}" aria-label="Вернуть">✕</button></span>`).join('') + (blB.size > 1 ? clearBtn('blB') : '')) || '<p class="hint">пусто</p>';
  $('#bl-products').innerHTML = ([...blP].map(c => { const r = BYCODE.get(c); return `<span class="bl-chip">${esc(r ? r.t : c)}<button type="button" data-unp="${esc(c)}" aria-label="Вернуть">✕</button></span>`; }).join('') + (blP.size > 1 ? clearBtn('blP') : '')) || '<p class="hint">пусто</p>';
}
$('#prefs-view').addEventListener('click', e => {
  const acc = e.target.closest('[data-acc]');
  if (acc) {
    const body = $('#' + acc.dataset.acc);
    body.hidden = !body.hidden;
    acc.setAttribute('aria-expanded', String(!body.hidden));
    acc.querySelector('.acc-x').textContent = body.hidden ? 'Показать' : 'Скрыть';
    return;
  }
  const clr = e.target.closest('[data-clear]');
  if (clr) {
    const k = clr.dataset.clear;
    if (!clr.dataset.sure) { clr.dataset.sure = '1'; clr.textContent = 'точно?'; setTimeout(() => { delete clr.dataset.sure; clr.textContent = 'вернуть все'; }, 3000); return; }
    if (k === 'blB') { blB.clear(); LS.set('blB', []); }
    if (k === 'blP') { blP.clear(); LS.set('blP', []); }
    renderPrefs(); render();
    return;
  }
  const ub = e.target.closest('[data-unb]'), up = e.target.closest('[data-unp]');
  if (ub) { blB.delete(ub.dataset.unb); LS.set('blB', [...blB]); renderPrefs(); render(); return; }
  if (up) { blP.delete(up.dataset.unp); LS.set('blP', [...blP]); renderPrefs(); render(); return; }
});

/* ---------- общая делегация по сеткам карточек ---------- */
function handleCardClicks(e) {
  const f = e.target.closest('[data-fav]');
  if (f) { e.stopPropagation(); toggleFav(f.dataset.fav); return true; }
  const inc = e.target.closest('[data-inc]'), dec = e.target.closest('[data-dec]');
  if (inc) { e.stopPropagation(); addToCart(inc.dataset.inc, 1); return true; }
  if (dec) { e.stopPropagation(); addToCart(dec.dataset.dec, -1); return true; }
  if (e.target.closest('.act') || e.target.closest('.act-c')) return true;
  const c = e.target.closest('.card')?.dataset.c || e.target.closest('.citem')?.dataset.c;
  if (c) { openCard(c); return true; }
  return false;
}
$('#list').addEventListener('click', handleCardClicks);
$('#cart-items').addEventListener('click', e => {
  if (e.target.closest('#to-search')) return switchTab('catalog');
  handleCardClicks(e);
});
$('#empty').addEventListener('click', e => {
  if (!e.target.closest('#reset-f')) return;
  $('#stock').checked = true;
  toRoot();
});

/* ---------- вкладки ---------- */
function switchTab(name) {
  tab = name;
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $('#top').hidden = name !== 'catalog';
  $('#list-view').hidden = name !== 'catalog';
  $('#cart-view').hidden = name !== 'cart';
  $('#fav-view').hidden = name !== 'fav';
  $('#prefs-view').hidden = name !== 'prefs';
  if (name === 'catalog') render();
  else if (name === 'cart') renderCart();
  else if (name === 'fav') renderFav();
  else renderPrefs();
  scrollTo(0, 0);
}
$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('button[data-tab]');
  if (b) switchTab(b.dataset.tab);
});
$('#cats').addEventListener('click', e => {
  const b = e.target.closest('.chip');
  if (!b || b.dataset.sub === undefined) return;
  sub = b.dataset.sub;
  renderHead();
  render();
  scrollTo(0, 0);
});
/* тап по плитке — переход в список раздела (или в список выгодных) */
$('#tiles').addEventListener('click', e => {
  const b = e.target.closest('[data-tile],[data-deals]');
  if (!b) return;
  sub = '';
  // незакрытый поисковый запрос иначе «съедал» весь раздел и экран выглядел пустым
  $('#q').value = ''; $('#q-clear').hidden = true;
  if (b.dataset.deals) { onlyDeals = true; cat = ''; $('#sort').value = 'rel'; }
  else { cat = b.dataset.tile; onlyDeals = false; }
  renderHead();
  render();
  scrollTo(0, 0);
});
$('#back').addEventListener('click', toRoot);
$('#q').addEventListener('input', e => {
  $('#q-clear').hidden = !e.target.value;
  renderHead(); render();
});
$('#q-clear').addEventListener('click', () => {
  $('#q').value = ''; $('#q-clear').hidden = true;
  renderHead(); render();
});
$('#sort').addEventListener('change', render);
$('#stock').addEventListener('change', render);

boot();
