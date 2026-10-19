// Click-to-mark map picker used inside the Report Item modals.
// The page provides the map div (#reportMap) and hidden inputs
// (id_latitude / id_longitude). Clicking sets the coordinates.
(function () {
    if (typeof L === 'undefined') {
        return; // Leaflet unavailable (offline) - coordinates stay optional.
    }
    var mapEl = document.getElementById('reportMap');
    if (!mapEl) {
        return;
    }

    // Centered on the CSPC Nabua campus
    var campusCenter = [13.4059, 123.3758];
    var map = L.map('reportMap').setView(campusCenter, 16);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
    }).addTo(map);

    var latInput = document.getElementById('id_latitude');
    var lngInput = document.getElementById('id_longitude');
    var marker = null;

    function placeMarker(latlng) {
        if (marker) {
            marker.setLatLng(latlng);
        } else {
            marker = L.marker(latlng).addTo(map);
        }
        if (latInput) { latInput.value = latlng.lat.toFixed(6); }
        if (lngInput) { lngInput.value = latlng.lng.toFixed(6); }
    }

    // Prefill if the form was re-rendered after a validation error
    if (latInput && lngInput && latInput.value && lngInput.value) {
        var pre = [parseFloat(latInput.value), parseFloat(lngInput.value)];
        if (!isNaN(pre[0]) && !isNaN(pre[1])) {
            placeMarker(pre);
            map.setView(pre, 17);
        }
    }

    map.on('click', function (e) {
        placeMarker(e.latlng);
    });

    // The modal starts hidden, so Leaflet needs a resize once it is shown.
    window.refreshReportMap = function () {
        setTimeout(function () { map.invalidateSize(); }, 60);
    };

    window.openReportModal = function () {
        var m = document.getElementById('uploadModal');
        if (m) { m.style.display = 'flex'; }
        if (window.refreshReportMap) { window.refreshReportMap(); }
    };

    window.closeReportModal = function () {
        var m = document.getElementById('uploadModal');
        if (m) { m.style.display = 'none'; }
    };
})();