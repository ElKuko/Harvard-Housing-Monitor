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
#
# SecureCafe portals use ASP.NET WebForms with generated IDs.
# We cast a wide net and pick the first visible match.
SEL_EMAIL_INPUT = (
    "input[type='email'], "
    "input[id*='email' i], "
    "input[name*='email' i], "
    "input[id*='user' i], "
    "input[name*='user' i], "
    "input[id*='login' i], "
    "input[name*='login' i], "
    "input[type='text']"          # broadest fallback
)
SEL_PASSWORD_INPUT = "input[type='password']"
# After entering email, the portal shows a "Continue" button (not "Next")
SEL_AFTER_EMAIL_BUTTON = (
    "input[type='submit'][value*='Continue' i], "
    "input[type='button'][value*='Continue' i], "
    "input[type='submit'][value*='Next' i], "
    "button:has-text('Continue'), "
    "button:has-text('Next'), "
    "a:has-text('Continue')"
)
SEL_LOGIN_BUTTON   = (
    "input[type='submit'][value*='Login' i], "
    "input[type='submit'][value*='Sign' i], "
    "input[type='submit'][value*='Submit' i], "
    "button:has-text('Login'), "
    "button:has-text('Sign In'), "
    "button:has-text('Log In')"
)
# Post-login interstitial "Continue" (appears after password step)
SEL_CONTINUE_BUTTON = (
    "input[type='submit'][value*='Continue' i], "
    "input[type='button'][value*='Continue' i], "
    "button:has-text('Continue'), "
    "a:has-text('Continue')"
)
SEL_LISTING_INDICATOR = "table, .sc-search-results, #searchResults, .unit-row, [class*='listing']"

# Path to save a debug screenshot when login fails
DEBUG_SCREENSHOT = "logs/login_debug.png"


def login(page: Page) -> None:
    """
    Perform the full multi-step login and land on the listing page.
    Raises RuntimeError on any failure.
    """
    logger.info("Navigating to portal: %s", PORTAL_URL)
    page.goto(PORTAL_URL, wait_until="networkidle", timeout=BROWSER_TIMEOUT_MS)

    # ── Step 1: Enter email / username ──────────────────────────────────────
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

def _save_debug_screenshot(page: Page, label: str) -> None:
    try:
        from pathlib import Path
        Path("logs").mkdir(exist_ok=True)
        path = f"logs/debug_{label}.png"
        page.screenshot(path=path, full_page=True)
        logger.info("Debug screenshot saved: %s", path)
    except Exception as exc:
        logger.debug("Could not save screenshot: %s", exc)


def _fill_email(page: Page) -> None:
    logger.debug("Waiting for email/username input")

    # Log all visible inputs to help diagnose selector mismatches
    try:
        page.wait_for_selector("input", timeout=BROWSER_TIMEOUT_MS)
        inputs = page.locator("input").all()
        for inp in inputs:
            try:
                itype = inp.get_attribute("type") or "text"
                iid   = inp.get_attribute("id") or ""
                iname = inp.get_attribute("name") or ""
                logger.debug("Found input: type=%s id=%s name=%s", itype, iid, iname)
            except Exception:
                pass
    except PWTimeout:
        _save_debug_screenshot(page, "no_inputs")
        raise RuntimeError("No input fields found on login page")

    # Try each candidate selector in order, pick first visible one
    email_input = None
    for sel in SEL_EMAIL_INPUT.split(", "):
        sel = sel.strip()
        loc = page.locator(sel)
        if loc.count() > 0:
            candidate = loc.first
            try:
                if candidate.is_visible():
                    itype = candidate.get_attribute("type") or ""
                    # Skip hidden / password / submit / button inputs
                    if itype.lower() not in ("password", "submit", "button", "hidden", "checkbox", "radio"):
                        logger.debug("Using email selector: %s", sel)
                        email_input = candidate
                        break
            except Exception:
                continue

    if email_input is None:
        _save_debug_screenshot(page, "no_email_input")
        raise RuntimeError(
            "Email input not found on login page. "
            f"A debug screenshot was saved to {DEBUG_SCREENSHOT}"
        )

    email_input.fill(HH_EMAIL)
    logger.debug("Email/username entered")

    # Click the Continue/Next button to advance to the password step
    after_email_btn = page.locator(SEL_AFTER_EMAIL_BUTTON)
    if after_email_btn.count() > 0 and after_email_btn.first.is_visible():
        after_email_btn.first.click()
        logger.debug("Clicked Continue after email")
        page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)
    else:
        logger.debug("No Continue/Next button after email – assuming single-page form")


def _fill_password(page: Page) -> None:
    logger.debug("Waiting for password input")
    try:
        page.wait_for_selector(SEL_PASSWORD_INPUT, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        _save_debug_screenshot(page, "no_password_input")
        raise RuntimeError("Password input not found – login flow may have changed")

    page.locator(SEL_PASSWORD_INPUT).first.fill(HH_PASSWORD)
    logger.debug("Password entered")

    login_btn = page.locator(SEL_LOGIN_BUTTON)
    if login_btn.count() == 0 or not login_btn.first.is_visible():
        _save_debug_screenshot(page, "no_login_button")
        raise RuntimeError("Login button not found")

    login_btn.first.click()
    logger.debug("Clicked Login")
    page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)


def _click_continue(page: Page) -> None:
    """Click the post-login Continue button if present; silently skip if absent."""
    try:
        page.wait_for_selector(SEL_CONTINUE_BUTTON, timeout=5000)
        page.locator(SEL_CONTINUE_BUTTON).first.click()
        logger.debug("Clicked Continue")
        page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        logger.debug("No Continue button – skipping")


def _verify_listing_page(page: Page) -> None:
    """Confirm we landed on a page that has listing content."""
    try:
        page.wait_for_selector(SEL_LISTING_INDICATOR, timeout=BROWSER_TIMEOUT_MS)
    except PWTimeout:
        _save_debug_screenshot(page, "listing_page_not_found")
        title = page.title()
        raise RuntimeError(
            f"Did not land on listing page after login (page title: '{title}'). "
            "The login may have failed or the portal flow changed. "
            "Check logs/debug_listing_page_not_found.png for a screenshot."
        )
