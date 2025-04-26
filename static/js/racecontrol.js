// static/js/racecontrol.js
let falseStartTimeoutId = null;
let falseStartTimeoutExpired = false;
let falseRestartTimeoutId = null;
let falseRestartTimeoutExpired = false;
let emptyTeamsSocketInstance = null;
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
 * Hides the False Start button if it's currently visible.
 */
function hideFalseStartButton() {
    const btn = document.getElementById('falseStartButton');
    if (btn && !btn.hidden) {
        console.log("Hiding False Start button due to timeout or state change.");
        btn.hidden = true;
        if ( falseStartTimeoutExpired) {
            document.getElementById('pauseButton')?.removeAttribute('hidden');
        }
    }
    falseStartTimeoutExpired = false;
    if (falseStartTimeoutId) {
        clearTimeout(falseStartTimeoutId);
        falseStartTimeoutId = null;
    }
}

/**
 * Hides the False Restart button if it's currently visible.
 */
function hideFalseRestartButton() {
    const btn = document.getElementById('falseRestartButton');
    if (btn && !btn.hidden) {
        console.log("Hiding False Restart button due to timeout or state change.");
        btn.hidden = true;
        if ( falseRestartTimeoutExpired) {
            document.getElementById('pauseButton')?.removeAttribute('hidden');
        }
    }
    falseRestartTimeoutExpired = false;
    if (falseRestartTimeoutId) {
        clearTimeout(falseRestartTimeoutId);
        falseRestartTimeoutId = null;
    }
}

/**
 * Updates button visibility based on the provided race state.
 * @param {string} state - The current state ('initial', 'ready', 'running', 'paused', 'ended')
 * @param {object} [options] - Optional parameters like { showFalseStart: true }
 */
function updateButtonVisibility(state, options = {}) {
    console.log(`Updating button visibility for state: ${state}`, options);
    const allActionButtons = document.querySelectorAll('#race-control-buttons .race-action-btn');
    allActionButtons.forEach(btn => btn.hidden = true); // Hide all first

    // Clear any pending temporary button timeouts unless explicitly told otherwise
    if (!options.keepFalseStart) hideFalseStartButton();
    if (!options.keepFalseRestart) hideFalseRestartButton();

    // Show buttons based on state
    switch (state) {
        case 'initial': // Not ready, not started
            document.getElementById('preRaceCheckButton')?.removeAttribute('hidden');
            document.getElementById('emptyTeamsCard')?.style.setProperty('display', 'block', 'important');
            document.getElementById('teamSelectCard')?.style.setProperty('display', 'none', 'important');
            break;
        case 'ready': // Ready, not started
            document.getElementById('startButton')?.removeAttribute('hidden');
            document.getElementById('emptyTeamsCard')?.style.setProperty('display', 'none', 'important');
            document.getElementById('teamSelectCard')?.style.setProperty('display', 'block', 'important');
            break;
        case 'running': // Ready, started
            if (options.showFalseStart ) {
                document.getElementById('falseStartButton')?.removeAttribute('hidden'); // Show initially
                if (!options.keepFalseStart) { // Avoid restarting timeout if already running
                    falseStartTimeoutId = setTimeout(() => {
                        falseStartTimeoutExpired = true;
                        hideFalseStartButton();
                    }, 15000); // 15 seconds
                }
            } else {
                document.getElementById('pauseButton')?.removeAttribute('hidden');
            };
            break;

        case 'paused': // Started, paused
            if (options.showFalseRestart ) {
            document.getElementById('falseRestartButton')?.removeAttribute('hidden'); // Show initially
                // Start timeout to hide False Restart button after a delay
                if (!options.keepFalseRestart) { // Avoid restarting timeout
                    falseRestartTimeoutId = setTimeout(() => {
                        falseRestartTimeoutExpired = true;
                        hideFalseRestartButton();
                    }, 15000); // 15 seconds
                }
            } else {
                document.getElementById('pauseButton')?.removeAttribute('hidden'); // Show initially
            };
            break;
        case 'ended': // Ended
            // No buttons shown by default in 'ended' state
            break;
        default:
            console.warn("Unknown state passed to updateButtonVisibility:", state);
            // Show pre-check as a fallback?
            document.getElementById('preRaceCheckButton')?.removeAttribute('hidden');

    }
    // Ensure all visible buttons are enabled
    document.querySelectorAll('#race-control-buttons .race-action-btn:not([hidden])').forEach(btn => btn.disabled = false);
}

