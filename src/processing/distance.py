"""
Computes straight-line distance (miles) between a property address
and Harvard Divinity School using the geopy library.

geopy's Nominatim geocoder is free and requires no API key.
Rate limit: 1 request/second – the caller must ensure this.
"""
import logging
import time
from typing import Optional

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

from config import HDS_ADDRESS

logger = logging.getLogger(__name__)

# Geocoder instance (shared)
_geocoder = Nominatim(user_agent="harvard_housing_monitor/1.0")

# Cache geocoded results to avoid repeated calls for the same address
_geocache: dict[str, Optional[tuple[float, float]]] = {}

# Harvard Divinity School coordinates (pre-resolved)
_HDS_COORDS: Optional[tuple[float, float]] = None


def _get_hds_coords() -> Optional[tuple[float, float]]:
    global _HDS_COORDS
    if _HDS_COORDS is None:
        _HDS_COORDS = _geocode(HDS_ADDRESS)
    return _HDS_COORDS


def compute_distance(property_name: str, address_hint: str = "") -> Optional[float]:
    """
    Geocode `property_name` (optionally supplemented with `address_hint`) and
    return the geodesic distance in miles to Harvard Divinity School.

    Returns None if geocoding fails.
    """
    hds = _get_hds_coords()
    if hds is None:
        logger.error("Could not geocode HDS address; distances will be NULL")
        return None

    query = _build_query(property_name, address_hint)
    coords = _geocode(query)

    if coords is None:
        # Try appending "Cambridge, MA" as fallback
        fallback = f"{property_name}, Cambridge, MA"
        if fallback != query:
            coords = _geocode(fallback)

    if coords is None:
        logger.warning("Could not geocode property: %s", property_name)
        return None

    miles = geodesic(hds, coords).miles
    logger.debug("Distance from '%s' to HDS: %.2f mi", property_name, miles)
    return round(miles, 3)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_query(property_name: str, address_hint: str) -> str:
    parts = [property_name.strip()]
    hint = address_hint.strip()
    if hint:
        parts.append(hint)
    # Ensure we include city/state if not already present
    joined = ", ".join(parts)
    if "cambridge" not in joined.lower() and "ma" not in joined.lower():
        joined += ", Cambridge, MA"
    return joined


def _geocode(query: str) -> Optional[tuple[float, float]]:
    if query in _geocache:
        return _geocache[query]

    try:
        time.sleep(1)  # Nominatim rate limit
        location = _geocoder.geocode(query, timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            _geocache[query] = coords
            return coords
        _geocache[query] = None
        return None
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        logger.warning("Geocoding error for '%s': %s", query, exc)
        _geocache[query] = None
        return None
