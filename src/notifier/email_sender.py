"""
Sends the daily Harvard Housing Monitor email via SMTP.
"""
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_FROM, EMAIL_TO,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_daily_email(
    new_units: list[dict],
    total_scanned: int,
    run_id: str,
) -> tuple[str, str, bool]:
    """
    Build and send the daily summary email.

    Returns (subject, body, success).
    """
    subject, body = _build_message(new_units, total_scanned)
    success = _send(subject, body)
    return subject, body, success


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def _build_message(new_units: list[dict], total_scanned: int) -> tuple[str, str]:
    if new_units:
        subject = f"Harvard Housing Monitor: {len(new_units)} New Unit{'s' if len(new_units) != 1 else ''} Found"
        body = _new_units_body(new_units, total_scanned)
    else:
        subject = "Harvard Housing Monitor: No New Units Today"
        body = _no_new_units_body(total_scanned)

    return subject, body


def _no_new_units_body(total_scanned: int) -> str:
    return (
        f"No new listings were added today.\n\n"
        f"Total units scanned: {total_scanned}\n"
        f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )


def _new_units_body(new_units: list[dict], total_scanned: int) -> str:
    lines = [
        f"New listings detected ({len(new_units)}):",
        "=" * 60,
        "",
    ]

    for u in new_units:
        lines.extend(_format_unit(u))
        lines.append("")

    lines.extend([
        "-" * 60,
        f"Total units scanned today: {total_scanned}",
        f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ])

    return "\n".join(lines)


def _format_unit(u: dict) -> list[str]:
    """Format a single unit for the email body."""
    bedrooms  = _fmt_bedrooms(u.get("bedrooms"))
    bathrooms = u.get("bathrooms")
    sqft      = u.get("sqft")
    rent      = u.get("rent")
    distance  = u.get("distance_to_hds")
    url       = u.get("details_url") or "N/A"

    lease = _fmt_lease(u.get("lease_start_date"), u.get("lease_end_date"))

    lines = [
        f"{u.get('property_name', 'Unknown')} – {u.get('unit', 'Unknown')}",
        f"  Rent:     {f'${rent:,.2f}' if rent else 'N/A'}",
        f"  Beds:     {bedrooms}  |  Baths: {bathrooms if bathrooms is not None else 'N/A'}  |  SqFt: {sqft if sqft else 'N/A'}",
        f"  Lease:    {lease}",
        f"  Distance: {f'{distance:.2f} miles' if distance is not None else 'N/A'}",
        f"  Details:  {url}",
    ]
    return lines


def _fmt_bedrooms(bedrooms) -> str:
    if bedrooms is None:
        return "N/A"
    if bedrooms == 0:
        return "Studio"
    return str(bedrooms)


def _fmt_lease(start: Optional[str], end: Optional[str]) -> str:
    parts = []
    if start:
        parts.append(start)
    if end:
        parts.append(end)
    return " → ".join(parts) if parts else "N/A"


# ---------------------------------------------------------------------------
# SMTP transport
# ---------------------------------------------------------------------------

def _send(subject: str, body: str) -> bool:
    if not EMAIL_TO:
        logger.warning("EMAIL_TO not configured – skipping email send")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject

    # Plain text part
    msg.attach(MIMEText(body, "plain"))

    # HTML part
    html_body = _text_to_html(body)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.info("Email sent to %s: %s", EMAIL_TO, subject)
        return True
    except smtplib.SMTPException as exc:
        logger.error("Failed to send email: %s", exc)
        return False


def _text_to_html(text: str) -> str:
    """Minimal plain-text → HTML conversion."""
    import html as html_mod
    escaped = html_mod.escape(text)
    # Preserve line breaks
    escaped = escaped.replace("\n", "<br>\n")
    # Preserve monospace alignment for the unit blocks
    return f"<html><body><pre style='font-family:monospace'>{escaped}</pre></body></html>"