/**
 * Handles clicks on race action buttons. Sends request to backend API.
 * Updates button visibility on success based on FSM logic.
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

    // --- Disable ALL action buttons during processing ---
    const allActionButtons = document.querySelectorAll('#race-control-buttons .race-action-btn');
    allActionButtons.forEach(btn => btn.disabled = true);
    const originalButtonHTML = button.innerHTML;
    button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;
    console.log(`Sending POST request to: ${url}`);

    // --- Clear relevant timeouts when an action is initiated ---
    if (action !== 'false_start') clearTimeout(falseStartTimeoutId);
    if (action !== 'false_restart') clearTimeout(falseRestartTimeoutId);


    try {
        const response = await fetch(url, { /* ... fetch options ... */ });
        console.log(`Received response for ${action}. Status: ${response.status}`);

        if (response.ok) {
            let data;
            try { data = await response.json(); console.log(`Action '${action}' response data:`, data); }
            catch (e) { addSystemMessage("Invalid response.", "warning"); return; }

            const isLogicalError = data.result === false || (data.error && Array.isArray(data.error) && data.error.length > 0) || data.status === 'error';

            if (isLogicalError) {
                // --- Handle Logical Failure ---
                console.warn(`Action '${action}' failed logically.`);
                if (data.error && Array.isArray(data.error) && data.error.length > 0) {
                    data.error.forEach(errorMsg => { addSystemMessage(errorMsg, 'warning'); });
                } else { addSystemMessage(data.message || `Action '${action}' failed.`, 'warning'); }
                // Restore clicked button text
                button.innerHTML = originalButtonHTML;
                // Determine current state to re-enable correct buttons (or rely on WS)
                // For now, just re-enable all potentially visible buttons for simplicity on error
                allActionButtons.forEach(btn => btn.disabled = false);


            } else {
                // --- Handle Logical Success ---
                console.log(`Action '${action}' successful logically.`);
                addSystemMessage(data.message || `Action '${action}' successful.`, 'success');

                // --- Determine NEXT state and update button visibility ---
                let nextState = 'unknown';
                let options = {}; // Options for updateButtonVisibility

                switch (action) {
                    case 'pre_check':     nextState = 'ready'; break;
                    case 'start':         nextState = 'running'; options = { showFalseStart: true }; break;
                    case 'pause':         nextState = 'paused'; break;
                    case 'resume':        nextState = 'paused'; options = { showFalseRestart: true }; break; // Resume goes back to running
                    case 'end':           nextState = 'ended'; break;
                    case 'false_start':   nextState = 'ready'; break; // False start goes back to ready
                    case 'false_restart': nextState = 'paused'; break; // False restart goes back to paused
                }

                updateButtonVisibility(nextState, options); // Update UI based on FSM

                // Connect lanes only after successful pre-check
                if (action === 'pre_check') {
                    if (typeof connectToLaneSockets === 'function') connectToLaneSockets(); else console.error("connectToLaneSockets missing!");
                }
            }

        } else { // Handle HTTP errors
            let errorMsg = `Error: ${response.status}`; /* ... get details ... */ addSystemMessage(errorMsg, 'danger');
            button.innerHTML = originalButtonHTML; // Restore button text
            allActionButtons.forEach(btn => btn.disabled = false); // Re-enable all on HTTP error
        }
    } catch (error) { // Handle network errors
        console.error(`Network error:`, error); addSystemMessage(`Network error: ${error}.`, 'danger');
        button.innerHTML = originalButtonHTML; // Restore button text
        allActionButtons.forEach(btn => btn.disabled = false); // Re-enable all on network error
    }
    // No finally block needed as enablement is handled in error/success paths now
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
    if (stopGoButton) { stopGoButton.addEventListener('click', async () => { /* ... */ }); }


    // --- Set Initial Button State ---
    // Determine initial state based on which buttons are initially visible in the HTML
    let initialState = 'initial'; // Default
    if (document.getElementById('startButton')?.offsetParent !== null) initialState = 'ready'; // Check visibility more reliably
    else if (document.getElementById('pauseButton')?.offsetParent !== null) initialState = 'running';
    else if (document.getElementById('resumeButton')?.offsetParent !== null) initialState = 'paused';
    else if (!document.querySelector('#race-control-buttons .race-action-btn:not([hidden])')) initialState = 'ended'; // If no buttons visible

    updateButtonVisibility(initialState); // Set initial visibility

    // --- Initial Lane Connection Check ---
    // Connect if initial state is ready, running, or paused
    if (['ready', 'running', 'paused'].includes(initialState)) {
        console.log(`Page loaded: Round state is ${initialState}. Connecting lane sockets.`);
        setTimeout(connectToLaneSockets, 200);
    } else {
        console.log("Page loaded: Round not ready/started/paused. Skipping initial lane connection.");
        window.lanesConnected = false;
    }

});
