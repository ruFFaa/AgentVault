console.log("Developer Portal JS Loaded.");

const API_BASE_PATH = "/api/v1"; // Re-define or import if needed
const API_KEY_STORAGE_ITEM = 'developerApiKey';

// DOM Elements
let loginSection, dashboardSection, apiKeyInput, loginButton, loginError, logoutButton, myCardsList, submitStatus;
let agentCardJsonTextarea, validateCardButton, submitCardButton, validationErrorsPre;
// --- ADDED: Submit form section element for scrolling ---
let submitCardSection;
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
    agentCardJsonTextarea = document.getElementById('agent-card-json');
    validateCardButton = document.getElementById('validate-card-button');
    submitCardButton = document.getElementById('submit-card-button');
    validationErrorsPre = document.getElementById('validation-errors');
    // --- ADDED: Assign submit form section ---
    submitCardSection = document.getElementById('submit-card-section');
    // --- END ADDED ---


    if (loginButton) {
        loginButton.addEventListener('click', handleLogin);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }
    if (validateCardButton) {
        validateCardButton.addEventListener('click', handleValidateCard);
    }
    // --- MODIFIED: Set initial submit handler ---
    if (submitCardButton) {
        // Set the initial state
        resetSubmitForm();
    }
    // --- END MODIFIED ---

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
    if (validationErrorsPre) validationErrorsPre.textContent = '';
    if (agentCardJsonTextarea) agentCardJsonTextarea.value = ''; // Clear textarea
    // --- ADDED: Reset submit form on logout ---
    resetSubmitForm();
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
             let errorDetail = `HTTP error! status: ${response.status}`;
             try {
                 const errorData = await response.json();
                 errorDetail = errorData.detail || errorDetail;
             } catch (e) { /* ignore if body isn't json */ }
             throw new Error(errorDetail);
        }
        const data = await response.json();
        console.debug("Received owned cards data:", data);
        renderOwnedCards(data.items || []);
    } catch (error) {
        console.error("Error loading owned cards:", error);
        myCardsList.innerHTML = `<p style="color: red;">Error loading your agent cards: ${escapeHTML(error.message || String(error))}</p>`;
    }
}

