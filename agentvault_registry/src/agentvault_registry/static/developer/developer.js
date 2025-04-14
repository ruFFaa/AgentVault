console.log("Developer Portal JS Loaded.");

const API_BASE_PATH = "/api/v1"; // Re-define or import if needed
const API_KEY_STORAGE_ITEM = 'developerApiKey';

// DOM Elements
let loginSection, dashboardSection, apiKeyInput, loginButton, loginError, logoutButton, myCardsList, submitStatus;
// --- ADDED: Elements for submit form ---
let agentCardJsonTextarea, validateCardButton, submitCardButton, validationErrorsPre;
// --- END ADDED ---


// Helper function to escape HTML
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, function (match) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[match];
    });
}


document.addEventListener('DOMContentLoaded', () => {
    // Assign elements after DOM is loaded
    loginSection = document.getElementById('login-section');
    dashboardSection = document.getElementById('dashboard-section');
    apiKeyInput = document.getElementById('developer-api-key');
    loginButton = document.getElementById('login-button');
    loginError = document.getElementById('login-error');
    logoutButton = document.getElementById('logout-button');
    myCardsList = document.getElementById('my-cards-list');
    submitStatus = document.getElementById('submit-status');
    // --- ADDED: Assign submit form elements ---
    agentCardJsonTextarea = document.getElementById('agent-card-json');
    validateCardButton = document.getElementById('validate-card-button');
    submitCardButton = document.getElementById('submit-card-button');
    validationErrorsPre = document.getElementById('validation-errors');
    // --- END ADDED ---


    if (loginButton) {
        loginButton.addEventListener('click', handleLogin);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }
    // --- ADDED: Event listener for validate button ---
    if (validateCardButton) {
        validateCardButton.addEventListener('click', handleValidateCard);
    }
    // --- END ADDED ---
    // --- ADDED: Event listener for submit button ---
    if (submitCardButton) {
        submitCardButton.addEventListener('click', handleSubmitNewCard);
    }
    // --- END ADDED ---

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

    // Store key in sessionStorage and add warning
    try {
        sessionStorage.setItem(API_KEY_STORAGE_ITEM, apiKey);
        console.log("API Key stored in session storage.");
        // Add a security warning
        console.warn("SECURITY WARNING: API Key stored in sessionStorage. This is vulnerable to XSS attacks if the site has vulnerabilities. Ensure the site is secure.");
    } catch (e) {
        console.error("Failed to store API key in sessionStorage:", e);
        if (loginError) {
            loginError.textContent = 'Error storing API key. Please ensure sessionStorage is available and not full.';
            loginError.style.display = 'block';
        }
        return; // Don't proceed if storage failed
    }

    loginError.style.display = 'none'; // Hide error on successful login/storage
    showDashboard();
    loadOwnedCards(); // Load cards after login
}

function handleLogout() {
    sessionStorage.removeItem(API_KEY_STORAGE_ITEM);
    console.log("API Key removed from session storage.");
    if (myCardsList) myCardsList.innerHTML = ''; // Clear card list
    if (submitStatus) submitStatus.textContent = ''; // Clear submit status
    // --- ADDED: Clear validation errors on logout ---
    if (validationErrorsPre) validationErrorsPre.textContent = '';
    if (agentCardJsonTextarea) agentCardJsonTextarea.value = ''; // Clear textarea
    // --- END ADDED ---
    showLogin();
}


async function loadOwnedCards() {
    console.log("loadOwnedCards() called.");
    if (!myCardsList) return; // Exit if list element doesn't exist

    myCardsList.innerHTML = '<p>Fetching your agent cards...</p>';
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
        console.debug("Received owned cards data:", data);
        // Call the rendering function with the items
        renderOwnedCards(data.items || []); // Pass empty array if items is missing
    } catch (error) {
        console.error("Error loading owned cards:", error);
        myCardsList.innerHTML = `<p style="color: red;">Error loading your agent cards: ${escapeHTML(error.message || String(error))}</p>`;
    }
}

