const menuToggle = document.getElementById('menuToggle');
const sideMenu = document.getElementById('sideMenu');
const closeMenu = document.getElementById('closeMenu');
const modal = document.getElementById("uploadModal");
const openBtn = document.getElementById("openModalBtn");
const closeX = document.getElementById("closeModalBtn");
const cancelBtn = document.getElementById("cancelModalBtn");

// Event listeners for menu toggle and close button
menuToggle.addEventListener('click', () => {
    sideMenu.classList.toggle('open');
    menuToggle.classList.add('hidden');
});

closeMenu.addEventListener('click', () => {
    sideMenu.classList.remove('open');
    menuToggle.classList.remove('hidden');
});

// Open modal on button click
openBtn.onclick = function() {
    modal.style.display = "flex"; // Using flex alignment centers it nicely
}

// Close modal when clicking (X) or 'Cancel'
closeX.onclick = function() { modal.style.display = "none"; }
cancelBtn.onclick = function() { modal.style.display = "none"; }

// Close modal if user clicks anywhere outside of the modal box
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}