function renderOwnedCards(cards) {
    console.log(`Rendering ${cards.length} owned cards.`);
    if (!myCardsList) return;

    myCardsList.innerHTML = '';

    if (!cards || cards.length === 0) {
        myCardsList.innerHTML = '<p>No agent cards found for this developer.</p>';
        return;
    }

    cards.forEach(card => {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'agent-card';
        cardDiv.id = `owned-card-${card.id}`;

        const nameEl = document.createElement('h4');
        nameEl.textContent = card.name || 'Unnamed Card';

        const idEl = document.createElement('small');
        idEl.textContent = `ID: ${card.id}`;
        idEl.style.display = 'block';
        idEl.style.marginBottom = '10px';

        const descEl = document.createElement('p');
        descEl.textContent = card.description || 'No description.';
        descEl.style.marginBottom = '10px';

        const buttonDiv = document.createElement('div');

        const editButton = document.createElement('button');
        editButton.textContent = 'Edit';
        editButton.dataset.cardId = card.id;
        // --- MODIFIED: Call implemented handleEditCard ---
        editButton.onclick = () => handleEditCard(card.id);
        // --- END MODIFIED ---
        editButton.style.marginRight = '5px';

        const deactivateButton = document.createElement('button');
        deactivateButton.textContent = 'Deactivate';
        deactivateButton.dataset.cardId = card.id;
        deactivateButton.onclick = () => handleDeactivateCard(card.id);
        deactivateButton.style.backgroundColor = '#ffc107';
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

// --- MODIFIED: Implemented handleEditCard ---
async function handleEditCard(cardId) {
    console.log(`Edit button clicked for card ID: ${cardId}`);
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre || !submitCardButton || !submitCardSection) {
        console.error("Required elements for editing not found.");
        return;
    }

    // Clear previous status/errors
    submitStatus.textContent = 'Fetching card data...';
    submitStatus.style.color = 'inherit';
    validationErrorsPre.textContent = '';
    agentCardJsonTextarea.value = ''; // Clear textarea initially

    const fetchUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    console.debug(`Fetching card details from: ${fetchUrl}`);

    try {
        const response = await makeAuthenticatedRequest(fetchUrl, { method: 'GET' });

        if (!response.ok) {
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore */ }
            throw new Error(errorDetail);
        }

        const cardFullData = await response.json();
        console.debug("Received card data for edit:", cardFullData);

        if (!cardFullData || !cardFullData.card_data) {
            throw new Error("Received invalid card data structure from server.");
        }

        // Pretty-print and populate textarea
        const cardJsonString = JSON.stringify(cardFullData.card_data, null, 2);
        agentCardJsonTextarea.value = cardJsonString;

        // Update submit button text and action
        submitCardButton.textContent = 'Update Card';
        submitCardButton.dataset.editingCardId = cardId; // Store ID for update handler
        // Remove previous listener (if any) and add new one
        submitCardButton.removeEventListener('click', handleSubmitNewCard);
        submitCardButton.removeEventListener('click', handleUpdateCardWrapper); // Remove wrapper if exists
        submitCardButton.addEventListener('click', handleUpdateCardWrapper);

        submitStatus.textContent = `Editing card ${cardId}. Make changes and click 'Update Card'.`;
        submitStatus.style.color = 'blue';

        // Scroll to the form
        submitCardSection.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error("Error fetching card for edit:", error);
        submitStatus.textContent = `Error fetching card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
        // Optionally reset form if fetch fails?
        // resetSubmitForm();
    }
}
// --- END MODIFIED ---

// Wrapper function to pass cardId to handleUpdateCard from event listener
function handleUpdateCardWrapper(event) {
    const button = event.target;
    const cardId = button.dataset.editingCardId;
    if (cardId) {
        handleUpdateCard(cardId);
    } else {
        console.error("Could not find card ID for update.");
        if(submitStatus) submitStatus.textContent = "Error: Could not determine which card to update.";
    }
}

// --- ADDED: handleUpdateCard function ---
async function handleUpdateCard(cardId) {
    console.log(`Update Card button clicked for card ID: ${cardId}`);
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre || !submitCardButton) {
        console.error("Required elements for update not found.");
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

    // AgentCardUpdate schema only requires card_data for PUT
    const requestBody = { card_data: parsedJson };
    const updateUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;

    console.debug(`Sending PUT request to: ${updateUrl}`);
    submitStatus.textContent = `Updating card ${cardId}...`;

    try {
        const response = await makeAuthenticatedRequest(updateUrl, {
            method: 'PUT',
            body: JSON.stringify(requestBody),
            // Content-Type header is added by makeAuthenticatedRequest
        });

        if (response.status === 200) { // PUT returns 200 OK on success
            const updatedCard = await response.json();
            submitStatus.textContent = `Agent Card ${cardId} updated successfully!`;
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
            agentCardJsonTextarea.value = ''; // Clear textarea
            resetSubmitForm(); // Reset button to "Submit New" state
            loadOwnedCards(); // Refresh the list
        } else if (response.status === 422) {
            const errorData = await response.json();
            console.error("Update validation error:", errorData);
            submitStatus.textContent = 'Update Failed (Validation Error).';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${errorData.detail || 'Unknown validation error.'}`;
        } else {
            // Handle other non-2xx errors (404, 500, etc.)
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore if body isn't json */ }
            throw new Error(errorDetail); // Treat unexpected status as error
        }

    } catch (error) {
        // Catches errors from makeAuthenticatedRequest (like 401/403) or network errors
        console.error("Error during update request:", error);
        submitStatus.textContent = `Error updating card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}
// --- END ADDED ---


async function handleDeactivateCard(cardId) {
    console.log(`Deactivate button clicked for card ID: ${cardId}`);
    if (!submitStatus) return;

    submitStatus.textContent = '';
    submitStatus.style.color = 'inherit';

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

        if (response.status === 204) {
            submitStatus.textContent = `Agent Card ${cardId} deactivated successfully.`;
            submitStatus.style.color = 'green';
            setTimeout(() => { if (submitStatus.textContent.includes(cardId)) submitStatus.textContent = ''; }, 3000);
            loadOwnedCards();
        } else {
            let errorDetail = `Unexpected status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore */ }
             throw new Error(errorDetail);
        }

    } catch (error) {
        console.error("Error during deactivation request:", error);
        submitStatus.textContent = `Error deactivating card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}


// Helper for making authenticated requests
async function makeAuthenticatedRequest(url, options = {}) {
    const apiKey = getApiKey();
    if (!apiKey) {
        console.error("No API Key found for authenticated request. Logging out.");
        handleLogout();
        throw new Error("Not authenticated");
    }

    options.headers = options.headers || {};
    options.headers['X-Api-Key'] = apiKey;
    if (options.body && !options.headers['Content-Type']) {
         options.headers['Content-Type'] = 'application/json';
    }

    console.debug(`Making authenticated request to: ${url}`, options);
    const response = await fetch(url, options);

    if (response.status === 401 || response.status === 403) {
        console.error("Authentication failed (401/403). Logging out.");
        handleLogout();
        let errorDetail = `Authentication failed: ${response.status}`;
         try {
             const errorData = await response.json();
             errorDetail = errorData.detail || errorDetail;
         } catch (e) { /* ignore */ }
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
    submitStatus.textContent = '';
    submitStatus.style.color = 'inherit';
    validationErrorsPre.textContent = '';
    validationErrorsPre.style.color = 'red';

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
            headers: { 'Content-Type': 'application/json', },
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore */ }
            throw new Error(errorDetail);
        }

        const result = await response.json();
        console.debug("Validation response:", result);

        if (result.is_valid) {
            submitStatus.textContent = 'Card data is valid!';
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
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
    submitStatus.textContent = '';
    submitStatus.style.color = 'inherit';
    validationErrorsPre.textContent = '';
    validationErrorsPre.style.color = 'red';

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
        const response = await makeAuthenticatedRequest(submitUrl, {
            method: 'POST',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 201) {
            const newCard = await response.json();
            submitStatus.textContent = `Agent Card submitted successfully! ID: ${newCard.id}`;
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
            agentCardJsonTextarea.value = '';
            loadOwnedCards();
        } else if (response.status === 422) {
            const errorData = await response.json();
            console.error("Submission validation error:", errorData);
            submitStatus.textContent = 'Submission Failed (Validation Error).';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${errorData.detail || 'Unknown validation error.'}`;
        } else {
            let errorDetail = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* ignore */ }
            throw new Error(errorDetail);
        }

    } catch (error) {
        console.error("Error during submission request:", error);
        submitStatus.textContent = `Error during submission: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}

// --- ADDED: Helper to reset submit form state ---
function resetSubmitForm() {
    if (submitCardButton) {
        submitCardButton.textContent = 'Submit New Card';
        delete submitCardButton.dataset.editingCardId; // Remove editing state
        // Remove potential update listener and ensure submit listener is attached
        submitCardButton.removeEventListener('click', handleUpdateCardWrapper);
        submitCardButton.removeEventListener('click', handleSubmitNewCard); // Remove first just in case
        submitCardButton.addEventListener('click', handleSubmitNewCard);
    }
    // Optional: Clear textarea and status messages as well?
    // if (agentCardJsonTextarea) agentCardJsonTextarea.value = '';
    // if (submitStatus) submitStatus.textContent = '';
    // if (validationErrorsPre) validationErrorsPre.textContent = '';
}
// --- END ADDED ---
