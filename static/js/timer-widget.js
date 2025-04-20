// static/js/racecontrol.js

/**
 * Creates a WebSocket connection with automatic reconnection logic.
 * (Keep function definition as is)
 */
function createWebSocketWithReconnect(url, messageHandler, openHandler = null, errorHandler = null, closeHandler = null) {
    // ... (implementation from previous version) ...
    let socket;
    let reconnectTimeout;
    const RECONNECT_DELAY = 5000;
    function connect() { /* ... */ }
    connect();
    return { /* send, close, getReadyState */ };
}

/**
 * Function to get CSRF token (Keep as is)
 */
function getCookie(name) {
    // ... (implementation from previous version) ...
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') { /* ... */ }
    return cookieValue;
}

/**
 * Function to add a system message (Simplified for debugging)
 * (Keep simplified version or restore Bootstrap features if parentElement error is resolved)
 * @param {string} message - The message text
 * @param {string} tag - The message type/tag (e.g., 'success', 'warning', 'danger', 'info')
 */
function addSystemMessage(message, tag) {
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) { console.warn("Messages container not found"); return; }
    const alertDiv = document.createElement('div');
    // Using simplified classes for now
    alertDiv.className = `alert alert-${tag} m-2`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.textContent = message;
    messagesContainer.insertBefore(alertDiv, messagesContainer.firstChild);
    setTimeout(() => { if (alertDiv) { alertDiv.remove(); } }, 7000);
}


/**
 * Function to connect to lane sockets (Keep as is)
 */
function connectToLaneSockets() {
    // ... (implementation from previous version) ...
    if (window.lanesConnected) { console.log("Lane sockets already connected."); return; }
    window.lanesConnected = true; window.laneSocketsArray = window.laneSocketsArray || []; console.log("Connecting to pit lane sockets...");
    fetch('/get_race_lanes/')
    .then(response => { if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`); return response.json(); })
    .then(laneData => { /* ... */ }) // Keep implementation
    .catch(error => { /* ... */ }); // Keep implementation
}


/**
 * Handles clicks on race action buttons. Sends request to backend API.
 * Checks backend logical result within the JSON response.
 * Displays each error from the 'errors' array as a separate message.
 * @param {Event} event - The click event object
 */
async function handleRaceAction(event) {
    const button = event.currentTarget;
    const action = button.dataset.action;
    const url = button.dataset.url;
    const roundIdContainer = document.getElementById('race-control-buttons');
    const roundId = roundIdContainer?.dataset.roundId;
    const csrfToken = getCookie('csrftoken');

    console.log(`Button clicked. Action: ${action}, URL: ${url}, RoundID: ${roundId}`);

    if (!action || !url || !roundId || !csrfToken) { /* ... validation ... */ return; }

    button.disabled = true;
    const originalButtonHTML = button.innerHTML;
    button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;
    console.log(`Sending POST request to: ${url}`);

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
        });
        console.log(`Received response for ${action}. Status: ${response.status}`);

        // --- Check HTTP Status FIRST ---
        if (response.ok) {
            // --- Try to parse JSON ---
            let data;
            try {
                data = await response.json();
                console.log(`Action '${action}' response data:`, data);
            } catch (e) {
                console.error("Could not parse JSON response:", e);
                addSystemMessage("Action succeeded but received invalid response from server.", "warning");
                if (button) { button.disabled = false; button.innerHTML = originalButtonHTML; }
                return;
            }

            // --- Check LOGICAL Result from Backend ---
            // Check if backend explicitly signals failure OR provides an errors array
            if (data.result === false || (data.errors && Array.isArray(data.errors) && data.errors.length > 0) || data.status === 'error') {
                // Logical failure reported by backend
                console.warn(`Action '${action}' failed logically according to backend.`);

                // --- Display Error Messages ---
                if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
                    // Call addSystemMessage for each error in the list
                    data.errors.forEach(errorMsg => {
                        // Ensure the item is a string before displaying
                        if (typeof errorMsg === 'string') {
                            addSystemMessage(errorMsg, 'warning'); // Use 'warning' or 'danger'
                        } else {
                            console.warn("Non-string item found in errors array:", errorMsg);
                        }
                    });
                } else if (data.message) {
                    // Use message field if errors array is not present/empty
                    addSystemMessage(data.message, 'warning');
                } else {
                    // Default failure message if no specific errors/message provided
                    addSystemMessage("Action failed according to backend.", 'warning');
                }
                // --- End Display Error Messages ---

                // Re-enable the button on logical failure
                if (button) {
                    button.disabled = false;
                    button.innerHTML = originalButtonHTML;
                }

            } else {
                // Logical success reported by backend
                console.log(`Action '${action}' successful logically.`);
                addSystemMessage(data.message || `Action '${action}' successful.`, data.status || 'success');

                // --- DYNAMIC UI UPDATES for SUCCESS ---
                if (action === 'pre_check') {
                    console.log("Pre-race check successful. Updating UI and connecting lanes...");
                    if (button) button.style.display = 'none';
                    const startButton = document.getElementById('startButton');
                    if (startButton) startButton.style.display = 'inline-block';
                    document.getElementById('emptyTeamsCard')?.style.setProperty('display', 'none', 'important');
                    document.getElementById('teamSelectCard')?.style.setProperty('display', 'block', 'important');
                    connectToLaneSockets();
                }
                // Add other UI update logic here...

                // Re-enable button if it wasn't hidden
                if (button && button.style.display !== 'none') {
                    button.disabled = false;
                    button.innerHTML = originalButtonHTML;
                }
                // --- END DYNAMIC UI UPDATES ---
            }

        } else { // Handle HTTP errors (4xx, 5xx)
            let errorMsg = `Error performing action '${action}'. Status: ${response.status}`;
            try { /* ... try parsing error json ... */ } catch (e) { /* ... */ }
            console.error(`Action '${action}' failed. Status: ${response.status}`);
            addSystemMessage(errorMsg, 'danger');
            if (button) { /* ... re-enable button ... */ }
        }
    } catch (error) { // Handle network errors
        console.error(`Network or fetch error during action '${action}':`, error);
        addSystemMessage(`Network error: ${error}. Please check connection.`, 'danger');
        if (button) { /* ... re-enable button ... */ }
    }
}

/**
 * Function to update the empty teams list UI (Keep as is)
 */
function updateEmptyTeamsList(teams) {
    // ... (implementation from previous version) ...
}


// --- Event Listeners Setup ---
document.addEventListener('DOMContentLoaded', () => {
    // ... (Keep event listener setup for action buttons, stop&go) ...
    const actionButtons = document.querySelectorAll('.race-action-btn');
    actionButtons.forEach(button => { button.addEventListener('click', handleRaceAction); });
    const stopGoButton = document.getElementById('stopGoButton');
    if (stopGoButton) { stopGoButton.addEventListener('click', async () => { /* ... */ }); }

    // --- Initial Lane Connection Check (Keep as is) ---
    const isReadyOrStarted = document.getElementById('startButton') || document.getElementById('pauseButton') || document.getElementById('resumeButton') || document.getElementById('endButton');
    const roundIdContainer = document.getElementById('race-control-buttons');
    const roundId = roundIdContainer?.dataset.roundId;
    if (roundId && isReadyOrStarted) { /* ... */ setTimeout(connectToLaneSockets, 200); }
    else { /* ... */ window.lanesConnected = false; }

}); // End DOMContentLoaded
