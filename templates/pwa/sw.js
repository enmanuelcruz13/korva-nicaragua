/* Korva Nicaragua - Service Worker (PWA / TWA)
   Estrategia: network-first con fallback a cache para navegación,
   y cache-first para assets estáticos. */
const VERSION = 'v1.0.0';
const CACHE = `korva-${VERSION}`;
const APP_SHELL = [
  '/',
  '/static/pwa/manifest.json',
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png',
  '/static/pwa/apple-touch-icon.png',
];

/* Cachear el app shell al instalar */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch(() => {
            /* recurso opcional, ignorar error */
          })
        )
      );
    }).then(() => self.skipWaiting())
  );
});

/* Activar y limpiar cachés viejas */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  /* Solo GET */
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  /* No cachear API, admin ni mensajes en vivo (evita datos stale) */
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/admin') ||
      url.pathname.startsWith('/send-message/')) {
    return;
  }

  /* Estrategia network-first para navegación (HTML): la web es una red social
     con datos dinámicos, priorizamos red y usamos caché solo si offline. */
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) =>
            cached || caches.match('/')
          )
        )
    );
    return;
  }

  /* Cache-first (cache, luego red) para assets estáticos */
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});

/* ===== Notificaciones Push ===== */
self.addEventListener('push', (event) => {
  let data;
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Korva Nicaragua', body: event.data ? event.data.text() : '', url: '/' };
  }

  const title = data.title || 'Korva Nicaragua';
  const options = {
    body: data.body || '',
    icon: data.icon || '/static/pwa/icon-192.png',
    badge: data.badge || '/static/pwa/icon-192.png',
    data: { url: data.url || '/notifications/' },
    vibrate: [200, 100, 200],
    tag: data.tag || 'korva-notification',
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/notifications/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});