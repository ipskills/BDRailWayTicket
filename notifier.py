"""
Email notifications via Gmail SMTP.

Requires an *app password* (not your normal Gmail password):
  1. Enable 2-Step Verification on the Google account.
  2. Create an app password at https://myaccount.google.com/apppasswords
  3. Put the 16-character password in GMAIL_APP_PASSWORD (see .env.example).
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailNotifier:
    def __init__(self, gmail_address, app_password, host="smtp.gmail.com", port=587):
        self.gmail_address = gmail_address
        self.app_password = app_password
        self.host = host
        self.port = port

    def _connect(self):
        context = ssl.create_default_context()
        server = smtplib.SMTP(self.host, self.port, timeout=30)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(self.gmail_address, self.app_password)
        return server

    def test_connection(self):
        """Verify credentials without sending anything."""
        try:
            server = self._connect()
            server.quit()
            return {"success": True, "message": "SMTP login OK"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def send(self, to_address, subject, body_text, body_html=None):
        if not to_address:
            return {"success": False, "message": "No recipient address set"}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.gmail_address
        msg["To"] = to_address
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        try:
            server = self._connect()
            server.sendmail(self.gmail_address, [to_address], msg.as_string())
            server.quit()
            return {"success": True, "message": f"Email sent to {to_address}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


def notifier_from_config(config):
    """Build an EmailNotifier from a Config-like object, or return None if the
    Gmail credentials aren't set."""
    address = getattr(config, "GMAIL_ADDRESS", None)
    password = getattr(config, "GMAIL_APP_PASSWORD", None)
    if not (address and password):
        return None
    return EmailNotifier(
        address,
        password,
        getattr(config, "SMTP_HOST", "smtp.gmail.com"),
        getattr(config, "SMTP_PORT", 587),
    )
