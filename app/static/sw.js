/**
 * terminchen — Service Worker (offline shell cache)
 *
 * Caches the app shell (CSS, JS, icons) so the calendar loads faster on repeat
 * visits. API/HTML requests always go to the network (no stale data).
 */

var CACHE_NAME = 'terminchen-v3';
var SHELL_URLS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/rsvp.js',
  '/static/js/clipboard.js',
  '/static/js/countdown.js',
  '/static/manifest.json',
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL_URLS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (n) { return n !== CACHE_NAME; })
          .map(function (n) { return caches.delete(n); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);

  // Only cache same-origin static assets
  if (url.origin !== location.origin) return;
  if (!url.pathname.startsWith('/static/')) return;

  e.respondWith(
    caches.match(e.request).then(function (cached) {
      // Serve from cache, but also update cache in background
      var fetchPromise = fetch(e.request).then(function (response) {
        if (response.ok) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function () {
        return cached;
      });

      return cached || fetchPromise;
    })
  );
});
