console.log("Recover with Key JS Loaded.");

const API_BASE_PATH = "/auth"; // Auth endpoints prefix
const TEMP_TOKEN_STORAGE_ITEM = 'tempPasswordSetToken'; // Key for sessionStorage

// DOM Elements
const recoverForm = document.getElementById('recover-form');
const emailInput = document.getElementById('recover-email');
const recoveryKeyInput = document.getElementById('recover-key');
const recoverButton = document.getElementById('recover-button');
const messageArea = document.getElementById('recover-message-area');

if (recoverForm) {
    recoverForm.addEventListener('submit', handleRecoverySubmit);
}

async function handleRecoverySubmit(event) {
    event.preventDefault(); // Prevent default form submission
    clearMessages();
    setLoading(true);

    const email = emailInput.value.trim();
    const recoveryKey = recoveryKeyInput.value.trim();

    // Basic client-side validation
    if (!email || !recoveryKey) {
        showMessage("Please enter both email and recovery key.", true);
        setLoading(false);
        return;
    }
    // Basic email format check (browser validation helps too)
    if (!validateEmail(email)) {
         showMessage("Please enter a valid email address.", true);
         setLoading(false);
         return;
    }

    // Prepare API Payload
    const payload = {
        email: email,
        recovery_key: recoveryKey
    };

    // API Call
    try {
        const response = await fetch(`${API_BASE_PATH}/recover-account`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const responseData = await response.json();

        if (response.ok && responseData.access_token) {
            // Success - Store temporary token and redirect
            try {
                sessionStorage.setItem(TEMP_TOKEN_STORAGE_ITEM, responseData.access_token);
                console.log("Temporary password-set token stored in sessionStorage.");
                // Redirect to the page where the user sets the new password
                window.location.href = '/ui/set-new-password'; // Redirect to the next step
            } catch (e) {
                 console.error("Failed to store temporary token in sessionStorage:", e);
                 showMessage('Verification successful, but failed to prepare next step. Please ensure sessionStorage is enabled.', true);
            }
        } else {
            // Handle API errors (400, etc.)
            const errorMessage = responseData.detail || `Recovery failed with status ${response.status}.`;
            showMessage(errorMessage, true);
            console.error("Recovery API error:", responseData);
        }

    } catch (error) {
        console.error("Network or unexpected error during recovery:", error);
        showMessage(`An unexpected error occurred: ${error.message || String(error)}`, true);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    if (recoverButton) {
        recoverButton.disabled = isLoading;
        recoverButton.textContent = isLoading ? 'Verifying...' : 'Verify & Get Password Reset Token';
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

function validateEmail(email) {
    // Simple regex for basic format check
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}
