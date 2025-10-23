const CACHE_NAME = 'momentum-v1';
const FILES = [
  '/',
  '/index.html',
  '/app.js',
  '/manifest.json',
  '/service-worker.js',
  '/data/trending.json'
];

self.addEventListener('install', evt => {
  evt.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(FILES))
  );
  self.skipWaiting();
});

self.addEventListener('activate', evt => {
  evt.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', evt => {
  if (evt.request.method !== 'GET') return;
  const url = new URL(evt.request.url);
  // for JSON data, use network-first with fallback to cache
  if (url.pathname.endsWith('/data/trending.json') || url.pathname.endsWith('trending.json')) {
    evt.respondWith(
      fetch(evt.request).then(resp => {
        caches.open(CACHE_NAME).then(cache => cache.put(evt.request, resp.clone()));
        return resp;
      }).catch(() => caches.match(evt.request))
    );
    return;
  }
  evt.respondWith(
    caches.match(evt.request).then(cached => cached || fetch(evt.request))
  );
});
