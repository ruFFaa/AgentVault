import logging
from typing import Optional, List
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr

from .config import settings # Import configured settings

logger = logging.getLogger(__name__)

# --- fastapi-mail Configuration ---
# Ensure required settings are present
if not all([settings.MAIL_USERNAME, settings.MAIL_PASSWORD, settings.MAIL_FROM, settings.MAIL_SERVER]):
    logger.warning("Email settings incomplete. Email sending disabled.")
    conf = None # Disable if not configured
else:
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True, # Recommended for production
        TEMPLATE_FOLDER=Path(__file__).parent / 'templates' / 'email' # Path to templates
    )
    logger.info(f"FastAPI-Mail configured for server: {settings.MAIL_SERVER}:{settings.MAIL_PORT}")

fm = FastMail(conf) if conf else None

async def send_email(
    subject: str,
    recipients: List[EmailStr],
    template_name: str, # Use template name instead of raw body
    template_body: dict # Dictionary for template context
):
    """Sends an email using fastapi-mail and templates."""
    if not fm:
        logger.error("Email sending is disabled due to missing configuration.")
        # In a real app, you might want to raise an exception or handle this differently
        return

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        template_body=template_body, # Pass context to template
        subtype=MessageType.html # Specify HTML content
    )

    try:
        logger.info(f"Attempting to send email. Subject: '{subject}', To: {recipients}, Template: {template_name}")
        await fm.send_message(message, template_name=template_name)
        logger.info(f"Email sent successfully to {recipients}.")
    except Exception as e:
        logger.exception(f"Failed to send email. Subject: '{subject}', To: {recipients}")
        # Decide how to handle failures (e.g., raise, log, queue for retry)

async def send_verification_email(to_email: EmailStr, username: str, token: str):
    """Sends the email verification email."""
    subject = f"Verify your email for {settings.PROJECT_NAME}"
    # Ensure BASE_URL ends with a slash if needed, or construct carefully
    verification_link = f"{str(settings.BASE_URL).rstrip('/')}/auth/verify-email?token={token}"
    template_body = {
        "username": username,
        "verification_link": verification_link,
        "project_name": settings.PROJECT_NAME
    }
    await send_email(subject, [to_email], "verification.html", template_body)

async def send_password_reset_email(to_email: EmailStr, username: str, token: str):
    """Sends the password reset email."""
    subject = f"Password Reset Request for {settings.PROJECT_NAME}"
    # Link points to the UI page which will handle the token
    reset_link = f"{str(settings.BASE_URL).rstrip('/')}/ui/reset-password?token={token}"
    template_body = {
        "username": username,
        "reset_link": reset_link,
        "project_name": settings.PROJECT_NAME
    }
    await send_email(subject, [to_email], "password_reset.html", template_body)
