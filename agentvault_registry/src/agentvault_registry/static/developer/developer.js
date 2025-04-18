console.log("Developer Portal JS Loaded.");

const API_BASE_PATH = "/api/v1";
const AUTH_BASE_PATH = "/auth"; // For auth specific endpoints
const DEV_BASE_PATH = "/developers"; // For developer specific endpoints
const BUILDER_BASE_PATH = "/agent-builder"; // For builder endpoint
const JWT_STORAGE_ITEM = 'developerJsonWebToken'; // Use localStorage now

// DOM Elements
let loginRequiredMessage, dashboardSection, logoutButton;
let developerInfoSpan, developerNameDisplay, developerEmailDisplay;
let myCardsList, statusFilterSelect;
let agentCardJsonTextarea, validateCardButton, submitCardButton, validationErrorsPre, cancelEditButton, submitStatus;
let submitCardSection;
// API Key Elements
let apiKeysTable, apiKeysTbody, generateKeyButton, newKeyDescriptionInput, newKeyResultDiv, newPlainKeyPre, copyKeyButton, generateKeyMessage;
// Agent Builder Elements
let agentBuilderTypeRadios, wrapperConfigSection, adkConfigSection, generatePackageButton, generatePackageMessage;
let builderWrapperAuthSelect, builderWrapperServiceIdGroup, builderWrapperServiceIdInput;


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
    loginRequiredMessage = document.getElementById('login-required-message');
    dashboardSection = document.getElementById('dashboard-section');
    logoutButton = document.getElementById('logout-button');
    developerInfoSpan = document.getElementById('developer-info');
    developerNameDisplay = document.getElementById('developer-name-display');
    developerEmailDisplay = document.getElementById('developer-email-display'); // Added

    myCardsList = document.getElementById('my-cards-list');
    statusFilterSelect = document.getElementById('status-filter');

    submitCardSection = document.getElementById('submit-card-section');
    agentCardJsonTextarea = document.getElementById('agent-card-json');
    validateCardButton = document.getElementById('validate-card-button');
    submitCardButton = document.getElementById('submit-card-button');
    cancelEditButton = document.getElementById('cancel-edit-button');
    validationErrorsPre = document.getElementById('validation-errors');
    submitStatus = document.getElementById('submit-status');

    // API Key Elements
    apiKeysTable = document.getElementById('api-keys-table');
    apiKeysTbody = document.getElementById('api-keys-tbody');
    generateKeyButton = document.getElementById('generate-key-button');
    newKeyDescriptionInput = document.getElementById('new-key-description');
    newKeyResultDiv = document.getElementById('new-key-result');
    newPlainKeyPre = document.getElementById('new-plain-key');
    copyKeyButton = document.getElementById('copy-key-button');
    generateKeyMessage = document.getElementById('generate-key-message');

    // Agent Builder Elements
    agentBuilderTypeRadios = document.querySelectorAll('input[name="agent_builder_type"]');
    wrapperConfigSection = document.getElementById('wrapper-agent-config-section');
    adkConfigSection = document.getElementById('adk-agent-config-section');
    generatePackageButton = document.getElementById('generate-package-button');
    generatePackageMessage = document.getElementById('generate-package-message');
    builderWrapperAuthSelect = document.getElementById('builder-wrapper-auth');
    builderWrapperServiceIdGroup = document.getElementById('builder-wrapper-service-id-group');
    builderWrapperServiceIdInput = document.getElementById('builder-wrapper-service-id');


    // --- Event Listeners ---
    if (logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }
    if (validateCardButton) {
        validateCardButton.addEventListener('click', handleValidateCard);
    }
    if (submitCardButton) {
        resetSubmitForm(); // Set initial state for manual JSON submit
    }
    if (statusFilterSelect) {
        statusFilterSelect.addEventListener('change', handleFilterChange);
    }
    if (cancelEditButton) {
        cancelEditButton.addEventListener('click', resetSubmitForm);
    }
    if (generateKeyButton) {
        generateKeyButton.addEventListener('click', handleGenerateApiKey);
    }
    if (copyKeyButton) {
        copyKeyButton.addEventListener('click', handleCopyApiKey);
    }
    if (agentBuilderTypeRadios) {
        agentBuilderTypeRadios.forEach(radio => {
            radio.addEventListener('change', handleBuilderTypeChange);
        });
        // --- ADDED: Set initial builder section visibility ---
        handleBuilderTypeChange(); // Call once on load
        // --- END ADDED ---
    }
    if (generatePackageButton) {
        generatePackageButton.addEventListener('click', handleGenerateAgentPackage);
    }
    if (builderWrapperAuthSelect) {
        builderWrapperAuthSelect.addEventListener('change', handleWrapperAuthTypeChange);
        // --- ADDED: Set initial auth section visibility ---
        handleWrapperAuthTypeChange(); // Call once on load
        // --- END ADDED ---
    }

    // Initial check
    checkLoginStatusAndLoadData();
});

