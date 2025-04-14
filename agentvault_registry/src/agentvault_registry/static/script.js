console.log("AgentVault Registry UI Script Loaded.");

const API_BASE_PATH = "/api/v1";
let currentPage = 1;
let currentLimit = 100;
let currentSearch = '';

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed.");
    fetchAgentCards(); // Load initial list

    const backButton = document.getElementById('back-to-list');
    if (backButton) {
        backButton.addEventListener('click', showListView);
    }

    const searchInput = document.getElementById('search-input');
    let searchTimeout;
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            currentSearch = e.target.value;
            searchTimeout = setTimeout(() => {
                currentPage = 1;
                fetchAgentCards(0, currentLimit, currentSearch);
            }, 300);
        });
    }
});

function showListView() {
    const detailSection = document.getElementById('agent-detail-section');
    const listSection = document.getElementById('agent-list-section');
    const searchSection = document.getElementById('search-section');

    if (detailSection) detailSection.style.display = 'none';
    if (listSection) listSection.style.display = 'block';
    if (searchSection) searchSection.style.display = 'block';
}

function showDetailView() {
    const detailSection = document.getElementById('agent-detail-section');
    const listSection = document.getElementById('agent-list-section');
    const searchSection = document.getElementById('search-section');

    if (detailSection) detailSection.style.display = 'block';
    if (listSection) listSection.style.display = 'none';
    if (searchSection) searchSection.style.display = 'none';
}

async function fetchAgentCards(offset = 0, limit = 100, search = '') {
    console.log(`Fetching agents: offset=${offset}, limit=${limit}, search='${search}'`);
    const listContainer = document.getElementById('agent-list-container');
    if (listContainer) {
        listContainer.innerHTML = '<p>Loading agents...</p>';
    }
    const paginationControls = document.getElementById('pagination-controls');
    if (paginationControls) paginationControls.innerHTML = '';


    const apiUrl = `${API_BASE_PATH}/agent-cards/`;
    const params = new URLSearchParams();
    params.append('skip', offset);
    params.append('limit', limit);
    params.append('active_only', 'true');
    if (search) {
        params.append('search', search);
    }

    const urlWithParams = `${apiUrl}?${params.toString()}`;
    console.debug(`Fetching from URL: ${urlWithParams}`);

    try {
        const response = await fetch(urlWithParams);

        if (!response.ok) {
            console.error(`Error fetching agents: ${response.status} ${response.statusText}`);
            if (listContainer) {
                listContainer.innerHTML = `<p>Error loading agents: ${response.statusText}</p>`;
            }
            try {
                const errorData = await response.json();
                console.error("Error details:", errorData.detail);
                if (listContainer && errorData.detail) {
                     listContainer.innerHTML += `<p>Detail: ${errorData.detail}</p>`;
                }
            } catch (e) { /* Ignore if error body isn't JSON */ }
            return;
        }

        const data = await response.json();
        console.debug("Received data:", data);

        if (data && data.items && data.pagination) {
            currentPage = data.pagination.current_page;
            currentLimit = data.pagination.limit;
            renderAgentList(data.items, data.pagination);
        } else {
             console.error("Received invalid data structure from API:", data);
             if (listContainer) {
                listContainer.innerHTML = `<p>Error: Invalid data received from server.</p>`;
             }
        }

    } catch (error) {
        console.error("Network or other error fetching agents:", error);
        if (listContainer) {
            listContainer.innerHTML = `<p>Error loading agents. Check console for details.</p>`;
        }
    }
}

function renderAgentList(items, pagination) {
    console.log("Rendering agent list");
    const listContainer = document.getElementById('agent-list-container');
    if (!listContainer) return;

    if (items.length === 0) {
        listContainer.innerHTML = '<p>No agents found matching your criteria.</p>';
        renderPagination(pagination);
        return;
    }

    listContainer.innerHTML = '';

    items.forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-card';

        // Basic info
        let cardHTML = `
            <h3>${escapeHTML(agent.name)}</h3>
            <p>${escapeHTML(agent.description || 'No description provided.')}</p>
            <small>ID: ${escapeHTML(agent.id)}</small><br>
        `;

        // Add verified badge (anticipating the field)
        // Note: This field ('developer_is_verified') is NOT in the AgentCardSummary schema yet.
        // We will need to adjust the API or schema later if we want this in the list view.
        // For now, this check will likely always be false based on current API response.
        if (agent.developer_is_verified === true) {
             cardHTML += `<span class="verified-badge">(Verified Developer)</span><br>`;
        }

        // Add button
        cardHTML += `<button onclick="fetchAgentDetails('${escapeHTML(agent.id)}')">View Details</button>`;

        card.innerHTML = cardHTML;
        listContainer.appendChild(card);
    });

    renderPagination(pagination);
}

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

