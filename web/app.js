/* Корзинка — помощник покупок. Данные: web/data/* из build_site_data.py */
'use strict';
const $ = s => document.querySelector(s);
const LS = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { localStorage.setItem(k, JSON.stringify(v)); },
};
let META = null, ROWS = [], BYCODE = new Map();
let cart = LS.get('cart', {});          // code -> qty
let blP = new Set(LS.get('blP', []));   // чёрный список товаров
let blB = new Set(LS.get('blB', []));   // чёрный список брендов
let fav = new Set(LS.get('fav', []));
let tab = 'search';
const shardCache = {};

const fmt = n => n == null ? '—' : (Math.round(n * 100) / 100).toLocaleString('ru-RU');
const esc = s => (s ?? '').toString().replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function boot() {
  META = await (await fetch('data/meta.json')).json();
  const idx = await (await fetch('data/index.json')).json();
  const { cols } = idx;
  ROWS = idx.rows.map(a => { const o = {}; cols.forEach((c, i) => o[c] = a[i]); return o; });
  ROWS.forEach(r => BYCODE.set(String(r.c), r));
  META.cats.forEach(c => $('#cat').insertAdjacentHTML('beforeend', `<option>${esc(c)}</option>`));
  $('#meta-info').textContent = `Срез: ${META.date} · ${META.products} товаров · история за ${META.days} дн.`;
  render();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
}

function visible(r) {
  return !blP.has(String(r.c)) && !(r.b && blB.has(r.b));
}

function filterRows() {
  const q = $('#q').value.trim().toLowerCase();
  const cat = $('#cat').value;
  const stock = $('#stock').checked;
  let rs = ROWS.filter(visible);
  if (stock) rs = rs.filter(r => r.st);
  if (cat) rs = rs.filter(r => r.k1 === cat);
  if (tab === 'deals') rs = rs.filter(r => r.d > 0);
  if (q) {
    const terms = q.split(/\s+/);
    rs = rs.filter(r => {
      const hay = (r.t + ' ' + (r.b || '')).toLowerCase();
      return terms.every(t => hay.includes(t));
    });
  }
  const key = $('#sort').value;
  const dir = (key === 's' || key === 'v' || key === 'r') ? -1 : 1;
  rs.sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (x - y) * dir;
  });
  return rs;
}

function dealBadge(r) {
  if (!(r.d > 0)) return '';
  if (r.rel != null && r.rel <= -5) return `<span class="badge deal">выгода ${fmt(r.rel)}%</span>`;
  if (r.rel != null && r.rel >= -1) return `<span class="badge fake">цена как обычно</span>`;
  return '';
}

function itemHTML(r) {
  const img = r.im ? `<img loading="lazy" src="${esc(r.im)}" alt="">` : '<div></div>';
  const score = r.s != null ? `<span class="badge score">состав ${Math.round(r.s)}${r.sp != null ? ' · лучше ' + r.sp + '%' : ''}</span>` : '';
  return `<div class="item" data-c="${r.c}">${img}
    <div><div class="ti">${esc(r.t)}</div>
      <div class="sub">${r.d ? `<span class="badge disc">−${Math.round(r.d)}%</span>` : ''}${dealBadge(r)}${score}
      ${r.r ? `★ ${r.r} (${r.rc || 0})` : ''}</div></div>
    <div class="pr"><div class="now">${fmt(r.p)} ₽</div>
      ${r.op ? `<div class="old">${fmt(r.op)} ₽</div>` : ''}
      ${r.pk ? `<div class="pk">${fmt(r.pk)} ₽/${r.un}</div>` : ''}</div></div>`;
}

let shown = 0, curRows = [];
function render() {
  curRows = filterRows();
  shown = Math.min(60, curRows.length);
  $('#list').innerHTML = curRows.slice(0, shown).map(itemHTML).join('');
  $('#empty').hidden = curRows.length > 0;
  updateCartBadge();
}
function more() {
  if (shown >= curRows.length) return;
  const next = curRows.slice(shown, shown + 60);
  shown += next.length;
  $('#list').insertAdjacentHTML('beforeend', next.map(itemHTML).join(''));
}
window.addEventListener('scroll', () => {
  if (innerHeight + scrollY > document.body.scrollHeight - 600) more();
});

/* ---------- карточка ---------- */
async function loadDetail(code) {
  const shard = [...String(code)].reduce((s, ch) => s + ch.charCodeAt(0), 0) % META.shards;
  if (!shardCache[shard]) shardCache[shard] = await (await fetch(`data/details/${shard}.json`)).json();
  return shardCache[shard][String(code)] || {};
}

