console.log("Developer Portal JS Loaded.");

const API_BASE_PATH = "/api/v1"; // Re-define or import if needed
const API_KEY_STORAGE_ITEM = 'developerApiKey';

// DOM Elements
let loginSection, dashboardSection, apiKeyInput, loginButton, loginError, logoutButton;
let developerInfoSpan, developerNameDisplay; // For logged in status
let myCardsList, submitStatus, statusFilterSelect; // Added statusFilterSelect
let agentCardJsonTextarea, validateCardButton, submitCardButton, validationErrorsPre, cancelEditButton; // Added cancelEditButton
let submitCardSection;


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
    developerInfoSpan = document.getElementById('developer-info'); // Added
    developerNameDisplay = document.getElementById('developer-name-display'); // Added
    myCardsList = document.getElementById('my-cards-list');
    statusFilterSelect = document.getElementById('status-filter'); // Added
    submitStatus = document.getElementById('submit-status');
    agentCardJsonTextarea = document.getElementById('agent-card-json');
    validateCardButton = document.getElementById('validate-card-button');
    submitCardButton = document.getElementById('submit-card-button');
    cancelEditButton = document.getElementById('cancel-edit-button'); // Added
    validationErrorsPre = document.getElementById('validation-errors');
    submitCardSection = document.getElementById('submit-card-section');


    if (loginButton) {
        loginButton.addEventListener('click', handleLogin);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }
    if (validateCardButton) {
        validateCardButton.addEventListener('click', handleValidateCard);
    }
    if (submitCardButton) {
        resetSubmitForm(); // Set initial state
    }
    // --- ADDED: Event listener for filter ---
    if (statusFilterSelect) {
        statusFilterSelect.addEventListener('change', handleFilterChange);
    }
    // --- ADDED: Event listener for cancel edit ---
    if (cancelEditButton) {
        cancelEditButton.addEventListener('click', resetSubmitForm); // Cancel just resets the form
    }

    checkLoginStatus();
});

function getApiKey() {
    return sessionStorage.getItem(API_KEY_STORAGE_ITEM);
}

function checkLoginStatus() {
    const apiKey = getApiKey();
    if (apiKey) {
        console.log("API Key found. Showing dashboard.");
        showDashboard();
        loadOwnedCards(); // Load cards using default filter initially
    } else {
        console.log("No API Key found. Showing login.");
        showLogin();
    }
}

function showLogin() {
    if (loginSection) loginSection.style.display = 'block';
    if (dashboardSection) dashboardSection.style.display = 'none';
    if (apiKeyInput) apiKeyInput.value = '';
    if (loginError) loginError.style.display = 'none';
    // --- ADDED: Hide dev info/logout ---
    if (developerInfoSpan) developerInfoSpan.style.display = 'none';
    if (logoutButton) logoutButton.style.display = 'none';
    // --- END ADDED ---
}

function showDashboard() {
    if (loginSection) loginSection.style.display = 'none';
    if (dashboardSection) dashboardSection.style.display = 'block';
    if (loginError) loginError.style.display = 'none';
    // --- ADDED: Show dev info/logout ---
    if (developerInfoSpan) developerInfoSpan.style.display = 'inline'; // Or 'block' if preferred
    if (logoutButton) logoutButton.style.display = 'inline-block'; // Or 'block'
    // Note: We don't have the developer name easily, so keep placeholder for now
    // if (developerNameDisplay) developerNameDisplay.textContent = "Developer";
    // --- END ADDED ---
}

function handleLogin() {
    if (!apiKeyInput || !loginError) return;

    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        loginError.textContent = 'API Key cannot be empty.';
        loginError.style.display = 'block';
        return;
    }

    if (!apiKey.startsWith('avreg_')) {
         loginError.textContent = 'Invalid API Key format (must start with avreg_).';
         loginError.style.display = 'block';
         return;
    }

    // --- MODIFIED: Verify key with a lightweight API call before storing ---
    // We'll try fetching owned cards. If it fails with 401/403, the key is bad.
    // If it succeeds (even with 0 cards), the key is good.
    console.log("Verifying API Key by attempting to fetch owned cards...");
    loginError.textContent = 'Verifying key...';
    loginError.style.color = 'inherit';
    loginError.style.display = 'block';

    const tempOptions = {
        method: 'GET',
        headers: { 'X-Api-Key': apiKey }
    };

    fetch(`${API_BASE_PATH}/agent-cards/?owned_only=true&limit=1`, tempOptions)
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                throw new Error(`Authentication failed (${response.status}). Invalid API Key.`);
            }
            if (!response.ok) {
                // Handle other potential server errors during verification
                throw new Error(`Verification failed with HTTP status: ${response.status}`);
            }
            // Key is valid if we get here
            console.log("API Key verified successfully.");
            try {
                sessionStorage.setItem(API_KEY_STORAGE_ITEM, apiKey);
                console.log("API Key stored in session storage.");
                console.warn("SECURITY WARNING: API Key stored in sessionStorage..."); // Keep warning
                loginError.style.display = 'none';
                showDashboard();
                loadOwnedCards(); // Load cards after successful verification
            } catch (e) {
                console.error("Failed to store API key in sessionStorage:", e);
                loginError.textContent = 'Error storing API key. Please ensure sessionStorage is available.';
                loginError.style.color = 'red';
                loginError.style.display = 'block';
            }
        })
        .catch(error => {
            console.error("API Key verification failed:", error);
            loginError.textContent = `Login Failed: ${error.message}`;
            loginError.style.color = 'red';
            loginError.style.display = 'block';
            sessionStorage.removeItem(API_KEY_STORAGE_ITEM); // Ensure key isn't stored if verification fails
        });
    // --- END MODIFIED ---
}

