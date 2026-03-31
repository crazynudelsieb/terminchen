/**
 * terminchen — calendar view interactions
 */

(function () {
    'use strict';

    // ── Click day to create event ──
    var container = document.querySelector('.calendar-container');
    if (!container) return;
    var createUrl = container.dataset.createUrl;
    if (!createUrl) return;

    // Separator for query params
    var sep = createUrl.indexOf('?') === -1 ? '?' : '&';

    // Delegate clicks on month cells and week day blocks
    container.addEventListener('click', function (e) {
        // Don't intercept clicks on links or buttons inside the cell
        if (e.target.closest('a, button, .event-card')) return;

        var cell = e.target.closest('[data-date]');
        if (!cell) return;

        var dateVal = cell.dataset.date;
        if (dateVal) {
            window.location.href = createUrl + sep + 'date=' + dateVal;
        }
    });

    // Visual hint: cursor pointer on clickable cells
    container.querySelectorAll('[data-date]').forEach(function (el) {
        el.style.cursor = 'pointer';
    });
})();
