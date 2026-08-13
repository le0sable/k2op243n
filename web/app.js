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
let tab = 'search', cat = '', sub = '', curCode = null;
const shardCache = {};

const fmt = n => n == null || isNaN(n) ? '—' : (Math.round(n * 100) / 100).toLocaleString('ru-RU');
const esc = s => (s ?? '').toString().replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const qty = c => cart[String(c)] || 0;

/* иконки-заглушки без сетевых запросов */
const ICON_BOX = '<svg viewBox="0 0 24 24"><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5v-9Z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/></svg>';
const ICON_SEARCH = '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 21 21"/></svg>';
const ICON_CART = '<svg viewBox="0 0 24 24"><path d="M4 8h16l-1.6 11H5.6L4 8ZM9 8V5a3 3 0 0 1 6 0v3"/></svg>';
const ICON_HEART = '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.6-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 7-2.8c0 4.6-7 14.8-7 14.8Z"/></svg>';

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
  renderCats();
  $('#meta-info').textContent = `Срез: ${META.date} · ${fmt(META.products)} товаров · история ${META.days} дн.`;
  render();
  updateCartBadge();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
}

function skeletons() {
  $('#list').innerHTML = Array(5).fill('<div class="sk"><i class="b"></i><div><i class="l1"></i><i class="l2"></i></div></div>').join('');
}

/* категории: без выбора — разделы (k1), с выбором — «назад» + подкатегории (k2) */
function renderCats() {
  const el = $('#cats');
  if (!cat) {
    el.innerHTML = [`<button type="button" class="cat${!cat ? ' on' : ''}" data-cat="">Все</button>`]
      .concat((META.cats || []).map(c => `<button type="button" class="cat" data-cat="${esc(c)}">${esc(c)}</button>`)).join('');
    return;
  }
  const subs = [...new Set(ROWS.filter(r => r.k1 === cat && r.k2).map(r => r.k2))].sort();
  el.innerHTML = [`<button type="button" class="cat back" data-cat="">‹ ${esc(cat)}</button>`,
    `<button type="button" class="cat${!sub ? ' on' : ''}" data-sub="">Все</button>`]
    .concat(subs.map(c => `<button type="button" class="cat${sub === c ? ' on' : ''}" data-sub="${esc(c)}">${esc(c)}</button>`)).join('');
}

/* ---------- выборка ---------- */
function visible(r) { return !blP.has(String(r.c)) && !(r.b && blB.has(r.b)); }