function handleLogout() {
    sessionStorage.removeItem(API_KEY_STORAGE_ITEM);
    console.log("API Key removed from session storage.");
    if (myCardsList) myCardsList.innerHTML = '';
    if (submitStatus) submitStatus.textContent = '';
    if (validationErrorsPre) validationErrorsPre.textContent = '';
    if (agentCardJsonTextarea) agentCardJsonTextarea.value = '';
    resetSubmitForm();
    showLogin();
}

// --- ADDED: Filter change handler ---
function handleFilterChange() {
    if (!statusFilterSelect) return;
    console.log(`Filter changed to: ${statusFilterSelect.value}`);
    loadOwnedCards(); // Reload cards with the new filter applied
}
// --- END ADDED ---


async function loadOwnedCards() {
    console.log("loadOwnedCards() called.");
    if (!myCardsList || !statusFilterSelect) return; // Check filter exists

    myCardsList.innerHTML = '<p>Fetching your agent cards...</p>';
    statusFilterSelect.disabled = true; // Disable filter during load

    // --- MODIFIED: Read filter value and adjust API params ---
    const filterValue = statusFilterSelect.value;
    let apiUrl = `${API_BASE_PATH}/agent-cards/?owned_only=true&limit=250`; // Base query
    if (filterValue === 'active') {
        apiUrl += '&active_only=true';
    } else if (filterValue === 'inactive') {
        apiUrl += '&active_only=false'; // Fetch all, will filter client-side below (or could rely on API if it supported inactive only)
        // Note: API doesn't have active_only=false AND inactive_only=true, so we fetch all and filter here
    } else { // 'all'
         apiUrl += '&active_only=false';
    }
    // --- END MODIFIED ---

    try {
        const response = await makeAuthenticatedRequest(apiUrl, { method: 'GET' });
        if (!response.ok) {
             let errorDetail = `HTTP error! status: ${response.status}`;
             try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
             throw new Error(errorDetail);
        }
        const data = await response.json();
        console.debug("Received owned cards data (summaries):", data);

        // Fetch full details for each card to get status
        const cardDetailPromises = (data.items || []).map(summary =>
            makeAuthenticatedRequest(`${API_BASE_PATH}/agent-cards/${summary.id}`, { method: 'GET' }).then(res => res.json())
        );
        let fullCardsData = await Promise.all(cardDetailPromises);
        console.debug("Received full card details:", fullCardsData);

        // --- ADDED: Client-side filter for 'inactive' if needed ---
        if (filterValue === 'inactive') {
            fullCardsData = fullCardsData.filter(card => card.is_active === false);
            console.debug("Filtered for inactive cards client-side:", fullCardsData);
        }
        // --- END ADDED ---

        renderOwnedCards(fullCardsData || []); // Render using the potentially filtered full card data

    } catch (error) {
        console.error("Error loading owned cards:", error);
        myCardsList.innerHTML = `<p style="color: red;">Error loading your agent cards: ${escapeHTML(error.message || String(error))}</p>`;
    } finally {
        statusFilterSelect.disabled = false; // Re-enable filter
    }
}

