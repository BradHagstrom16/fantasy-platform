"""
utils/email.py
==============
Shared platform email helper.

All platform-level transactional email (auth, notifications) and game-specific
reminder content (Golf, CFB, World Cup) route through send_platform_email().

From-name: "The Commissioner's Club" for all outbound email.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)

PLATFORM_FROM_NAME = "The Commissioner's Club"


def send_platform_email(
    to_addr: str,
    subject: str,
    plain_body: str,
    html_body: str | None = None,
) -> bool:
    """
    Send a transactional platform email.

    Args:
        to_addr:    Recipient email address.
        subject:    Email subject line.
        plain_body: Plain-text fallback body (always required).
        html_body:  Optional HTML body — preferred by email clients.

    Returns:
        True if sent successfully, False otherwise.
    """
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('SMTP_PORT', 587))

    if not email_address or not email_password:
        logger.warning("Email credentials not configured — skipping send to %s", to_addr)
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{PLATFORM_FROM_NAME} <{email_address}>'
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(plain_body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        logger.info("Email sent to %s: %s", to_addr, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_addr)
        return False
