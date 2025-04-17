console.log("Login JS Loaded.");

const API_BASE_PATH = "/auth"; // Auth endpoints prefix
const JWT_STORAGE_ITEM = 'developerJsonWebToken'; // Key for localStorage

// DOM Elements
const loginForm = document.getElementById('login-form');
const emailInput = document.getElementById('login-email');
const passwordInput = document.getElementById('login-password');
const loginButton = document.getElementById('login-button');
const messageArea = document.getElementById('login-message');

if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
}

async function handleLogin(event) {
    event.preventDefault(); // Prevent default form submission
    clearMessages();
    setLoading(true);

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    // Basic client-side validation
    if (!email || !password) {
        showMessage("Please enter both email and password.", true);
        setLoading(false);
        return;
    }

    // Prepare form data for OAuth2PasswordRequestForm
    const formData = new FormData();
    formData.append('username', email); // FastAPI expects 'username' for email here
    formData.append('password', password);
    // grant_type is added automatically by OAuth2PasswordRequestForm dependency

    // API Call
    try {
        const response = await fetch(`${API_BASE_PATH}/login`, {
            method: 'POST',
            // DO NOT set Content-Type header when sending FormData,
            // the browser will set it correctly with the boundary.
            body: formData
        });

        const responseData = await response.json();

        if (response.status === 200 && responseData.access_token) {
            // Success
            try {
                localStorage.setItem(JWT_STORAGE_ITEM, responseData.access_token);
                console.log("JWT stored in localStorage.");
                // Redirect to the developer dashboard
                window.location.href = '/ui/developer';
            } catch (e) {
                 console.error("Failed to store JWT in localStorage:", e);
                 showMessage('Login successful, but failed to store session. Please ensure localStorage is enabled.', true);
            }
        } else {
            // Handle API errors (401, etc.)
            const errorMessage = responseData.detail || `Login failed with status ${response.status}.`;
            showMessage(errorMessage, true); // Show specific error from API if available
            console.error("Login API error:", responseData);
        }

    } catch (error) {
        console.error("Network or unexpected error during login:", error);
        showMessage(`An unexpected error occurred: ${error.message || String(error)}`, true);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    if (loginButton) {
        loginButton.disabled = isLoading;
        loginButton.textContent = isLoading ? 'Logging In...' : 'Login';
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
