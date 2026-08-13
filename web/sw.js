/* Офлайн-кэш: оболочка — cache-first, данные — network-first с запасным кэшем,
   фото товаров — cache-first в отдельном кэше с ограничением по числу файлов. */
const SHELL = 'shell-v9';
const DATA = 'data-v9';
const IMG = 'img-v9';
const KEEP = new Set([SHELL, DATA, IMG]);
const SHELL_FILES = ['.', 'index.html', 'style.css', 'app.js', 'manifest.json', 'icon.svg'];
/* Оригиналы фото с auchan.ru весят 35–620 КБ, уменьшенных на CDN нет. Без кэша
   повторное листание качало их заново — сотни мегабайт за пару минут. */
const IMG_MAX = 600;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
// при активации выкидываем кэши прошлых версий, чтобы не залипла старая оболочка
self.addEventListener('activate', e => e.waitUntil(
  caches.keys()
    .then(ks => Promise.all(ks.filter(k => !KEEP.has(k)).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

// простая FIFO-обрезка: cache.keys() отдаёт записи в порядке добавления
async function trim(cache) {
  const ks = await cache.keys();
  if (ks.length <= IMG_MAX) return;
  await Promise.all(ks.slice(0, ks.length - IMG_MAX).map(k => cache.delete(k)));
}

async function photo(req) {
  const cache = await caches.open(IMG);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  // непрозрачные ответы (no-cors) тоже кладём: размер неизвестен, но повтор бесплатный
  if (res && (res.ok || res.type === 'opaque')) {
    await cache.put(req, res.clone());
    trim(cache);
  }
  return res;
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.origin !== location.origin) {
    // фото товаров — единственное, что мы тянем со стороны
    if (/(^|\.)auchan\.ru$/.test(url.hostname)) e.respondWith(photo(e.request).catch(() => fetch(e.request)));
    return;
  }
  if (url.pathname.includes('/data/')) {
    e.respondWith(
      fetch(e.request).then(r => {
        const copy = r.clone();
        caches.open(DATA).then(c => c.put(e.request, copy));
        return r;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
