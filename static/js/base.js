const menusItemsDropDown = document.querySelectorAll('.menu-item-dropdown');
const menusItemsStatic = document.querySelectorAll('.menu-item-static');
const sidebar = document.getElementById('sidebar');
const menuBtn = document.getElementById('menu-btn');
const sidebarBtn = document.getElementById('sidebar-btn');
const darkModeBtn = document.getElementById('dark-mode-btn');

darkModeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
});

sidebarBtn.addEventListener('click', () => {
    document.body.classList.toggle('sidebar-hidden');
});

menuBtn.addEventListener('click', () => {
    sidebar.classList.toggle('minimize');
});

menusItemsDropDown.forEach((menuItem) => {
    menuItem.addEventListener('click', () => {
        const subMenu = menuItem.querySelector('.sub-menu');
        const isActive = menuItem.classList.toggle('sub-menu-toggle');
        if (subMenu) {
            if (isActive) {
                subMenu.style.height = `${subMenu.scrollHeight + 6}px`;
                subMenu.style.padding = '0.2rem 0';
            } else {
                subMenu.style.height = '0';
                subMenu.style.padding = '0';
            }
        }
        menusItemsDropDown.forEach((item) => {
            if (item !== menuItem) {
                const otherSubmenu = item.querySelector('.sub-menu');
                if (otherSubmenu) {
                    item.classList.remove('sub-menu-toggle');
                    otherSubmenu.style.height = '0';
                    otherSubmenu.style.padding = '0';
                }
            }
        });
    });
});

menusItemsStatic.forEach((menuItem) => {
    menuItem.addEventListener('mouseenter', () => {

        if (!sidebar.classList.contains('minimize')) return;

        menusItemsDropDown.forEach((item) => {
            const otherSubmenu = item.querySelector('.sub-menu');
            if (otherSubmenu) {
                item.classList.remove('sub-menu-toggle');
                otherSubmenu.style.height = '0';
                otherSubmenu.style.padding = '0';
            }
        });
    });
});

function checkWindowsSize() {
    sidebar.classList.remove('minimize');
}

checkWindowsSize();
window.addEventListener('resize', checkWindowsSize);


//Fucncion de maximizar la mantalla

const fullscreenToggle = document.getElementById("fullscreenToggle");

fullscreenToggle.addEventListener("click", () => {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().then(() => {
            fullscreenToggle.classList.remove("bi-arrows-fullscreen");
            fullscreenToggle.classList.add("bi-arrows-angle-contract");
        });
    } else {
        document.exitFullscreen().then(() => {
            fullscreenToggle.classList.remove("bi-arrows-angle-contract");
            fullscreenToggle.classList.add("bi-arrows-fullscreen");
        });
    }
});

// Opcional: actualizar el ícono si se cambia el estado fuera del botón
document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement) {
        fullscreenToggle.classList.remove("bi-arrows-angle-contract");
        fullscreenToggle.classList.add("bi-arrows-fullscreen");
    } else {
        fullscreenToggle.classList.remove("bi-arrows-fullscreen");
        fullscreenToggle.classList.add("bi-arrows-angle-contract");
    }
});
