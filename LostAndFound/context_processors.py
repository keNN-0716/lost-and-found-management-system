"""Template context processors."""

from django.conf import settings


def map_tiles(request):
    """Expose the map tile URL + attribution to all templates.

    The CARTO Basemaps API key lives in .env (never committed) and is
    appended server-side so it never appears in the public repository.
    Falls back to a keyless ESRI basemap when no CARTO key is configured.
    """
    key = getattr(settings, "CARTO_API_KEY", "")
    if key:
        return {
            "tile_url": (
                "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/"
                "{z}/{x}/{y}{r}.png?key=" + key
            ),
            "tile_attribution": "&copy; OpenStreetMap contributors &copy; CARTO",
        }
    return {
        "tile_url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        ),
        "tile_attribution": (
            "Map data &copy; Esri, HERE, Garmin, FAO, NOAA, USGS, "
            "OpenStreetMap contributors"
        ),
    }
