/* CSPC Lost & Found — interface behavior */
(function () {
  'use strict';

  var sidebar = document.getElementById('appSidebar');
  var sidebarOverlay = document.getElementById('sidebarOverlay');
  var mobileToggle = document.getElementById('mobileMenuToggle');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('is-open');
    sidebarOverlay && sidebarOverlay.classList.add('is-open');
    document.body.classList.add('nav-lock');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'true');
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    sidebarOverlay && sidebarOverlay.classList.remove('is-open');
    document.body.classList.remove('nav-lock');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'false');
  }

  mobileToggle && mobileToggle.addEventListener('click', openSidebar);
  sidebarOverlay && sidebarOverlay.addEventListener('click', closeSidebar);
  document.querySelectorAll('.sidebar-link').forEach(function (link) {
    link.addEventListener('click', closeSidebar);
  });

  function openModal(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.add('is-open');
    document.body.classList.add('nav-lock');
    var focusable = el.querySelector('input, textarea, select, button');
    if (focusable) focusable.focus();
  }

  function closeModal(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('is-open');
    if (!document.querySelector('.modal-overlay.is-open, .confirm-dialog.is-open, .sidebar.is-open')) {
      document.body.classList.remove('nav-lock');
    }
  }

  document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal(overlay.id);
    });
  });

  window.openModal = openModal;
  window.closeModal = closeModal;

  document.querySelectorAll('.alert[data-auto-dismiss]').forEach(function (alert) {
    var delay = parseInt(alert.dataset.autoDismiss, 10) || 4000;
    setTimeout(function () {
      alert.classList.add('is-leaving');
      setTimeout(function () { alert.remove(); }, 380);
    }, delay);
  });

  var pendingForm = null;
  var confirmDialog = document.getElementById('confirmDialog');

  function closeConfirm() {
    confirmDialog && confirmDialog.classList.remove('is-open');
    if (!document.querySelector('.modal-overlay.is-open, .sidebar.is-open')) {
      document.body.classList.remove('nav-lock');
    }
    pendingForm = null;
  }

  window.requestConfirm = function (formEl, title, message) {
    pendingForm = formEl;
    if (!confirmDialog) {
      formEl.submit();
      return;
    }
    document.getElementById('confirmTitle').textContent = title || 'Are you sure?';
    document.getElementById('confirmMessage').textContent = message || 'This action cannot be undone.';
    confirmDialog.classList.add('is-open');
    document.body.classList.add('nav-lock');
    document.getElementById('confirmProceed').focus();
  };

  document.getElementById('confirmCancel') && document.getElementById('confirmCancel').addEventListener('click', closeConfirm);
  confirmDialog && confirmDialog.addEventListener('click', function (e) {
    if (e.target === confirmDialog) closeConfirm();
  });

  document.getElementById('confirmProceed') && document.getElementById('confirmProceed').addEventListener('click', function () {
    if (pendingForm) {
      markBusy(pendingForm);
      var form = pendingForm;
      pendingForm = null;
      form.submit();
    }
  });

  function markBusy(form) {
    var btn = form.querySelector('[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.classList.add('is-busy');
    btn.dataset.label = btn.textContent;
    btn.textContent = 'Working…';
  }

  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      if (form.getAttribute('onsubmit')) return;
      markBusy(form);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-overlay.is-open').forEach(function (m) { closeModal(m.id); });
    if (confirmDialog && confirmDialog.classList.contains('is-open')) closeConfirm();
    closeSidebar();
  });

  document.querySelectorAll('.upload-area input[type="file"]').forEach(function (input) {
    input.addEventListener('change', function () {
      var file = this.files && this.files[0];
      var preview = this.closest('.upload-area') && this.closest('.upload-area').querySelector('.upload-preview');
      var label = this.closest('.upload-area') && this.closest('.upload-area').querySelector('.upload-area-text');
      if (!file || !preview) return;
      var reader = new FileReader();
      reader.onload = function (event) {
        preview.src = event.target.result;
        preview.classList.add('is-visible');
        if (label) label.textContent = file.name;
      };
      reader.readAsDataURL(file);
    });
  });

  var errorModal = document.querySelector('[data-open-on-load]');
  if (errorModal) openModal(errorModal.id);

  var report = new URLSearchParams(window.location.search).get('report');
  if (report === '1' && !errorModal) {
    if (document.getElementById('reportLostModal')) openModal('reportLostModal');
    if (document.getElementById('reportFoundModal')) openModal('reportFoundModal');
  }

  document.querySelectorAll('[data-filter-bar]').forEach(function (bar) {
    var group = document.querySelector('[data-filter-group]');
    var empty = document.querySelector('[data-filter-empty]');
    if (!group) return;
    bar.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-filter]');
      if (!btn) return;
      bar.querySelectorAll('[data-filter]').forEach(function (chip) {
        chip.classList.toggle('is-active', chip === btn);
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
})();