function filterRows() {
  const q = $('#q').value.trim().toLowerCase();
  let rs = ROWS.filter(visible);
  if ($('#stock').checked) rs = rs.filter(r => r.st);
  if (cat) rs = rs.filter(r => r.k1 === cat);
  if (sub) rs = rs.filter(r => r.k2 === sub);
  // «Скидки» — только настоящая выгода, разоблачённые скидки сюда не попадают
  if (tab === 'deals') rs = rs.filter(r => r.d > 0 && r.rel != null && r.rel < -1);
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
function photoHTML(r, cls) {
  const ph = `<div class="ph">${ICON_BOX}</div>`;
  const img = r.im ? `<img loading="lazy" src="${esc(r.im)}" alt="" onerror="this.style.display='none'">` : '';
  return `<div class="thumb ${cls || ''}">${ph}${img}</div>`;
}

// один бейдж на карточку (док 4.2)
function dealBadge(r) {
  if (!(r.d > 0)) return '';
  const d = Math.round(r.d);
  if (r.rel != null && r.rel <= -5) return `<span class="badge good">−${d}% · выгодно</span>`;
  if (r.rel == null || r.rel >= -1) return `<span class="badge fake">цена как обычно</span>`;
  return `<span class="badge small">−${d}%</span>`;
}

function scoreCls(s) { return s >= 67 ? 'good' : s >= 34 ? 'mid' : 'bad'; }

function scoreHTML(r) {
  if (r.s == null) return '';
  const s = Math.max(0, Math.min(100, Math.round(r.s))), k = scoreCls(s);
  return `<span class="score"><span class="track"><i class="fill s-${k}" style="width:${s}%"></i></span>
    <span class="score-n c-${k}">${s}</span></span>`;
}

function qtyHTML(code) {
  const n = qty(code);
  if (!n) return `<span class="qty"><button type="button" data-inc="${esc(code)}" aria-label="Добавить">+</button></span>`;
  return `<span class="qty"><button type="button" data-dec="${esc(code)}" aria-label="Убрать">−</button>
    <span class="n">${n}</span><button type="button" data-inc="${esc(code)}" aria-label="Добавить">+</button></span>`;
}

function itemHTML(r) {
  return `<article class="item" data-c="${esc(r.c)}">
    ${photoHTML(r)}
    <div><div class="ti">${esc(r.t)}</div>
      <div class="sub">${dealBadge(r)}${scoreHTML(r)}</div></div>
    <div class="rt"><div class="pr"><div class="now">${fmt(r.p)} ₽</div>
      ${r.pk ? `<div class="pk">${fmt(r.pk)} ₽/${esc(r.un || 'кг')}</div>` : ''}</div>
      ${qtyHTML(r.c)}</div></article>`;
}

function emptyHTML(icon, h, p, btn) {
  return `${icon}<h3>${h}</h3><p>${p}</p>${btn || ''}`;
}

/* ---------- лента ---------- */
let shown = 0, curRows = [];
function render() {
  curRows = filterRows();
  shown = Math.min(60, curRows.length);
  $('#list').innerHTML = curRows.slice(0, shown).map(itemHTML).join('');
  const e = $('#empty');
  e.hidden = curRows.length > 0;
  if (!e.hidden) {
    e.innerHTML = tab === 'deals'
      ? emptyHTML('', 'Сейчас нет проверенных скидок', 'Список обновляется вместе с ценами каждый день')
      : emptyHTML(ICON_SEARCH, 'Ничего не нашлось', 'Проверьте написание или уберите фильтры',
        '<button type="button" class="ghost" id="reset-f">Сбросить фильтры</button>');
  }
  if (tab === 'deals') {
    const fake = ROWS.filter(r => visible(r) && r.d > 0 && (r.rel == null || r.rel >= -1)).length;
    $('#legend').hidden = false;
    $('#legend').textContent = `Только скидки, подтверждённые историей цен · ${fmt(fake)} фейковых скрыто`;
  } else $('#legend').hidden = true;
}
function more() {
  if (shown >= curRows.length) return;
  const next = curRows.slice(shown, shown + 60);
  shown += next.length;
  $('#list').insertAdjacentHTML('beforeend', next.map(itemHTML).join(''));
}
addEventListener('scroll', () => {
  if (tab !== 'search' && tab !== 'deals') return;
  if (innerHeight + scrollY > document.body.scrollHeight - 600) more();
});

/* обновить счётчики в уже отрисованном DOM, не перерисовывая ленту */
function syncQty(code) {
  $$(`[data-c="${CSS.escape(String(code))}"] .qty`).forEach(el => el.outerHTML = qtyHTML(code));
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

/* ---------- карточка товара ---------- */
async function loadDetail(code) {
  const shard = [...String(code)].reduce((s, ch) => s + ch.charCodeAt(0), 0) % META.shards;
  if (!shardCache[shard]) shardCache[shard] = await (await fetch(`data/details/${shard}.json`)).json();
  return shardCache[shard][String(code)] || {};
}

function spark(hist) {
  if (!hist || hist.length < 2) return '';
  const ps = hist.map(h => h[1]).filter(p => typeof p === 'number');
  if (ps.length < 2) return '';
  const min = Math.min(...ps), max = Math.max(...ps), pad = (max - min) || 1;
  const W = 300, H = 56;
  const pts = ps.map((p, i) => `${(i / (ps.length - 1) * (W - 10) + 5).toFixed(1)},${(H - 10 - (p - min) / pad * (H - 20)).toFixed(1)}`);
  const last = pts.at(-1).split(',');
  return `<svg class="spark" viewBox="0 0 ${W} ${H}">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="var(--accent)"/>
    <text x="5" y="${H - 1}" font-size="9" fill="var(--muted)">${fmt(min)}–${fmt(max)} ₽ за ${ps.length} дн.</text></svg>`;
}

function similar(r) {
  return ROWS.filter(x => x.c !== r.c && visible(x) && x.st && x.k2 && x.k2 === r.k2)
    .sort((a, b) => (b.v ?? -1) - (a.v ?? -1)).slice(0, 8);
}

const FLAGS = { sugar_first: 'сахар в начале состава', palm: 'пальмовое масло', flavor_enh: 'усилители вкуса', sweetener: 'подсластители' };
const E_NAMES = { 0: 'безопасная', 1: 'нейтральная', 2: 'сомнительная', 3: 'нежелательная' };

function renderFoot() {
  const r = BYCODE.get(String(curCode));
  if (!r) return;
  const n = qty(r.c), f = fav.has(String(r.c));
  $('#card-foot').innerHTML = `
    <button type="button" class="fav-btn ${f ? 'on' : ''}" id="c-fav" aria-label="Любимое">${f ? '♥' : '♡'}</button>
    ${n ? `<span class="qty" style="margin:0 4px">
        <button type="button" data-dec="${esc(r.c)}">−</button><span class="n">${n}</span>
        <button type="button" data-inc="${esc(r.c)}">+</button></span>
      <button type="button" class="cta in" id="c-add">В списке · ${fmt(r.p * n)} ₽</button>`
      : `<button type="button" class="cta" id="c-add">${ICON_CART}<span>В список</span></button>`}`;
}

async function openCard(code) {
  const r = BYCODE.get(String(code));
  if (!r) return;
  curCode = String(code);
  $('#c-menu-pop').hidden = true;
  $('#card-overlay').hidden = false;
  $('#card-body').innerHTML = `<div class="c-photo"></div><div class="sk" style="border:0;background:none;padding:12px 0">
    <div><i class="l1"></i><i class="l2"></i></div></div>`;
  renderFoot();
  const d = await loadDetail(code) || {};
  if (curCode !== String(code)) return; // успели открыть другой товар
  const s = r.s == null ? null : Math.max(0, Math.min(100, Math.round(r.s)));
  const sk = s == null ? '' : scoreCls(s);
  const sim = similar(r);
  $('#card-body').innerHTML = `
    ${photoHTML(r, 'c-photo')}
    <h2>${esc(r.t)}</h2>
    <div class="c-sub">${[r.b, d.country, r.k2 || r.k1].filter(Boolean).map(esc).join(' · ') || '—'}</div>
    <div class="price-row"><span class="price-now">${fmt(r.p)} ₽</span>
      ${r.op && r.op > r.p ? `<span class="price-old">${fmt(r.op)} ₽</span>` : ''}
      ${dealBadge(r)}</div>
    ${s == null ? '' : `<div class="score-big"><div class="top"><span class="n c-${sk}">${s}</span>
      <span class="track"><i class="fill s-${sk}" style="display:block;width:${s}%"></i></span></div>
      <div class="hint" style="margin-top:8px">Оценка состава${r.sp != null ? ` · лучше ${r.sp}% товаров в категории` : ''}</div></div>`}
    ${(r.fl || []).length ? `<div class="e-list">${r.fl.map(f => `<span class="badge flag">${esc(FLAGS[f] || f)}</span>`).join('')}</div>` : ''}
    ${d.e && d.e.length ? `<div class="e-list">${d.e.map(c => {
      const h = (d.eh && d.eh[c]) ?? 0;
      return `<span class="e h${h}" title="${E_NAMES[h]}">Е${esc(c)} · ${E_NAMES[h]}</span>`;
    }).join('')}</div>` : ''}
    ${spark(d.hist)}
    <div class="kvs">
      ${r.pk ? `<div class="kv">Цена за ${esc(r.un || 'кг')}<b>${fmt(r.pk)} ₽</b></div>` : ''}
      ${r.typ ? `<div class="kv">Обычная цена<b>${fmt(r.typ)} ₽</b></div>` : ''}
      ${r.kc ? `<div class="kv">КБЖУ / 100 г<b>${fmt(r.kc)} ккал · Б${fmt(r.pr)} Ж${fmt(d.fat)} У${fmt(d.carb)}</b></div>` : ''}
      ${r.de && r.d ? `<div class="kv">Скидка до<b>${esc(r.de)}</b></div>` : ''}
      ${!r.st ? `<div class="kv" style="color:var(--danger)">Наличие<b style="color:var(--danger)">нет в магазине</b></div>` : ''}
    </div>
    ${d.comp ? `<div class="comp"><b>Состав:</b> <span class="txt clip" id="comp-txt">${esc(d.comp)}</span>
      <button type="button" class="more" id="comp-more">Показать полностью</button></div>`
      : '<p class="hint">Состав не указан</p>'}
    <div class="sim-h">Похожие в «${esc(r.k2 || r.k1 || 'категории')}» — качество за рубль</div>
    ${sim.length ? `<div class="sim">${sim.map(x => `<div class="s-card" data-c="${esc(x.c)}">
        ${photoHTML(x)}<div class="st">${esc(x.t)}</div>
        <div class="sp">${fmt(x.p)} ₽</div>${scoreHTML(x)}</div>`).join('')}</div>`
      : '<p class="hint">нет похожих в наличии</p>'}`;
  $('#card-body').scrollTop = 0;
}
function closeCard() { $('#card-overlay').hidden = true; $('#c-menu-pop').hidden = true; curCode = null; }

$('#card-overlay').addEventListener('click', e => { if (e.target.id === 'card-overlay') closeCard(); });
addEventListener('keydown', e => { if (e.key === 'Escape') closeCard(); });

// клики внутри шторки — одна делегация
$('#card').addEventListener('click', e => {
  const t = e.target;
  if (t.closest('#comp-more')) {
    const txt = $('#comp-txt'), on = txt.classList.toggle('clip');
    $('#comp-more').textContent = on ? 'Показать полностью' : 'Свернуть';
    return;
  }
  if (t.closest('#c-menu')) { const p = $('#c-menu-pop'); p.hidden = !p.hidden; if (!p.hidden) fillMenu(); return; }
  const dec = t.closest('[data-dec]'), inc = t.closest('[data-inc]');
  if (dec) return addToCart(dec.dataset.dec, -1);
  if (inc) return addToCart(inc.dataset.inc, 1);
  if (t.closest('#c-add')) { addToCart(curCode, 1); toast('Добавлено в список'); return; }
  if (t.closest('#c-fav')) {
    const k = String(curCode);
    fav.has(k) ? fav.delete(k) : fav.add(k);
    LS.set('fav', [...fav]); renderFoot();
    toast(fav.has(k) ? 'В любимом' : 'Убрано из любимого');
    return;
  }
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
function fillMenu() {
  const r = BYCODE.get(String(curCode));
  $('#c-menu-pop').innerHTML = `<button type="button" data-menu="p">Скрыть этот товар</button>
    ${r && r.b ? `<button type="button" data-menu="b">Скрыть бренд «${esc(r.b)}»</button>` : ''}`;
}

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
    return `<div class="citem" data-c="${esc(c)}">
      <div><div class="ti">${esc(r.t)}</div>
        <div class="sub">${fmt(r.p)} ₽ за шт.${!r.st ? ' · <b style="color:var(--danger)">нет в наличии</b>' : ''}</div></div>
      <div class="right">${qtyHTML(c)}<span class="sum">${fmt(r.p * cart[c])} ₽</span></div></div>`;
  }).join('') || `<div class="empty">${emptyHTML(ICON_CART, 'Список пуст', 'Добавляйте товары кнопкой + в поиске',
    '<button type="button" class="ghost" id="to-search">К поиску</button>')}</div>`;
  $('#cart-clear').hidden = !codes.length;
  const budget = LS.get('budget', null);
  if (document.activeElement !== $('#budget')) $('#budget').value = budget ?? '';
  const over = budget && total > budget;
  $('#cart-total').textContent = `Итого ${fmt(total)} ₽`;
  $('#cart-total').className = 'total' + (over ? ' over' : '');
  const pct = budget ? Math.min(100, total / budget * 100) : 0;
  const bar = $('#budget-bar');
  bar.style.width = pct + '%';
  bar.className = 'bar-fill' + (over ? ' over' : pct >= 85 ? ' warn' : '');
  $('#budget-hint').textContent = !budget ? 'Задайте бюджет, чтобы видеть прогресс'
    : over ? `Превышение на ${fmt(total - budget)} ₽` : `${Math.round(pct)}% бюджета · остаток ${fmt(budget - total)} ₽`;
  updateCartBadge();
}
$('#budget').addEventListener('input', e => { LS.set('budget', +e.target.value || null); renderCart(); });
$('#cart-clear').addEventListener('click', e => {
  const b = e.currentTarget;
  if (b.dataset.sure) { cart = {}; LS.set('cart', cart); renderCart(); updateCartBadge(); return; }
  b.dataset.sure = '1'; b.textContent = 'Точно очистить?'; b.classList.add('danger');
  setTimeout(() => { delete b.dataset.sure; b.textContent = 'Очистить список'; b.classList.remove('danger'); }, 3000);
});

/* ---------- моё ---------- */
function renderPrefs() {
  const favRows = [...fav].map(c => BYCODE.get(c)).filter(Boolean);
  $('#fav-h').innerHTML = `Любимое (${favRows.length})` +
    (favRows.length ? ' <button type="button" class="mini-clear" data-clear="fav">очистить</button>' : '');
  $('#fav-items').innerHTML = favRows.map(itemHTML).join('')
    || `<div class="empty">${emptyHTML(ICON_HEART, 'Пока нет избранного', 'Отмечайте товары ♡ в карточке')}</div>`;
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
    if (!clr.dataset.sure) { clr.dataset.sure = '1'; clr.textContent = 'точно?'; setTimeout(() => { delete clr.dataset.sure; }, 3000); return; }
    if (k === 'fav') { fav.clear(); LS.set('fav', []); }
    if (k === 'blB') { blB.clear(); LS.set('blB', []); }
    if (k === 'blP') { blP.clear(); LS.set('blP', []); }
    renderPrefs(); render();
    return;
  }
  const ub = e.target.closest('[data-unb]'), up = e.target.closest('[data-unp]');
  if (ub) { blB.delete(ub.dataset.unb); LS.set('blB', [...blB]); renderPrefs(); render(); return; }
  if (up) { blP.delete(up.dataset.unp); LS.set('blP', [...blP]); renderPrefs(); render(); return; }
  const inc = e.target.closest('[data-inc]'), dec = e.target.closest('[data-dec]');
  if (inc) return addToCart(inc.dataset.inc, 1);
  if (dec) return addToCart(dec.dataset.dec, -1);
  const c = e.target.closest('.item')?.dataset.c;
  if (c) openCard(c);
});