function renderPagination(pagination) {
     console.log("Rendering pagination");
     const paginationControls = document.getElementById('pagination-controls');
     if (!paginationControls) return;

     paginationControls.innerHTML = '';

     if (pagination.total_items === 0 && pagination.offset === 0) {
         paginationControls.innerHTML = '<span>No agents found.</span>';
         return;
     }
     if (pagination.total_pages <= 1) {
         paginationControls.innerHTML = `<span>Total: ${pagination.total_items}</span>`;
         return;
     }


     const prevDisabled = pagination.current_page <= 1;
     const nextDisabled = pagination.current_page >= pagination.total_pages;

     const prevButton = document.createElement('button');
     prevButton.textContent = 'Previous';
     prevButton.disabled = prevDisabled;
     if (!prevDisabled) {
         prevButton.onclick = () => {
             const newOffset = (pagination.current_page - 2) * pagination.limit;
             fetchAgentCards(newOffset, pagination.limit, currentSearch);
         };
     }

     const nextButton = document.createElement('button');
     nextButton.textContent = 'Next';
     nextButton.disabled = nextDisabled;
     if (!nextDisabled) {
         nextButton.onclick = () => {
             const newOffset = pagination.current_page * pagination.limit;
             fetchAgentCards(newOffset, pagination.limit, currentSearch);
         };
     }

     const pageInfo = document.createElement('span');
     pageInfo.textContent = ` Page ${pagination.current_page} of ${pagination.total_pages} (Total: ${pagination.total_items}) `;
     pageInfo.style.margin = "0 10px";

     paginationControls.appendChild(prevButton);
     paginationControls.appendChild(pageInfo);
     paginationControls.appendChild(nextButton);
}


// --- MODIFIED: Implemented fetchAgentDetails ---
async function fetchAgentDetails(cardId) {
    console.log(`Fetching details for card ID: ${cardId}`);
    const detailContentEl = document.getElementById('agent-detail-content');
    const privacyLink = document.getElementById('privacy-policy-link');
    const termsLink = document.getElementById('terms-link');

    // Show loading state
    if (detailContentEl) detailContentEl.textContent = `Loading details for ${escapeHTML(cardId)}...`;
    if (privacyLink) privacyLink.style.display = 'none';
    if (termsLink) termsLink.style.display = 'none';
    showDetailView(); // Switch view immediately

    const apiUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    console.debug(`Fetching detail from URL: ${apiUrl}`);

    try {
        const response = await fetch(apiUrl);

        if (!response.ok) {
            console.error(`Error fetching details: ${response.status} ${response.statusText}`);
            let errorDetail = response.statusText;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
                console.error("Error details:", errorDetail);
            } catch (e) { /* Ignore if error body isn't JSON */ }
            if (detailContentEl) {
                detailContentEl.textContent = `Error loading details: ${escapeHTML(errorDetail)}`;
            }
            return; // Stop processing
        }

        const cardData = await response.json();
        console.debug("Received detail data:", cardData);

        if (cardData) {
            renderAgentDetails(cardData); // Call rendering function
        } else {
             console.error("Received invalid data structure from detail API:", cardData);
             if (detailContentEl) {
                detailContentEl.textContent = `Error: Invalid data received from server.`;
             }
        }

    } catch (error) {
        console.error("Network or other error fetching details:", error);
        if (detailContentEl) {
            detailContentEl.textContent = `Error loading details. Check console for details.`;
        }
    }
}
// --- END MODIFIED ---

// --- MODIFIED: Implemented renderAgentDetails ---
function renderAgentDetails(card) {
    console.log("Rendering agent details");
    const detailContentEl = document.getElementById('agent-detail-content');
    const privacyLink = document.getElementById('privacy-policy-link');
    const termsLink = document.getElementById('terms-link');

    if (!detailContentEl || !privacyLink || !termsLink) {
        console.error("Detail view elements not found.");
        return;
    }

    // Basic Info
    let headerInfo = `Developer ID: ${escapeHTML(card.developer_id)} `;
    if (card.developer_is_verified === true) {
        headerInfo += `<span class="verified-badge">(Verified Developer)</span>`;
    } else {
        headerInfo += `(Not Verified)`;
    }
    headerInfo += `<br>Active: ${card.is_active ? 'Yes' : 'No'}`;
    headerInfo += `<br>Last Updated: ${escapeHTML(new Date(card.updated_at).toLocaleString())}`;

    // Pretty print card_data JSON
    let cardDataJson = "{}"; // Default empty object
    try {
        cardDataJson = JSON.stringify(card.card_data || {}, null, 2);
    } catch (e) {
        console.error("Error stringifying card_data:", e);
        cardDataJson = "{ Error displaying card data }";
    }

    detailContentEl.innerHTML = // Use innerHTML to render the badge span
        `<p>${headerInfo}</p><pre>${escapeHTML(cardDataJson)}</pre>`;

    // Handle Policy Links
    const cardData = card.card_data || {}; // Ensure card_data exists
    if (cardData.privacyPolicyUrl) {
        privacyLink.href = cardData.privacyPolicyUrl;
        privacyLink.style.display = 'inline';
    } else {
        privacyLink.style.display = 'none';
    }

    if (cardData.termsOfServiceUrl) {
        termsLink.href = cardData.termsOfServiceUrl;
        termsLink.style.display = 'inline';
    } else {
        termsLink.style.display = 'none';
    }
}
// --- END MODIFIED ---
