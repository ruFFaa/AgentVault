import pytest
import logging
from unittest.mock import patch, AsyncMock, ANY
# --- MODIFIED: Removed EmailStr import ---
# from pydantic import EmailStr
# --- END MODIFIED ---

# Import functions to test
from agentvault_registry.email_utils import (
    send_verification_email,
    send_password_reset_email,
    send_email # Also test the base function indirectly
)
# Import settings for checking project name usage
from agentvault_registry.config import settings
# Import MessageSchema for type checking
from fastapi_mail import MessageSchema

# --- Test send_verification_email ---

@pytest.mark.asyncio
@patch("agentvault_registry.email_utils.fm", new_callable=AsyncMock) # Mock the fm instance
async def test_send_verification_email_success(mock_fm: AsyncMock):
    """Test sending a verification email successfully."""
    # Arrange
    # --- MODIFIED: Use plain string for email ---
    test_email = "test@example.com"
    # --- END MODIFIED ---
    test_username = "TestUser"
    test_token = "verify_token_123"
    expected_subject = f"Verify your email for {settings.PROJECT_NAME}"
    expected_template = "verification.html"
    expected_link_part = f"/auth/verify-email?token={test_token}"

    # Mock the send_message method on the mocked fm instance
    mock_fm.send_message = AsyncMock()

    # Act
    await send_verification_email(test_email, test_username, test_token)

    # Assert
    mock_fm.send_message.assert_awaited_once()
    # Check the arguments passed to send_message
    call_args, call_kwargs = mock_fm.send_message.call_args
    assert len(call_args) == 1 # Should be called with the MessageSchema object
    message_arg = call_args[0]
    assert isinstance(message_arg, MessageSchema)
    assert call_kwargs.get("template_name") == expected_template

    # Check the content of the MessageSchema
    assert message_arg.subject == expected_subject
    assert message_arg.recipients == [test_email] # Compare with plain string
    assert isinstance(message_arg.template_body, dict)
    assert message_arg.template_body.get("username") == test_username
    assert message_arg.template_body.get("project_name") == settings.PROJECT_NAME
    assert "verification_link" in message_arg.template_body
    assert expected_link_part in message_arg.template_body["verification_link"]

# --- Test send_password_reset_email ---

@pytest.mark.asyncio
@patch("agentvault_registry.email_utils.fm", new_callable=AsyncMock) # Mock the fm instance
async def test_send_password_reset_email_success(mock_fm: AsyncMock):
    """Test sending a password reset email successfully."""
    # Arrange
    # --- MODIFIED: Use plain string for email ---
    test_email = "reset@example.com"
    # --- END MODIFIED ---
    test_username = "ResetUser"
    test_token = "reset_token_456"
    expected_subject = f"Password Reset Request for {settings.PROJECT_NAME}"
    expected_template = "password_reset.html"
    expected_link_part = f"/ui/reset-password?token={test_token}" # Points to UI

    # Mock the send_message method
    mock_fm.send_message = AsyncMock()

    # Act
    await send_password_reset_email(test_email, test_username, test_token)

    # Assert
    mock_fm.send_message.assert_awaited_once()
    # Check the arguments passed to send_message
    call_args, call_kwargs = mock_fm.send_message.call_args
    assert len(call_args) == 1
    message_arg = call_args[0]
    assert isinstance(message_arg, MessageSchema)
    assert call_kwargs.get("template_name") == expected_template

    # Check the content of the MessageSchema
    assert message_arg.subject == expected_subject
    assert message_arg.recipients == [test_email] # Compare with plain string
    assert isinstance(message_arg.template_body, dict)
    assert message_arg.template_body.get("username") == test_username
    assert message_arg.template_body.get("project_name") == settings.PROJECT_NAME
    assert "reset_link" in message_arg.template_body
    assert expected_link_part in message_arg.template_body["reset_link"]

# --- Test send_email base function when fm is None ---

@pytest.mark.asyncio
@patch("agentvault_registry.email_utils.fm", None) # Patch fm to be None
@patch("agentvault_registry.email_utils.logger.error") # Mock logger.error
async def test_send_email_fm_is_none(mock_logger_error):
    """Test that send_email logs error and doesn't raise if fm is None."""
    # Act
    # Call the base function directly (though usually called by others)
    await send_email(
        subject="Test Subject",
        # --- MODIFIED: Use plain string for email ---
        recipients=["no-send@example.com"],
        # --- END MODIFIED ---
        template_name="test.html",
        template_body={"key": "value"}
    )

    # Assert
    mock_logger_error.assert_called_once_with(
        "Email sending is disabled due to missing configuration."
    )

# --- Test send_email base function error handling ---

@pytest.mark.asyncio
@patch("agentvault_registry.email_utils.fm", new_callable=AsyncMock) # Mock the fm instance
@patch("agentvault_registry.email_utils.logger.exception") # Mock logger.exception
async def test_send_email_send_message_raises_error(mock_logger_exception, mock_fm: AsyncMock):
    """Test that send_email logs exception if fm.send_message fails."""
    # Arrange
    # --- MODIFIED: Use plain string for email ---
    test_email = "fail@example.com"
    # --- END MODIFIED ---
    test_subject = "Failure Test"
    error_message = "SMTP Connection Error"
    mock_fm.send_message = AsyncMock(side_effect=Exception(error_message))

    # Act
    await send_email(
        subject=test_subject,
        recipients=[test_email], # Pass plain string
        template_name="fail.html",
        template_body={"user": "fail_user"}
    )

    # Assert
    mock_fm.send_message.assert_awaited_once()
    mock_logger_exception.assert_called_once()
    # Check that the log message contains relevant info
    log_call_args = mock_logger_exception.call_args[0]
    assert f"Failed to send email. Subject: '{test_subject}', To: {['fail@example.com']}" in log_call_args[0]