function getJwtToken() {
    return localStorage.getItem(JWT_STORAGE_ITEM);
}

async function checkLoginStatusAndLoadData() {
    const token = getJwtToken();
    if (token) {
        console.log("JWT found. Verifying token and fetching developer info...");
        try {
            const response = await makeAuthenticatedRequest(`${DEV_BASE_PATH}/me`, { method: 'GET' });
            if (!response.ok) {
                // Token might be expired or invalid
                throw new Error(`Verification failed: ${response.status}`);
            }
            const developerData = await response.json();
            console.log("Developer info fetched:", developerData);
            // Store name/email if needed elsewhere, update UI
            if (developerNameDisplay) developerNameDisplay.textContent = developerData.name || 'N/A';
            if (developerEmailDisplay) developerEmailDisplay.textContent = developerData.email || 'N/A'; // Display email
            showDashboard();
            loadOwnedCards(); // Load cards using default filter initially
            loadApiKeys(); // Load API keys
        } catch (error) {
            console.error("Token verification failed:", error);
            handleLogout(); // Clear invalid token and show login
        }
    } else {
        console.log("No JWT found. Showing login required message.");
        showLoginRequired();
    }
}

function showLoginRequired() {
    if (loginRequiredMessage) loginRequiredMessage.style.display = 'block';
    if (dashboardSection) dashboardSection.style.display = 'none';
    // Hide header elements that require login
    if (developerInfoSpan) developerInfoSpan.style.display = 'none';
    if (logoutButton) logoutButton.style.display = 'none';
}

function showDashboard() {
    if (loginRequiredMessage) loginRequiredMessage.style.display = 'none';
    if (dashboardSection) dashboardSection.style.display = 'block';
    // Show header elements
    if (developerInfoSpan) developerInfoSpan.style.display = 'inline';
    if (logoutButton) logoutButton.style.display = 'inline-block';
}

function handleLogout() {
    localStorage.removeItem(JWT_STORAGE_ITEM);
    console.log("JWT removed from localStorage.");
    // Clear UI state
    if (myCardsList) myCardsList.innerHTML = '';
    if (apiKeysTbody) apiKeysTbody.innerHTML = '';
    if (submitStatus) submitStatus.textContent = '';
    if (validationErrorsPre) validationErrorsPre.textContent = '';
    if (agentCardJsonTextarea) agentCardJsonTextarea.value = '';
    if (generateKeyMessage) generateKeyMessage.textContent = '';
    if (newKeyResultDiv) newKeyResultDiv.style.display = 'none';
    if (generatePackageMessage) generatePackageMessage.textContent = '';
    resetSubmitForm();
    // Redirect to login page or show login required message
    // window.location.href = '/ui/login'; // Or just show the message
    showLoginRequired();
}

function handleFilterChange() {
    if (!statusFilterSelect) return;
    console.log(`Filter changed to: ${statusFilterSelect.value}`);
    loadOwnedCards(); // Reload cards with the new filter applied
}

