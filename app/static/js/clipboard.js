/**
 * terminchen — copy-to-clipboard + QR toggle
 */

(function () {
    'use strict';

    // ── Copy buttons ──
    document.querySelectorAll('.btn-copy').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var targetId = btn.dataset.copyTarget;
            var input = document.getElementById(targetId);
            if (!input) return;

            navigator.clipboard.writeText(input.value).then(function () {
                var orig = btn.textContent;
                btn.textContent = '✓';
                setTimeout(function () { btn.textContent = orig; }, 1500);
            }).catch(function () {
                // Fallback: select the text
                input.select();
                input.setSelectionRange(0, 99999);
            });
        });
    });

    // ── QR toggle buttons ──
    document.querySelectorAll('.btn-qr-toggle').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var row = btn.closest('.share-link-row');
            if (!row) return;
            var container = row.querySelector('.share-qr-inline');
            if (!container) return;

            // Toggle visibility
            if (container.style.display !== 'none') {
                container.style.display = 'none';
                return;
            }
            // Lazy-load image
            if (!container.querySelector('img')) {
                var img = document.createElement('img');
                img.src = btn.dataset.qrSrc;
                img.alt = 'QR code';
                img.width = 160;
                img.height = 160;
                container.appendChild(img);
            }
            container.style.display = 'block';
        });
    });
})();
