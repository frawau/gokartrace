// static/js/racecontrol.js

/**
 * Creates a WebSocket connection with automatic reconnection logic.
 * @param {string} url - The WebSocket URL to connect to.
 * @param {function} messageHandler - Function to call when a message is received.
 * @param {function} [openHandler=null] - Function to call when the connection opens.
 * @param {function} [errorHandler=null] - Function to call on WebSocket error.
 * @param {function} [closeHandler=null] - Function to call when the connection closes.
 * @returns {object} - An object with 'send' and 'close' methods.
 */
function createWebSocketWithReconnect(url, messageHandler, openHandler = null, errorHandler = null, closeHandler = null) {
    let socket;
    let reconnectTimeout;
    // Shorten delay for quicker reconnect attempts, but increase slightly on repeated failures? (Simple fixed delay for now)
    const RECONNECT_DELAY = 5000; // 5 seconds

    function connect() {
        // Add check to prevent multiple concurrent connection attempts for the same URL if needed
        console.log(`Attempting to connect WebSocket to ${url}`);
        // Clean up previous socket instance if exists
        if (socket && socket.readyState !== WebSocket.CLOSED) {
            console.log(`Closing existing socket to ${url} before reconnecting.`);
            socket.close(1000, "Reconnecting"); // Close gracefully
        }

        socket = new WebSocket(url);

        socket.onmessage = messageHandler; // Assign the message handler

        socket.onopen = function(event) {
            console.log(`WebSocket connection established to ${url}`);
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout); // Clear timer on successful connection
                reconnectTimeout = null;
            }
            if (openHandler) openHandler(event); // Call custom open handler
        };

            socket.onerror = function(event) {
                console.error(`WebSocket error on ${url}:`, event);
                if (errorHandler) errorHandler(event);
                // Note: The 'close' event will usually fire immediately after 'error'.
                // Reconnection logic is handled in 'onclose'.
            };

                socket.onclose = function(event) {
                    console.log(`WebSocket connection to ${url} closed. Code: ${event.code}, Reason: '${event.reason}', Clean: ${event.wasClean}`);
                    if (closeHandler) closeHandler(event);

                    // Attempt to reconnect only if closure was not clean (code 1000 is clean close)
                    // Avoid reconnecting if the code is 1000 (Normal Closure) or 1005 (No Status Rcvd - often indicates browser tab closing)
                    // Consider other codes? e.g., 1001 (Going Away) might also indicate no need to reconnect.
                    if (event.code !== 1000 && event.code !== 1005) {
                        console.log(`WebSocket closed unexpectedly. Reconnecting in ${RECONNECT_DELAY / 1000} seconds...`);
                        if (reconnectTimeout) clearTimeout(reconnectTimeout); // Clear previous timer if any
                        reconnectTimeout = setTimeout(connect, RECONNECT_DELAY);
                    } else {
                        console.log(`WebSocket closed normally or tab closing. No automatic reconnect for ${url}.`);
                        if (reconnectTimeout) clearTimeout(reconnectTimeout); // Ensure timer is cleared on clean close
                    }
                };
    }

    connect(); // Initial connection attempt

    return {
        /**
         * Sends data through the WebSocket if open.
         * @param {string|object} data - Data to send (will be stringified if object).
         */
        send: function(data) {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const message = typeof data === 'string' ? data : JSON.stringify(data);
                socket.send(message);
            } else {
                console.warn(`Cannot send message to ${url}, socket not open. State: ${socket?.readyState}`);
                // Optional: Queue message or notify user
            }
        },
        /**
         * Closes the WebSocket connection cleanly.
         */
        close: function() {
            if (socket) {
                console.log(`Manually closing WebSocket connection to ${url}`);
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout); // Prevent reconnect on manual close
                    reconnectTimeout = null;
                }
                socket.close(1000, "Client closed connection"); // Use code 1000 for clean close
            }
        },
        /**
         * Gets the current readyState of the WebSocket.
         * @returns {number|null} WebSocket.CONNECTING, .OPEN, .CLOSING, .CLOSED or null
         */
        getReadyState: function() {
            return socket ? socket.readyState : null;
        }
    };
}


/**
 * Function to get CSRF token (Keep as is)
 */
function getCookie(name) {
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
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) {
        console.warn("Messages container not found");
        return;
    }
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
 * Needs access to createWebSocketWithReconnect, addSystemMessage
 */
