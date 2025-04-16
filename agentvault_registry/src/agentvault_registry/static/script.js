console.log("AgentVault Registry UI Script Loaded.");

const API_BASE_PATH = "/api/v1";
let currentPage = 1;
let currentLimit = 100; // Keep default limit reasonable
let currentSearch = '';
let searchTimeout; // For debouncing

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed.");
    fetchAgentCards(); // Load initial list

    const backButton = document.getElementById('back-to-list');
    if (backButton) {
        backButton.addEventListener('click', showListView);
    }

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const searchTerm = e.target.value;
            searchTimeout = setTimeout(() => {
                console.log(`Debounced search triggered for: '${searchTerm}'`);
                currentSearch = searchTerm;
                currentPage = 1; // Reset to first page on new search
                fetchAgentCards(0, currentLimit, currentSearch);
            }, 300);
        });
    }
});

function showListView() {
    const detailSection = document.getElementById('agent-detail-section');
    const listSection = document.getElementById('agent-list-section');
    const searchSection = document.getElementById('search-section');
    const paginationControls = document.getElementById('pagination-controls'); // Added

    if (detailSection) detailSection.style.display = 'none';
    if (listSection) listSection.style.display = 'block';
    if (searchSection) searchSection.style.display = 'block';
    if (paginationControls) paginationControls.style.display = 'block'; // Added: Show pagination
}

function showDetailView() {
    const detailSection = document.getElementById('agent-detail-section');
    const listSection = document.getElementById('agent-list-section');
    const searchSection = document.getElementById('search-section');
    const paginationControls = document.getElementById('pagination-controls'); // Added

    if (detailSection) detailSection.style.display = 'block';
    if (listSection) listSection.style.display = 'none';
    if (searchSection) searchSection.style.display = 'none';
    if (paginationControls) paginationControls.style.display = 'none'; // Added: Hide pagination
}

async function fetchAgentCards(offset = 0, limit = currentLimit, search = currentSearch) {
    console.log(`Fetching agents: offset=${offset}, limit=${limit}, search='${search}'`);
    const listContainer = document.getElementById('agent-list-container');
    if (listContainer) listContainer.innerHTML = '<p>Loading agents...</p>';
    const paginationControls = document.getElementById('pagination-controls');
    if (paginationControls) paginationControls.innerHTML = '';

    const apiUrl = `${API_BASE_PATH}/agent-cards/`;
    const params = new URLSearchParams();
    params.append('skip', offset);
    params.append('limit', limit);
    params.append('active_only', 'true');
    if (search) params.append('search', search);
    // Add other filters (tags, tee) here later if UI elements are added

    const urlWithParams = `${apiUrl}?${params.toString()}`;
    console.debug(`Fetching from URL: ${urlWithParams}`);

    try {
        const response = await fetch(urlWithParams);
        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }
        const data = await response.json();
        console.debug("Received data:", data);

        if (data && data.items && data.pagination) {
            currentPage = data.pagination.current_page;
            currentLimit = data.pagination.limit;
            renderAgentList(data.items, data.pagination);
        } else {
             throw new Error("Invalid data structure received from API");
        }
    } catch (error) {
        console.error("Error fetching agents:", error);
        if (listContainer) listContainer.innerHTML = `<p style="color: red;">Error loading agents: ${escapeHTML(error.message)}</p>`;
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
        card.innerHTML = `
            <h3>${escapeHTML(agent.name)}</h3>
            <p>${escapeHTML(agent.description || 'No description provided.')}</p>
            <small>ID: ${escapeHTML(agent.id)}</small><br>
            <button onclick="fetchAgentDetails('${escapeHTML(agent.id)}')">View Details</button>
        `;
        // Note: Verified badge cannot be shown here as summary doesn't include developer_is_verified
        listContainer.appendChild(card);
    });

    renderPagination(pagination);
}

