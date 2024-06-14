window.addEventListener('resize', function() {
    var sidebarWidth = document.getElementById('offcanvas').offsetWidth;
    document.getElementById('main-map').style.width = `calc(100% - ${sidebarWidth}px)`;
});