async function loadOwnedCards() {
    console.log("loadOwnedCards() called.");
    if (!myCardsList || !statusFilterSelect) return;

    myCardsList.innerHTML = '<p>Fetching your agent cards...</p>';
    statusFilterSelect.disabled = true;

    const filterValue = statusFilterSelect.value;
    let apiUrl = `${API_BASE_PATH}/agent-cards/?owned_only=true&limit=250`;
    if (filterValue === 'active') {
        apiUrl += '&active_only=true';
    } else if (filterValue === 'inactive') {
        apiUrl += '&active_only=false';
    } else { // 'all'
         apiUrl += '&active_only=false';
    }

    try {
        // Use JWT for this request now
        const response = await makeAuthenticatedRequest(apiUrl, { method: 'GET' });
        if (!response.ok) {
             let errorDetail = `HTTP error! status: ${response.status}`;
             try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
             throw new Error(errorDetail);
        }
        const data = await response.json();
        console.debug("Received owned cards data (summaries):", data);

        // Fetch full details for each card to get status and verified status
        const cardDetailPromises = (data.items || []).map(summary =>
            makeAuthenticatedRequest(`${API_BASE_PATH}/agent-cards/${summary.id}`, { method: 'GET' })
            .then(res => res.ok ? res.json() : Promise.reject(new Error(`Failed to fetch details for ${summary.id}: ${res.status}`)))
            .catch(err => {
                console.error(`Error fetching details for card ${summary.id}:`, err);
                return null; // Return null for failed fetches
            })
        );
        let fullCardsData = (await Promise.all(cardDetailPromises)).filter(card => card !== null); // Filter out nulls from failed fetches
        console.debug("Received full card details:", fullCardsData);

        // Client-side filter for 'inactive' if needed
        if (filterValue === 'inactive') {
            fullCardsData = fullCardsData.filter(card => card.is_active === false);
            console.debug("Filtered for inactive cards client-side:", fullCardsData);
        } else if (filterValue === 'active') {
             fullCardsData = fullCardsData.filter(card => card.is_active === true);
             console.debug("Filtered for active cards client-side:", fullCardsData);
        }

        renderOwnedCards(fullCardsData || []);

    } catch (error) {
        console.error("Error loading owned cards:", error);
        myCardsList.innerHTML = `<p style="color: red;">Error loading your agent cards: ${escapeHTML(error.message || String(error))}</p>`;
    } finally {
        statusFilterSelect.disabled = false;
    }
}

function renderOwnedCards(cards) {
    // ... (renderOwnedCards logic remains largely the same, using card.developer_is_verified) ...
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

        // Use developer_is_verified from the AgentCardRead schema
        if (card.developer_is_verified) {
            const badge = document.createElement('span');
            badge.className = 'verified-badge';
            badge.textContent = 'Verified Dev';
            nameEl.appendChild(badge);
        }

        const idEl = document.createElement('div');
        idEl.className = 'card-id';
        // Display humanReadableId from card_data if available
        const humanId = card.card_data?.humanReadableId || 'N/A';
        idEl.textContent = `ID: ${escapeHTML(humanId)} (UUID: ${card.id})`; // Show both

        const descEl = document.createElement('p');
        descEl.textContent = card.description || 'No description.';

        const buttonDiv = document.createElement('div');
        buttonDiv.className = 'card-actions';

        const editButton = document.createElement('button');
        editButton.textContent = 'View / Edit';
        editButton.className = 'button-edit';
        editButton.dataset.cardId = card.id; // Use UUID for actions
        editButton.onclick = () => handleEditCard(card.id); // Use UUID

        const toggleStatusButton = document.createElement('button');
        toggleStatusButton.textContent = card.is_active ? 'Deactivate' : 'Activate';
        toggleStatusButton.className = `button-toggle-status ${card.is_active ? '' : 'activate'}`;
        toggleStatusButton.dataset.cardId = card.id; // Use UUID
        toggleStatusButton.onclick = () => handleToggleStatus(card.id); // Use UUID

        buttonDiv.appendChild(editButton);
        buttonDiv.appendChild(toggleStatusButton);

        cardDiv.appendChild(nameEl);
        cardDiv.appendChild(idEl);
        cardDiv.appendChild(descEl);
        cardDiv.appendChild(buttonDiv);

        myCardsList.appendChild(cardDiv);
    });
}

