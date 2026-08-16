import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def send_email(*, to_email: str, subject: str, content: str) -> bool:
    """Sends a plain-text email via SendGrid. Isolated in its own function
    so tests can monkeypatch this instead of hitting SendGrid's API.

    Returns False (rather than raising) when SENDGRID_API_KEY isn't
    configured or the send fails, so a broken email integration never
    blocks the thing that triggered it (e.g. feedback submission still
    succeeds and is still saved to the DB even if the email doesn't go out).
    """
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not configured -- skipping email to %s", to_email)
        return False

    message = Mail(
        from_email=settings.EMAIL_FROM,
        to_emails=to_email,
        subject=subject,
        plain_text_content=content,
    )
    try:
        SendGridAPIClient(settings.SENDGRID_API_KEY).send(message)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False