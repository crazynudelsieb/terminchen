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
})();