async function handleEditCard(cardUuid) { // Parameter is UUID now
    console.log(`View/Edit button clicked for card UUID: ${cardUuid}`);
    if (!agentCardJsonTextarea || !submitStatus || !validationErrorsPre || !submitCardButton || !submitCardSection || !cancelEditButton) {
        console.error("Required elements for editing not found.");
        return;
    }

    submitStatus.textContent = 'Fetching card data...';
    submitStatus.style.color = 'inherit';
    validationErrorsPre.textContent = '';
    agentCardJsonTextarea.value = '';

    const fetchUrl = `${API_BASE_PATH}/agent-cards/${cardUuid}`; // Use UUID
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
        submitCardButton.dataset.editingCardId = cardUuid; // Store UUID
        submitCardButton.removeEventListener('click', handleSubmitNewCard);
        submitCardButton.removeEventListener('click', handleUpdateCardWrapper);
        submitCardButton.addEventListener('click', handleUpdateCardWrapper);

        cancelEditButton.style.display = 'inline-block';

        submitStatus.textContent = `Editing card ${cardFullData.card_data?.humanReadableId || cardUuid}. Modify JSON and click 'Update Card'.`;
        submitStatus.style.color = 'blue';
        submitCardSection.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error("Error fetching card for edit:", error);
        submitStatus.textContent = `Error fetching card ${cardUuid}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
        resetSubmitForm();
    }
}

function handleUpdateCardWrapper(event) {
    const button = event.target;
    const cardUuid = button.dataset.editingCardId; // Get UUID
    if (cardUuid) {
        handleUpdateCard(cardUuid); // Pass UUID
    } else {
        console.error("Could not find card UUID for update.");
        if(submitStatus) submitStatus.textContent = "Error: Could not determine which card to update.";
    }
}

async function handleUpdateCard(cardUuid) { // Parameter is UUID
    console.log(`Update Card button clicked for card UUID: ${cardUuid}`);
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
    const updateUrl = `${API_BASE_PATH}/agent-cards/${cardUuid}`; // Use UUID

    console.debug(`Sending PUT request to: ${updateUrl}`);
    submitStatus.textContent = `Updating card ${cardUuid}...`;

    try {
        const response = await makeAuthenticatedRequest(updateUrl, {
            method: 'PUT',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 200) {
            const updatedCard = await response.json();
            submitStatus.textContent = `Agent Card ${updatedCard.card_data?.humanReadableId || cardUuid} updated successfully!`;
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
        submitStatus.textContent = `Error updating card ${cardUuid}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}


