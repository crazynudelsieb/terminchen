/**
 * terminchen — Locale-aware date input wrapper
 *
 * Replaces native <input type="date"> (which uses browser locale)
 * with a text input that shows the date in the calendar's configured format
 * (EU = dd.mm.yyyy, US = mm/dd/yyyy) while keeping a hidden field with ISO value.
 *
 * Usage: Add class="date-input-wrap" and data-date-format="EU"|"US" to the input,
 * or set a global data-date-format on a parent .calendar-container / form.
 */
(function () {
  'use strict';

  // Detect the calendar's configured date format from the page
  function getDateFormat(el) {
    // Check the element itself first
    var fmt = el.getAttribute('data-date-format');
    if (fmt) return fmt;
    // Walk up to find a parent with the setting
    var parent = el.closest('[data-date-format]');
    if (parent) return parent.getAttribute('data-date-format');
    // Fallback
    return 'EU';
  }

  // Format an ISO date string (YYYY-MM-DD) to display format
  function formatDate(isoStr, fmt) {
    if (!isoStr) return '';
    var parts = isoStr.split('-');
    if (parts.length !== 3) return isoStr;
    var y = parts[0], m = parts[1], d = parts[2];
    if (fmt === 'US') {
      return m + '/' + d + '/' + y;
    }
    return d + '.' + m + '.' + y;
  }

  // Parse a display-format date back to ISO (YYYY-MM-DD)
  function parseDate(displayStr, fmt) {
    if (!displayStr) return '';
    // Already ISO format
    if (/^\d{4}-\d{2}-\d{2}$/.test(displayStr)) return displayStr;
    // Accept both slash and dot separators for user convenience.
    var parts = displayStr.split(/[\/.]/);
    if (parts.length !== 3) return displayStr;
    if (fmt === 'US') {
      // mm/dd/yyyy
      return parts[2] + '-' + parts[0].padStart(2, '0') + '-' + parts[1].padStart(2, '0');
    }
    // dd.mm.yyyy (EU)
    return parts[2] + '-' + parts[1].padStart(2, '0') + '-' + parts[0].padStart(2, '0');
  }

  // Get placeholder text for the format
  function getPlaceholder(fmt) {
    return fmt === 'US' ? 'mm/dd/yyyy' : 'dd.mm.yyyy';
  }

  // Enhance all date inputs on the page
  function enhanceDateInputs() {
    var dateInputs = document.querySelectorAll('input[type="date"]');

    dateInputs.forEach(function (original) {
      // Skip already-enhanced inputs
      if (original.dataset.enhanced) return;
      original.dataset.enhanced = 'true';

      var fmt = getDateFormat(original);
      var isoValue = original.value || '';
      var name = original.name;
      var id = original.id;
      var required = original.required;
      var className = original.className;
      var title = original.title;

      // Create the visible text input
      var textInput = document.createElement('input');
      textInput.type = 'text';
      textInput.className = className;
      textInput.placeholder = getPlaceholder(fmt);
      textInput.title = title || getPlaceholder(fmt).toUpperCase();
      textInput.autocomplete = 'off';
      textInput.value = formatDate(isoValue, fmt);
      if (id) textInput.id = id + '_display';
      if (required) textInput.required = true;

      // Create hidden input that holds the ISO value for the server
      var hiddenInput = document.createElement('input');
      hiddenInput.type = 'hidden';
      hiddenInput.name = name;
      if (id) hiddenInput.id = id;
      hiddenInput.value = isoValue;

      // Create a small calendar button to open native picker
      var pickerBtn = document.createElement('button');
      pickerBtn.type = 'button';
      pickerBtn.className = 'btn-date-picker';
      pickerBtn.textContent = '📅';
      pickerBtn.title = 'Open date picker';
      pickerBtn.setAttribute('aria-label', 'Open date picker');

      // Hidden native date input for the picker popup
      var nativePicker = document.createElement('input');
      nativePicker.type = 'date';
      nativePicker.className = 'native-date-picker-hidden';
      nativePicker.tabIndex = -1;
      nativePicker.setAttribute('aria-hidden', 'true');
      nativePicker.value = isoValue;

      // Wrapper
      var wrapper = document.createElement('div');
      wrapper.className = 'date-input-wrapper';
      wrapper.appendChild(textInput);
      wrapper.appendChild(pickerBtn);
      wrapper.appendChild(nativePicker);
      wrapper.appendChild(hiddenInput);

      // Replace original
      original.parentNode.replaceChild(wrapper, original);

      // === Event handlers ===

      // When user types in the text input, parse and update hidden field
      textInput.addEventListener('input', function () {
        var val = textInput.value.trim();
        // Auto-insert slashes as user types
        var iso = parseDate(val, fmt);
        if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
          hiddenInput.value = iso;
          nativePicker.value = iso;
          textInput.setCustomValidity('');
        } else if (val === '') {
          hiddenInput.value = '';
          nativePicker.value = '';
          textInput.setCustomValidity('');
        } else {
          hiddenInput.value = '';
          textInput.setCustomValidity('Please enter a date as ' + getPlaceholder(fmt).toUpperCase());
        }
      });

      textInput.addEventListener('blur', function () {
        // On blur, try to reformat what they typed
        var val = textInput.value.trim();
        if (!val) return;
        var iso = parseDate(val, fmt);
        if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
          textInput.value = formatDate(iso, fmt);
          hiddenInput.value = iso;
          nativePicker.value = iso;
        }
      });

      // Calendar button opens native picker
      pickerBtn.addEventListener('click', function () {
        nativePicker.showPicker ? nativePicker.showPicker() : nativePicker.click();
      });

      // When native picker changes, update text and hidden
      nativePicker.addEventListener('change', function () {
        var iso = nativePicker.value;
        textInput.value = formatDate(iso, fmt);
        hiddenInput.value = iso;
        textInput.setCustomValidity('');
      });
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceDateInputs);
  } else {
    enhanceDateInputs();
  }
})();
