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

    var tileUrl = (typeof window.MAP_TILE_URL !== 'undefined' && window.MAP_TILE_URL)
        ? window.MAP_TILE_URL
        : 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
    var tileAttribution = (typeof window.MAP_TILE_ATTRIBUTION !== 'undefined' && window.MAP_TILE_ATTRIBUTION)
        ? window.MAP_TILE_ATTRIBUTION
        : 'Map data &copy; Esri, HERE, Garmin, FAO, NOAA, USGS, OpenStreetMap contributors';
    L.tileLayer(tileUrl, {
        maxZoom: 19,
        subdomains: 'abcd',
        attribution: tileAttribution
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