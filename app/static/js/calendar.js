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

    // Encode current page URL so the create-event form can return here
    var returnTo = encodeURIComponent(window.location.href);

    // Delegate clicks on month cells and week day blocks
    container.addEventListener('click', function (e) {
        // Don't intercept clicks on links or buttons inside the cell
        if (e.target.closest('a, button, .event-card')) return;

        var cell = e.target.closest('[data-date]');
        if (!cell) return;

        var dateVal = cell.dataset.date;
        if (dateVal) {
            window.location.href = createUrl + sep + 'date=' + dateVal + '&return_to=' + returnTo;
        }
    });

    // Visual hint: cursor pointer on clickable cells
    container.querySelectorAll('[data-date]').forEach(function (el) {
        el.style.cursor = 'pointer';
    });

    // ── Append return_to to event detail links ──
    // So the back button on event detail returns to this exact calendar view.
    container.querySelectorAll('a[href*="/event/"]').forEach(function (link) {
        var href = link.getAttribute('href');
        // Only patch internal event detail links (skip external URLs like location)
        if (href && !href.match(/^https?:\/\//) && href.indexOf('/event/') !== -1) {
            var linkSep = href.indexOf('?') === -1 ? '?' : '&';
            link.setAttribute('href', href + linkSep + 'return_to=' + returnTo);
        }
    });
})();