/* ---------- лента и корзина: делегация кликов ---------- */
$('#list').addEventListener('click', e => {
  const inc = e.target.closest('[data-inc]'), dec = e.target.closest('[data-dec]');
  if (inc) { e.stopPropagation(); return addToCart(inc.dataset.inc, 1); }
  if (dec) { e.stopPropagation(); return addToCart(dec.dataset.dec, -1); }
  if (e.target.closest('.qty')) return;   // тап между кнопками не открывает карточку
  const c = e.target.closest('.item')?.dataset.c;
  if (c) openCard(c);
});
$('#cart-items').addEventListener('click', e => {
  const inc = e.target.closest('[data-inc]'), dec = e.target.closest('[data-dec]');
  if (inc) return addToCart(inc.dataset.inc, 1);
  if (dec) return addToCart(dec.dataset.dec, -1);
  if (e.target.closest('#to-search')) return switchTab('search');
  if (e.target.closest('.qty')) return;
  const c = e.target.closest('.citem')?.dataset.c;
  if (c) openCard(c);
});
$('#empty').addEventListener('click', e => {
  if (!e.target.closest('#reset-f')) return;
  $('#q').value = ''; cat = ''; sub = ''; $('#stock').checked = true;
  renderCats();
  render();
});

/* ---------- вкладки ---------- */
function switchTab(name) {
  tab = name;
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  const listMode = name === 'search' || name === 'deals';
  $('#top').hidden = !listMode;
  $('#list-view').hidden = !listMode;
  $('#cart-view').hidden = name !== 'cart';
  $('#prefs-view').hidden = name !== 'prefs';
  $('#cats').hidden = name === 'deals';   // в скидках категорий нет (док 3.2)
  if (name === 'deals') { $('#sort').value = 'rel'; render(); }
  else if (name === 'search') render();
  else if (name === 'cart') renderCart();
  else renderPrefs();
  scrollTo(0, 0);
}
$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('button[data-tab]');
  if (b) switchTab(b.dataset.tab);
});
$('#cats').addEventListener('click', e => {
  const b = e.target.closest('.cat');
  if (!b) return;
  if (b.dataset.cat !== undefined) { cat = b.dataset.cat; sub = ''; }
  else sub = b.dataset.sub;
  renderCats();
  render();
});
$('#q').addEventListener('input', render);
$('#sort').addEventListener('change', render);
$('#stock').addEventListener('change', render);

boot();
