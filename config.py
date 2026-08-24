"""
Central configuration for the BD Railway toolkit.

Values are read from environment variables, optionally populated from a local
`.env` file. No external dependency is required (a tiny loader is built in), but
if `python-dotenv` is installed it works too.

Copy `.env.example` to `.env` and fill in your values, then never commit `.env`.
"""
import os


def _load_dotenv(path=".env"):
    """Minimal .env loader so we don't hard-depend on python-dotenv."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Real environment variables take precedence over the file.
                os.environ.setdefault(key, value)
    except Exception:
        pass


_load_dotenv()


def _get(name, default=None):
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _get_int(name, default):
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    # --- Gmail / SMTP (the account emails are sent FROM) ---
    GMAIL_ADDRESS = _get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = _get("GMAIL_APP_PASSWORD")
    SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = _get_int("SMTP_PORT", 587)

    # Recipient. If left empty, the monitor/app uses the email on your
    # railway profile (fetched from the API after login).
    NOTIFY_EMAIL = _get("NOTIFY_EMAIL")

    # --- Railway auth ---
    # Optional: paste a Bearer token copied from the site (DevTools > Network >
    # any request's Authorization header, minus the leading "Bearer ") so the
    # monitor can run without an interactive OTP login. Tokens expire; re-grab
    # when searches start returning "Not logged in".
    RAILWAY_AUTH_TOKEN = _get("RAILWAY_AUTH_TOKEN")
    RAILWAY_MOBILE = _get("RAILWAY_MOBILE")

    # --- Monitor behaviour ---
    # How often to poll. Keep this polite (>= 30s) so you don't get rate-limited
    # or IP-banned by the railway API.
    POLL_INTERVAL_SECONDS = _get_int("POLL_INTERVAL_SECONDS", 60)
    # Re-send a reminder every N minutes while seats stay available.
    # 0 = only email once, when seats first appear.
    REALERT_MINUTES = _get_int("REALERT_MINUTES", 0)

    @classmethod
    def email_ready(cls):
        return bool(cls.GMAIL_ADDRESS and cls.GMAIL_APP_PASSWORD)

    @classmethod
    def missing_email_fields(cls):
        missing = []
        if not cls.GMAIL_ADDRESS:
            missing.append("GMAIL_ADDRESS")
        if not cls.GMAIL_APP_PASSWORD:
            missing.append("GMAIL_APP_PASSWORD")
        return missing