function spark(hist) {
  if (!hist || hist.length < 2) return '';
  const ps = hist.map(h => h[1]);
  const min = Math.min(...ps), max = Math.max(...ps), pad = (max - min) || 1;
  const W = 300, H = 56;
  const pts = ps.map((p, i) => `${(i / (ps.length - 1) * (W - 10) + 5).toFixed(1)},${(H - 8 - (p - min) / pad * (H - 16)).toFixed(1)}`);
  return `<svg class="spark" viewBox="0 0 ${W} ${H}">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    <circle cx="${pts.at(-1).split(',')[0]}" cy="${pts.at(-1).split(',')[1]}" r="3.5" fill="var(--accent)"/>
    <text x="5" y="${H - 1}" font-size="9" fill="var(--muted)">${fmt(min)}–${fmt(max)} ₽ за ${hist.length} дн.</text></svg>`;
}

function similar(r) {
  return ROWS.filter(x => x.c !== r.c && visible(x) && x.st && x.k2 === r.k2)
    .sort((a, b) => (b.v ?? -1) - (a.v ?? -1)).slice(0, 5);
}

async function openCard(code) {
  const r = BYCODE.get(String(code));
  if (!r) return;
  const d = await loadDetail(code);
  const flags = { sugar_first: 'сахар в начале состава', palm: 'пальмовое масло', flavor_enh: 'усилители вкуса', sweetener: 'подсластители' };
  const eNames = { 0: '', 1: 'нейтральная', 2: 'сомнительная', 3: 'нежелательная' };
  $('#card').innerHTML = `
    <h2>${esc(r.t)}</h2>
    <div class="hint">${esc(r.b || '')} ${d.country ? '· ' + esc(d.country) : ''} · ${esc(r.k2 || r.k1 || '')}</div>
    ${r.im ? `<img class="photo" src="${esc(r.im)}" alt="">` : ''}
    <div class="row">
      <div class="kv">Цена<b>${fmt(r.p)} ₽${r.op ? ` <s style="color:var(--muted);font-weight:400">${fmt(r.op)}</s>` : ''}</b></div>
      ${r.pk ? `<div class="kv">За ${r.un}<b>${fmt(r.pk)} ₽</b></div>` : ''}
      ${r.typ ? `<div class="kv">Обычная цена<b>${fmt(r.typ)} ₽</b></div>` : ''}
      ${r.s != null ? `<div class="kv">Состав<b>${Math.round(r.s)}/100${r.sp != null ? ` · лучше ${r.sp}% в категории` : ''}</b></div>` : ''}
      ${r.r ? `<div class="kv">Оценка<b>★ ${r.r} (${r.rc})</b></div>` : ''}
      ${r.kc ? `<div class="kv">КБЖУ/100г<b>${r.kc} ккал · Б${fmt(r.pr)} Ж${fmt(d.fat)} У${fmt(d.carb)}</b></div>` : ''}
    </div>
    <div class="row">${dealBadge(r)}${(r.fl || []).map(f => `<span class="badge flag">${flags[f] || f}</span>`).join('')}
      ${r.de && r.d ? `<span class="hint">скидка до ${r.de}</span>` : ''}</div>
    ${spark(d.hist)}
    ${d.e && d.e.length ? `<div class="e-list">${d.e.map(c => `<span class="e h${d.eh[c] ?? 0}" title="${eNames[d.eh[c] ?? 0]}">Е${c}</span>`).join('')}</div>` : ''}
    ${d.comp ? `<div class="comp"><b>Состав:</b> ${esc(d.comp)}</div>` : '<div class="hint">Состав не указан</div>'}
    <div class="row">
      <button class="act" id="c-add">🧺 В список${cart[r.c] ? ` (${cart[r.c]})` : ''}</button>
      <button class="ghost" id="c-fav">${fav.has(String(r.c)) ? '♥ В любимом' : '♡ В любимое'}</button>
      <button class="danger" id="c-blp">Скрыть товар</button>
      ${r.b ? `<button class="danger" id="c-blb">Скрыть бренд</button>` : ''}
    </div>
    <div class="sim-h">Похожие в «${esc(r.k2 || r.k1)}» — по качеству за рубль:</div>
    ${similar(r).map(itemHTML).join('') || '<div class="hint">нет похожих в наличии</div>'}`;
  $('#card-overlay').hidden = false;
  $('#c-add').onclick = () => { cart[r.c] = (cart[r.c] || 0) + 1; LS.set('cart', cart); openCard(code); updateCartBadge(); };
  $('#c-fav').onclick = () => { const k = String(r.c); fav.has(k) ? fav.delete(k) : fav.add(k); LS.set('fav', [...fav]); openCard(code); };
  $('#c-blp').onclick = () => { blP.add(String(r.c)); LS.set('blP', [...blP]); closeCard(); render(); };
  const bb = $('#c-blb');
  if (bb) bb.onclick = () => { if (confirm(`Скрыть все товары «${r.b}»?`)) { blB.add(r.b); LS.set('blB', [...blB]); closeCard(); render(); } };
}
function closeCard() { $('#card-overlay').hidden = true; }
$('#card-overlay').addEventListener('click', e => { if (e.target.id === 'card-overlay') closeCard(); });