function renderOwnedCards(cards) {
    console.log(`Rendering ${cards.length} owned cards.`);
    if (!myCardsList) return; // Should exist, but safety check

    myCardsList.innerHTML = ''; // Clear previous content

    if (!cards || cards.length === 0) {
        myCardsList.innerHTML = '<p>No agent cards found for this developer.</p>';
        return;
    }

    cards.forEach(card => {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'agent-card'; // Reuse existing style if desired
        cardDiv.id = `owned-card-${card.id}`; // Add unique ID to card div

        const nameEl = document.createElement('h4');
        nameEl.textContent = card.name || 'Unnamed Card';

        const idEl = document.createElement('small');
        idEl.textContent = `ID: ${card.id}`;
        idEl.style.display = 'block'; // Make ID appear on its own line
        idEl.style.marginBottom = '10px';

        const descEl = document.createElement('p');
        descEl.textContent = card.description || 'No description.';
        descEl.style.marginBottom = '10px';

        const buttonDiv = document.createElement('div'); // Container for buttons

        const editButton = document.createElement('button');
        editButton.textContent = 'Edit';
        editButton.dataset.cardId = card.id; // Store ID for later use
        editButton.onclick = () => handleEditCard(card.id); // Placeholder handler
        editButton.style.marginRight = '5px';

        const deactivateButton = document.createElement('button');
        deactivateButton.textContent = 'Deactivate';
        deactivateButton.dataset.cardId = card.id;
        deactivateButton.onclick = () => handleDeactivateCard(card.id); // Use function reference
        deactivateButton.style.backgroundColor = '#ffc107'; // Warning color
        deactivateButton.style.color = '#333';

        buttonDiv.appendChild(editButton);
        buttonDiv.appendChild(deactivateButton);

        cardDiv.appendChild(nameEl);
        cardDiv.appendChild(idEl);
        cardDiv.appendChild(descEl);
        cardDiv.appendChild(buttonDiv);

        myCardsList.appendChild(cardDiv);
    });
}

// Placeholder handlers for buttons
function handleEditCard(cardId) {
    console.log(`Placeholder: Edit button clicked for card ID: ${cardId}`);
    alert(`Edit functionality for card ${cardId} not implemented yet.`);
    // TODO: Implement logic to populate the submit form with this card's data
}

