const CACHE_NAME = 'momentum-cache-v3';
const BASE_PATH = '/momentum-pwa';
const FILES_TO_CACHE = [
  `${BASE_PATH}/`,
  `${BASE_PATH}/index.html`,
  `${BASE_PATH}/app.js`,
  `${BASE_PATH}/manifest.json`,
  `${BASE_PATH}/service-worker.js`,
  `${BASE_PATH}/data/trending.json`
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(FILES_TO_CACHE)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => k === CACHE_NAME ? null : caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Network-first for data file
  if (request.url.includes('/data/trending.json')) {
    event.respondWith(
      fetch(request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Cache-first for app shell
  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request))
  );
});