function renderOwnedCards(cards) {
    console.log(`Rendering ${cards.length} owned cards.`);
    if (!myCardsList) return;

    myCardsList.innerHTML = '';

    if (!cards || cards.length === 0) {
        const filterValue = statusFilterSelect ? statusFilterSelect.value : 'all';
        myCardsList.innerHTML = `<p>No agent cards found for this developer${filterValue !== 'all' ? ` with status '${filterValue}'` : ''}.</p>`;
        return;
    }

    // Sort cards, maybe active first? (Optional)
    cards.sort((a, b) => (a.is_active === b.is_active) ? 0 : a.is_active ? -1 : 1);

    cards.forEach(card => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `agent-card ${card.is_active ? 'active-card' : 'inactive-card'}`;
        cardDiv.id = `owned-card-${card.id}`;

        const nameEl = document.createElement('h4');
        const statusSpan = document.createElement('span');
        statusSpan.className = `card-status ${card.is_active ? 'card-status-active' : 'card-status-inactive'}`;
        statusSpan.textContent = card.is_active ? 'Active' : 'Inactive';
        nameEl.appendChild(statusSpan);
        nameEl.appendChild(document.createTextNode(card.name || 'Unnamed Card'));

        if (card.developer_is_verified) {
            const badge = document.createElement('span');
            badge.className = 'verified-badge';
            badge.textContent = 'Verified Dev';
            nameEl.appendChild(badge);
        }

        const idEl = document.createElement('div');
        idEl.className = 'card-id';
        idEl.textContent = `ID: ${card.id}`;

        const descEl = document.createElement('p');
        descEl.textContent = card.description || 'No description.';

        const buttonDiv = document.createElement('div');
        buttonDiv.className = 'card-actions';

        const editButton = document.createElement('button');
        editButton.textContent = 'View / Edit';
        editButton.className = 'button-edit';
        editButton.dataset.cardId = card.id;
        editButton.onclick = () => handleEditCard(card.id);

        const toggleStatusButton = document.createElement('button');
        toggleStatusButton.textContent = card.is_active ? 'Deactivate' : 'Activate';
        toggleStatusButton.className = `button-toggle-status ${card.is_active ? '' : 'activate'}`;
        toggleStatusButton.dataset.cardId = card.id;
        toggleStatusButton.onclick = () => handleToggleStatus(card.id);

        buttonDiv.appendChild(editButton);
        buttonDiv.appendChild(toggleStatusButton);

        cardDiv.appendChild(nameEl);
        cardDiv.appendChild(idEl);
        // Status is now part of the header (h4)
        cardDiv.appendChild(descEl);
        cardDiv.appendChild(buttonDiv);

        myCardsList.appendChild(cardDiv);
    });
}

async function handleEditCard(cardId) {
    // ... (handleEditCard remains mostly unchanged) ...
    console.log(`View/Edit button clicked for card ID: ${cardId}`);
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre || !submitCardButton || !submitCardSection || !cancelEditButton) { // Added cancelEditButton check
        console.error("Required elements for editing not found.");
        return;
    }

    submitStatus.textContent = 'Fetching card data...';
    submitStatus.style.color = 'inherit';
    validationErrorsPre.textContent = '';
    agentCardJsonTextarea.value = '';

    const fetchUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    console.debug(`Fetching card details from: ${fetchUrl}`);

    try {
        const response = await makeAuthenticatedRequest(fetchUrl, { method: 'GET' });

        if (!response.ok) {
            let errorDetail = `HTTP error! status: ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }
        const cardFullData = await response.json();
        console.debug("Received card data for edit:", cardFullData);

        if (!cardFullData || !cardFullData.card_data) {
            throw new Error("Received invalid card data structure from server.");
        }

        const cardJsonString = JSON.stringify(cardFullData.card_data, null, 2);
        agentCardJsonTextarea.value = cardJsonString;

        submitCardButton.textContent = 'Update Card';
        submitCardButton.dataset.editingCardId = cardId;
        submitCardButton.removeEventListener('click', handleSubmitNewCard);
        submitCardButton.removeEventListener('click', handleUpdateCardWrapper);
        submitCardButton.addEventListener('click', handleUpdateCardWrapper);

        cancelEditButton.style.display = 'inline-block'; // Show Cancel button

        submitStatus.textContent = `Editing card ${cardId}. Modify JSON and click 'Update Card'.`;
        submitStatus.style.color = 'blue';
        submitCardSection.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error("Error fetching card for edit:", error);
        submitStatus.textContent = `Error fetching card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
        resetSubmitForm(); // Reset form if fetch fails
    }
}

function handleUpdateCardWrapper(event) {
    // ... (handleUpdateCardWrapper remains unchanged) ...
    const button = event.target;
    const cardId = button.dataset.editingCardId;
    if (cardId) {
        handleUpdateCard(cardId);
    } else {
        console.error("Could not find card ID for update.");
        if(submitStatus) submitStatus.textContent = "Error: Could not determine which card to update.";
    }
}

