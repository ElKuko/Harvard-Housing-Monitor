"""
Fetches detail pages for individual listings and extracts full text content.

Operates on a second Playwright page (tab) so the main listing page stays open.
"""
import logging
from playwright.sync_api import Browser, Page, TimeoutError as PWTimeout

from config import BROWSER_TIMEOUT_MS

logger = logging.getLogger(__name__)

# Elements that typically contain rich unit description text
SEL_CONTENT = (
    ".unit-detail, "
    "#unitDetails, "
    ".listing-detail, "
    ".property-description, "
    "main, "
    "article, "
    "#content, "
    ".content"
)


def extract_detail(browser: Browser, url: str) -> str:
    """
    Open `url` in a new tab, extract all meaningful text, close the tab.
    Returns the extracted text, or empty string on failure.
    """
    if not url:
        return ""

    page: Page = browser.new_page()
    try:
        logger.debug("Opening detail page: %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)

        # Try structured content areas first
        for selector in SEL_CONTENT.split(", "):
            el = page.locator(selector.strip()).first
            if el.count() > 0:
                text = el.inner_text().strip()
                if len(text) > 50:  # ignore trivially short matches
                    logger.debug("Extracted %d chars from '%s'", len(text), selector.strip())
                    return _clean_text(text)

        # Fallback: grab everything in <body>
        body_text = page.locator("body").inner_text().strip()
        return _clean_text(body_text)

    except PWTimeout:
        logger.warning("Timeout loading detail page: %s", url)
        return ""
    except Exception as exc:
        logger.warning("Error loading detail page %s: %s", url, exc)
        return ""
    finally:
        page.close()


def _clean_text(text: str) -> str:
    """Collapse excess whitespace while preserving paragraph structure."""
    import re
    # Normalise line endings
    text = re.sub(r"\r\n?", "\n", text)
    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()