async function handleToggleStatus(cardUuid) { // Parameter is UUID
    console.log(`Toggle Status button clicked for card UUID: ${cardUuid}`);
    if (!submitStatus) return;

    submitStatus.textContent = `Fetching current status for ${cardUuid}...`;
    submitStatus.style.color = 'inherit';

    const fetchUrl = `${API_BASE_PATH}/agent-cards/${cardUuid}`; // Use UUID
    let currentStatus = null;
    try {
        const response = await makeAuthenticatedRequest(fetchUrl, { method: 'GET' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const cardData = await response.json();
        currentStatus = cardData.is_active;
        console.log(`Current status for ${cardUuid} is ${currentStatus}`);
    } catch (error) {
        console.error("Error fetching current status:", error);
        submitStatus.textContent = `Error fetching status for card ${cardUuid}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
        return;
    }

    if (currentStatus === null) {
        submitStatus.textContent = `Error: Could not determine current status for card ${cardUuid}.`;
        submitStatus.style.color = 'red';
        return;
    }

    const action = currentStatus ? "Deactivate" : "Activate";
    const newStatus = !currentStatus;
    if (!confirm(`Are you sure you want to ${action.toLowerCase()} Agent Card ${cardUuid}?`)) {
        console.log(`${action} cancelled by user.`);
        submitStatus.textContent = `${action} cancelled.`;
        setTimeout(() => { if (submitStatus && submitStatus.textContent.includes('cancelled')) submitStatus.textContent = ''; }, 3000);
        return;
    }

    const updateUrl = `${API_BASE_PATH}/agent-cards/${cardUuid}`; // Use UUID
    const requestBody = { is_active: newStatus };

    console.debug(`Sending PUT request to toggle status: ${updateUrl}`, requestBody);
    submitStatus.textContent = `${action.replace(/e$/, '')}ing card ${cardUuid}...`;

    try {
        const response = await makeAuthenticatedRequest(updateUrl, {
            method: 'PUT',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 200) {
            submitStatus.textContent = `Agent Card ${cardUuid} ${action.toLowerCase()}d successfully.`;
            submitStatus.style.color = 'green';
            setTimeout(() => { if (submitStatus && submitStatus.textContent.includes(cardUuid)) submitStatus.textContent = ''; }, 3000);
            loadOwnedCards();
        } else {
            let errorDetail = `Unexpected status: ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
             throw new Error(errorDetail);
        }

    } catch (error) {
        console.error(`Error during ${action.toLowerCase()} request:`, error);
        submitStatus.textContent = `Error ${action.toLowerCase()}ing card ${cardUuid}: ${escapeHTML(error.message || String(error))}`;
        submitStatus.style.color = 'red';
    }
}

// --- MODIFIED: Use JWT from localStorage ---
async function makeAuthenticatedRequest(url, options = {}) {
    const token = getJwtToken(); // Get JWT from localStorage
    if (!token) {
        console.error("No JWT found for authenticated request. Logging out.");
        handleLogout(); // Trigger logout flow
        throw new Error("Not authenticated");
    }

    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${token}`; // Set Bearer token header
    if (options.body && !options.headers['Content-Type']) {
         options.headers['Content-Type'] = 'application/json';
    }

    console.debug(`Making authenticated request to: ${url}`, options);
    const response = await fetch(url, options);

    // Check for 401/403 specifically after the call
    if (response.status === 401 || response.status === 403) {
        console.error(`Authentication/Authorization failed (${response.status}). Logging out.`);
        handleLogout(); // Trigger logout flow
        let errorDetail = `Authentication/Authorization failed: ${response.status}`;
         try {
             const errorData = await response.json();
             errorDetail = errorData.detail || errorDetail;
         } catch (e) { /* ignore */ }
        throw new Error(errorDetail); // Throw error to be caught by caller
    }

    // Return the response for the caller to handle other statuses (like 404, 422, 500)
    return response;
}
// --- END MODIFIED ---

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
        // Validation is public, no auth needed
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
    // ... (handleSubmitNewCard remains largely unchanged, uses makeAuthenticatedRequest) ...
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
        const response = await makeAuthenticatedRequest(submitUrl, { // Uses JWT now
            method: 'POST',
            body: JSON.stringify(requestBody),
        });

        if (response.status === 201) {
            const newCard = await response.json();
            submitStatus.textContent = `Agent Card submitted successfully! ID: ${newCard.id}`;
            submitStatus.style.color = 'green';
            validationErrorsPre.textContent = '';
            agentCardJsonTextarea.value = '';
            loadOwnedCards(); // Refresh list
        } else if (response.status === 422) {
            const errorData = await response.json();
            console.error("Submission validation error:", errorData);
            submitStatus.textContent = 'Submission Failed (Validation Error).';
            submitStatus.style.color = 'red';
            validationErrorsPre.textContent = `Validation Errors:\n${errorData.detail || 'Unknown validation error.'}`;
        } else {
            // Handle other errors (like 401/403 already handled by makeAuthenticatedRequest)
            let errorDetail = `HTTP error! status: ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }
    } catch (error) {
        console.error("Error during submission request:", error);
        // Avoid showing "Not authenticated" twice if makeAuthenticatedRequest threw it
        if (error.message !== "Not authenticated") {
            submitStatus.textContent = `Error during submission: ${escapeHTML(error.message || String(error))}`;
            submitStatus.style.color = 'red';
        }
    }
}

