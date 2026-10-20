(function () {
  const menuToggle = document.getElementById("menuToggle");
  const sideMenu = document.getElementById("sideMenu");
  const closeMenu = document.getElementById("closeMenu");
  const navBackdrop = document.getElementById("navBackdrop");

  function openMenu() {
    if (!sideMenu) return;
    sideMenu.classList.add("open");
    if (menuToggle) {
      menuToggle.classList.add("hidden");
      menuToggle.setAttribute("aria-expanded", "true");
    }
    if (navBackdrop) navBackdrop.hidden = false;
  }

  function closeNav() {
    if (!sideMenu) return;
    sideMenu.classList.remove("open");
    if (menuToggle) {
      menuToggle.classList.remove("hidden");
      menuToggle.setAttribute("aria-expanded", "false");
    }
    if (navBackdrop) navBackdrop.hidden = true;
  }

  if (menuToggle && sideMenu) {
    menuToggle.addEventListener("click", openMenu);
  }
  if (closeMenu) {
    closeMenu.addEventListener("click", closeNav);
  }
  if (navBackdrop) {
    navBackdrop.addEventListener("click", closeNav);
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeNav();
  });

  // Modal helpers — only wire when the upload modal exists on the page
  const modal = document.getElementById("uploadModal");
  const openBtn = document.getElementById("openModalBtn");
  const closeX = document.getElementById("closeModalBtn");
  const cancelBtn = document.getElementById("cancelModalBtn");

  if (modal && openBtn) {
    openBtn.addEventListener("click", function () {
      modal.style.display = "flex";
    });
  }
  if (modal && closeX) {
    closeX.addEventListener("click", function () {
      modal.style.display = "none";
    });
  }
  if (modal && cancelBtn) {
    cancelBtn.addEventListener("click", function () {
      modal.style.display = "none";
    });
  }
  if (modal) {
    window.addEventListener("click", function (event) {
      if (event.target === modal) {
        modal.style.display = "none";
      }
    });
  }
})();
