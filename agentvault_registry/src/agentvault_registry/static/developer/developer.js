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


    // TODO: Optionally verify key against a simple backend endpoint before storing?
    // For now, just store it.

    sessionStorage.setItem(API_KEY_STORAGE_ITEM, apiKey);
    console.log("API Key stored in session storage.");
    loginError.style.display = 'none';
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
        // try {
        //     const response = await makeAuthenticatedRequest(`${API_BASE_PATH}/agent-cards/?developer_owned=true`, { method: 'GET' }); // Need API endpoint for this
        //     if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
        //     const data = await response.json();
        //     renderOwnedCards(data.items); // Need render function
        // } catch (error) {
        //     console.error("Error loading owned cards:", error);
        //     myCardsList.innerHTML = '<p style="color: red;">Error loading your agent cards.</p>';
        // }
        myCardsList.innerHTML = '<p>Card loading not implemented yet.</p>'; // Placeholder content
    }
}

// Helper for making authenticated requests
async function makeAuthenticatedRequest(url, options = {}) {
    const apiKey = getApiKey();
    if (!apiKey) {
        console.error("No API Key found for authenticated request.");
        handleLogout(); // Force logout if key disappears
        throw new Error("Not authenticated");
    }

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
        throw new Error(`Authentication failed: ${response.status}`);
    }

    return response;
}


// TODO: Add event listeners for validate, submit buttons
// TODO: Implement renderOwnedCards function
// TODO: Implement validateCardData function
// TODO: Implement submitNewCard function