function resetSubmitForm() {
    // ... (resetSubmitForm remains unchanged) ...
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
}

// --- ADDED: API Key Management JS ---
async function loadApiKeys() {
    console.log("Loading API keys...");
    if (!apiKeysTbody || !apiKeysTable) return;
    apiKeysTbody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
    apiKeysTable.style.display = 'table'; // Show table structure

    try {
        const response = await makeAuthenticatedRequest(`${DEV_BASE_PATH}/me/apikeys`, { method: 'GET' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const keys = await response.json();
        renderApiKeys(keys);
    } catch (error) {
        console.error("Error loading API keys:", error);
        apiKeysTbody.innerHTML = `<tr><td colspan="6" style="color: red;">Error loading keys: ${escapeHTML(error.message)}</td></tr>`;
    }
}

function renderApiKeys(keys) {
    if (!apiKeysTbody || !apiKeysTable) return;
    apiKeysTbody.innerHTML = ''; // Clear loading/previous

    if (!keys || keys.length === 0) {
        apiKeysTbody.innerHTML = '<tr><td colspan="6">No programmatic API keys found. Generate one below.</td></tr>';
        return;
    }

    keys.forEach(key => {
        const row = apiKeysTbody.insertRow();
        row.insertCell().textContent = key.key_prefix || 'N/A';
        row.insertCell().textContent = key.description || '-';
        row.insertCell().textContent = key.created_at ? new Date(key.created_at).toLocaleString() : '-';
        row.insertCell().textContent = key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'Never';
        row.insertCell().innerHTML = `<span class="card-status ${key.is_active ? 'card-status-active' : 'card-status-inactive'}">${key.is_active ? 'Active' : 'Inactive'}</span>`;

        const actionsCell = row.insertCell();
        if (key.is_active) {
            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Deactivate';
            deleteButton.className = 'button-delete-key'; // Add class for styling/selection
            deleteButton.onclick = () => handleDeleteApiKey(key.id, key.key_prefix); // Pass ID and prefix
            actionsCell.appendChild(deleteButton);
        } else {
            actionsCell.textContent = '-';
        }
    });
}

async function handleGenerateApiKey() {
    console.log("Generate API Key button clicked.");
    if (!generateKeyButton || !newKeyDescriptionInput || !generateKeyMessage || !newKeyResultDiv || !newPlainKeyPre) return;

    const description = newKeyDescriptionInput.value.trim() || null; // Send null if empty
    setGenerateKeyLoading(true);
    generateKeyMessage.textContent = '';
    generateKeyMessage.style.color = 'inherit';
    newKeyResultDiv.style.display = 'none';
    newPlainKeyPre.textContent = '';

    try {
        const response = await makeAuthenticatedRequest(`${DEV_BASE_PATH}/me/apikeys`, {
            method: 'POST',
            body: JSON.stringify({ description: description }) // Send description in body
        });

        const responseData = await response.json();

        if (response.status === 201 && responseData.plain_api_key) {
            console.log("API Key generated successfully:", responseData.api_key_info);
            newPlainKeyPre.textContent = responseData.plain_api_key;
            newKeyResultDiv.style.display = 'block';
            generateKeyMessage.textContent = "Key generated successfully. Copy it now!";
            generateKeyMessage.style.color = 'green';
            newKeyDescriptionInput.value = ''; // Clear input
            loadApiKeys(); // Refresh the list
        } else {
            const errorMsg = responseData.detail || `Failed with status ${response.status}`;
            throw new Error(errorMsg);
        }
    } catch (error) {
        console.error("Error generating API key:", error);
        generateKeyMessage.textContent = `Error: ${escapeHTML(error.message)}`;
        generateKeyMessage.style.color = 'red';
    } finally {
        setGenerateKeyLoading(false);
    }
}

function setGenerateKeyLoading(isLoading) {
     if (generateKeyButton) {
        generateKeyButton.disabled = isLoading;
        generateKeyButton.textContent = isLoading ? 'Generating...' : 'Generate Key';
    }
     if (newKeyDescriptionInput) {
        newKeyDescriptionInput.disabled = isLoading;
    }
}

function handleCopyApiKey() {
    if (!newPlainKeyPre) return;
    const keyToCopy = newPlainKeyPre.textContent;
    navigator.clipboard.writeText(keyToCopy).then(() => {
        console.log("API Key copied to clipboard.");
        if (copyKeyButton) copyKeyButton.textContent = 'Copied!';
        setTimeout(() => { if (copyKeyButton) copyKeyButton.textContent = 'Copy'; }, 2000);
    }).catch(err => {
        console.error('Failed to copy API key: ', err);
        alert('Failed to copy key. Please copy manually.');
    });
}

async function handleDeleteApiKey(keyId, keyPrefix) {
    console.log(`Delete button clicked for key ID: ${keyId}, Prefix: ${keyPrefix}`);
    if (!confirm(`Are you sure you want to deactivate the API key starting with "${keyPrefix}"? This cannot be undone.`)) {
        return;
    }

    // Optionally disable the specific button during deletion
    const button = event.target;
    if (button) button.disabled = true;

    try {
        const response = await makeAuthenticatedRequest(`${DEV_BASE_PATH}/me/apikeys/${keyId}`, { // Use key ID
            method: 'DELETE'
        });

        if (response.status === 204) {
            console.log(`API Key ${keyId} deactivated successfully.`);
            loadApiKeys(); // Refresh list
        } else {
             let errorDetail = `Unexpected status: ${response.status}`;
             try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
             throw new Error(errorDetail);
        }
    } catch (error) {
        console.error(`Error deactivating API key ${keyId}:`, error);
        alert(`Failed to deactivate key: ${error.message}`);
        if (button) button.disabled = false; // Re-enable button on error
    }
}

// --- ADDED: Agent Builder JS ---
function handleBuilderTypeChange() {
    if (!wrapperConfigSection || !adkConfigSection || !agentBuilderTypeRadios) return;
    const selectedType = document.querySelector('input[name="agent_builder_type"]:checked')?.value;
    console.log(`Agent builder type changed to: ${selectedType}`);
    if (selectedType === 'simple_wrapper') {
        wrapperConfigSection.style.display = 'block';
        adkConfigSection.style.display = 'none';
    } else if (selectedType === 'adk_agent') {
        wrapperConfigSection.style.display = 'none';
        adkConfigSection.style.display = 'block';
    }
}

function handleWrapperAuthTypeChange() {
    if (!builderWrapperAuthSelect || !builderWrapperServiceIdGroup) return;
    const selectedAuth = builderWrapperAuthSelect.value;
    // --- FIXED: Correctly hide/show based on value ---
    builderWrapperServiceIdGroup.style.display = (selectedAuth === 'apiKey') ? 'block' : 'none';
    // --- END FIXED ---
}


async function handleGenerateAgentPackage() {
    console.log("Generate Agent Package button clicked.");
    if (!generatePackageButton || !generatePackageMessage) return;

    setGeneratePackageLoading(true);
    generatePackageMessage.textContent = '';
    generatePackageMessage.className = 'message-area'; // Reset class

    const buildConfig = {};
    let isValid = true;

    function showValidationError(msg) { // Helper inside function
        if (generatePackageMessage) {
            generatePackageMessage.textContent = msg;
            generatePackageMessage.className = 'message-area error';
            generatePackageMessage.style.display = 'block';
        }
    }

    try {
        // Common fields
        buildConfig.agent_name = document.getElementById('builder-agent-name').value.trim();
        buildConfig.agent_description = document.getElementById('builder-agent-desc').value.trim();
        buildConfig.human_readable_id = document.getElementById('builder-agent-id').value.trim() || null; // Send null if empty
        buildConfig.agent_builder_type = document.querySelector('input[name="agent_builder_type"]:checked').value;
        buildConfig.wrapper_auth_type = document.getElementById('builder-wrapper-auth').value;
        buildConfig.wrapper_service_id = document.getElementById('builder-wrapper-service-id').value.trim() || null;

        // Basic validation
        if (!buildConfig.agent_name) { isValid = false; showValidationError("Agent Name is required."); }
        if (!buildConfig.agent_description) { isValid = false; showValidationError("Agent Description is required."); }
        if (buildConfig.wrapper_auth_type === 'apiKey' && !buildConfig.wrapper_service_id) {
             isValid = false; showValidationError("Service ID is required when API Key auth is selected for the wrapper.");
        }
        if (buildConfig.human_readable_id && !/^[a-z0-9]+(?:[-_][a-z0-9]+)*\/[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(buildConfig.human_readable_id)) {
             isValid = false; showValidationError("Human-Readable ID format invalid (e.g., 'my-org/my-agent').");
        }


        // Type-specific fields
        if (buildConfig.agent_builder_type === 'simple_wrapper') {
            buildConfig.wrapper_llm_backend_type = document.getElementById('builder-wrapper-backend').value;
            buildConfig.wrapper_model_name = document.getElementById('builder-wrapper-model').value.trim();
            buildConfig.wrapper_system_prompt = document.getElementById('builder-wrapper-prompt').value.trim() || null;
            if (!buildConfig.wrapper_model_name) { isValid = false; showValidationError("Model Name is required for Simple Wrapper."); }
        } else if (buildConfig.agent_builder_type === 'adk_agent') {
            buildConfig.adk_model_name = document.getElementById('builder-adk-model').value.trim();
            buildConfig.adk_instruction = document.getElementById('builder-adk-instruction').value.trim();
            buildConfig.adk_tools = Array.from(document.querySelectorAll('#adk-agent-config-section input[type="checkbox"]:checked')).map(cb => cb.value);
             if (!buildConfig.adk_model_name) { isValid = false; showValidationError("Model Name is required for ADK Agent."); }
             if (!buildConfig.adk_instruction) { isValid = false; showValidationError("Agent Instruction is required for ADK Agent."); }
        }

        if (!isValid) {
            setGeneratePackageLoading(false);
            return; // Stop if client-side validation failed
        }

        console.log("Agent Build Config:", buildConfig);
        generatePackageMessage.textContent = 'Generating package... please wait.';
        generatePackageMessage.style.display = 'block'; // Ensure message area is visible

        // API Call to generate
        const response = await makeAuthenticatedRequest(`${BUILDER_BASE_PATH}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/zip' // Expect a zip file
            },
            body: JSON.stringify(buildConfig)
        });

        if (response.ok && response.headers.get('content-type') === 'application/zip') {
            const blob = await response.blob();
            // Extract filename more reliably
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `${buildConfig.agent_name.toLowerCase().replace(/[^a-z0-9]/gi, '_') || 'agent'}.zip`; // Default filename
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename\*?=['"]?([^'";]+)['"]?/);
                if (filenameMatch && filenameMatch) {
                    filename = decodeURIComponent(filenameMatch);
                }
            }

            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
            generatePackageMessage.textContent = `Agent package '${filename}' downloaded successfully! Check the INSTRUCTIONS.md inside.`;
            generatePackageMessage.className = 'message-area success';
        } else {
            // Handle API errors (422, 500)
            let errorDetail = `Generation failed with status ${response.status}.`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* Ignore if response is not JSON */ }
            throw new Error(errorDetail);
        }

    } catch (error) {
        console.error("Error generating agent package:", error);
        showValidationError(`Error: ${escapeHTML(error.message || String(error))}`);
    } finally {
        setGeneratePackageLoading(false);
    }
}

function setGeneratePackageLoading(isLoading) {
    if (generatePackageButton) {
        generatePackageButton.disabled = isLoading;
        generatePackageButton.textContent = isLoading ? 'Generating...' : 'Generate Agent Package';
    }
    // Optionally disable form fields during generation
}

// --- Removed duplicate showValidationError ---
// --- END ADDED ---