/* ---------- список покупок ---------- */
function updateCartBadge() {
  const n = Object.values(cart).reduce((a, b) => a + b, 0);
  $('#cart-n').hidden = !n;
  $('#cart-n').textContent = n;
}
function renderCart() {
  const codes = Object.keys(cart);
  let total = 0;
  $('#cart-items').innerHTML = codes.map(c => {
    const r = BYCODE.get(c);
    if (!r) return '';
    total += r.p * cart[c];
    return `<div class="citem"><div style="cursor:pointer" data-c="${c}"><div class="ti">${esc(r.t)}</div>
        <div class="hint">${fmt(r.p)} ₽ ${r.d ? `· −${Math.round(r.d)}%` : ''} ${!r.st ? '· <b style="color:var(--danger)">нет в наличии</b>' : ''}</div></div>
      <div class="qty"><button data-dec="${c}">−</button><span>${cart[c]}</span><button data-inc="${c}">+</button></div>
      <div class="pr"><b>${fmt(r.p * cart[c])} ₽</b></div></div>`;
  }).join('') || '<p class="hint">Список пуст — добавляй товары из карточек.</p>';
  const budget = LS.get('budget', null);
  $('#budget').value = budget ?? '';
  const over = budget && total > budget;
  $('#cart-total').textContent = `Итого: ${fmt(total)} ₽` + (over ? ` (превышение на ${fmt(total - budget)} ₽)` : budget ? ` из ${fmt(budget)} ₽` : '');
  $('#cart-total').className = over ? 'over' : '';
}
$('#budget').addEventListener('change', e => { LS.set('budget', +e.target.value || null); renderCart(); });
$('#cart-clear').onclick = () => { if (confirm('Очистить список?')) { cart = {}; LS.set('cart', cart); renderCart(); updateCartBadge(); } };
$('#cart-items').addEventListener('click', e => {
  const dec = e.target.dataset.dec, inc = e.target.dataset.inc, c = e.target.closest('[data-c]')?.dataset.c;
  if (dec) { if (--cart[dec] <= 0) delete cart[dec]; LS.set('cart', cart); renderCart(); updateCartBadge(); }
  else if (inc) { cart[inc]++; LS.set('cart', cart); renderCart(); updateCartBadge(); }
  else if (c) openCard(c);
});

/* ---------- настройки ---------- */
function renderPrefs() {
  $('#bl-brands').innerHTML = [...blB].map(b => `<span class="bl-chip">${esc(b)}<button data-unb="${esc(b)}">✕</button></span>`).join('') || '<p class="hint">пусто</p>';
  $('#bl-products').innerHTML = [...blP].map(c => { const r = BYCODE.get(c); return `<span class="bl-chip">${esc(r ? r.t : c)}<button data-unp="${c}">✕</button></span>`; }).join('') || '<p class="hint">пусто</p>';
  $('#fav-items').innerHTML = [...fav].map(c => { const r = BYCODE.get(c); return r ? itemHTML(r) : ''; }).join('') || '<p class="hint">пусто</p>';
}
$('#prefs-view').addEventListener('click', e => {
  const b = e.target.dataset.unb, p = e.target.dataset.unp, c = e.target.closest('.item')?.dataset.c;
  if (b) { blB.delete(b); LS.set('blB', [...blB]); renderPrefs(); render(); }
  else if (p) { blP.delete(p); LS.set('blP', [...blP]); renderPrefs(); render(); }
  else if (c) openCard(c);
});

/* ---------- вкладки и события ---------- */
document.querySelectorAll('#tabs button').forEach(btn => btn.onclick = () => {
  tab = btn.dataset.tab;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b === btn));
  const listMode = tab === 'search' || tab === 'deals';
  $('#top').hidden = !listMode;
  $('#list').hidden = !listMode;
  $('#empty').hidden = true;
  $('#cart-view').hidden = tab !== 'cart';
  $('#prefs-view').hidden = tab !== 'prefs';
  if (tab === 'deals') { $('#sort').value = 'rel'; render(); }
  else if (tab === 'search') render();
  else if (tab === 'cart') renderCart();
  else renderPrefs();
  scrollTo(0, 0);
});
['#q', '#cat', '#sort', '#stock'].forEach(s => $(s).addEventListener('input', render));
$('#list').addEventListener('click', e => { const c = e.target.closest('.item')?.dataset.c; if (c) openCard(c); });
$('#card').addEventListener?.('click', () => {});
document.addEventListener('click', e => { const c = e.target.closest('#card .item')?.dataset.c; if (c) openCard(c); });

boot();
