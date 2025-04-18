import logging
from typing import Optional, List
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr

from .config import settings # Import configured settings

logger = logging.getLogger(__name__)

# --- fastapi-mail Configuration ---
# Check if essential server settings are present for basic connection
if settings.MAIL_SERVER and settings.MAIL_FROM:
    # --- MODIFIED: Conditional Credentials/TLS ---
    use_credentials = bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD)
    # Only enable STARTTLS if credentials are used AND MAIL_STARTTLS is True
    # Disable STARTTLS if SSL_TLS is True (they are mutually exclusive)
    use_starttls = use_credentials and settings.MAIL_STARTTLS and not settings.MAIL_SSL_TLS
    use_ssl_tls = use_credentials and settings.MAIL_SSL_TLS # Only enable SSL if creds are used

    logger.info(f"Configuring FastAPI-Mail:")
    logger.info(f"  Server: {settings.MAIL_SERVER}:{settings.MAIL_PORT}")
    logger.info(f"  Use Credentials: {use_credentials}")
    logger.info(f"  Use STARTTLS: {use_starttls}")
    logger.info(f"  Use SSL/TLS: {use_ssl_tls}")

    # --- ADDED: Debug log for ConnectionConfig values ---
    logger.debug(f"DEBUG EMAIL_UTILS: ConnectionConfig params - "
                 f"MAIL_USERNAME='{settings.MAIL_USERNAME or ''}', "
                 f"MAIL_PASSWORD='*****' (hidden), " # Hide password in logs
                 f"MAIL_FROM='{settings.MAIL_FROM}', "
                 f"MAIL_PORT={settings.MAIL_PORT}, "
                 f"MAIL_SERVER='{settings.MAIL_SERVER}', "
                 f"MAIL_STARTTLS={use_starttls}, "
                 f"MAIL_SSL_TLS={use_ssl_tls}, "
                 f"USE_CREDENTIALS={use_credentials}")
    # --- END ADDED ---

    conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME or "", # Provide empty string if None
        MAIL_PASSWORD=settings.MAIL_PASSWORD or "", # Provide empty string if None
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=use_starttls,
        MAIL_SSL_TLS=use_ssl_tls,
        USE_CREDENTIALS=use_credentials,
        VALIDATE_CERTS=True, # Keep True for real servers
        TEMPLATE_FOLDER=Path(__file__).parent / 'templates' / 'email' # Path to templates
    )
    # --- END MODIFIED ---
else:
    logger.warning("Email settings (MAIL_SERVER, MAIL_FROM) are incomplete. Email sending disabled.")
    conf = None # Disable if not configured


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
