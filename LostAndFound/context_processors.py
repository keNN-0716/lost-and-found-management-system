"""Template context processors."""

from django.conf import settings

# CSPC campus focus: keep the map locked to this area (Leaflet maxBounds).
# Format: [[south, west], [north, east]] - about a 2.2 km box around campus.
CAMPUS_BOUNDS = [[13.3959, 123.3658], [13.4159, 123.3858]]
CAMPUS_MIN_ZOOM = 15  # stop users from zooming out to the whole world


def map_tiles(request):
    """Expose the map tile URL/attribution and campus bounds to all templates.

    The CARTO Basemaps API key lives in .env (never committed) and is
    appended server-side so it never appears in the public repository.
    Falls back to a keyless ESRI basemap when no CARTO key is configured.
    """
    key = getattr(settings, "CARTO_API_KEY", "")
    if key:
        data = {
            "tile_url": (
                "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/"
                "{z}/{x}/{y}{r}.png?key=" + key
            ),
            "tile_attribution": "&copy; OpenStreetMap contributors &copy; CARTO",
        }
    else:
        data = {
            "tile_url": (
                "https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
            ),
            "tile_attribution": (
                "Map data &copy; Esri, HERE, Garmin, FAO, NOAA, USGS, "
                "OpenStreetMap contributors"
            ),
        }
    data["campus_bounds"] = CAMPUS_BOUNDS
    data["campus_min_zoom"] = CAMPUS_MIN_ZOOM
    return data
