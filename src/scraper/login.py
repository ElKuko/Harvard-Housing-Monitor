"""
Playwright-based login flow for the Harvard Housing portal.

The portal uses a multi-step UI:
  1. Load page
  2. Enter email → click Next
  3. Enter password → click Login
  4. Click Continue
  5. Confirm landing on listing page
"""
import logging
from playwright.sync_api import Page, TimeoutError as PWTimeout

from config import PORTAL_URL, HH_EMAIL, HH_PASSWORD, BROWSER_TIMEOUT_MS

logger = logging.getLogger(__name__)

# CSS selectors – kept in one place for easy maintenance
SEL_EMAIL_INPUT    = "input[type='email'], input[id*='email' i], input[name*='email' i]"
SEL_PASSWORD_INPUT = "input[type='password']"
SEL_NEXT_BUTTON    = "input[type='submit'][value*='Next' i], button:has-text('Next'), a:has-text('Next')"
SEL_LOGIN_BUTTON   = (
    "input[type='submit'][value*='Login' i], "
    "input[type='submit'][value*='Sign' i], "
    "button:has-text('Login'), button:has-text('Sign In')"
)
SEL_CONTINUE_BUTTON = (
    "input[type='submit'][value*='Continue' i], "
    "button:has-text('Continue'), a:has-text('Continue')"
)
# A reliable element present only on the authenticated listing page
SEL_LISTING_INDICATOR = "table, .sc-search-results, #searchResults, .unit-row, [class*='listing']"


def login(page: Page) -> None:
    """
    Perform the full multi-step login and land on the listing page.
    Raises RuntimeError on any failure.
    """
    logger.info("Navigating to portal: %s", PORTAL_URL)
    page.goto(PORTAL_URL, wait_until="networkidle", timeout=BROWSER_TIMEOUT_MS)

    # ── Step 1: Enter email ─────────────────────────────────────────────────
    _fill_email(page)

    # ── Step 2: Enter password ──────────────────────────────────────────────
    _fill_password(page)

    # ── Step 3: Click Continue (post-login interstitial) ────────────────────
    _click_continue(page)

    # ── Step 4: Verify we are on the listing page ───────────────────────────
    _verify_listing_page(page)

    logger.info("Login successful")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fill_email(page: Page) -> None:
    logger.debug("Waiting for email input")
    try:
        page.wait_for_selector(SEL_EMAIL_INPUT, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        raise RuntimeError("Email input not found on login page")

    email_input = page.locator(SEL_EMAIL_INPUT).first
    email_input.fill(HH_EMAIL)
    logger.debug("Email entered")

    # Click Next to advance to the password step
    next_btn = page.locator(SEL_NEXT_BUTTON).first
    if next_btn.count() == 0 or not next_btn.is_visible():
        # Some portals show email + password on one page – skip "Next"
        logger.debug("No 'Next' button found; assuming single-page login form")
        return

    next_btn.click()
    logger.debug("Clicked Next")
    page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)


def _fill_password(page: Page) -> None:
    logger.debug("Waiting for password input")
    try:
        page.wait_for_selector(SEL_PASSWORD_INPUT, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        raise RuntimeError("Password input not found – login flow may have changed")

    page.locator(SEL_PASSWORD_INPUT).fill(HH_PASSWORD)
    logger.debug("Password entered")

    login_btn = page.locator(SEL_LOGIN_BUTTON).first
    login_btn.click()
    logger.debug("Clicked Login")
    page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)


def _click_continue(page: Page) -> None:
    """
    After authentication the portal sometimes shows an interstitial with a
    'Continue' button. Click it if present; silently skip if absent.
    """
    try:
        page.wait_for_selector(SEL_CONTINUE_BUTTON, timeout=5000)
        page.locator(SEL_CONTINUE_BUTTON).first.click()
        logger.debug("Clicked Continue")
        page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        logger.debug("No Continue button found – skipping")


def _verify_listing_page(page: Page) -> None:
    """Confirm we landed on a page that has listing content."""
    try:
        page.wait_for_selector(SEL_LISTING_INDICATOR, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        # Capture page title to give a better error message
        title = page.title()
        raise RuntimeError(
            f"Did not land on listing page after login (page title: '{title}'). "
            "The login may have failed or the portal flow changed."
        )
