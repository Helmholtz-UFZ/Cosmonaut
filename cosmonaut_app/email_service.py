"""Email service for sending notifications via SMTP."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from cosmonaut_app.config import (
    EMAIL_PASSWORD,
    EMAIL_PORT,
    EMAIL_SENDER,
    EMAIL_SERVER,
    EMAIL_USERNAME,
)

log = logging.getLogger(__name__)


def send_mail(recipients, subject, body):
    """Send an email to one or more recipients via SMTP with STARTTLS.

    In test/dev environments (EMAIL_SERVER == "test"), logs the email
    instead of sending it.

    Args:
        recipients: List of email addresses.
        subject: Email subject line.
        body: Plain-text email body.
    """
    if EMAIL_SERVER == "test":
        log.info(
            f"Test mode — email not sent. "
            f"To: {recipients}, Subject: {subject}, Body length: {len(body)} chars"
        )
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    # Explicit display name: EMAIL_SENDER is currently the sister project's
    # mailbox (no cosmonaut@ufz.de exists yet) — the display name is what
    # identifies the sending app to recipients. If a COSMONAUT alias is ever
    # set up, only the env files need to change.
    msg["From"] = formataddr(("COSMONAUT", EMAIL_SENDER))
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(EMAIL_SERVER, int(EMAIL_PORT)) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        log.info(f"Email sent to {recipients}: {subject}")
    except Exception:  # noqa — SMTP, socket, DNS, … — never let email crash the caller
        log.error(f"Failed to send email to {recipients}: {subject}", exc_info=True)
