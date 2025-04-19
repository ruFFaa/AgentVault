console.log("Register JS Loaded.");

const API_BASE_PATH = "/auth"; // Auth endpoints prefix

// DOM Elements
const registerForm = document.getElementById('register-form');
const nameInput = document.getElementById('register-name');
const emailInput = document.getElementById('register-email');
const passwordInput = document.getElementById('register-password');
const confirmPasswordInput = document.getElementById('register-confirm-password');
const registerButton = document.getElementById('register-button');
const messageArea = document.getElementById('register-message');
const recoveryKeysDisplay = document.getElementById('recovery-keys-display');
const recoveryKeysList = document.getElementById('recovery-keys-list');
const registrationDisabledMessage = document.getElementById('registration-disabled-message'); // Added

// ===== ADDED: Disable form on load =====
document.addEventListener('DOMContentLoaded', () => {
    if (registrationDisabledMessage && registrationDisabledMessage.style.display !== 'none') {
        // If the disabled message is visible (meaning we intend to disable)
        if (registerForm) {
            const elementsToDisable = registerForm.querySelectorAll('input, button');
            elementsToDisable.forEach(el => el.disabled = true);
            console.log("Registration form disabled via JS due to temporary service outage.");
        }
    }
});
// ===== END ADDED =====

if (registerForm) {
    registerForm.addEventListener('submit', handleRegister);
}

async function handleRegister(event) {
    event.preventDefault(); // Prevent default form submission
    clearMessages();

    // ===== ADDED: Check if button is disabled before proceeding =====
    if (registerButton && registerButton.disabled) {
        showMessage("Registration is currently disabled.", true);
        return;
    }
    // ===== END ADDED =====

    setLoading(true);

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value; // Keep original for SecretStr
    const confirmPassword = confirmPasswordInput.value;

    // --- Client-side Validation ---
    if (!name || !email || !password || !confirmPassword) {
        showMessage("Please fill in all fields.", true);
        setLoading(false);
        return;
    }
    if (password.length < 8) {
        showMessage("Password must be at least 8 characters long.", true);
        setLoading(false);
        return;
    }
    if (password !== confirmPassword) {
        showMessage("Passwords do not match.", true);
        setLoading(false);
        return;
    }
    // Basic email format check (browser validation helps too)
    if (!validateEmail(email)) {
         showMessage("Please enter a valid email address.", true);
         setLoading(false);
         return;
    }

    // --- Prepare API Payload ---
    const payload = {
        name: name,
        email: email,
        password: password // Send plain password, backend handles hashing
    };

    // --- API Call ---
    try {
        const response = await fetch(`${API_BASE_PATH}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json' // Expect JSON response
            },
            body: JSON.stringify(payload)
        });

        const responseData = await response.json();

        // ===== MODIFIED: Check for 503 specifically =====
        if (response.status === 503) {
            showMessage(responseData.detail || "Registration is temporarily disabled.", true);
        } else if (response.status === 201) {
        // ===== END MODIFIED =====
            // Success
            showMessage(responseData.message || "Registration successful! Check your email.", false);
            displayRecoveryKeys(responseData.recovery_keys);
            registerForm.reset(); // Clear form
            registerButton.disabled = true; // Disable button after success
        } else {
            // Handle API errors (400, 409, 500 etc.)
            const errorMessage = responseData.detail || `Registration failed with status ${response.status}.`;
            showMessage(errorMessage, true);
            console.error("Registration API error:", responseData);
        }

    } catch (error) {
        console.error("Network or unexpected error during registration:", error);
        showMessage(`An unexpected error occurred: ${error.message || String(error)}`, true);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    if (registerButton) {
        // Only modify if not permanently disabled by the banner logic
        if (!registerButton.hasAttribute('data-permanently-disabled')) {
             registerButton.disabled = isLoading;
        }
        registerButton.textContent = isLoading ? 'Registering...' : 'Register';
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
    if (recoveryKeysDisplay) {
        recoveryKeysDisplay.style.display = 'none';
    }
    if (recoveryKeysList) {
        recoveryKeysList.innerHTML = '';
    }
}

function displayRecoveryKeys(keys) {
    if (!recoveryKeysDisplay || !recoveryKeysList || !keys || keys.length === 0) {
        return;
    }
    recoveryKeysList.innerHTML = ''; // Clear previous
    keys.forEach(key => {
        const li = document.createElement('li');
        li.textContent = key;
        recoveryKeysList.appendChild(li);
    });
    recoveryKeysDisplay.style.display = 'block';
}

function validateEmail(email) {
    // Simple regex for basic format check
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}
