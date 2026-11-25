/* CSPC Lost & Found — interface behaviour
   Theme switch, drawer navigation, dialogs, confirm flow, toasts, filters,
   upload preview and small form helpers. No dependencies.
   The initial theme is resolved by the inline script in partials/head_common.html
   so the page never paints in the wrong theme. */
(function () {
  'use strict';

  var root = document.documentElement;
  var body = document.body;
  var reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------------ theme */
  var THEME_KEY = 'cspc-theme';

  function storedTheme() {
    try {
      var t = localStorage.getItem(THEME_KEY);
      return t === 'light' || t === 'dark' ? t : null;
    } catch (e) { return null; }
  }

  function paintTheme(theme) {
    root.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#e8eefb' : '#030d2e');
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      var dark = theme === 'dark';
      btn.setAttribute('aria-checked', dark ? 'true' : 'false');
      btn.setAttribute('aria-label', dark ? 'Dark theme' : 'Light theme');
      btn.setAttribute('title', dark ? 'Switch to light theme' : 'Switch to dark theme');
    });
  }

  function setTheme(theme, persist) {
    function change() { paintTheme(theme); }
    if (document.startViewTransition && !reduceMotion) {
      document.startViewTransition(change);
    } else if (!reduceMotion) {
      root.classList.add('theme-anim');
      change();
      setTimeout(function () { root.classList.remove('theme-anim'); }, 380);
    } else {
      change();
    }
    if (persist) {
      try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* storage unavailable */ }
    }
  }

  paintTheme(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');

  document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true);
    });
  });

  // Follow the operating system until the person makes an explicit choice.
  if (window.matchMedia) {
    var mq = matchMedia('(prefers-color-scheme: light)');
    var onSystemChange = function (e) { if (!storedTheme()) setTheme(e.matches ? 'light' : 'dark', false); };
    if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
  }
  // Keep other open tabs in step.
  window.addEventListener('storage', function (e) {
    if (e.key === THEME_KEY && (e.newValue === 'light' || e.newValue === 'dark')) paintTheme(e.newValue);
  });

  /* ------------------------------------------------------------ scroll lock */
  function syncLock() {
    var open = document.querySelector('.dialog.is-open, .sidebar.is-open');
    body.classList.toggle('nav-lock', !!open);
  }

  /* ---------------------------------------------------------------- sidebar */
  var sidebar = document.getElementById('appSidebar');
  var overlay = document.getElementById('sidebarOverlay');
  var menuBtn = document.getElementById('mobileMenuToggle');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('is-open');
    overlay && overlay.classList.add('is-open');
    menuBtn && menuBtn.setAttribute('aria-expanded', 'true');
    syncLock();
    var first = sidebar.querySelector('a, button');
    first && first.focus({ preventScroll: true });
  }
  function closeSidebar(restoreFocus) {
    if (!sidebar || !sidebar.classList.contains('is-open')) return;
    sidebar.classList.remove('is-open');
    overlay && overlay.classList.remove('is-open');
    menuBtn && menuBtn.setAttribute('aria-expanded', 'false');
    syncLock();
    if (restoreFocus && menuBtn) menuBtn.focus({ preventScroll: true });
  }
  menuBtn && menuBtn.addEventListener('click', openSidebar);
  overlay && overlay.addEventListener('click', function () { closeSidebar(true); });
  document.querySelectorAll('.nav__link').forEach(function (l) { l.addEventListener('click', function () { closeSidebar(false); }); });
  // Leaving the drawer layout (e.g. rotating a tablet) must not leave the page locked.
  if (window.matchMedia) {
    matchMedia('(min-width: 1024px)').addEventListener('change', function (e) { if (e.matches) closeSidebar(false); });
  }

  /* ---------------------------------------------------------------- dialogs */
  var lastTrigger = null;
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function openModal(id, trigger) {
    var el = document.getElementById(id);
    if (!el) return;
    lastTrigger = trigger || document.activeElement;
    el.classList.add('is-open');
    el.setAttribute('aria-hidden', 'false');
    syncLock();
    // Focus the first form field when there is one, otherwise the first control.
    var target = el.querySelector('input:not([type="hidden"]):not([type="file"]), textarea, select') || el.querySelector('button:not([data-close-dialog]), button');
    window.setTimeout(function () { target && target.focus({ preventScroll: true }); }, 30);
  }

  function closeModal(id) {
    var el = document.getElementById(id);
    if (!el || !el.classList.contains('is-open')) return;
    el.classList.remove('is-open');
    el.setAttribute('aria-hidden', 'true');
    syncLock();
    if (lastTrigger && document.body.contains(lastTrigger)) lastTrigger.focus({ preventScroll: true });
    lastTrigger = null;
  }

  window.openModal = openModal;
  window.closeModal = closeModal;

  document.addEventListener('click', function (e) {
    var opener = e.target.closest('[data-open-dialog]');
    if (opener) { e.preventDefault(); openModal(opener.getAttribute('data-open-dialog'), opener); return; }
    var closer = e.target.closest('[data-close-dialog]');
    if (closer) { var d = closer.closest('.dialog'); d && closeModal(d.id); return; }
    if (e.target.classList && e.target.classList.contains('dialog')) {
      if (e.target.id === 'confirmDialog') closeConfirm(); else closeModal(e.target.id);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var openDialog = document.querySelector('.dialog.is-open');
      if (openDialog) { if (openDialog.id === 'confirmDialog') closeConfirm(); else closeModal(openDialog.id); return; }
      closeSidebar(true);
      return;
    }
    if (e.key === 'Tab') {
      var dlg = document.querySelector('.dialog.is-open');
      var scope = dlg || (sidebar && sidebar.classList.contains('is-open') ? sidebar : null);
      if (!scope) return;
      var nodes = Array.prototype.filter.call(scope.querySelectorAll(FOCUSABLE), function (n) { return n.offsetParent !== null; });
      if (!nodes.length) return;
      var first = nodes[0], last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  /* ---------------------------------------------------------- confirm flow */
  var confirmDialog = document.getElementById('confirmDialog');
  var pendingForm = null;

  function closeConfirm() {
    if (!confirmDialog) return;
    confirmDialog.classList.remove('is-open');
    confirmDialog.setAttribute('aria-hidden', 'true');
    syncLock();
    if (lastTrigger && document.body.contains(lastTrigger)) lastTrigger.focus({ preventScroll: true });
    lastTrigger = null;
    pendingForm = null;
  }

  // Titles and messages are plain text set with textContent, so item names can
  // never be interpreted as markup or script.
  window.requestConfirm = function (formEl, title, message) {
    pendingForm = formEl;
    if (!confirmDialog) { formEl.submit(); return; }
    lastTrigger = document.activeElement;
    document.getElementById('confirmTitle').textContent = title || 'Are you sure?';
    document.getElementById('confirmMessage').textContent = message || 'This action cannot be undone.';
    confirmDialog.classList.add('is-open');
    confirmDialog.setAttribute('aria-hidden', 'false');
    syncLock();
    window.setTimeout(function () { document.getElementById('confirmProceed').focus({ preventScroll: true }); }, 30);
  };

  var cancelBtn = document.getElementById('confirmCancel');
  var proceedBtn = document.getElementById('confirmProceed');
  cancelBtn && cancelBtn.addEventListener('click', closeConfirm);
  proceedBtn && proceedBtn.addEventListener('click', function () {
    if (!pendingForm) return;
    var form = pendingForm;
    pendingForm = null;
    markBusy(form);
    form.submit();
  });

  /* ------------------------------------------------------------ form busy */
  function markBusy(form) {
    var btn = form.querySelector('[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.classList.add('is-busy');
    btn.setAttribute('aria-busy', 'true');
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.hasAttribute('data-confirm-title')) {
      e.preventDefault();
      window.requestConfirm(form, form.getAttribute('data-confirm-title'), form.getAttribute('data-confirm-message'));
      return;
    }
    markBusy(form);
  });

  // Coming back via the browser's back button must not leave buttons stuck.
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('.btn.is-busy').forEach(function (b) {
      b.disabled = false; b.classList.remove('is-busy'); b.removeAttribute('aria-busy');
    });
  });

  /* ----------------------------------------------------------------- toasts */
  function dismissToast(t) {
    if (!t || t.classList.contains('is-leaving')) return;
    t.classList.add('is-leaving');
    window.setTimeout(function () { t.remove(); }, 300);
  }
  document.querySelectorAll('.toast').forEach(function (t) {
    var delay = parseInt(t.getAttribute('data-auto-dismiss'), 10) || 5000;
    var timer = window.setTimeout(function () { dismissToast(t); }, delay);
    t.addEventListener('mouseenter', function () { window.clearTimeout(timer); });
    t.addEventListener('mouseleave', function () { timer = window.setTimeout(function () { dismissToast(t); }, 2400); });
  });
  document.addEventListener('click', function (e) {
    var close = e.target.closest('.toast__close');
    if (close) dismissToast(close.closest('.toast'));
  });

  /* ---------------------------------------------------------------- uploads */
  document.querySelectorAll('.upload input[type="file"]').forEach(function (input) {
    var box = input.closest('.upload');
    var preview = box.querySelector('.upload__preview');
    var label = box.querySelector('.upload__text');
    input.addEventListener('change', function () {
      var file = this.files && this.files[0];
      if (!file || !preview) return;
      var reader = new FileReader();
      reader.onload = function (ev) {
        preview.src = ev.target.result;
        preview.classList.add('is-visible');
        if (label) label.textContent = file.name;
      };
      reader.readAsDataURL(file);
    });
    ['dragenter', 'dragover'].forEach(function (n) { box.addEventListener(n, function () { box.classList.add('is-drag'); }); });
    ['dragleave', 'drop'].forEach(function (n) { box.addEventListener(n, function () { box.classList.remove('is-drag'); }); });
  });

  /* ---------------------------------------------------- auto-open report form */
  var errorDialog = document.querySelector('[data-open-on-load]');
  if (errorDialog) {
    openModal(errorDialog.id);
  } else if (new URLSearchParams(window.location.search).get('report') === '1') {
    var target = document.getElementById('reportLostModal') || document.getElementById('reportFoundModal');
    target && openModal(target.id);
  }

  /* ---------------------------------------------------------- status filter */
  document.querySelectorAll('[data-filter-bar]').forEach(function (bar) {
    var group = document.querySelector('[data-filter-group]');
    var empty = document.querySelector('[data-filter-empty]');
    if (!group) return;
    bar.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-filter]');
      if (!btn) return;
      bar.querySelectorAll('[data-filter]').forEach(function (chip) {
        var on = chip === btn;
        chip.classList.toggle('is-active', on);
        chip.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var value = btn.getAttribute('data-filter');
      var shown = 0;
      group.querySelectorAll('[data-status]').forEach(function (card) {
        var match = value === 'all' || card.getAttribute('data-status') === value;
        card.classList.toggle('is-filtered-out', !match);
        if (match) shown += 1;
      });
      if (empty) empty.classList.toggle('is-visible', shown === 0);
    });
  });

  /* -------------------------------------------------------- password reveal */
  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    var wrap = document.createElement('div');
    wrap.className = 'pw';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw__btn';
    btn.setAttribute('aria-label', 'Show password');
    btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = '<svg class="i" aria-hidden="true"><use href="#i-eye"/></svg>';
    wrap.appendChild(btn);
    btn.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', show ? 'true' : 'false');
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.querySelector('use').setAttribute('href', show ? '#i-eye-off' : '#i-eye');
      input.focus();
    });
  });

  /* ------------------------------------------------------- "/" focuses search */
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (document.querySelector('.dialog.is-open')) return;
    var field = document.querySelector('[data-search-hotkey]');
    if (field) { e.preventDefault(); field.focus(); field.select(); }
  });
})();
