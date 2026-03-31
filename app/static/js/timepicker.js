/**
 * terminchen — Locale-aware time input wrapper
 *
 * Replaces native <input type="time"> (which uses browser locale for 12/24h)
 * with a text input that shows the time in the calendar's configured format
 * (24h = HH:MM, 12h = h:MM AM/PM) while keeping a hidden field with 24h value.
 *
 * Reads data-time-format="24"|"12" from the input itself or a parent element.
 */
(function () {
  'use strict';

  function getTimeFormat(el) {
    var fmt = el.getAttribute('data-time-format');
    if (fmt) return fmt;
    var parent = el.closest('[data-time-format]');
    if (parent) return parent.getAttribute('data-time-format');
    return '24';
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  /**
   * Format a 24h "HH:MM" string to the display format.
   */
  function formatTime(hhmm, fmt) {
    if (!hhmm) return '';
    var parts = hhmm.split(':');
    if (parts.length < 2) return hhmm;
    var h = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10);
    if (isNaN(h) || isNaN(m)) return hhmm;

    if (fmt === '12') {
      var suffix = h >= 12 ? 'PM' : 'AM';
      var h12 = h % 12 || 12;
      return h12 + ':' + pad(m) + ' ' + suffix;
    }
    return pad(h) + ':' + pad(m);
  }

  /**
   * Parse a display-format time string back to 24h "HH:MM".
   * Handles: "14:30", "2:30 PM", "2:30PM", "2:30 pm", "14:30", "9:05 AM"
   */
  function parseTime(str, fmt) {
    if (!str) return '';
    str = str.trim();

    // Already 24h HH:MM
    if (/^\d{1,2}:\d{2}$/.test(str) && fmt === '24') {
      var p = str.split(':');
      return pad(parseInt(p[0], 10)) + ':' + pad(parseInt(p[1], 10));
    }

    // Try to parse AM/PM format
    var ampmMatch = str.match(/^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm|a|p)$/i);
    if (ampmMatch) {
      var h = parseInt(ampmMatch[1], 10);
      var m = parseInt(ampmMatch[2], 10);
      var period = ampmMatch[3].toUpperCase();
      if (period.charAt(0) === 'P' && h !== 12) h += 12;
      if (period.charAt(0) === 'A' && h === 12) h = 0;
      return pad(h) + ':' + pad(m);
    }

    // Try bare HH:MM (could be 24h input in 12h mode)
    var bareMatch = str.match(/^(\d{1,2}):(\d{2})$/);
    if (bareMatch) {
      var hh = parseInt(bareMatch[1], 10);
      var mm = parseInt(bareMatch[2], 10);
      if (hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59) {
        return pad(hh) + ':' + pad(mm);
      }
    }

    // Try bare hour (e.g. "19" or "7")
    var hourMatch = str.match(/^(\d{1,2})$/);
    if (hourMatch) {
      var hr = parseInt(hourMatch[1], 10);
      if (hr >= 0 && hr <= 23) {
        return pad(hr) + ':00';
      }
    }

    // Try bare hour with AM/PM (e.g. "7pm", "7 pm")
    var hourAmpmMatch = str.match(/^(\d{1,2})\s*(AM|PM|am|pm|a|p)$/i);
    if (hourAmpmMatch) {
      var hv = parseInt(hourAmpmMatch[1], 10);
      var per = hourAmpmMatch[2].toUpperCase();
      if (per.charAt(0) === 'P' && hv !== 12) hv += 12;
      if (per.charAt(0) === 'A' && hv === 12) hv = 0;
      return pad(hv) + ':00';
    }

    return '';
  }

  function getPlaceholder(fmt) {
    return fmt === '12' ? 'h:MM AM/PM' : 'HH:MM';
  }

  function enhanceTimeInputs() {
    var timeInputs = document.querySelectorAll('input[type="time"]');

    timeInputs.forEach(function (original) {
      if (original.dataset.timeEnhanced) return;
      original.dataset.timeEnhanced = 'true';

      var fmt = getTimeFormat(original);
      var isoValue = original.value || '';  // "HH:MM" 24h format
      var name = original.name;
      var id = original.id;
      var className = original.className;

      // Create visible text input
      var textInput = document.createElement('input');
      textInput.type = 'text';
      textInput.className = className;
      textInput.placeholder = getPlaceholder(fmt);
      textInput.autocomplete = 'off';
      textInput.inputMode = fmt === '12' ? 'text' : 'numeric';
      textInput.value = formatTime(isoValue, fmt);
      if (id) textInput.id = id + '_display';

      // Hidden input with 24h value for the server
      var hiddenInput = document.createElement('input');
      hiddenInput.type = 'hidden';
      hiddenInput.name = name;
      if (id) hiddenInput.id = id;
      hiddenInput.value = isoValue;

      // Replace original
      var frag = document.createDocumentFragment();
      frag.appendChild(textInput);
      frag.appendChild(hiddenInput);
      original.parentNode.replaceChild(frag, original);

      // === Event handlers ===

      textInput.addEventListener('input', function () {
        var val = textInput.value.trim();
        var parsed = parseTime(val, fmt);
        if (parsed) {
          hiddenInput.value = parsed;
          textInput.setCustomValidity('');
        } else if (val === '') {
          hiddenInput.value = '';
          textInput.setCustomValidity('');
        } else {
          hiddenInput.value = '';
          textInput.setCustomValidity('Please enter a time as ' + getPlaceholder(fmt));
        }
      });

      textInput.addEventListener('blur', function () {
        var val = textInput.value.trim();
        if (!val) return;
        var parsed = parseTime(val, fmt);
        if (parsed) {
          textInput.value = formatTime(parsed, fmt);
          hiddenInput.value = parsed;
          textInput.setCustomValidity('');
        }
      });
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceTimeInputs);
  } else {
    enhanceTimeInputs();
  }
})();
