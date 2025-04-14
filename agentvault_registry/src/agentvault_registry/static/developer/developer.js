console.log("Developer Portal JS Loaded.");

const API_BASE_PATH = "/api/v1"; // Re-define or import if needed
const API_KEY_STORAGE_ITEM = 'developerApiKey';

// DOM Elements
let loginSection, dashboardSection, apiKeyInput, loginButton, loginError, logoutButton, myCardsList, submitStatus;

document.addEventListener('DOMContentLoaded', () => {
    // Assign elements after DOM is loaded
    loginSection = document.getElementById('login-section');
    dashboardSection = document.getElementById('dashboard-section');
    apiKeyInput = document.getElementById('developer-api-key');
    loginButton = document.getElementById('login-button');
    loginError = document.getElementById('login-error');
    logoutButton = document.getElementById('logout-button');
    myCardsList = document.getElementById('my-cards-list');
    submitStatus = document.getElementById('submit-status'); // Get submit status element

    if (loginButton) {
        loginButton.addEventListener('click', handleLogin);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    checkLoginStatus();
});

function getApiKey() {
    // Retrieve the key from sessionStorage
    return sessionStorage.getItem(API_KEY_STORAGE_ITEM);
}

function checkLoginStatus() {
    const apiKey = getApiKey();
    if (apiKey) {
        console.log("API Key found in session storage. Showing dashboard.");
        showDashboard();
        loadOwnedCards(); // Attempt to load cards
    } else {
        console.log("No API Key found. Showing login.");
        showLogin();
    }
}

function showLogin() {
    if (loginSection) loginSection.style.display = 'block';
    if (dashboardSection) dashboardSection.style.display = 'none';
    if (apiKeyInput) apiKeyInput.value = ''; // Clear input on show
    if (loginError) loginError.style.display = 'none'; // Hide error
}

function showDashboard() {
    if (loginSection) loginSection.style.display = 'none';
    if (dashboardSection) dashboardSection.style.display = 'block';
    if (loginError) loginError.style.display = 'none';
}

function handleLogin() {
    if (!apiKeyInput || !loginError) return;

    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        loginError.textContent = 'API Key cannot be empty.';
        loginError.style.display = 'block';
        return;
    }

    // Basic validation (can add more checks later if needed)
    if (!apiKey.startsWith('avreg_')) { // Example basic check
         loginError.textContent = 'Invalid API Key format (must start with avreg_).';
         loginError.style.display = 'block';
         return;
    }

    // --- ADDED: Store key in sessionStorage and add warning ---
    try {
        sessionStorage.setItem(API_KEY_STORAGE_ITEM, apiKey);
        console.log("API Key stored in session storage.");
        // Add a security warning
        console.warn("SECURITY WARNING: API Key stored in sessionStorage. This is vulnerable to XSS attacks if the site has vulnerabilities. Ensure the site is secure.");
        // Optionally display a less technical warning to the user if needed:
        // if (loginError) {
        //     loginError.textContent = 'Warning: Key stored for session only. Close browser to clear.';
        //     loginError.style.color = 'orange'; // Indicate warning
        //     loginError.style.display = 'block';
        // }
    } catch (e) {
        console.error("Failed to store API key in sessionStorage:", e);
        if (loginError) {
            loginError.textContent = 'Error storing API key. Please ensure sessionStorage is available and not full.';
            loginError.style.display = 'block';
        }
        return; // Don't proceed if storage failed
    }
    // --- END ADDED ---

    loginError.style.display = 'none'; // Hide error on successful login/storage
    showDashboard();
    loadOwnedCards(); // Load cards after login
}

function handleLogout() {
    sessionStorage.removeItem(API_KEY_STORAGE_ITEM);
    console.log("API Key removed from session storage.");
    if (myCardsList) myCardsList.innerHTML = ''; // Clear card list
    if (submitStatus) submitStatus.textContent = ''; // Clear submit status
    showLogin();
}

// Placeholder - will be implemented later
async function loadOwnedCards() {
    console.log("Placeholder: loadOwnedCards() called.");
    if (myCardsList) {
        myCardsList.innerHTML = '<p>Fetching your agent cards...</p>';
        // TODO: Implement API call using makeAuthenticatedRequest
        // Example structure:
        try {
            // Use owned_only=true parameter
            const response = await makeAuthenticatedRequest(`${API_BASE_PATH}/agent-cards/?owned_only=true`, { method: 'GET' });
            if (!response.ok) {
                 // Try to get error detail from response
                 let errorDetail = `HTTP error! status: ${response.status}`;
                 try {
                     const errorData = await response.json();
                     errorDetail = errorData.detail || errorDetail;
                 } catch (e) { /* ignore if body isn't json */ }
                 throw new Error(errorDetail);
            }
            const data = await response.json();
            // renderOwnedCards(data.items); // Need render function
            myCardsList.innerHTML = `<p>Card loading successful (but rendering not implemented yet). Found ${data.items.length} cards.</p>`; // Placeholder content
        } catch (error) {
            console.error("Error loading owned cards:", error);
            myCardsList.innerHTML = `<p style="color: red;">Error loading your agent cards: ${error.message || error}</p>`;
        }
        // myCardsList.innerHTML = '<p>Card loading not implemented yet.</p>'; // Placeholder content
    }
}

// Helper for making authenticated requests
async function makeAuthenticatedRequest(url, options = {}) {
    // --- MODIFIED: Retrieve key and handle missing key ---
    const apiKey = getApiKey();
    if (!apiKey) {
        console.error("No API Key found for authenticated request. Logging out.");
        handleLogout(); // Force logout if key disappears
        throw new Error("Not authenticated"); // Stop the request
    }
    // --- END MODIFIED ---

    // Ensure headers object exists
    options.headers = options.headers || {};
    // Add the API key header
    options.headers['X-Api-Key'] = apiKey;
    // Ensure Content-Type is set for POST/PUT if body exists
    if (options.body && !options.headers['Content-Type']) {
         options.headers['Content-Type'] = 'application/json';
    }

    console.debug(`Making authenticated request to: ${url}`, options);
    const response = await fetch(url, options);

    // Check for auth errors
    if (response.status === 401 || response.status === 403) {
        console.error("Authentication failed (401/403). Logging out.");
        handleLogout();
        // Throw an error to stop further processing in the calling function
        // Try to get detail from response body
        let errorDetail = `Authentication failed: ${response.status}`;
         try {
             const errorData = await response.json();
             errorDetail = errorData.detail || errorDetail;
         } catch (e) { /* ignore if body isn't json */ }
        throw new Error(errorDetail);
    }

    return response;
}


// TODO: Add event listeners for validate, submit buttons
// TODO: Implement renderOwnedCards function
// TODO: Implement validateCardData function
// TODO: Implement submitNewCard function