function connectToLaneSockets() {
    // Check if already connected (using a simple flag)
    if (window.lanesConnected) {
        console.log("Lane sockets already connected or connection attempt in progress.");
        return;
    }
    window.lanesConnected = true; // Set flag immediately
    window.laneSocketsArray = window.laneSocketsArray || [];

    console.log("Connecting to pit lane sockets...");

    // Use Fetch API to get lane details
    fetch('/get_race_lanes/') // Replace with your actual URL
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error getting lanes! status: ${response.status}`);
        return response.json();
    })
    .then(laneData => {
        if (!laneData || !laneData.lanes || !Array.isArray(laneData.lanes) || laneData.lanes.length === 0) {
            console.warn("No valid lanes array returned from server", laneData);
            window.lanesConnected = false; // Reset flag if no lanes
            return;
        }
        console.log("Received lane data:", laneData);
        const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';

        laneData.lanes.forEach(laneInfo => {
            if (typeof laneInfo.lane === 'undefined') {
                console.warn("Invalid lane info object received:", laneInfo); return;
            }
            const laneNumber = laneInfo.lane;
            const laneElement = document.getElementById(`lane-${laneNumber}`);
            if (!laneElement) {
                console.warn(`Lane element lane-${laneNumber} not found`); return;
            }

            // Connect WebSocket (Uses createWebSocketWithReconnect defined above)
            const laneSocketUrl = `${wsScheme}://${window.location.host}/ws/pitlanes/${laneNumber}/`;
            const laneSocket = createWebSocketWithReconnect(
                laneSocketUrl,
                (event) => { // onmessage
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'rclane.update') {
                            const currentLaneElement = document.getElementById(`lane-${laneNumber}`);
                            if (currentLaneElement) {
                                currentLaneElement.innerHTML = data.lane_html; // Update inner HTML
                            }
                        }
                    } catch (e) { console.error(`Error parsing lane ${laneNumber} WS message:`, e, event.data); }
                }, null,
                (event) => console.error(`WS error lane ${laneNumber}`),
                                                            (event) => console.log(`WS closed lane ${laneNumber}`)
            );
            window.laneSocketsArray.push(laneSocket);

            // Initial Lane Load
            fetch(`/pitlanedetail/${laneNumber}/`) // Replace with your URL
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error loading lane detail! status: ${response.status}`);
                return response.text();
            })
            .then(htmlData => {
                const currentLaneElement = document.getElementById(`lane-${laneNumber}`);
                if (currentLaneElement) currentLaneElement.innerHTML = htmlData;
            })
            .catch(error => {
                console.error(`Failed initial load lane ${laneNumber}:`, error);
                if (laneElement) laneElement.innerHTML = `<div class="p-2 text-danger">Error loading Lane ${laneNumber}</div>`;
            });
        });
    })
    .catch(error => {
        console.error('Failed to get race lanes:', error);
        addSystemMessage(`Failed to load pit lanes: ${error}`, "danger");
        window.lanesConnected = false; // Reset flag on error
    });
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
    const csrfToken = getCookie('csrftoken');

    // --- Basic validation ---
    if (!action || !url) { addSystemMessage('Error: Button missing action/URL.', 'danger'); return; }
    if (!roundId) { addSystemMessage('Error: Round ID missing.', 'danger'); return; }
    if (!csrfToken) { addSystemMessage('Error: CSRF Token missing.', 'danger'); return; }

    button.disabled = true;
    const originalButtonHTML = button.innerHTML;
    button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;

    console.log(`Performing action: ${action} on round ${roundId} via URL: ${url}`);

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
        });

        if (response.ok) {
            const data = await response.json();
            console.log(`Action '${action}' successful:`, data);
            addSystemMessage(data.message || `Action '${action}' successful.`, data.status || 'success');

            // Trigger lane connection on successful pre-race check
            if (action === 'pre_check' && (data.status === 'success' || data.ready === true)) {
                console.log("Pre-race check successful and round is ready. Connecting to lane sockets...");
                document.getElementById('emptyTeamsCard')?.style.setProperty('display', 'none', 'important');
                document.getElementById('teamSelectCard')?.style.setProperty('display', 'block', 'important');
                connectToLaneSockets(); // Call the function here
            }

            // Reload the page to update button states correctly
            addSystemMessage("Updating status... Page will reload shortly.", "info");
            setTimeout(() => { window.location.reload(); }, 1500);

        } else { // Handle HTTP errors
            let errorMsg = `Error performing action '${action}'. Status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorData.message || errorMsg;
            } catch (e) { errorMsg = `${errorMsg} - ${response.statusText}`; }
            console.error(`Action '${action}' failed:`, response);
            addSystemMessage(errorMsg, 'danger');
            button.disabled = false; // Re-enable button on error
            button.innerHTML = originalButtonHTML;
        }
    } catch (error) { // Handle network errors
        console.error(`Network error during action '${action}':`, error);
        addSystemMessage(`Network error: ${error}. Please check connection.`, 'danger');
        button.disabled = false; // Re-enable button on error
        button.innerHTML = originalButtonHTML;
    }
}

