/**
 * terminchen — Service Worker
 *
 * Features:
 *  - App shell cache (CSS, JS, icons) with stale-while-revalidate
 *  - Offline fallback page for navigation requests
 *  - Background sync: queued RSVP actions replay when back online
 *  - Push notifications: event reminders
 *  - Periodic background sync: refresh calendar data (Chromium only)
 */

var CACHE_NAME = 'terminchen-v7';
var OFFLINE_URL = '/offline';
var SYNC_TAG_RSVP = 'rsvp-sync';
var DB_NAME = 'terminchen-sw';
var STORE_NAME = 'pending-rsvps';

var SHELL_URLS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/rsvp.js',
  '/static/js/clipboard.js',
  '/static/js/countdown.js',
  '/static/manifest.json',
  '/static/icons/icon-48.png',
  '/static/icons/icon-72.png',
  '/static/icons/icon-96.png',
  '/static/icons/icon-128.png',
  '/static/icons/icon-144.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-256.png',
  '/static/icons/icon-384.png',
  '/static/icons/icon-512.png',
  OFFLINE_URL,
];


// ── IndexedDB helpers for offline RSVP queue ──

function openDB() {
  return new Promise(function (resolve, reject) {
    var req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = function (e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = function (e) { resolve(e.target.result); };
    req.onerror = function (e) { reject(e.target.error); };
  });
}

function addPendingRsvp(rsvpData) {
  return openDB().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).add(rsvpData);
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function (e) { reject(e.target.error); };
    });
  });
}

function getAllPendingRsvps() {
  return openDB().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE_NAME, 'readonly');
      var req = tx.objectStore(STORE_NAME).getAll();
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  });
}

function clearPendingRsvps() {
  return openDB().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).clear();
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function (e) { reject(e.target.error); };
    });
  });
}


// ── Install: pre-cache shell + offline page ──

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL_URLS);
    })
  );
  self.skipWaiting();
});


// ── Activate: clean old caches ──

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


// ── Fetch: navigation (offline fallback) + static (stale-while-revalidate) ──

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);

  // Only handle same-origin requests
  if (url.origin !== location.origin) return;

  // ── Navigation requests: network-first, offline fallback ──
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(function () {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  // ── RSVP API: intercept POST failures → queue for background sync ──
  if (url.pathname.match(/\/api\/cal\/[^/]+\/event\/[^/]+\/rsvp$/) &&
      e.request.method === 'POST') {
    e.respondWith(
      fetch(e.request.clone()).catch(function () {
        // Network failed — queue the request for background sync
        var ct = e.request.headers.get('content-type') || '';
        var bodyPromise = ct.indexOf('application/json') !== -1
          ? e.request.clone().json()
          : Promise.resolve({});
        return bodyPromise.then(function (body) {
          return addPendingRsvp({
            url: e.request.url,
            body: body,
            timestamp: Date.now(),
          }).then(function () {
            // Request background sync
            if (self.registration.sync) {
              return self.registration.sync.register(SYNC_TAG_RSVP);
            }
          }).then(function () {
            // Return a synthetic success response so UI updates optimistically
            return new Response(JSON.stringify({ ok: true, queued: true }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          });
        }).catch(function () {
          return new Response(JSON.stringify({ error: 'Offline. RSVP could not be queued.' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          });
        });
      })
    );
    return;
  }

  // ── Static assets: stale-while-revalidate ──
  if (!url.pathname.startsWith('/static/')) return;

  e.respondWith(
    caches.match(e.request).then(function (cached) {
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


// ── Background Sync: replay queued RSVPs ──

self.addEventListener('sync', function (e) {
  if (e.tag === SYNC_TAG_RSVP) {
    e.waitUntil(replayPendingRsvps());
  }
});

function replayPendingRsvps() {
  return getAllPendingRsvps().then(function (pending) {
    if (!pending.length) return;

    var promises = pending.map(function (item) {
      return fetch(item.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item.body),
        credentials: 'same-origin',
      });
    });

    return Promise.all(promises).then(function () {
      return clearPendingRsvps();
    });
  });
}


// ── Push Notifications ──

self.addEventListener('push', function (e) {
  if (!e.data) return;

  var payload;
  try {
    payload = e.data.json();
  } catch (err) {
    payload = { title: 'terminchen', body: e.data.text() };
  }

  var options = {
    body: payload.body || '',
    icon: payload.icon || '/static/icons/icon-192.png',
    badge: payload.badge || '/static/icons/icon-96.png',
    tag: payload.tag || 'terminchen',
    data: { url: payload.url || '/' },
    vibrate: [100, 50, 100],
    actions: [
      { action: 'open', title: 'Open' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
  };

  e.waitUntil(
    self.registration.showNotification(payload.title || 'terminchen', options)
  );
});

self.addEventListener('notificationclick', function (e) {
  e.notification.close();

  if (e.action === 'dismiss') return;

  var targetUrl = (e.notification.data && e.notification.data.url) || '/';

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windowClients) {
      // Focus existing window if already open
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url.indexOf(targetUrl) !== -1 && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});


// ── Periodic Background Sync (Chromium only) ──

self.addEventListener('periodicsync', function (e) {
  if (e.tag === 'refresh-calendars') {
    e.waitUntil(
      // Refresh the offline page cache so it stays current
      caches.open(CACHE_NAME).then(function (cache) {
        return cache.add(OFFLINE_URL);
      })
    );
  }
});
