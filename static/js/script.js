const menuToggle = document.getElementById('menuToggle');
const sideMenu = document.getElementById('sideMenu');
const closeMenu = document.getElementById('closeMenu');
const modal = document.getElementById("uploadModal");

// Event listeners for menu toggle and close button
if (menuToggle && sideMenu && closeMenu) {
    menuToggle.addEventListener('click', () => {
        sideMenu.classList.toggle('open');
        menuToggle.classList.add('hidden');
    });

    closeMenu.addEventListener('click', () => {
        sideMenu.classList.remove('open');
        menuToggle.classList.remove('hidden');
    });
}

// Close modal if user clicks anywhere outside of the modal box
// (open/close buttons inside the page use inline onclick handlers)
if (modal) {
    window.addEventListener('click', function (event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    });
}
