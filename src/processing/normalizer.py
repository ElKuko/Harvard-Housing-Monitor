"""
Cleans and normalises raw listing rows scraped from the portal.

Input:  raw dict from listing_extractor (all string values)
Output: clean dict matching the `units` table schema
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalise(raw: dict) -> Optional[dict]:
    """
    Convert a raw scraped row to a canonical unit dict.
    Returns None if the row cannot produce a valid unique_id.
    """
    property_name = _clean_str(raw.get("property_name", ""))
    unit          = _clean_str(raw.get("unit", ""))

    if not property_name or not unit:
        logger.debug("Skipping row – missing property_name or unit: %s", raw)
        return None

    unique_id = f"{property_name}|{unit}"

    bedrooms  = _parse_bedrooms(raw.get("bedrooms", ""))
    bathrooms = _parse_float(raw.get("bathrooms", ""))
    sqft      = _parse_int(raw.get("sqft", ""))
    rent      = _parse_rent(raw.get("rent", ""))

    lease_start, lease_end = _parse_lease_dates(raw.get("lease_dates", ""))

    return {
        "unique_id":        unique_id,
        "property_name":    property_name,
        "unit":             unit,
        "bedrooms":         bedrooms,
        "bathrooms":        bathrooms,
        "sqft":             sqft,
        "rent":             rent,
        "lease_start_date": lease_start,
        "lease_end_date":   lease_end,
        "details_url":      raw.get("details_url") or None,
        "detail_text":      None,           # populated by detail_extractor later
        "distance_to_hds":  None,           # populated by distance calculator later
    }


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

def _clean_str(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _parse_bedrooms(value: str) -> Optional[int]:
    """
    "0" → 0 (studio)
    "1" → 1
    "Studio" → 0
    """
    value = (value or "").strip().lower()
    if not value:
        return None
    if "studio" in value:
        return 0
    m = re.search(r"(\d+)", value)
    return int(m.group(1)) if m else None


def _parse_float(value: str) -> Optional[float]:
    value = (value or "").strip()
    m = re.search(r"[\d.]+", value.replace(",", ""))
    return float(m.group()) if m else None


def _parse_int(value: str) -> Optional[int]:
    f = _parse_float(value)
    return int(f) if f is not None else None


def _parse_rent(value: str) -> Optional[float]:
    """
    "$2,700.00" → 2700.0
    "2700"      → 2700.0
    """
    value = (value or "").strip().replace("$", "").replace(",", "")
    m = re.search(r"[\d.]+", value)
    return float(m.group()) if m else None


def _parse_lease_dates(value: str) -> tuple[Optional[str], Optional[str]]:
    """
    "4/17/2026 - 6/30/2027" → ("2026-04-17", "2027-06-30")
    """
    if not value:
        return None, None

    # Split on dash/em-dash surrounded by optional spaces
    parts = re.split(r"\s*[-–—]\s*", value.strip())
    start = _parse_single_date(parts[0]) if len(parts) >= 1 else None
    end   = _parse_single_date(parts[1]) if len(parts) >= 2 else None
    return start, end


def _parse_single_date(value: str) -> Optional[str]:
    """
    Accepts M/D/YYYY and returns YYYY-MM-DD.
    """
    value = (value or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        month, day, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None
