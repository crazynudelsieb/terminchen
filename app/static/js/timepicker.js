/**
 * terminchen — Locale-aware time input with masked entry
 *
 * For 24h mode: displays a "__:__" mask. Digits fill from the right as you type
 * (e.g. 9→"__:_9", 90→"__:90", 900→"_9:00", 2000→"20:00"). Colon is always
 * visible and never needs to be typed. Cursor can be placed left or right of
 * the colon to edit hours or minutes directly.
 *
 * For 12h mode: free-text input with flexible parsing (AM/PM).
 *
 * Reads data-time-format="24"|"12" from the input itself or a parent element.
 */
(function () {
  'use strict';

  /* ── Helpers ──────────────────────────────────── */

  function getTimeFormat(el) {
    var fmt = el.getAttribute('data-time-format');
    if (fmt) return fmt;
    var parent = el.closest('[data-time-format]');
    if (parent) return parent.getAttribute('data-time-format');
    return '24';
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  var EMPTY_MASK = '\u2007\u2007:\u2007\u2007';   // figure-space padded  "  :  "

  /** Build display string from 4-char digit buffer "0900" → "09:00", empty slots → figure space */
  function maskFromDigits(digits) {
    var d = digits.split('');
    var fs = '\u2007';  // figure space (same width as a digit)
    return (d[0] || fs) + (d[1] || fs) + ':' + (d[2] || fs) + (d[3] || fs);
  }

  /** Strip non-digit chars from a string */
  function onlyDigits(s) { return s.replace(/\D/g, ''); }

  /** Convert 4-digit buffer to validated "HH:MM" or '' */
  function digitsToHHMM(digits) {
    if (digits.length !== 4) return '';
    var h = parseInt(digits.substring(0, 2), 10);
    var m = parseInt(digits.substring(2, 4), 10);
    if (h >= 0 && h <= 23 && m >= 0 && m <= 59) return pad(h) + ':' + pad(m);
    return '';
  }

  /** Format a 24h "HH:MM" string to display format */
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
   * Parse any free-text time string to 24h "HH:MM".
   * Handles: "14:30", "2:30 PM", "830", "2000", "19", "7pm", etc.
   */
  function parseTime(str, fmt) {
    if (!str) return '';
    str = str.trim();

    // HH:MM with optional AM/PM
    var colonMatch = str.match(/^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm|a|p)?$/i);
    if (colonMatch) {
      var h = parseInt(colonMatch[1], 10);
      var m = parseInt(colonMatch[2], 10);
      if (colonMatch[3]) {
        var per = colonMatch[3].toUpperCase();
        if (per.charAt(0) === 'P' && h !== 12) h += 12;
        if (per.charAt(0) === 'A' && h === 12) h = 0;
      }
      if (h >= 0 && h <= 23 && m >= 0 && m <= 59) return pad(h) + ':' + pad(m);
    }

    // 3-4 bare digits: last two = minutes
    var bareDigits = str.match(/^(\d{3,4})$/);
    if (bareDigits) {
      var raw = bareDigits[1].padStart(4, '0');
      return digitsToHHMM(raw);
    }

    // 1-2 bare digits: treat as hour
    var hourMatch = str.match(/^(\d{1,2})$/);
    if (hourMatch) {
      var hr = parseInt(hourMatch[1], 10);
      if (hr >= 0 && hr <= 23) return pad(hr) + ':00';
    }

    // Bare hour with AM/PM
    var hourAmpm = str.match(/^(\d{1,2})\s*(AM|PM|am|pm|a|p)$/i);
    if (hourAmpm) {
      var hv = parseInt(hourAmpm[1], 10);
      var pr = hourAmpm[2].toUpperCase();
      if (pr.charAt(0) === 'P' && hv !== 12) hv += 12;
      if (pr.charAt(0) === 'A' && hv === 12) hv = 0;
      return pad(hv) + ':00';
    }

    return '';
  }

  /* ── Masked input behaviour (24h) ────────────── */

  function initMaskedInput(textInput, hiddenInput, fmt) {
    // Internal state: 4-char string of digits (may have leading empty = '')
    var digits = '';

    // Initialise from existing value
    var initVal = hiddenInput.value || '';
    if (initVal && /^\d{2}:\d{2}$/.test(initVal)) {
      digits = initVal.replace(':', '');
    }

    function render() {
      textInput.value = digits.length ? maskFromDigits(digits.padStart(4, '0')) : EMPTY_MASK;
      if (digits.length === 4) {
        var valid = digitsToHHMM(digits);
        hiddenInput.value = valid;
        textInput.setCustomValidity(valid ? '' : 'Invalid time');
      } else {
        hiddenInput.value = '';
        textInput.setCustomValidity(digits.length ? '' : '');
      }
    }

    /** Place cursor after the last meaningful position */
    function setCursorEnd() {
      // always put cursor at the end of the display text
      var len = textInput.value.length;
      textInput.setSelectionRange(len, len);
    }

    render();

    // On focus: show mask, position cursor
    textInput.addEventListener('focus', function () {
      if (!textInput.value || textInput.value === textInput.placeholder) {
        textInput.value = EMPTY_MASK;
      }
      // small delay so the browser doesn't override cursor position
      setTimeout(setCursorEnd, 0);
    });

    // On blur: clean up display
    textInput.addEventListener('blur', function () {
      if (digits.length === 0) {
        textInput.value = '';
        hiddenInput.value = '';
        textInput.setCustomValidity('');
        return;
      }
      // Pad and validate
      var padded = digits.padStart(4, '0');
      var valid = digitsToHHMM(padded);
      if (valid) {
        digits = padded;
        hiddenInput.value = valid;
        textInput.value = formatTime(valid, fmt);
        textInput.setCustomValidity('');
      }
    });

    // Intercept all key input
    textInput.addEventListener('keydown', function (e) {
      // Allow Tab, Enter, Escape to pass through
      if (e.key === 'Tab' || e.key === 'Enter' || e.key === 'Escape') return;

      e.preventDefault();

      if (e.key === 'Backspace') {
        if (digits.length > 0) {
          digits = digits.substring(0, digits.length - 1);
          render();
        }
        return;
      }

      if (e.key === 'Delete') {
        digits = '';
        render();
        return;
      }

      // Only accept digit keys
      if (/^\d$/.test(e.key)) {
        if (digits.length >= 4) {
          // Field full — shift left: drop first digit, append new
          digits = digits.substring(1) + e.key;
        } else {
          digits += e.key;
        }
        render();
      }
    });

    // Handle paste & mobile input (beforeinput / input fallback)
    textInput.addEventListener('beforeinput', function (e) {
      if (e.inputType === 'insertText' || e.inputType === 'insertFromPaste') {
        e.preventDefault();
        var newDigits = onlyDigits(e.data || '');
        for (var i = 0; i < newDigits.length; i++) {
          if (digits.length >= 4) {
            digits = digits.substring(1) + newDigits[i];
          } else {
            digits += newDigits[i];
          }
        }
        render();
      }
      if (e.inputType === 'deleteContentBackward') {
        e.preventDefault();
        if (digits.length > 0) {
          digits = digits.substring(0, digits.length - 1);
          render();
        }
      }
      if (e.inputType === 'deleteContentForward' || e.inputType === 'deleteByCut') {
        e.preventDefault();
        digits = '';
        render();
      }
    });
  }

  /* ── Free-text input behaviour (12h) ─────────── */

  function initFreeTextInput(textInput, hiddenInput, fmt) {
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
        textInput.setCustomValidity('Please enter a time as h:MM AM/PM');
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
  }

  /* ── Enhancement entry point ─────────────────── */

  function enhanceTimeInputs() {
    var timeInputs = document.querySelectorAll('input[data-role="time"], input[type="time"]');

    timeInputs.forEach(function (original) {
      if (original.dataset.timeEnhanced) return;
      original.dataset.timeEnhanced = 'true';

      var fmt = getTimeFormat(original);
      var isoValue = original.value || '';
      var name = original.name;
      var id = original.id;
      var className = original.className;
      var isAlreadyText = (original.type === 'text');
      var textInput, hiddenInput;

      if (isAlreadyText) {
        // Input is already type="text" from HTML — enhance in-place
        original.inputMode = 'text';
        original.autocomplete = 'off';
        original.placeholder = fmt === '12' ? 'h:MM AM/PM' : 'HH:MM';

        hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = name;
        if (id) hiddenInput.id = id + '_hidden';
        hiddenInput.value = isoValue ? parseTime(isoValue, fmt) || isoValue : '';
        original.parentNode.insertBefore(hiddenInput, original.nextSibling);

        original.removeAttribute('name');
        if (id) original.id = id + '_display';

        // Format display value
        if (isoValue) {
          var parsed24 = parseTime(isoValue, fmt);
          if (parsed24) {
            original.value = formatTime(parsed24, fmt);
            hiddenInput.value = parsed24;
          }
        }

        textInput = original;
      } else {
        // Legacy type="time" — replace with text input
        textInput = document.createElement('input');
        textInput.type = 'text';
        textInput.className = className;
        textInput.placeholder = fmt === '12' ? 'h:MM AM/PM' : 'HH:MM';
        textInput.autocomplete = 'off';
        textInput.inputMode = 'text';
        textInput.value = formatTime(isoValue, fmt);
        if (id) textInput.id = id + '_display';

        hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = name;
        if (id) hiddenInput.id = id;
        hiddenInput.value = isoValue;

        var frag = document.createDocumentFragment();
        frag.appendChild(textInput);
        frag.appendChild(hiddenInput);
        original.parentNode.replaceChild(frag, original);
      }

      // Attach behaviour based on format
      if (fmt === '24') {
        initMaskedInput(textInput, hiddenInput, fmt);
      } else {
        // 12h: format existing value, then use free-text
        if (isoValue && !isAlreadyText) {
          textInput.value = formatTime(isoValue, fmt);
        }
        initFreeTextInput(textInput, hiddenInput, fmt);
      }
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceTimeInputs);
  } else {
    enhanceTimeInputs();
  }
})();
