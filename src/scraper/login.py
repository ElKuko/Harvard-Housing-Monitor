"""
Playwright-based login flow for the Harvard Housing portal.

The portal uses a single-page form with two phases:
  1. Enter email → click Continue (password field is hidden)
  2. Password field becomes visible → enter password → click Continue again
  3. Confirm landing on listing page

The form may be inside an iframe on the host page, so we search all frames.

Exact IDs from the live HTML:
  - Email input:    id="Username"
  - Password input: id="Password"  (hidden/disabled until after step 1)
  - Submit button:  id="SubmitLogin"  type="button"  text="Continue"
"""
import logging
from playwright.sync_api import Page, Frame, TimeoutError as PWTimeout

from config import PORTAL_URL, HH_EMAIL, HH_PASSWORD, BROWSER_TIMEOUT_MS

logger = logging.getLogger(__name__)

SEL_LISTING_INDICATOR = "table, .sc-search-results, #searchResults, .unit-row, [class*='listing']"


def login(page: Page) -> None:
    """
    Perform the full login and land on the listing page.
    Raises RuntimeError on any failure.
    """
    logger.info("Navigating to portal: %s", PORTAL_URL)
    page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
    # Give JS a moment to render the form
    page.wait_for_timeout(3000)

    # Dismiss cookie consent popup if present
    _dismiss_cookie_popup(page)

    # The form may live inside an iframe – find the right frame context
    frame = _find_form_frame(page)

    # ── Step 1: Enter email → click Continue ────────────────────────────────
    _enter_email(frame)

    # ── Step 2: Wait for password → enter → click Continue ──────────────────
    _enter_password(frame)

    # ── Step 3: Verify listing page loaded ───────────────────────────────────
    _verify_listing_page(page)

    logger.info("Login successful")


# ---------------------------------------------------------------------------
# Frame detection
# ---------------------------------------------------------------------------

def _dismiss_cookie_popup(page: Page) -> None:
    """Click Accept/Reject on cookie consent banners if present."""
    candidates = [
        "button:has-text('Accept All')",
        "button:has-text('Accept all')",
        "button:has-text('Reject All')",
        "button:has-text('Reject all')",
        "button:has-text('Accept Cookies')",
        "button[id*='accept' i]",
        "button[class*='accept' i]",
    ]
    for sel in candidates:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=2000):
                btn.click()
                logger.debug("Dismissed cookie popup with: %s", sel)
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue
    logger.debug("No cookie popup found – continuing")


def _find_form_frame(page: Page) -> Frame:
    """
    Return the Frame that contains the login form (#Username).
    Falls back to the main frame if not found in any iframe.
    """
    # Check main frame first
    if page.locator("#Username").count() > 0:
        logger.debug("Login form found in main frame")
        return page

    # Search all iframes
    for frame in page.frames:
        try:
            if frame.locator("#Username").count() > 0:
                logger.debug("Login form found in iframe: %s", frame.url)
                return frame
        except Exception:
            continue

    # Wait a moment and retry (iframes may still be loading)
    page.wait_for_timeout(3000)
    for frame in page.frames:
        try:
            if frame.locator("#Username").count() > 0:
                logger.debug("Login form found in iframe after wait: %s", frame.url)
                return frame
        except Exception:
            continue

    logger.debug("Could not find #Username in any frame – using main frame")
    return page


# ---------------------------------------------------------------------------
# Login steps
# ---------------------------------------------------------------------------

def _enter_email(frame) -> None:
    """Fill the email field and click Continue to reveal the password field."""
    logger.debug("Waiting for #Username input")
    try:
        frame.wait_for_selector("#Username", timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        _save_debug_screenshot_frame(frame, "no_username_input")
        raise RuntimeError(
            "Email input (#Username) not found. "
            "Check logs/debug_no_username_input.png"
        )

    frame.fill("#Username", HH_EMAIL)
    logger.debug("Email entered")

    # Click the Continue button (id="SubmitLogin")
    try:
        frame.wait_for_selector("#SubmitLogin", timeout=BROWSER_TIMEOUT_MS)
        frame.click("#SubmitLogin")
        logger.debug("Clicked Continue (after email)")
    except PWTimeout:
        _save_debug_screenshot_frame(frame, "no_submit_button")
        raise RuntimeError("Continue button (#SubmitLogin) not found")

    # Wait for password field to become visible
    try:
        frame.wait_for_selector(
            "#Password:not([disabled])",
            state="visible",
            timeout=BROWSER_TIMEOUT_MS,
        )
        logger.debug("Password field is now visible")
    except PWTimeout:
        _save_debug_screenshot_frame(frame, "password_not_visible")
        raise RuntimeError(
            "Password field did not appear after clicking Continue. "
            "The email may be incorrect or not registered. "
            "Check logs/debug_password_not_visible.png"
        )


def _enter_password(frame) -> None:
    """Fill the password field and submit the form."""
    frame.fill("#Password", HH_PASSWORD)
    logger.debug("Password entered")

    frame.click("#SubmitLogin")
    logger.debug("Clicked Continue (after password)")

    # Wait for navigation / network idle
    try:
        frame.page.wait_for_load_state("domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
    except Exception:
        pass  # some portals don't fully settle – proceed to verification


def _verify_listing_page(page: Page) -> None:
    """Confirm we landed on a page that contains listing content."""
    # Check all frames for the listing indicator
    try:
        page.wait_for_selector(SEL_LISTING_INDICATOR, timeout=BROWSER_TIMEOUT_MS)
        return
    except PWTimeout:
        pass

    for frame in page.frames:
        try:
            if frame.locator(SEL_LISTING_INDICATOR).count() > 0:
                logger.debug("Listing indicator found in frame: %s", frame.url)
                return
        except Exception:
            continue

    _save_debug_screenshot_frame(page, "listing_page_not_found")
    title = page.title()
    raise RuntimeError(
        f"Did not land on listing page after login (page title: '{title}'). "
        "Check logs/debug_listing_page_not_found.png"
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _save_debug_screenshot_frame(frame_or_page, label: str) -> None:
    try:
        from pathlib import Path
        Path("logs").mkdir(exist_ok=True)
        path = f"logs/debug_{label}.png"
        # frame_or_page may be a Frame or a Page
        if hasattr(frame_or_page, "screenshot"):
            frame_or_page.screenshot(path=path, full_page=True)
        else:
            frame_or_page.page.screenshot(path=path, full_page=True)
        logger.info("Debug screenshot saved: %s", path)
    except Exception as exc:
        logger.debug("Could not save screenshot: %s", exc)