function escapeHTML(str) {
    // ... (escapeHTML function remains unchanged) ...
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
    // ... (renderPagination function remains unchanged) ...
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


async function fetchAgentDetails(cardId) {
    console.log(`Fetching details for card ID: ${cardId}`);
    // --- MODIFIED: Get references to new detail elements ---
    const detailNameEl = document.getElementById('detail-agent-name');
    const detailIdEl = document.getElementById('detail-agent-id');
    const detailVersionEl = document.getElementById('detail-agent-version');
    const detailProviderEl = document.getElementById('detail-provider');
    const detailDevVerifiedEl = document.getElementById('detail-dev-verified');
    const detailEndpointUrlEl = document.getElementById('detail-endpoint-url');
    const detailDescriptionEl = document.getElementById('detail-description');
    const detailAuthSchemesEl = document.getElementById('detail-auth-schemes');
    const detailCapabilitiesEl = document.getElementById('detail-capabilities');
    const detailTagsEl = document.getElementById('detail-tags');
    const detailLastUpdatedEl = document.getElementById('detail-last-updated');
    const privacyLink = document.getElementById('privacy-policy-link');
    const termsLink = document.getElementById('terms-link');
    const providerLink = document.getElementById('provider-link');
    const supportLink = document.getElementById('support-link');
    // --- END MODIFIED ---

    // Show loading state in main name field
    if (detailNameEl) detailNameEl.textContent = `Loading Agent Details...`;
    // Clear other fields
    const elementsToClear = [detailIdEl, detailVersionEl, detailProviderEl, detailDevVerifiedEl, detailEndpointUrlEl, detailDescriptionEl, detailAuthSchemesEl, detailCapabilitiesEl, detailTagsEl, detailLastUpdatedEl];
    elementsToClear.forEach(el => { if (el) el.innerHTML = ''; }); // Use innerHTML to clear lists too
    const linksToHide = [privacyLink, termsLink, providerLink, supportLink];
    linksToHide.forEach(link => { if (link) link.style.display = 'none'; });

    showDetailView(); // Switch view

    const apiUrl = `${API_BASE_PATH}/agent-cards/${cardId}`;
    console.debug(`Fetching detail from URL: ${apiUrl}`);

    try {
        const response = await fetch(apiUrl); // Public endpoint

        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) {}
            throw new Error(errorDetail);
        }

        const cardFullData = await response.json(); // This is AgentCardRead schema
        console.debug("Received detail data:", cardFullData);

        if (cardFullData && cardFullData.card_data) {
            renderAgentDetails(cardFullData); // Call rendering function with the full data object
        } else {
             throw new Error("Invalid data structure received from detail API");
        }

    } catch (error) {
        console.error("Error fetching details:", error);
        if (detailNameEl) detailNameEl.textContent = 'Error Loading Details';
        if (detailDescriptionEl) detailDescriptionEl.textContent = `Failed to load agent details: ${escapeHTML(error.message)}`;
    }
}

