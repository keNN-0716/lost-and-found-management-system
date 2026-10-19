// Heatmap renderer for lost/found item density (CSPC campus centered).
// Data is provided by heatmap.html via lostPoints / foundPoints / pointType.
(function () {
    if (typeof L === 'undefined') {
        return; // Leaflet failed to load (offline) - leave the empty container.
    }

    var mapEl = document.getElementById('heatmap');
    if (!mapEl) {
        return;
    }

    var mapBounds = (typeof window.MAP_BOUNDS !== 'undefined' && window.MAP_BOUNDS)
        ? window.MAP_BOUNDS
        : [[13.3959, 123.3658], [13.4159, 123.3858]];
    var mapMinZoom = (typeof window.MAP_MIN_ZOOM !== 'undefined' && window.MAP_MIN_ZOOM)
        ? window.MAP_MIN_ZOOM
        : 15;
    var map = L.map('heatmap', {
        maxBounds: mapBounds,
        maxBoundsViscosity: 1.0,
        minZoom: mapMinZoom
    }).setView(campusCenter, campusZoom);

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

    // Fit the view to whichever points are shown, so clusters stay in frame.
    var active = [];
    if (pointType === 'all' || pointType === 'lost') {
        active = active.concat(lostPoints);
    }
    if (pointType === 'all' || pointType === 'found') {
        active = active.concat(foundPoints);
    }

    if (active.length > 0) {
        var bounds = L.latLngBounds(active.map(function (p) { return [p[0], p[1]]; }));
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
    }

    if (typeof L.heatLayer === 'function') {
        if ((pointType === 'all' || pointType === 'lost') && lostPoints.length) {
            L.heatLayer(lostPoints, {
                radius: 30,
                blur: 20,
                maxZoom: 17,
                gradient: { 0.2: '#3b7dd8', 0.5: '#f3e75a', 0.8: '#f5a623', 1: '#e74c3c' }
            }).addTo(map);
        }
        if ((pointType === 'all' || pointType === 'found') && foundPoints.length) {
            L.heatLayer(foundPoints, {
                radius: 30,
                blur: 20,
                maxZoom: 17,
                gradient: { 0.2: '#2ecc71', 0.5: '#a8e6cf', 0.8: '#f5e642', 1: '#155724' }
            }).addTo(map);
        }
    }
})();