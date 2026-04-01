/**
 * terminchen — shared utilities
 */

(function () {
    'use strict';

    // Auto-dismiss flash messages after 5 seconds
    document.querySelectorAll('.flash').forEach(function (el) {
        setTimeout(function () {
            el.style.transition = 'opacity 0.3s ease';
            el.style.opacity = '0';
            setTimeout(function () { el.remove(); }, 300);
        }, 5000);
    });

    /**
     * Simple fetch wrapper with CSRF token from meta or cookie.
     * @param {string} url
     * @param {object} options
     * @returns {Promise<Response>}
     */
    window.apiFetch = function (url, options) {
        options = options || {};
        options.headers = options.headers || {};
        options.headers['Content-Type'] = 'application/json';
        // Include CSRF token for state-changing requests
        var csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            options.headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
        }
        options.credentials = 'same-origin';
        return fetch(url, options);
    };

    // ── Delete confirmations ──────────────────────────
    // Any button/submit with class .btn-confirm-delete and data-confirm
    // will show a browser confirm dialog before proceeding.
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.btn-confirm-delete');
        if (!btn) return;
        var msg = btn.getAttribute('data-confirm') || 'Are you sure?';
        if (!confirm(msg)) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    // ── Push Notification opt-in ──────────────────────
    // Footer buttons with class .btn-push-subscribe trigger subscription.
    // Hidden on non-calendar pages (no share_token).
    document.querySelectorAll('.btn-push-subscribe').forEach(function (btn) {
        var shareToken = btn.dataset.shareToken;
        if (!shareToken) {
            btn.style.display = 'none';
            return;
        }
        btn.addEventListener('click', function () {
            subscribeToPush(shareToken, btn);
        });
    });

    function subscribeToPush(shareToken, btn) {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            alert('Push notifications are not supported in this browser.');
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Subscribing…';

        // 1) Get the VAPID public key from the server
        fetch('/api/push/vapid-key')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.enabled) {
                alert('Push notifications are not enabled on this server.');
                btn.disabled = false;
                btn.textContent = '🔔 Notifications';
                return;
            }

            var publicKey = urlBase64ToUint8Array(data.key);

            return navigator.serviceWorker.ready.then(function (reg) {
                return reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: publicKey,
                });
            });
        })
        .then(function (subscription) {
            if (!subscription) return;

            // 2) Send the subscription to the server
            var sub = subscription.toJSON();
            return window.apiFetch('/api/cal/' + shareToken + '/push/subscribe', {
                method: 'POST',
                body: JSON.stringify({
                    endpoint: sub.endpoint,
                    keys: sub.keys,
                }),
            });
        })
        .then(function (res) {
            if (res && res.ok) {
                btn.textContent = '🔔 Subscribed';
                btn.classList.add('btn-push-active');
            }
        })
        .catch(function (err) {
            console.error('Push subscription failed:', err);
            btn.disabled = false;
            btn.textContent = '🔔 Notifications';
            if (err && err.name === 'NotAllowedError') {
                alert('Notification permission was denied. Enable it in your browser settings.');
            }
        });
    }

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; i++) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    // ── Periodic Background Sync registration ────────
    // Register for periodic sync if supported (Chromium only).
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready.then(function (reg) {
            if ('periodicSync' in reg) {
                reg.periodicSync.register('refresh-calendars', {
                    minInterval: 12 * 60 * 60 * 1000, // 12 hours
                }).catch(function () {
                    // Permission denied or not supported — silently ignore
                });
            }
        });
    }
})();