// --- MODIFIED: Implement handleDeactivateCard ---
async function handleDeactivateCard(cardId) {
    console.log(`Deactivate button clicked for card ID: ${cardId}`);
    if (!submitStatus) return;

    // Clear previous status
    submitStatus.textContent = '';
    submitStatus.style.color = 'inherit';

    // Confirmation dialog
    if (!confirm(`Are you sure you want to deactivate Agent Card ${cardId}? This action cannot be undone directly through the UI.`)) {
        console.log("Deactivation cancelled by user.");
        return;
    }

    const deactivateUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    console.debug(`Sending DELETE request to: ${deactivateUrl}`);
    submitStatus.textContent = `Deactivating card ${cardId}...`;

    try {
        const response = await makeAuthenticatedRequest(deactivateUrl, {
            method: 'DELETE',
        });

        // DELETE returns 204 No Content on success
        if (response.status === 204) {
            submitStatus.textContent = `Agent Card ${cardId} deactivated successfully.`;
            submitStatus.style.color = 'green';
            // Optionally clear message after a delay
            setTimeout(() => { if (submitStatus.textContent.includes(cardId)) submitStatus.textContent = ''; }, 3000);
            loadOwnedCards(); // Refresh the list
        } else {
            // Handle unexpected success statuses or specific errors if needed
            let errorDetail = `Unexpected status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore if body isn't json */ }
             throw new Error(errorDetail); // Treat unexpected status as error
        }

    } catch (error) {
        // Catches errors from makeAuthenticatedRequest (like 401/403/404) or network errors
        console.error("Error during deactivation request:", error);
        submitStatus.textContent = `Error deactivating card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}
// --- END MODIFIED ---


// Helper for making authenticated requests
async function makeAuthenticatedRequest(url, options = {}) {
    const apiKey = getApiKey();
    if (!apiKey) {
        console.error("No API Key found for authenticated request. Logging out.");
        handleLogout(); // Force logout if key disappears
        throw new Error("Not authenticated"); // Stop the request
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

// Validation Handler
async function handleValidateCard() {
    console.log("Validate button clicked.");
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre) {
        console.error("Required elements for validation not found.");
        return;
    }

    const jsonText = agentCardJsonTextarea.value;
    submitStatus.textContent = ''; // Clear previous status
    submitStatus.style.color = 'inherit'; // Reset color
    validationErrorsPre.textContent = ''; // Clear previous errors
    validationErrorsPre.style.color = 'red'; // Set error color

    if (!jsonText.trim()) {
        validationErrorsPre.textContent = 'Error: JSON input cannot be empty.';
        return;
    }

    let parsedJson;
    try {
        parsedJson = JSON.parse(jsonText);
    } catch (e) {
        console.error("JSON parsing error:", e);
        validationErrorsPre.textContent = `Error: Invalid JSON format.\n${e.message}`;
        return;
    }

    const requestBody = { card_data: parsedJson };
    const validationUrl = `${API_BASE_PATH}/utils/validate-card`;

    console.debug(`Sending validation request to: ${validationUrl}`);
    submitStatus.textContent = 'Validating...';

    try {
        const response = await fetch(validationUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            // Handle non-2xx HTTP errors from the validation endpoint itself
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore if body isn't json */ }
            throw new Error(errorDetail);
        }

        const result = await response.json();
        console.debug("Validation response:", result);

        if (result.is_valid) {
            submitStatus.textContent = 'Card data is valid!';
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = ''; // Clear errors on success
        } else {
            submitStatus.textContent = 'Validation Failed.';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${result.detail || 'Unknown validation error.'}`;
        }

    } catch (error) {
        console.error("Error during validation request:", error);
        submitStatus.textContent = `Error during validation: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}

// Submit Handler
async function handleSubmitNewCard() {
    console.log("Submit New Card button clicked.");
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre) {
        console.error("Required elements for submission not found.");
        return;
    }

    const jsonText = agentCardJsonTextarea.value;
    submitStatus.textContent = ''; // Clear previous status
    submitStatus.style.color = 'inherit'; // Reset color
    validationErrorsPre.textContent = ''; // Clear previous errors
    validationErrorsPre.style.color = 'red'; // Set error color

    if (!jsonText.trim()) {
        validationErrorsPre.textContent = 'Error: JSON input cannot be empty.';
        return;
    }

    let parsedJson;
    try {
        parsedJson = JSON.parse(jsonText);
    } catch (e) {
        console.error("JSON parsing error:", e);
        validationErrorsPre.textContent = `Error: Invalid JSON format.\n${e.message}`;
        return;
    }

    const requestBody = { card_data: parsedJson };
    const submitUrl = `${API_BASE_PATH}/agent-cards/`;

    console.debug(`Sending submit request to: ${submitUrl}`);
    submitStatus.textContent = 'Submitting...';

    try {
        // Use the authenticated helper
        const response = await makeAuthenticatedRequest(submitUrl, {
            method: 'POST',
            body: JSON.stringify(requestBody),
            // Content-Type header is added by makeAuthenticatedRequest
        });

        // Check for specific API errors (besides 401/403 handled by helper)
        if (response.status === 201) {
            const newCard = await response.json();
            submitStatus.textContent = `Agent Card submitted successfully! ID: ${newCard.id}`;
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
            agentCardJsonTextarea.value = ''; // Clear textarea on success
            loadOwnedCards(); // Refresh the list
        } else if (response.status === 422) {
            const errorData = await response.json();
            console.error("Submission validation error:", errorData);
            submitStatus.textContent = 'Submission Failed (Validation Error).';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${errorData.detail || 'Unknown validation error.'}`;
        } else {
            // Handle other non-2xx errors
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore if body isn't json */ }
            throw new Error(errorDetail); // Treat unexpected status as error
        }

    } catch (error) {
        // Catches errors from makeAuthenticatedRequest (like 401/403) or network errors
        console.error("Error during submission request:", error);
        submitStatus.textContent = `Error during submission: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}


// TODO: Implement handleEditCard logic
