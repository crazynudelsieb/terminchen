/**
 * terminchen — RSVP interactions
 * Supports both the full RSVP widget (event detail) and quick RSVP (event cards).
 */

(function () {
    'use strict';

    var MEMBER_KEY_PREFIX = 'terminchen_member_';
    var LEGACY_MEMBER_KEY_PREFIX = 'zngai_member_';

    // ── Restore remembered member selections from localStorage ──

    function rememberMember(shareToken, memberId) {
        try {
            localStorage.setItem(MEMBER_KEY_PREFIX + shareToken, memberId);
            // Keep legacy key in sync for older clients/pages.
            localStorage.setItem(LEGACY_MEMBER_KEY_PREFIX + shareToken, memberId);
        } catch(e) {}
    }

    function getRememberedMember(shareToken) {
        try {
            return (
                localStorage.getItem(MEMBER_KEY_PREFIX + shareToken) ||
                localStorage.getItem(LEGACY_MEMBER_KEY_PREFIX + shareToken) ||
                ''
            );
        } catch(e) {
            return '';
        }
    }

    function autoSelectMember(selectEl, shareToken) {
        if (selectEl && !selectEl.value) {
            var saved = getRememberedMember(shareToken);
            if (saved) {
                selectEl.value = saved;
            }
        }
    }

    // ── Full RSVP widget (event detail page) ──────────

    var widget = document.querySelector('.rsvp-widget');
    if (widget) {
        initFullWidget(widget);
    }

    // ── Quick RSVP widgets (calendar views) ───────────

    document.querySelectorAll('.quick-rsvp').forEach(function (qr) {
        initQuickRsvp(qr);
    });

    function initFullWidget(widget) {
        var eventId = widget.dataset.eventId;
        var shareToken = widget.dataset.shareToken;
        var memberSelect = document.getElementById('rsvp-member-select');
        var buttons = widget.querySelectorAll('.btn-rsvp');

        // Auto-select remembered member
        autoSelectMember(memberSelect, shareToken);

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var memberId = memberSelect.value;
                if (!memberId) {
                    alert('Please select your name first.');
                    return;
                }
                rememberMember(shareToken, memberId);
                submitRsvp(shareToken, eventId, memberId, btn.dataset.status, function () {
                    buttons.forEach(function (b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    refreshRsvpLists(shareToken, eventId);
                });
            });
        });
    }

    function initQuickRsvp(container) {
        var eventId = container.dataset.eventId;
        var shareToken = container.dataset.shareToken;
        var select = container.querySelector('.quick-rsvp-select');
        var buttons = container.querySelectorAll('.btn-rsvp-quick');

        // Prefer server-side remembered member from session when present.
        if (select && !select.value && container.dataset.selectedMemberId) {
            select.value = container.dataset.selectedMemberId;
        }

        // Auto-select remembered member
        autoSelectMember(select, shareToken);

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var memberId = select.value;
                if (!memberId) {
                    alert('Please select your name first.');
                    return;
                }
                rememberMember(shareToken, memberId);
                submitRsvp(shareToken, eventId, memberId, btn.dataset.status, function () {
                    buttons.forEach(function (b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    // Update badge counts on the card
                    refreshQuickBadges(container, shareToken, eventId);
                });
            });
        });
    }

    function submitRsvp(shareToken, eventId, memberId, status, onSuccess) {
        var url = '/api/cal/' + shareToken + '/event/' + eventId + '/rsvp';

        window.apiFetch(url, {
            method: 'POST',
            body: JSON.stringify({ member_id: memberId, status: status }),
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.ok) {
                onSuccess();
            } else {
                alert(data.error || 'Failed to update RSVP.');
            }
        })
        .catch(function () {
            alert('Network error. Please try again.');
        });
    }

    function esc(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

    function isValidColor(c) {
        return /^#[0-9A-Fa-f]{3,6}$/.test(c);
    }

    function refreshRsvpLists(shareToken, eventId) {
        var url = '/api/cal/' + shareToken + '/event/' + eventId + '/rsvp';

        window.apiFetch(url, { method: 'GET' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var container = document.getElementById('rsvp-lists');
            if (!container) return;

            var html = '';
            var groups = [
                { key: 'in', label: 'Attending', cssClass: 'rsvp-group-in' },
                { key: 'maybe', label: 'Maybe', cssClass: 'rsvp-group-maybe' },
                { key: 'out', label: 'Not attending', cssClass: 'rsvp-group-out' },
                { key: 'no_response', label: 'No response', cssClass: 'rsvp-group-none' },
            ];

            groups.forEach(function (g) {
                var members = data.rsvps[g.key] || [];
                if (members.length === 0) return;

                html += '<div class="rsvp-group ' + esc(g.cssClass) + '">';
                html += '<h4>' + esc(g.label) + ' (' + members.length + ')</h4>';
                html += '<ul>';
                members.forEach(function (m) {
                    var avatarHtml;
                    var safeColor = isValidColor(m.color) ? m.color : '#999';
                    if (m.avatar_url) {
                        avatarHtml = '<span class="avatar avatar-sm" style="--avatar-color:' + safeColor + ';"><img src="' + esc(m.avatar_url) + '" alt="' + esc(m.name) + '" loading="lazy"></span>';
                    } else {
                        var initials = (m.name || '?').charAt(0).toUpperCase();
                        avatarHtml = '<span class="avatar avatar-sm" style="--avatar-color:' + safeColor + ';"><span class="avatar-initials">' + esc(initials) + '</span></span>';
                    }
                    html += '<li>' + avatarHtml + ' ' + esc(m.name) + '</li>';
                });
                html += '</ul></div>';
            });

            container.innerHTML = html;
        });
    }

    function refreshQuickBadges(container, shareToken, eventId) {
        var url = '/api/cal/' + shareToken + '/event/' + eventId + '/rsvp';

        window.apiFetch(url, { method: 'GET' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var badges = container.closest('.event-card');
            if (!badges) return;
            var summaryEl = badges.querySelector('.event-rsvp-summary');
            if (!summaryEl) return;

            var counts = { in: 0, maybe: 0, out: 0 };
            ['in', 'maybe', 'out'].forEach(function (s) {
                counts[s] = (data.rsvps[s] || []).length;
            });

            var html = '';
            if (counts['in']) html += '<span class="rsvp-badge rsvp-badge-in">\u2713 ' + counts['in'] + '</span>';
            if (counts['maybe']) html += '<span class="rsvp-badge rsvp-badge-maybe">? ' + counts['maybe'] + '</span>';
            if (counts['out']) html += '<span class="rsvp-badge rsvp-badge-out">\u2717 ' + counts['out'] + '</span>';
            summaryEl.innerHTML = html;
        });
    }
})();
