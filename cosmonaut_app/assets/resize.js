// This is a workaround to resize the map when the sidebar is toggled as Dash doesn't support resizing the map when the sidebar is toggled.
window.addEventListener('resize', function() {
    var sidebarWidth = document.getElementById('offcanvas').offsetWidth;
    document.getElementById('main-map').style.width = `calc(100% - ${sidebarWidth}px)`;
});