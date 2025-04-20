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
    function connect() {
        console.log(`Attempting WS connect: ${url}`);
        if (socket && socket.readyState !== WebSocket.CLOSED) {
            socket.close(1000, "Reconnecting");
        }
        socket = new WebSocket(url);
        socket.onmessage = messageHandler;
        socket.onopen = (event) => {
            console.log(`WS open: ${url}`);
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
            if (openHandler) openHandler(event);
        };
            socket.onerror = (event) => {
                console.error(`WS error: ${url}`, event);
                if (errorHandler) errorHandler(event);
            };
                socket.onclose = (event) => {
                    console.log(`WS close: ${url}. Code: ${event.code}, Clean: ${event.wasClean}`);
                    if (closeHandler) closeHandler(event);
                    if (event.code !== 1000 && event.code !== 1005) {
                        console.log(`WS unexpected close. Reconnecting in ${RECONNECT_DELAY / 1000}s...`);
                        if (reconnectTimeout) clearTimeout(reconnectTimeout);
                        reconnectTimeout = setTimeout(connect, RECONNECT_DELAY);
                    } else {
                        if (reconnectTimeout) clearTimeout(reconnectTimeout);
                    }
                };
    }
    connect();
    return {
        send: function(data) {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(typeof data === 'string' ? data : JSON.stringify(data));
            } else { console.warn(`WS not open for send: ${url}`); }
        },
        close: function() {
            if (socket) {
                console.log(`Manual WS close: ${url}`);
                if (reconnectTimeout) clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
                socket.close(1000, "Client closed connection");
            }
        },
        getReadyState: function() { return socket ? socket.readyState : null; }
    };
}

/**
 * Function to get CSRF token (Keep as is)
 */
