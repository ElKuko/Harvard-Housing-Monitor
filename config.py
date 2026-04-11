import os
from dotenv import load_dotenv

load_dotenv()

# Portal
PORTAL_URL = "https://huhousing-harvard.securecafe.com/onlineleasing/apartmentsforrent/guestlogin.aspx"

# Credentials
HH_EMAIL = os.getenv("HH_EMAIL", "")
HH_PASSWORD = os.getenv("HH_PASSWORD", "")

# Email
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# Database
DB_PATH = os.getenv("DB_PATH", "data/housing.db")

# Scheduler
DAILY_RUN_TIME = os.getenv("DAILY_RUN_TIME", "08:00")

# Harvard Divinity School coordinates (45 Francis Ave, Cambridge, MA)
HDS_ADDRESS = "45 Francis Ave, Cambridge, MA 02138"

# Browser
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