async function handleUpdateCard(cardId) {
    // ... (handleUpdateCard remains unchanged) ...
    console.log(`Update Card button clicked for card ID: ${cardId}`);
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre || !submitCardButton) {
        console.error("Required elements for update not found.");
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
    try { parsedJson = JSON.parse(jsonText); } catch (e) {
        console.error("JSON parsing error:", e);
        validationErrorsPre.textContent = `Error: Invalid JSON format.\n${e.message}`;
        return;
    }

    const requestBody = { card_data: parsedJson }; // Only send card_data for PUT
    const updateUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;

    console.debug(`Sending PUT request to: ${updateUrl}`);
    submitStatus.textContent = `Updating card ${cardId}...`;

    try {
        const response = await makeAuthenticatedRequest(updateUrl, {
            method: 'PUT',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 200) {
            const updatedCard = await response.json();
            submitStatus.textContent = `Agent Card ${cardId} updated successfully!`;
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
            agentCardJsonTextarea.value = '';
            resetSubmitForm();
            loadOwnedCards(); // Refresh list
        } else if (response.status === 422) {
            const errorData = await response.json();
            console.error("Update validation error:", errorData);
            submitStatus.textContent = 'Update Failed (Validation Error).';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${errorData.detail || 'Unknown validation error.'}`;
        } else {
            let errorDetail = `HTTP error! status: ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }
    } catch (error) {
        console.error("Error during update request:", error);
        submitStatus.textContent = `Error updating card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}


async function handleToggleStatus(cardId) {
    // ... (handleToggleStatus remains unchanged) ...
    console.log(`Toggle Status button clicked for card ID: ${cardId}`);
    if (!submitStatus) return;

    submitStatus.textContent = `Fetching current status for ${cardId}...`;
    submitStatus.style.color = 'inherit';

    const fetchUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    let currentStatus = null;
    try {
        const response = await makeAuthenticatedRequest(fetchUrl, { method: 'GET' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const cardData = await response.json();
        currentStatus = cardData.is_active;
        console.log(`Current status for ${cardId} is ${currentStatus}`);
    } catch (error) {
        console.error("Error fetching current status:", error);
        submitStatus.textContent = `Error fetching status for card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
        return;
    }

    if (currentStatus === null) {
        submitStatus.textContent = `Error: Could not determine current status for card ${cardId}.`;
        submitStatus.style.color = 'red';
        return;
    }

    const action = currentStatus ? "Deactivate" : "Activate";
    const newStatus = !currentStatus;
    if (!confirm(`Are you sure you want to ${action.toLowerCase()} Agent Card ${cardId}?`)) {
        console.log(`${action} cancelled by user.`);
        submitStatus.textContent = `${action} cancelled.`;
        setTimeout(() => { if (submitStatus.textContent.includes('cancelled')) submitStatus.textContent = ''; }, 3000);
        return;
    }

    const updateUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    const requestBody = { is_active: newStatus };

    console.debug(`Sending PUT request to toggle status: ${updateUrl}`, requestBody);
    submitStatus.textContent = `${action.replace(/e$/, '')}ing card ${cardId}...`;

    try {
        const response = await makeAuthenticatedRequest(updateUrl, {
            method: 'PUT',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 200) {
            submitStatus.textContent = `Agent Card ${cardId} ${action.toLowerCase()}d successfully.`;
            submitStatus.style.color = 'green';
            setTimeout(() => { if (submitStatus.textContent.includes(cardId)) submitStatus.textContent = ''; }, 3000);
            loadOwnedCards();
        } else {
            let errorDetail = `Unexpected status: ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
             throw new Error(errorDetail);
        }

    } catch (error) {
        console.error(`Error during ${action.toLowerCase()} request:`, error);
        submitStatus.textContent = `Error ${action.toLowerCase()}ing card ${cardId}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}


async function makeAuthenticatedRequest(url, options = {}) {
    // ... (makeAuthenticatedRequest remains unchanged) ...
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

async function handleValidateCard() {
    // ... (handleValidateCard remains unchanged) ...
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
    try { parsedJson = JSON.parse(jsonText); } catch (e) {
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
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
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

async function handleSubmitNewCard() {
    // ... (handleSubmitNewCard remains unchanged) ...
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
    try { parsedJson = JSON.parse(jsonText); } catch (e) {
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
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }
    } catch (error) {
        console.error("Error during submission request:", error);
        submitStatus.textContent = `Error during submission: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}

function resetSubmitForm() {
    // --- MODIFIED: Also hide cancel button and clear textarea ---
    if (submitCardButton) {
        submitCardButton.textContent = 'Submit New Card';
        delete submitCardButton.dataset.editingCardId;
        submitCardButton.removeEventListener('click', handleUpdateCardWrapper);
        submitCardButton.removeEventListener('click', handleSubmitNewCard);
        submitCardButton.addEventListener('click', handleSubmitNewCard);
    }
    if (cancelEditButton) {
        cancelEditButton.style.display = 'none'; // Hide cancel button
    }
    if (agentCardJsonTextarea) {
        agentCardJsonTextarea.value = ''; // Clear editor
    }
    if (submitStatus) {
        submitStatus.textContent = ''; // Clear status message
        submitStatus.style.color = 'inherit';
    }
     if (validationErrorsPre) {
        validationErrorsPre.textContent = ''; // Clear validation errors
    }
    // --- END MODIFIED ---
}
