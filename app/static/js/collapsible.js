/**
 * terminchen — reusable collapsible section helpers
 */

(function () {
    'use strict';

    function getIndicatorForBody(body) {
        if (!body || !body.id) return null;
        var header = document.querySelector('.collapsible-header[data-toggle="' + body.id + '"]');
        return header ? header.querySelector('.collapse-indicator') : null;
    }

    function setSectionCollapsed(bodyId, collapsed) {
        var body = document.getElementById(bodyId);
        if (!body) return;
        var indicator = getIndicatorForBody(body);
        if (collapsed) {
            body.style.display = 'none';
            if (indicator) indicator.textContent = '▸';
        } else {
            body.style.display = '';
            if (indicator) indicator.textContent = '▾';
        }
    }

    function initCollapsibleSections() {
        document.querySelectorAll('.collapsible-header').forEach(function (header) {
            if (header.dataset.collapsibleBound === '1') return;
            header.dataset.collapsibleBound = '1';

            header.addEventListener('click', function () {
                var targetId = this.getAttribute('data-toggle');
                var body = document.getElementById(targetId);
                var indicator = this.querySelector('.collapse-indicator');
                if (!body || !indicator) return;

                if (body.style.display === 'none') {
                    body.style.display = '';
                    indicator.textContent = '▾';
                } else {
                    body.style.display = 'none';
                    indicator.textContent = '▸';
                }
            });
        });
    }

    window.initCollapsibleSections = initCollapsibleSections;
    window.setSectionCollapsed = setSectionCollapsed;
})();
