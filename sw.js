const CACHE_NAME = 'cangjingge-v1';
const ASSETS = ['/', '/manifest.json', '/icons/icon-192.png', '/icons/icon-512.png'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(caches.keys().then(keys =>
        Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ));
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);
    // API requests: network only
    if (url.pathname.startsWith('/api/')) return;
    // Pages and assets: network first, cache fallback
    e.respondWith(
        fetch(e.request).then(r => {
            if (r.ok) {
                const clone = r.clone();
                caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
            }
            return r;
        }).catch(() => caches.match(e.request))
    );
});