function getCookie(name) {
    // ... (implementation from previous version) ...
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Function to add a system message (Keep as is)
 */
function addSystemMessage(message, tag) {
    // ... (implementation from previous version) ...
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) { console.warn("Messages container not found"); return; }
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tag} alert-dismissible fade show m-2`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.style.opacity = '1';
    alertDiv.style.transition = 'opacity 0.5s ease-out';
    alertDiv.textContent = message;
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    alertDiv.appendChild(closeButton);
    messagesContainer.insertBefore(alertDiv, messagesContainer.firstChild);
    setTimeout(() => {
        if (alertDiv) {
            alertDiv.style.opacity = '0';
            setTimeout(() => { alertDiv.remove(); }, 500);
        }
    }, 7000);
}

/**
 * Function to connect to lane sockets (Keep as is)
 */
function connectToLaneSockets() {
    // ... (implementation from previous version, including window.lanesConnected check) ...
    if (window.lanesConnected) { console.log("Lane sockets already connected."); return; }
    window.lanesConnected = true;
    window.laneSocketsArray = window.laneSocketsArray || [];
    console.log("Connecting to pit lane sockets...");
    fetch('/get_race_lanes/')
    .then(response => { if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`); return response.json(); })
    .then(laneData => {
        if (!laneData || !laneData.lanes || !Array.isArray(laneData.lanes) || laneData.lanes.length === 0) {
            console.warn("No valid lanes array returned", laneData); window.lanesConnected = false; return;
        }
        const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
        laneData.lanes.forEach(laneInfo => {
            if (typeof laneInfo.lane === 'undefined') { console.warn("Invalid lane info:", laneInfo); return; }
            const laneNumber = laneInfo.lane;
            const laneElement = document.getElementById(`lane-${laneNumber}`);
            if (!laneElement) { console.warn(`Lane element lane-${laneNumber} not found`); return; }
            const laneSocketUrl = `${wsScheme}://${window.location.host}/ws/pitlanes/${laneNumber}/`;
            const laneSocket = createWebSocketWithReconnect( laneSocketUrl, (event) => { /* ... */ }, null, (event) => console.error(`WS error lane ${laneNumber}`), (event) => console.log(`WS closed lane ${laneNumber}`) );
            window.laneSocketsArray.push(laneSocket);
            fetch(`/pitlanedetail/${laneNumber}/`)
            .then(response => { if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`); return response.text(); })
            .then(htmlData => { const el = document.getElementById(`lane-${laneNumber}`); if (el) el.innerHTML = htmlData; })
            .catch(error => { console.error(`Failed initial load lane ${laneNumber}:`, error); if (laneElement) laneElement.innerHTML = `<div class="p-2 text-danger">Error loading Lane ${laneNumber}</div>`; });
        });
    })
    .catch(error => { console.error('Failed get_race_lanes:', error); addSystemMessage(`Failed load pit lanes: ${error}`, "danger"); window.lanesConnected = false; });
}


/**
 * Handles clicks on race action buttons. Sends request to backend API.
 * @param {Event} event - The click event object
 */
async function handleRaceAction(event) {
    const button = event.currentTarget;
    const action = button.dataset.action;
    const url = button.dataset.url;
    const roundIdContainer = document.getElementById('race-control-buttons');
    const roundId = roundIdContainer?.dataset.roundId;
    const csrfToken = getCookie('csrftoken'); // Assumes getCookie is defined elsewhere

    console.log(`Button clicked. Action: ${action}, URL: ${url}, RoundID: ${roundId}`);

    // --- Basic validation ---
    if (!action || !url) { addSystemMessage('Error: Button missing action/URL.', 'danger'); console.error('Button missing data attributes:', button); return; }
    if (!roundId) { addSystemMessage('Error: Round ID missing.', 'danger'); return; } // Keep check even if not used in fetch URL
    if (!csrfToken) { addSystemMessage('Error: CSRF Token missing. Cannot send request.', 'danger'); return; }

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
        if (response.ok) { // Status 200-299
            // --- Try to parse JSON ---
            let data;
            try {
                 data = await response.json();
                 console.log(`Action '${action}' response data:`, data);
            } catch (e) {
                 // Handle cases where backend sends 2xx status but non-JSON body
                 console.error("Could not parse JSON response despite OK status:", e);
                 addSystemMessage("Action status OK but received invalid response from server.", "warning");
                 // Re-enable button and return, as we can't process the result
                 if (button) { button.disabled = false; button.innerHTML = originalButtonHTML; }
                 return;
            }

            // --- Check LOGICAL Result from Backend ---
            // Adjust condition based on your actual backend response structure for failure
            const isLogicalError = data.result === false || (data.error && Array.isArray(data.error) && data.error.length > 0) || data.status === 'error';

            if (isLogicalError) {
                // Logical failure reported by backend
                console.warn(`Action '${action}' failed logically according to backend.`);

                // --- Display Error Messages ---
                if (data.error && Array.isArray(data.error) && data.error.length > 0) {
                    // Call addSystemMessage for each error in the list
                    data.error.forEach(errorMsg => {
                        if (typeof errorMsg === 'string') {
                             addSystemMessage(errorMsg, 'warning'); // Use 'warning' or 'danger'
                        } else {
                             console.warn("Non-string item found in errors array:", errorMsg);
                             addSystemMessage("Received an invalid error format from backend.", "warning");
                        }
                    });
                } else if (data.message) {
                    // Use message field if errors array is not present/empty
                    addSystemMessage(data.message, 'warning');
                } else {
                    // Default failure message if no specific errors/message provided
                    addSystemMessage(`Action '${action}' failed according to backend.`, 'warning');
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
                // Example for successful pre_check:
                if (action === 'pre_check') {
                     console.log("Pre-race check successful. Updating UI and connecting lanes...");
                     if (button) button.style.display = 'none'; // Hide pre-check button
                     const startButton = document.getElementById('startButton');
                     if (startButton) startButton.style.display = 'inline-block'; // Show start button
                     // Show/Hide team list cards
                     document.getElementById('emptyTeamsCard')?.style.setProperty('display', 'none', 'important');
                     document.getElementById('teamSelectCard')?.style.setProperty('display', 'block', 'important');
                     // Connect lanes (assumes connectToLaneSockets is defined)
                     if (typeof connectToLaneSockets === 'function') {
                         connectToLaneSockets();
                     } else {
                         console.error("connectToLaneSockets function not found!");
                     }
                }
                // Add similar 'else if (action === 'start')' blocks etc. for other actions...
                // Remember to handle showing/hiding the correct buttons based on the new state

                // Re-enable button if it wasn't hidden by the UI update logic above
                // (e.g., pause/resume buttons might just change text/class, not disappear)
                if (button && button.style.display !== 'none') {
                     button.disabled = false;
                     button.innerHTML = originalButtonHTML; // Or update text, e.g., Pause -> Resume
                }
                // --- END DYNAMIC UI UPDATES ---
            }

        } else { // Handle HTTP errors (4xx, 5xx)
            let errorMsg = `Error performing action '${action}'. Status: ${response.status}`;
            try {
                // Try to get more specific error from JSON response body, even on HTTP error
                const errorData = await response.json();
                errorMsg = errorData.error || errorData.message || errorMsg;
                console.error(`Server error detail for ${action}:`, errorData);
            } catch (e) {
                // Response wasn't JSON or couldn't be parsed, use status text
                errorMsg = `${errorMsg} (${response.statusText})`;
                console.warn("Could not parse error response as JSON.");
            }
            console.error(`Action '${action}' failed HTTP Status. Status: ${response.status}`);
            addSystemMessage(errorMsg, 'danger');
            // Re-enable button on failure
            if (button) {
                button.disabled = false;
                button.innerHTML = originalButtonHTML;
            }
        }
    } catch (error) { // Handle network errors or other exceptions during fetch
        console.error(`Network or fetch error during action '${action}':`, error);
        addSystemMessage(`Network error: ${error}. Please check connection.`, 'danger');
        // Re-enable button on failure
        if (button) {
            button.disabled = false;
            button.innerHTML = originalButtonHTML;
        }
    }
}

/**
 * Function to update the empty teams list UI (Keep as is)
 */
function updateEmptyTeamsList(teams) {
    // ... (implementation from previous version) ...
    const emptyTeamsUL = document.getElementById('emptyTeamsUL');
    const placeholder = document.getElementById('emptyTeamsPlaceholder');
    const emptyTeamsSocket = window.emptyTeamsSocket;
    if (!emptyTeamsUL || !placeholder) return;
    // Clear current list
    emptyTeamsUL.innerHTML = '';

    if (teams.length === 0) {
        placeholder.textContent = 'No empty teams found';
        placeholder.style.display = 'block';
        emptyTeamsUL.style.display = 'none';
    } else {
        placeholder.style.display = 'none';
        emptyTeamsUL.style.display = 'block';

        // Add each team to the list
        teams.forEach(function(team) {
            const li = document.createElement('li');
            li.className = 'list-group-item d-flex justify-content-between align-items-center';

            // Format: Team name (Number) - Championship name
            li.innerHTML = `
            <span>${team.team_name} (#${team.number}) - ${team.championship_name}</span>
            <button class="btn btn-sm btn-outline-danger delete-single-team"
            data-team-id="${team.id}">Delete</button>
            `;

            emptyTeamsUL.appendChild(li);
        });

        // Add event listeners for individual team deletion
        document.querySelectorAll('.delete-single-team').forEach(button => {
            button.addEventListener('click', function() {
                const teamId = this.getAttribute('data-team-id');
                if (confirm('Delete this team?')) {
                    const emptyTeamsSocket = new WebSocket(
                        'ws://' + window.location.host + '/ws/empty_teams/'
                    );

                    emptyTeamsSocket.onopen = function() {
                        emptyTeamsSocket.send(JSON.stringify({
                            'action': 'delete_single_team',
                            'team_id': teamId
                        }));
                    };
                }
            });
        });
    }
}


// --- Event Listeners Setup ---
document.addEventListener('DOMContentLoaded', () => {
    // Add listeners to all race action buttons
    const actionButtons = document.querySelectorAll('.race-action-btn');
    actionButtons.forEach(button => {
        button.addEventListener('click', handleRaceAction);
    });

    // Add listener for Stop&Go button (Keep as is)
    const stopGoButton = document.getElementById('stopGoButton');
    // ... (rest of stopGoButton listener logic from v3) ...
    if (stopGoButton) { stopGoButton.addEventListener('click', async () => { /* ... */ }); }


    // --- Initial Lane Connection Check ---
    const isReadyOrStarted = document.getElementById('startButton') || document.getElementById('pauseButton') || document.getElementById('resumeButton') || document.getElementById('endButton');
    const roundIdContainer = document.getElementById('race-control-buttons');
    const roundId = roundIdContainer?.dataset.roundId;
    if (roundId && isReadyOrStarted) {
        console.log("Page loaded: Round ready/started. Connecting lane sockets.");
        setTimeout(connectToLaneSockets, 200);
    } else {
        console.log("Page loaded: Round not ready/started. Skipping initial lane connection.");
        window.lanesConnected = false;
    }

}); // End DOMContentLoaded