// --- MODIFIED: renderAgentDetails function ---
function renderAgentDetails(card) { // Expects full AgentCardRead object
    console.log("Rendering agent details for:", card.id);
    const cardData = card.card_data || {}; // The nested card data object

    // Get element references (could be passed as args too)
    const detailNameEl = document.getElementById('detail-agent-name');
    const detailIdEl = document.getElementById('detail-agent-id');
    const detailVersionEl = document.getElementById('detail-agent-version');
    const detailProviderEl = document.getElementById('detail-provider');
    const detailDevVerifiedEl = document.getElementById('detail-dev-verified');
    const detailEndpointUrlEl = document.getElementById('detail-endpoint-url');
    const detailDescriptionEl = document.getElementById('detail-description');
    const detailAuthSchemesEl = document.getElementById('detail-auth-schemes');
    const detailCapabilitiesEl = document.getElementById('detail-capabilities');
    const detailTagsEl = document.getElementById('detail-tags');
    const detailLastUpdatedEl = document.getElementById('detail-last-updated');
    const privacyLink = document.getElementById('privacy-policy-link');
    const termsLink = document.getElementById('terms-link');
    const providerLink = document.getElementById('provider-link');
    const supportLink = document.getElementById('support-link');

    // --- Populate Fields ---
    if (detailNameEl) detailNameEl.textContent = card.name || cardData.name || 'Unnamed Agent'; // Use outer name first
    if (detailIdEl) detailIdEl.textContent = cardData.humanReadableId || 'N/A';
    if (detailVersionEl) detailVersionEl.textContent = cardData.agentVersion || 'N/A';
    if (detailDescriptionEl) detailDescriptionEl.textContent = card.description || cardData.description || 'No description provided.';

    // Provider Info
    if (detailProviderEl) {
        const provider = cardData.provider;
        if (provider && provider.name) {
            detailProviderEl.textContent = escapeHTML(provider.name);
            if (provider.url && providerLink) {
                providerLink.href = provider.url;
                providerLink.style.display = 'inline';
                providerLink.textContent = 'Provider Website';
            } else if (providerLink) {
                providerLink.style.display = 'none';
            }
            if (provider.support_contact && supportLink) {
                // Basic check if it looks like an email or URL
                const isEmail = provider.support_contact.includes('@');
                supportLink.href = isEmail ? `mailto:${provider.support_contact}` : provider.support_contact;
                supportLink.style.display = 'inline';
                supportLink.textContent = 'Support Contact';
            } else if (supportLink) {
                supportLink.style.display = 'none';
            }
        } else {
            detailProviderEl.textContent = 'N/A';
            if (providerLink) providerLink.style.display = 'none';
            if (supportLink) supportLink.style.display = 'none';
        }
    }

    // Developer Verified Status
    if (detailDevVerifiedEl) {
        if (card.developer_is_verified) {
            detailDevVerifiedEl.innerHTML = `<span class="verified-badge">Yes</span>`;
        } else {
            detailDevVerifiedEl.textContent = 'No';
        }
    }

    // Endpoint URL
    if (detailEndpointUrlEl && cardData.url) {
        detailEndpointUrlEl.href = cardData.url;
        detailEndpointUrlEl.textContent = cardData.url;
    } else if (detailEndpointUrlEl) {
        detailEndpointUrlEl.textContent = 'N/A';
        detailEndpointUrlEl.removeAttribute('href');
    }

    // Authentication Schemes
    if (detailAuthSchemesEl) {
        detailAuthSchemesEl.innerHTML = ''; // Clear previous
        const schemes = cardData.authSchemes || [];
        if (schemes.length > 0) {
            schemes.forEach(scheme => {
                const li = document.createElement('li');
                let text = `<strong>${escapeHTML(scheme.scheme)}</strong>`;
                if (scheme.description) {
                    text += `: ${escapeHTML(scheme.description)}`;
                }
                if (scheme.tokenUrl) {
                    text += ` (Token URL: <a href="${escapeHTML(scheme.tokenUrl)}" target="_blank" rel="noopener">${escapeHTML(scheme.tokenUrl)}</a>)`;
                }
                if (scheme.service_identifier) {
                     text += ` <span class="detail-value monospace" style="font-size: 0.8em;">(Service ID: ${escapeHTML(scheme.service_identifier)})</span>`;
                }
                li.innerHTML = text;
                detailAuthSchemesEl.appendChild(li);
            });
        } else {
            detailAuthSchemesEl.innerHTML = '<li>No authentication schemes specified.</li>';
        }
    }

    // Capabilities
    if (detailCapabilitiesEl) {
        detailCapabilitiesEl.innerHTML = ''; // Clear previous
        const caps = cardData.capabilities || {};
        let hasCaps = false;
        if (caps.a2aVersion) {
            const li = document.createElement('li');
            li.innerHTML = `<strong>A2A Protocol Version:</strong> ${escapeHTML(caps.a2aVersion)}`;
            detailCapabilitiesEl.appendChild(li);
            hasCaps = true;
        }
        if (caps.mcpVersion) {
            const li = document.createElement('li');
            li.innerHTML = `<strong>MCP Version:</strong> ${escapeHTML(caps.mcpVersion)}`;
            detailCapabilitiesEl.appendChild(li);
            hasCaps = true;
        }
        if (caps.supportedMessageParts && caps.supportedMessageParts.length > 0) {
            const li = document.createElement('li');
            li.innerHTML = `<strong>Supported Parts:</strong> ${escapeHTML(caps.supportedMessageParts.join(', '))}`;
            detailCapabilitiesEl.appendChild(li);
            hasCaps = true;
        }
        if (caps.teeDetails) {
            const li = document.createElement('li');
            let teeText = `<strong>TEE Enabled:</strong> Yes (Type: ${escapeHTML(caps.teeDetails.type || 'Unknown')})`;
            if (caps.teeDetails.description) {
                teeText += ` - ${escapeHTML(caps.teeDetails.description)}`;
            }
            if (caps.teeDetails.attestationEndpoint) {
                 teeText += ` <a href="${escapeHTML(caps.teeDetails.attestationEndpoint)}" target="_blank" rel="noopener">[Attestation]</a>`;
            }
            li.innerHTML = teeText;
            detailCapabilitiesEl.appendChild(li);
            hasCaps = true;
        } else {
             const li = document.createElement('li');
             li.innerHTML = `<strong>TEE Enabled:</strong> No`;
             detailCapabilitiesEl.appendChild(li);
             hasCaps = true;
        }
        if (caps.supportsPushNotifications !== undefined) {
             const li = document.createElement('li');
             li.innerHTML = `<strong>Push Notifications:</strong> ${caps.supportsPushNotifications ? 'Supported' : 'Not Supported'}`;
             detailCapabilitiesEl.appendChild(li);
             hasCaps = true;
        }
        if (!hasCaps) {
            detailCapabilitiesEl.innerHTML = '<li>No specific capabilities listed.</li>';
        }
    }

    // Tags
    if (detailTagsEl) {
        detailTagsEl.innerHTML = ''; // Clear previous
        const tags = cardData.tags || [];
        if (tags.length > 0) {
            tags.forEach(tag => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.textContent = escapeHTML(tag);
                detailTagsEl.appendChild(tagEl);
            });
        } else {
            detailTagsEl.innerHTML = '<span class="detail-value">No tags specified.</span>';
        }
    }

    // Policy Links
    if (privacyLink) {
        if (cardData.privacyPolicyUrl) {
            privacyLink.href = cardData.privacyPolicyUrl;
            privacyLink.style.display = 'inline-block';
        } else {
            privacyLink.style.display = 'none';
        }
    }
    if (termsLink) {
        if (cardData.termsOfServiceUrl) {
            termsLink.href = cardData.termsOfServiceUrl;
            termsLink.style.display = 'inline-block';
        } else {
            termsLink.style.display = 'none';
        }
    }

    // Last Updated
    if (detailLastUpdatedEl) {
        try {
            const updatedDate = card.updated_at ? new Date(card.updated_at).toLocaleString() : 'N/A';
            detailLastUpdatedEl.textContent = escapeHTML(updatedDate);
        } catch (e) {
            detailLastUpdatedEl.textContent = escapeHTML(card.updated_at || 'N/A'); // Fallback
        }
    }
}
// --- END MODIFIED ---
