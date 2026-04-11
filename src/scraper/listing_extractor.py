"""
Extracts all apartment listing rows from the authenticated listing page.

The portal renders data inside an HTML table with columns:
    Property | Apartment | Bed | Bath | Sq.Ft. | Rent | Lease Start - Lease End | Amenities | Action

Returns a list of raw dicts (strings) ready for the normalizer.
"""
import logging
import re
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PWTimeout

from config import BROWSER_TIMEOUT_MS

logger = logging.getLogger(__name__)

# Selectors
SEL_TABLE        = "table"
SEL_HEADER_ROW   = "thead tr, tr:first-child"
SEL_DATA_ROWS    = "tbody tr"
SEL_DETAILS_LINK = "a[href*='details' i], a:has-text('Details'), a[href*='unit' i]"


def extract_listings(page: Page) -> list[dict]:
    """
    Parse all listing rows from the current page.
    Returns a list of raw dicts with string values (normalizer cleans them).
    """
    logger.info("Extracting listings from page")

    try:
        page.wait_for_selector(SEL_TABLE, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        raise RuntimeError("Listing table not found – may not be logged in")

    # Handle pagination: collect rows from all pages
    all_rows: list[dict] = []
    page_num = 1

    while True:
        rows = _extract_page_rows(page)
        logger.info("Page %d: found %d rows", page_num, len(rows))
        all_rows.extend(rows)

        # Try to go to next page
        if not _go_to_next_page(page):
            break
        page_num += 1

    logger.info("Total listings extracted: %d", len(all_rows))
    return all_rows


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_page_rows(page: Page) -> list[dict]:
    """Extract all data rows from the table currently visible on the page."""
    tables = page.locator(SEL_TABLE).all()
    if not tables:
        return []

    # Use the largest table (most rows) as the listing table
    listing_table = max(tables, key=lambda t: t.locator("tr").count())

    headers = _parse_headers(listing_table)
    if not headers:
        logger.warning("Could not determine table headers")
        return []

    logger.debug("Detected columns: %s", headers)

    rows: list[dict] = []
    data_rows = listing_table.locator("tbody tr").all()
    if not data_rows:
        # Fallback: skip header row
        data_rows = listing_table.locator("tr").all()[1:]

    for tr in data_rows:
        row = _parse_row(tr, headers)
        if row:
            rows.append(row)

    return rows


def _parse_headers(table) -> list[str]:
    """Return normalised header names from the table's first header row."""
    header_cells = table.locator("thead th, thead td").all()
    if not header_cells:
        header_cells = table.locator("tr:first-child th, tr:first-child td").all()

    return [_normalise_header(c.inner_text()) for c in header_cells]


def _normalise_header(text: str) -> str:
    """Map raw header text to a canonical field name."""
    text = text.strip().lower()
    mapping = {
        "property":    "property_name",
        "apartment":   "unit",
        "apt":         "unit",
        "unit":        "unit",
        "bed":         "bedrooms",
        "beds":        "bedrooms",
        "bedrooms":    "bedrooms",
        "bath":        "bathrooms",
        "baths":       "bathrooms",
        "bathrooms":   "bathrooms",
        "sq.ft.":      "sqft",
        "sqft":        "sqft",
        "sq ft":       "sqft",
        "size":        "sqft",
        "rent":        "rent",
        "price":       "rent",
        "lease":       "lease_dates",
        "lease dates": "lease_dates",
        "lease start - lease end": "lease_dates",
        "amenities":   "amenities",
        "action":      "action",
        "details":     "amenities",
    }
    for key, value in mapping.items():
        if key in text:
            return value
    return re.sub(r"\s+", "_", text)


def _parse_row(tr, headers: list[str]) -> Optional[dict]:
    """Parse a single <tr> into a dict using the provided headers."""
    cells = tr.locator("td").all()
    if not cells:
        return None

    row: dict = {}
    for i, header in enumerate(headers):
        if i >= len(cells):
            break
        cell = cells[i]

        if header == "amenities":
            # Extract the href from the Details link
            link = cell.locator(SEL_DETAILS_LINK).first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                row["details_url"] = _make_absolute_url(href)
            else:
                row["details_url"] = None
        else:
            row[header] = cell.inner_text().strip()

    # Skip completely empty rows
    if not any(v for k, v in row.items() if k not in ("details_url",)):
        return None

    return row


def _make_absolute_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    base = "https://huhousing-harvard.securecafe.com"
    return base + ("" if href.startswith("/") else "/") + href


def _go_to_next_page(page: Page) -> bool:
    """
    Click the 'Next' pagination control if it exists and is enabled.
    Returns True if navigation happened, False otherwise.
    """
    next_sel = (
        "a[aria-label='Next page'], "
        "a.next, "
        "li.next a, "
        "a:has-text('Next'), "
        "button:has-text('Next')"
    )
    next_btn = page.locator(next_sel).first
    if next_btn.count() == 0:
        return False

    classes = next_btn.get_attribute("class") or ""
    aria_disabled = next_btn.get_attribute("aria-disabled") or ""
    if "disabled" in classes or aria_disabled == "true":
        return False

    try:
        next_btn.click()
        page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)
        return True
    except Exception as exc:
        logger.debug("Pagination click failed: %s", exc)
        return False