/**
 * Function to update the empty teams list UI.
 * @param {Array} teams - Array of team objects {id, team_name, number, championship_name}
 */
function updateEmptyTeamsList(teams) {
    const emptyTeamsUL = document.getElementById('emptyTeamsUL');
    const placeholder = document.getElementById('emptyTeamsPlaceholder');
    // Assumes 'window.emptyTeamsSocket' is managed by the inline script or another mechanism
    // This function needs access to the correct socket instance to send delete messages.
    const emptyTeamsSocket = window.emptyTeamsSocket; // Example: Accessing a global/window-scoped socket

    if (!emptyTeamsUL || !placeholder) return;
    emptyTeamsUL.innerHTML = ''; // Clear current list

    if (!teams || teams.length === 0) {
        placeholder.textContent = 'No empty teams found';
        placeholder.style.display = 'block';
        emptyTeamsUL.style.display = 'none';
    } else {
        placeholder.style.display = 'none';
        emptyTeamsUL.style.display = 'block';
        teams.forEach(function(team) {
            const li = document.createElement('li');
            li.className = 'list-group-item d-flex justify-content-between align-items-center';
            li.innerHTML = `<span>${team.team_name} (#${team.number}) - ${team.championship_name}</span> <button class="btn btn-sm btn-outline-danger delete-single-team" data-team-id="${team.id}">Delete</button>`;
            emptyTeamsUL.appendChild(li);
        });
        // Add event listeners AFTER adding elements
        document.querySelectorAll('.delete-single-team').forEach(button => {
            button.addEventListener('click', function() {
                const teamId = this.getAttribute('data-team-id');
                if (confirm(`Delete team #${teamId}?`)) {
                    try {
                        if (emptyTeamsSocket && emptyTeamsSocket.getReadyState() === WebSocket.OPEN) { // Use helper method if available
                            emptyTeamsSocket.send(JSON.stringify({'action': 'delete_single_team', 'team_id': teamId}));
                        } else {
                            addSystemMessage("Connection not ready for delete action.", "warning");
                        }
                    } catch (e) { console.error("Error sending delete request:", e); addSystemMessage("Error sending delete request.", "danger");}
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

    // Add listener for Stop&Go button
    const stopGoButton = document.getElementById('stopGoButton');
    const teamSelect = document.getElementById('teamSelect');
    const teamSelectCard = document.getElementById('teamSelectCard');
    if (stopGoButton && teamSelect && teamSelectCard) {
        stopGoButton.addEventListener('click', async () => {
            const teamId = teamSelect.value;
            const csrfToken = getCookie('csrftoken');
            if (!teamId || !csrfToken) { addSystemMessage("Missing Team ID or CSRF Token.", "warning"); return; }
            const isServing = stopGoButton.textContent === 'Served';
            const url = isServing ? '/clear_penalty/' : '/serve_team/'; // DEFINE THESE URLS
            const actionText = isServing ? 'Clear Penalty' : 'Stop&Go Served';
            const originalText = isServing ? 'Served' : 'Stop&Go';
            stopGoButton.disabled = true;
            stopGoButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
                    body: `team_id=${encodeURIComponent(teamId)}`
                });
                if (response.ok) {
                    const data = await response.json();
                    addSystemMessage(data.message || `${actionText} recorded.`, 'success');
                    stopGoButton.textContent = isServing ? 'Stop&Go' : 'Served';
                    teamSelectCard.style.backgroundColor = isServing ? '' : 'rgba(255, 193, 7, 0.4)';
                    if (isServing) teamSelect.value = teamSelect.options[0]?.value || '';
                } else {
                    let errorMsg = `Error. Status: ${response.status}`;
                    try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch (e) {}
                    addSystemMessage(errorMsg, 'danger');
                    stopGoButton.textContent = originalText;
                }
            } catch (error) {
                console.error('Stop&Go network error:', error);
                addSystemMessage('Network error applying Stop&Go.', 'danger');
                stopGoButton.textContent = originalText;
            } finally {
                stopGoButton.disabled = false;
            }
        });
    }

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
