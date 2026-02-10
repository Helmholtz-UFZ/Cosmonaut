// This is a workaround to resize the map when the sidebar is toggled as Dash doesn't support resizing the map when the sidebar is toggled.
window.addEventListener('resize', function() {
    var offcanvas = document.getElementById('offcanvas');
    var mainMap = document.getElementById('main-map');
    if (offcanvas && mainMap) {
        mainMap.style.width = `calc(100% - ${offcanvas.offsetWidth}px)`;
    }
});