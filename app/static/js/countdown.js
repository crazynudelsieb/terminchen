/**
 * terminchen — Event Countdown Widget
 *
 * Usage (embed on any page):
 *   <div id="zngai-countdown" data-token="SHARE_TOKEN" data-base="https://cal.example.com"></div>
 *   <script src="https://cal.example.com/static/js/countdown.js"></script>
 *
 * The widget fetches the next upcoming event and shows a live countdown.
 */
(function () {
  'use strict';

  var container = document.getElementById('zngai-countdown');
  if (!container) return;

  var token = container.getAttribute('data-token');
  var base = (container.getAttribute('data-base') || '').replace(/\/$/, '');
  if (!token) { container.textContent = 'Missing data-token.'; return; }

  var apiUrl = base + '/api/cal/' + token + '/next-event';

  // Minimal inline styles so the widget looks OK even without the host stylesheet
  container.style.cssText = container.style.cssText || [
    'font-family:system-ui,-apple-system,sans-serif',
    'background:#1a1a2e', 'color:#e0e0e0', 'border-radius:12px',
    'padding:1.2rem 1.5rem', 'max-width:360px', 'text-align:center',
  ].join(';');

  container.innerHTML = '<span style="opacity:.5">Loading…</span>';

  fetch(apiUrl)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.event) {
        container.innerHTML = '<p style="margin:0;opacity:.6">No upcoming events</p>';
        return;
      }
      render(data);
    })
    .catch(function () {
      container.innerHTML = '<p style="margin:0;color:#f66">Could not load event</p>';
    });

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function formatCountdownDate(dt, allDay, dateFmt, timeFmt) {
    var days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    var dayName = days[dt.getDay()];
    var d = pad(dt.getDate());
    var m = pad(dt.getMonth() + 1);
    var y = dt.getFullYear();
    var datePart = dateFmt === 'US' ? (m + '/' + d + '/' + y) : (d + '/' + m + '/' + y);
    if (allDay) return dayName + ', ' + datePart;
    var h = dt.getHours();
    var min = pad(dt.getMinutes());
    if (timeFmt === '12') {
      var suffix = h >= 12 ? 'PM' : 'AM';
      var h12 = h % 12 || 12;
      return dayName + ', ' + datePart + ' ' + h12 + ':' + min + ' ' + suffix;
    }
    return dayName + ', ' + datePart + ' ' + pad(h) + ':' + min;
  }

  function render(data) {
    var ev = data.event;
    var cal = data.calendar;
    var start = new Date(ev.start_time + (ev.start_time.endsWith('Z') ? '' : 'Z'));

    var title = document.createElement('div');
    title.style.cssText = 'font-size:1.1rem;font-weight:600;margin-bottom:.4rem';
    title.textContent = ev.title;

    var dateEl = document.createElement('div');
    dateEl.style.cssText = 'font-size:.85rem;opacity:.7;margin-bottom:.6rem';
    dateEl.textContent = formatCountdownDate(start, ev.all_day, cal.date_format, cal.time_format);

    var countdown = document.createElement('div');
    countdown.style.cssText = 'font-size:1.3rem;font-weight:700;letter-spacing:.5px';

    var calName = document.createElement('div');
    calName.style.cssText = 'font-size:.7rem;opacity:.4;margin-top:.5rem';
    calName.textContent = cal.name;

    container.innerHTML = '';
    container.appendChild(title);
    container.appendChild(dateEl);
    container.appendChild(countdown);
    container.appendChild(calName);

    function tick() {
      var now = Date.now();
      var diff = start.getTime() - now;
      if (diff <= 0) {
        countdown.textContent = 'Happening now!';
        return;
      }
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var s = Math.floor((diff % 60000) / 1000);
      var parts = [];
      if (d > 0) parts.push(d + 'd');
      parts.push(h + 'h');
      parts.push(m + 'm');
      parts.push(s + 's');
      countdown.textContent = parts.join(' ');
    }

    tick();
    setInterval(tick, 1000);
  }
})();
