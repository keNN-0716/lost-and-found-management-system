const menuToggle = document.getElementById('menuToggle');
const sideMenu = document.getElementById('sideMenu');
const closeMenu = document.getElementById('closeMenu');

menuToggle.addEventListener('click', () => {
    sideMenu.classList.toggle('open');
    menuToggle.classList.add('hidden');
});

closeMenu.addEventListener('click', () => {
    sideMenu.classList.remove('open');
    menuToggle.classList.remove('hidden');
});