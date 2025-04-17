console.log("Set New Password JS Loaded.");

const API_BASE_PATH = "/auth"; // Auth endpoints prefix
const TEMP_TOKEN_STORAGE_ITEM = 'tempPasswordSetToken'; // Key for sessionStorage

// DOM Elements
const setPasswordForm = document.getElementById('set-password-form');
const newPasswordInput = document.getElementById('new-password');
const confirmPasswordInput = document.getElementById('confirm-new-password');
const setPasswordButton = document.getElementById('set-password-button');
const messageArea = document.getElementById('set-password-message');

// Check for token immediately on load
const tempToken = sessionStorage.getItem(TEMP_TOKEN_STORAGE_ITEM);
if (!tempToken) {
    showMessage("No valid recovery session found. Please start the recovery process again.", true);
    // Disable form if no token
    if (setPasswordForm) setPasswordForm.style.display = 'none';
    // Optionally redirect after a delay
    // setTimeout(() => { window.location.href = '/ui/login'; }, 4000);
}

if (setPasswordForm) {
    setPasswordForm.addEventListener('submit', handleSetPasswordSubmit);
}

async function handleSetPasswordSubmit(event) {
    event.preventDefault();
    clearMessages();
    setLoading(true);

    const newPassword = newPasswordInput.value; // Keep raw value
    const confirmPassword = confirmPasswordInput.value;

    // Client-side Validation
    if (!newPassword || !confirmPassword) {
        showMessage("Please enter and confirm your new password.", true);
        setLoading(false);
        return;
    }
    if (newPassword.length < 8) {
        showMessage("Password must be at least 8 characters long.", true);
        setLoading(false);
        return;
    }
    if (newPassword !== confirmPassword) {
        showMessage("Passwords do not match.", true);
        setLoading(false);
        return;
    }

    // Get the temporary token
    const token = sessionStorage.getItem(TEMP_TOKEN_STORAGE_ITEM);
    if (!token) {
        showMessage("Recovery session expired or invalid. Please start again.", true);
        setLoading(false);
        return;
    }

    // Prepare API Payload
    const payload = {
        new_password: newPassword // Send plain password
    };

    // API Call
    try {
        const response = await fetch(`${API_BASE_PATH}/set-new-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${token}` // Use the temporary token
            },
            body: JSON.stringify(payload)
        });

        const responseData = await response.json();

        if (response.ok) {
            // Success
            showMessage("Password updated successfully! Redirecting to login...", false);
            sessionStorage.removeItem(TEMP_TOKEN_STORAGE_ITEM); // Clear the used token
            setPasswordButton.disabled = true; // Disable button
            // Redirect after a short delay
            setTimeout(() => { window.location.href = '/ui/login'; }, 2500);
        } else {
            // Handle API errors (400, 401, 404, 500 etc.)
            const errorMessage = responseData.detail || `Password update failed with status ${response.status}.`;
            showMessage(errorMessage, true);
            console.error("Set password API error:", responseData);
            // If token was invalid (401), clear it
            if (response.status === 401) {
                sessionStorage.removeItem(TEMP_TOKEN_STORAGE_ITEM);
            }
        }

    } catch (error) {
        console.error("Network or unexpected error during password set:", error);
        showMessage(`An unexpected error occurred: ${error.message || String(error)}`, true);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    if (setPasswordButton) {
        setPasswordButton.disabled = isLoading;
        setPasswordButton.textContent = isLoading ? 'Setting Password...' : 'Set New Password';
    }
}

function showMessage(msg, isError = false) {
    if (messageArea) {
        messageArea.textContent = msg;
        messageArea.className = isError ? 'message-area error' : 'message-area success';
        messageArea.style.display = 'block';
    }
}

function clearMessages() {
    if (messageArea) {
        messageArea.textContent = '';
        messageArea.style.display = 'none';
    }
}
