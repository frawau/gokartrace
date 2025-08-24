// static/js/racecontrol.js
let falseStartTimeoutId = null;
let falseStartTimeoutExpired = false;
let falseRestartTimeoutId = null;
let falseRestartTimeoutExpired = false;
let emptyTeamsSocketInstance = null;

// Stop & Go state variables
let stopAndGoSocket = null;
let stopAndGoState = 'idle'; // 'idle', 'active', 'served'
let fenceEnabled = null;
let hmacSecret = null;

/**
 * Sign message with HMAC using Web Crypto API (SHA-256 for JavaScript compatibility)
 */
async function signMessage(messageData) {
  if (!hmacSecret) {
    console.error('HMAC secret not available - attempting to reload from DOM');
    
    // Try to get the secret again
    const roundData = document.getElementById('round-data');
    if (roundData) {
      hmacSecret = roundData.dataset.hmacSecret || roundData.getAttribute('data-hmac-secret');
      console.log('Retry: HMAC secret loaded:', hmacSecret ? 'YES' : 'NO');
    }
    
    // Try fallback from window
    if (!hmacSecret && window.STOPANDGO_HMAC_SECRET) {
      hmacSecret = window.STOPANDGO_HMAC_SECRET;
      console.log('Using fallback HMAC secret from window:', hmacSecret ? 'YES' : 'NO');
    }
    
    if (!hmacSecret) {
      console.error('HMAC secret still not available - message will not be signed!');
      return messageData;
    }
  }
  
  try {
    const messageStr = JSON.stringify(messageData);
    const encoder = new TextEncoder();
    const keyData = encoder.encode(hmacSecret);
    const messageBuffer = encoder.encode(messageStr);
    
    const key = await crypto.subtle.importKey(
      'raw',
      keyData,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    
    const signature = await crypto.subtle.sign('HMAC', key, messageBuffer);
    const signatureArray = new Uint8Array(signature);
    const signatureHex = Array.from(signatureArray)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
    
    messageData.hmac_signature = signatureHex;
    return messageData;
  } catch (error) {
    console.error('Error signing message:', error);
    return messageData;
  }
}
/**
 * Creates a WebSocket connection with automatic reconnection logic.
 * (Keep function definition as is)
 */
function createWebSocketWithReconnect(
  url,
  messageHandler,
  openHandler = null,
  errorHandler = null,
  closeHandler = null,
) {
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
      console.log(
        `WS close: ${url}. Code: ${event.code}, Clean: ${event.wasClean}`,
      );
      if (closeHandler) closeHandler(event);
      if (event.code !== 1000 && event.code !== 1005) {
        console.log(
          `WS unexpected close. Reconnecting in ${RECONNECT_DELAY / 1000}s...`,
        );
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(connect, RECONNECT_DELAY);
      } else {
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
      }
    };
  }
  connect();
  return {
    send: function (data) {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(typeof data === "string" ? data : JSON.stringify(data));
      } else {
        console.warn(`WS not open for send: ${url}`);
      }
    },
    close: function () {
      if (socket) {
        console.log(`Manual WS close: ${url}`);
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
        socket.close(1000, "Client closed connection");
      }
    },
    getReadyState: function () {
      return socket ? socket.readyState : null;
    },
  };
}

/**
 * Function to get CSRF token (Keep as is)
 */
function getCookie(name) {
  // ... (implementation from previous version) ...
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
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
  const messagesContainer = document.getElementById("messagesContainer");
  if (!messagesContainer) {
    console.warn("Messages container not found");
    return;
  }
  const alertDiv = document.createElement("div");
  alertDiv.className = `alert alert-${tag} alert-dismissible fade show m-2`;
  alertDiv.setAttribute("role", "alert");
  alertDiv.style.opacity = "1";
  alertDiv.style.transition = "opacity 0.5s ease-out";
  alertDiv.textContent = message;
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "btn-close";
  closeButton.setAttribute("data-bs-dismiss", "alert");
  closeButton.setAttribute("aria-label", "Close");
  alertDiv.appendChild(closeButton);
  messagesContainer.insertBefore(alertDiv, messagesContainer.firstChild);
  setTimeout(() => {
    if (alertDiv) {
      alertDiv.style.opacity = "0";
      setTimeout(() => {
        alertDiv.remove();
      }, 500);
    }
  }, 7000);
}

/**
 * Function to connect to lane sockets (Keep as is)
 */
function connectToLaneSockets() {
  // ... (implementation from previous version, including window.lanesConnected check) ...
  if (window.lanesConnected) {
    console.log("Lane sockets already connected.");
    return;
  }
  window.lanesConnected = true;
  window.laneSocketsArray = window.laneSocketsArray || [];
  console.log("Connecting to pit lane sockets...");
  fetch("/get_race_lanes/")
    .then((response) => {
      if (!response.ok)
        throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    })
    .then((laneData) => {
      if (
        !laneData ||
        !laneData.lanes ||
        !Array.isArray(laneData.lanes) ||
        laneData.lanes.length === 0
      ) {
        console.warn("No valid lanes array returned", laneData);
        window.lanesConnected = false;
        return;
      }
      const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
      laneData.lanes.forEach((laneInfo) => {
        if (typeof laneInfo.lane === "undefined") {
          console.warn("Invalid lane info:", laneInfo);
          return;
        }
        const laneNumber = laneInfo.lane;
        const laneElement = document.getElementById(`lane-${laneNumber}`);
        if (!laneElement) {
          console.warn(`Lane element lane-${laneNumber} not found`);
          return;
        }
        const laneSocketUrl = `${wsScheme}://${window.location.host}/ws/pitlanes/${laneNumber}/`;
        const laneSocket = createWebSocketWithReconnect(
          laneSocketUrl,
          (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === "lane.update") {
                  fetch(`/pitlanedetail/${laneNumber}/`)
                  .then(response => {
                      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                      return response.text();
                  })
                  .then(htmlData => {
                      const el = document.getElementById(`lane-${laneNumber}`);
                      if (el) el.innerHTML = htmlData;
                  })
                  .catch(error => {
                      console.error(`Failed to update lane ${laneNumber}:`, error);
                  })
              }
            } catch (error) {
              console.error(
                `Error processing message for lane ${laneNumber}:`,
                error,
              );
            }
          },
          null,
          (event) => console.error(`WS error lane ${laneNumber}`),
          (event) => console.log(`WS closed lane ${laneNumber}`),
        );
        window.laneSocketsArray.push(laneSocket);
        fetch(`/pitlanedetail/${laneNumber}/`)
          .then((response) => {
            if (!response.ok)
              throw new Error(`HTTP error! status: ${response.status}`);
            return response.text();
          })
          .then((htmlData) => {
            const el = document.getElementById(`lane-${laneNumber}`);
            if (el) el.innerHTML = htmlData;
          })
          .catch((error) => {
            console.error(`Failed initial load lane ${laneNumber}:`, error);
            if (laneElement)
              laneElement.innerHTML = `<div class="p-2 text-danger">Error loading Lane ${laneNumber}</div>`;
          });
      });
    })
    .catch((error) => {
      console.error("Failed get_race_lanes:", error);
      addSystemMessage(`Failed load pit lanes: ${error}`, "danger");
      window.lanesConnected = false;
    });
}

/**
 * Hides the False Start button if it's currently visible.
 */
function hideFalseStartButton() {
  const btn = document.getElementById("falseStartButton");
  if (btn && !btn.hidden) {
    console.log("Hiding False Start button due to timeout or state change.");
    btn.hidden = true;
    if (falseStartTimeoutExpired) {
      const pauseBtn = document.getElementById("pauseButton");
      if (pauseBtn) {
        pauseBtn.removeAttribute("hidden");
        pauseBtn.innerHTML = '<i class="fas fa-pause me-1"></i> Pause Race';
        pauseBtn.disabled = false;
      }
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
  const btn = document.getElementById("falseRestartButton");
  if (btn && !btn.hidden) {
    console.log("Hiding False Restart button due to timeout or state change.");
    btn.hidden = true;
    if (falseRestartTimeoutExpired) {
      const pauseBtn = document.getElementById("pauseButton");
      if (pauseBtn) {
        pauseBtn.removeAttribute("hidden");
        pauseBtn.innerHTML = '<i class="fas fa-pause me-1"></i> Pause Race';
        pauseBtn.disabled = false;
      }
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
  const allActionButtons = document.querySelectorAll(
    "#race-control-buttons .race-action-btn",
  );
  allActionButtons.forEach((btn) => (btn.hidden = true)); // Hide all first

  // Clear any pending temporary button timeouts unless explicitly told otherwise
  if (!options.keepFalseStart) hideFalseStartButton();
  if (!options.keepFalseRestart) hideFalseRestartButton();

  // Show buttons based on state
  switch (state) {
    case "initial": // Not ready, not started
      document.getElementById("preRaceCheckButton")?.removeAttribute("hidden");
      document
        .getElementById("emptyTeamsCard")
        ?.style.setProperty("display", "block", "important");
      document
        .getElementById("teamSelectCard")
        ?.style.setProperty("display", "none", "important");
      break;
    case "ready": // Ready, not started
      const startBtn = document.getElementById("startButton");
      if (startBtn) {
        startBtn.removeAttribute("hidden");
        startBtn.innerHTML = '<i class="fas fa-play me-1"></i> Start Race';
        startBtn.disabled = false;
      }
      document
        .getElementById("emptyTeamsCard")
        ?.style.setProperty("display", "none", "important");
      document
        .getElementById("teamSelectCard")
        ?.style.setProperty("display", "block", "important");
      break;
    case "running": // Ready, started
      if (options.showFalseStart) {
        const falseStartBtn = document.getElementById("falseStartButton");
        if (falseStartBtn) {
          falseStartBtn.removeAttribute("hidden");
          falseStartBtn.innerHTML = '<i class="fas fa-undo me-1"></i> False Start';
          falseStartBtn.disabled = false;
        }
        if (!options.keepFalseStart) {
          // Avoid restarting timeout if already running
          falseStartTimeoutId = setTimeout(() => {
            falseStartTimeoutExpired = true;
            hideFalseStartButton();
          }, 15000); // 15 seconds
        }
      } else if (options.showFalseRestart) {
        const falseRestartBtn = document.getElementById("falseRestartButton");
        if (falseRestartBtn) {
          falseRestartBtn.removeAttribute("hidden");
          falseRestartBtn.innerHTML = '<i class="fas fa-history me-1"></i> False Restart';
          falseRestartBtn.disabled = false;
        }
        // Start timeout to hide False Restart button after a delay
        if (!options.keepFalseRestart) {
          // Avoid restarting timeout
          falseRestartTimeoutId = setTimeout(() => {
            falseRestartTimeoutExpired = true;
            hideFalseRestartButton();
          }, 15000); // 15 seconds
        }
      } else {
        document.getElementById("pauseButton")?.removeAttribute("hidden");
      }
      break;

    case "paused": // Started, paused
      const resumeBtn = document.getElementById("resumeButton");
      if (resumeBtn) {
        resumeBtn.removeAttribute("hidden");
        resumeBtn.innerHTML = '<i class="fas fa-play-circle me-1"></i> Resume Race';
        resumeBtn.disabled = false;
      }
      break;
    case "ended": // Ended
      // No buttons shown by default in 'ended' state
      break;
    default:
      console.warn("Unknown state passed to updateButtonVisibility:", state);
      // Show pre-check as a fallback?
      document.getElementById("preRaceCheckButton")?.removeAttribute("hidden");
  }
  // Ensure all visible buttons are enabled
  document
    .querySelectorAll("#race-control-buttons .race-action-btn:not([hidden])")
    .forEach((btn) => (btn.disabled = false));
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
  const roundIdContainer = document.getElementById("race-control-buttons");
  const roundId = roundIdContainer?.dataset.roundId;
  const csrfToken = getCookie("csrftoken");

  console.log(
    `Button clicked. Action: ${action}, URL: ${url}, RoundID: ${roundId}`,
  );
  if (!action || !url || !roundId || !csrfToken) {
    /* ... validation ... */ return;
  }

  // --- Disable ALL action buttons during processing ---
  const allActionButtons = document.querySelectorAll(
    "#race-control-buttons .race-action-btn",
  );
  allActionButtons.forEach((btn) => (btn.disabled = true));
  const originalButtonHTML = button.innerHTML;
  button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;
  console.log(`Sending POST request to: ${url}`);

  // --- Clear relevant timeouts when an action is initiated ---
  if (action !== "false_start") clearTimeout(falseStartTimeoutId);
  if (action !== "false_restart") clearTimeout(falseRestartTimeoutId);

  try {
    const response = await fetch(url, {
      /* ... fetch options ... */
    });
    console.log(`Received response for ${action}. Status: ${response.status}`);

    if (response.ok) {
      let data;
      try {
        data = await response.json();
        console.log(`Action '${action}' response data:`, data);
      } catch (e) {
        addSystemMessage("Invalid response.", "warning");
        return;
      }

      const isLogicalError =
        data.result === false ||
        (data.error && Array.isArray(data.error) && data.error.length > 0) ||
        data.status === "error";

      if (isLogicalError) {
        // --- Handle Logical Failure ---
        console.warn(`Action '${action}' failed logically.`);
        if (data.error && Array.isArray(data.error) && data.error.length > 0) {
          data.error.forEach((errorMsg) => {
            addSystemMessage(errorMsg, "warning");
          });
        } else {
          addSystemMessage(
            data.message || `Action '${action}' failed.`,
            "warning",
          );
        }
        // Restore clicked button text and re-enable it
        button.innerHTML = originalButtonHTML;
        button.disabled = false;
        
        // Don't re-enable all buttons on error - let the current state determine visibility
        // The WebSocket or page state should handle proper button visibility
      } else {
        // --- Handle Logical Success ---
        console.log(`Action '${action}' successful logically.`);
        addSystemMessage(
          data.message || `Action '${action}' successful.`,
          "success",
        );

        // --- Determine NEXT state and update button visibility ---
        let nextState = "unknown";
        let options = {}; // Options for updateButtonVisibility

        switch (action) {
          case "pre_check":
            nextState = "ready";
            break;
          case "start":
            nextState = "running";
            options = { showFalseStart: true };
            break;
          case "pause":
            nextState = "paused";
            break;
          case "resume":
            nextState = "running";
            options = { showFalseRestart: true };
            break; // Resume goes back to running
          case "end":
            nextState = "ended";
            break;
          case "false_start":
            nextState = "ready";
            break; // False start goes back to ready
          case "false_restart":
            nextState = "paused";
            break; // False restart goes back to paused
        }

        updateButtonVisibility(nextState, options); // Update UI based on FSM

        // Connect lanes only after successful pre-check
        if (action === "pre_check") {
          if (typeof connectToLaneSockets === "function")
            connectToLaneSockets();
          else console.error("connectToLaneSockets missing!");
        }
      }
    } else {
      // Handle HTTP errors
      let errorMsg = `Error: ${response.status}`;
      /* ... get details ... */ addSystemMessage(errorMsg, "danger");
      button.innerHTML = originalButtonHTML; // Restore button text
      button.disabled = false; // Re-enable only the clicked button on HTTP error
    }
  } catch (error) {
    // Handle network errors
    console.error(`Network error:`, error);
    addSystemMessage(`Network error: ${error}.`, "danger");
    button.innerHTML = originalButtonHTML; // Restore button text
    button.disabled = false; // Re-enable only the clicked button on network error
  }
  // No finally block needed as enablement is handled in error/success paths now
}

/**
 * Function to update the empty teams list UI (Keep as is)
 */
function updateEmptyTeamsList(teams) {
  // ... (implementation from previous version) ...
  const emptyTeamsUL = document.getElementById("emptyTeamsUL");
  const placeholder = document.getElementById("emptyTeamsPlaceholder");
  const emptyTeamsSocket = window.emptyTeamsSocket;
  if (!emptyTeamsUL || !placeholder) return;
  // Clear current list
  emptyTeamsUL.innerHTML = "";

  if (teams.length === 0) {
    placeholder.textContent = "No empty teams found";
    placeholder.style.display = "block";
    emptyTeamsUL.style.display = "none";
  } else {
    placeholder.style.display = "none";
    emptyTeamsUL.style.display = "block";

    // Add each team to the list
    teams.forEach(function (team) {
      const li = document.createElement("li");
      li.className =
        "list-group-item d-flex justify-content-between align-items-center";

      // Format: Team name (Number) - Championship name
      li.innerHTML = `
            <span>${team.team_name} (#${team.number}) - ${team.championship_name}</span>
            <button class="btn btn-sm btn-outline-danger delete-single-team"
            data-team-id="${team.id}">Delete</button>
            `;

      emptyTeamsUL.appendChild(li);
    });

    // Add event listeners for individual team deletion
    document.querySelectorAll(".delete-single-team").forEach((button) => {
      button.addEventListener("click", function () {
        const teamId = this.getAttribute("data-team-id");
        if (confirm("Delete this team?")) {
          const emptyTeamsSocket = new WebSocket(
            "ws://" + window.location.host + "/ws/empty_teams/",
          );

          emptyTeamsSocket.onopen = function () {
            emptyTeamsSocket.send(
              JSON.stringify({
                action: "delete_single_team",
                team_id: teamId,
              }),
            );
          };
        }
      });
    });
  }
}

// --- Event Listeners Setup ---
console.log('JavaScript file loaded, setting up DOMContentLoaded listener...');

// Separate function to load HMAC secret
function loadHmacSecret() {
  console.log('Loading HMAC secret from template data...');
  const roundData = document.getElementById('round-data');
  console.log('Round data element:', roundData);
  if (roundData) {
    console.log('Round data attributes:', roundData.dataset);
    console.log('Available dataset keys:', Object.keys(roundData.dataset));
    
    // Try different attribute access methods
    hmacSecret = roundData.dataset.hmacSecret || roundData.getAttribute('data-hmac-secret');
    console.log('HMAC secret loaded:', hmacSecret ? 'YES' : 'NO');
    console.log('Secret value:', hmacSecret);
    console.log('Secret length:', hmacSecret ? hmacSecret.length : 'N/A');
  } else {
    console.error('round-data element not found!');
    
    // Try fallback from window
    if (window.STOPANDGO_HMAC_SECRET) {
      hmacSecret = window.STOPANDGO_HMAC_SECRET;
      console.log('Using fallback HMAC secret from window:', hmacSecret ? 'YES' : 'NO');
    }
  }
}

// Try to load secret immediately if DOM is already ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadHmacSecret);
} else {
  // DOM is already ready
  loadHmacSecret();
}

document.addEventListener("DOMContentLoaded", () => {
  console.log('DOMContentLoaded event fired!');
  
  // Ensure HMAC secret is loaded
  if (!hmacSecret) {
    console.log('HMAC secret not loaded yet, trying again...');
    loadHmacSecret();
  }
  // Add listeners to all race action buttons
  const actionButtons = document.querySelectorAll(".race-action-btn");
  actionButtons.forEach((button) => {
    button.addEventListener("click", handleRaceAction);
  });

  // Initialize Stop & Go functionality with multiple attempts
  function tryInitializeStopAndGo(attempt) {
    attempt = attempt || 1;
    console.log(`Attempt ${attempt} to initialize Stop & Go...`);
    
    const offenderSelect = document.getElementById('offenderSelect');
    const victimSelect = document.getElementById('victimSelect');
    const reasonSelect = document.getElementById('reasonSelect');
    
    if (offenderSelect && victimSelect && reasonSelect) {
      console.log('All Stop & Go elements found, initializing...');
      initializeStopAndGo();
      initializeDropdownLogic();
      return true;
    } else {
      console.log('Stop & Go elements not found:', {
        offender: !!offenderSelect,
        victim: !!victimSelect,
        reason: !!reasonSelect
      });
      
      if (attempt < 5) {
        setTimeout(() => tryInitializeStopAndGo(attempt + 1), 1000);
      } else {
        console.log('Failed to initialize Stop & Go after 5 attempts');
      }
      return false;
    }
  }
  
  tryInitializeStopAndGo();

  // --- Set Initial Button State ---
  // Determine initial state based on which buttons are initially visible in the HTML
  let initialState = "initial"; // Default
  if (document.getElementById("startButton")?.offsetParent !== null)
    initialState = "ready"; // Check visibility more reliably
  else if (document.getElementById("pauseButton")?.offsetParent !== null)
    initialState = "running";
  else if (document.getElementById("resumeButton")?.offsetParent !== null)
    initialState = "paused";
  else if (
    !document.querySelector(
      "#race-control-buttons .race-action-btn:not([hidden])",
    )
  )
    initialState = "ended"; // If no buttons visible

  updateButtonVisibility(initialState); // Set initial visibility

  // --- Initial Lane Connection Check ---
  // Connect if initial state is ready, running, or paused
  if (["ready", "running", "paused"].includes(initialState)) {
    console.log(
      `Page loaded: Round state is ${initialState}. Connecting lane sockets.`,
    );
    setTimeout(connectToLaneSockets, 200);
  } else {
    console.log(
      "Page loaded: Round not ready/started/paused. Skipping initial lane connection.",
    );
    window.lanesConnected = false;
  }
});

/**
 * Initialize Stop & Go functionality
 */
function initializeStopAndGo() {
  const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const stopAndGoSocketUrl = `${wsScheme}://${window.location.host}/ws/stopandgo/`;
  
  // Create Stop & Go WebSocket connection
  stopAndGoSocket = createWebSocketWithReconnect(
    stopAndGoSocketUrl,
    function(e) {
      try {
        const data = JSON.parse(e.data);
        handleStopAndGoMessage(data);
      } catch (err) {
        console.error('Error processing Stop & Go WS message:', err, e.data);
      }
    },
    function(e) {
      console.log('Stop & Go WS connected');
      // Query fence status on connection
      queryFenceStatus();
    },
    function(e) {
      addSystemMessage('Stop & Go station connection error.', 'danger');
    },
    function(e) {
      addSystemMessage('Stop & Go station disconnected.', e.wasClean ? 'info' : 'warning');
    }
  );
  
  // Add event listeners for buttons
  const stopGoButton = document.getElementById('stopGoButton');
  const toggleFenceButton = document.getElementById('toggleFenceButton');
  
  if (stopGoButton) {
    stopGoButton.addEventListener('click', handleStopGoButtonClick);
  }
  
  if (toggleFenceButton) {
    toggleFenceButton.addEventListener('click', handleToggleFenceClick);
  }
}

/**
 * Initialize dropdown interaction logic
 */
function initializeDropdownLogic() {
  console.log('Initializing dropdown logic...');
  const offenderSelect = document.getElementById('offenderSelect');
  const victimSelect = document.getElementById('victimSelect');
  const reasonSelect = document.getElementById('reasonSelect');
  const stopGoButton = document.getElementById('stopGoButton');
  
  console.log('Elements found:', {
    offenderSelect: !!offenderSelect,
    victimSelect: !!victimSelect,
    reasonSelect: !!reasonSelect,
    stopGoButton: !!stopGoButton
  });
  
  if (!offenderSelect || !victimSelect || !reasonSelect || !stopGoButton) {
    console.log('Some elements not found, skipping dropdown initialization');
    return; // Elements not found
  }
  
  console.log('All elements found, setting up event listeners...');
  
  // Test that the offender select exists and can be interacted with
  console.log('Offender select element:', offenderSelect);
  console.log('Offender select disabled state:', offenderSelect.disabled);
  
  // When offender is selected, populate victim dropdown and enable reason
  offenderSelect.addEventListener('change', function() {
    console.log('Change event fired on offender select!');
    const selectedOffenderId = this.value;
    console.log('Offender selected:', selectedOffenderId);
    console.log('Victim select before change:', victimSelect.disabled);
    console.log('Reason select before change:', reasonSelect.disabled);
    
    if (selectedOffenderId) {
      // Enable victim and reason dropdowns
      victimSelect.disabled = false;
      reasonSelect.disabled = false;
      console.log('Enabled victim and reason dropdowns');
      console.log('Victim select after enable:', victimSelect.disabled);
      console.log('Reason select after enable:', reasonSelect.disabled);
      
      // Populate victim dropdown (all teams except the offender)
      populateVictimDropdown(selectedOffenderId);
    } else {
      // Disable victim and reason dropdowns
      victimSelect.disabled = true;
      reasonSelect.disabled = true;
      victimSelect.value = '';
      reasonSelect.value = '';
      
      // Clear victim options
      victimSelect.innerHTML = '<option value="">Select victim team...</option>';
      console.log('Disabled victim and reason dropdowns');
    }
    
    checkFormCompletion();
  });
  
  // When victim or reason changes, check form completion
  victimSelect.addEventListener('change', checkFormCompletion);
  reasonSelect.addEventListener('change', checkFormCompletion);
  
  function populateVictimDropdown(excludeOffenderId) {
    const offenderOptions = offenderSelect.querySelectorAll('option[value]:not([value=""])');
    victimSelect.innerHTML = '<option value="">Select victim team...</option>';
    
    offenderOptions.forEach(option => {
      if (option.value !== excludeOffenderId) {
        const newOption = option.cloneNode(true);
        victimSelect.appendChild(newOption);
      }
    });
  }
  
  function checkFormCompletion() {
    const offenderSelected = offenderSelect.value !== '';
    const victimSelected = victimSelect.value !== '';
    const reasonSelected = reasonSelect.value !== '';
    
    if (offenderSelected && victimSelected && reasonSelected && stopAndGoState === 'idle') {
      stopGoButton.disabled = false;
      stopGoButton.style.backgroundColor = '#dc3545';
      stopGoButton.style.color = 'yellow';
      stopGoButton.textContent = 'Stop & Go';
    } else {
      stopGoButton.disabled = true;
      if (stopAndGoState === 'idle') {
        stopGoButton.style.backgroundColor = '#6c757d';
        stopGoButton.style.color = '#fff';
        stopGoButton.textContent = 'Stop & Go';
      }
    }
  }
}

/**
 * Handle Stop & Go button click
 */
function handleStopGoButtonClick() {
  const offenderSelect = document.getElementById('offenderSelect');
  const durationInput = document.getElementById('durationInput');
  const stopGoButton = document.getElementById('stopGoButton');
  
  if (stopAndGoState === 'idle') {
    // Send stop & go command
    const offenderTeamNumber = offenderSelect.selectedOptions[0]?.dataset.teamNumber;
    const duration = parseInt(durationInput.value) || 20;
    
    if (offenderTeamNumber && stopAndGoSocket) {
      // Send signed command to stop and go station
      const message = {
        type: 'send_race_command',
        team: parseInt(offenderTeamNumber),
        duration: duration,
        timestamp: new Date().toISOString()
      };
      
      signMessage(message).then(signedMessage => {
        stopAndGoSocket.send(JSON.stringify(signedMessage));
        
        // Update button to "Served" state
        stopAndGoState = 'active';
        stopGoButton.style.backgroundColor = '#fd7e14';
        stopGoButton.style.color = 'black';
        stopGoButton.textContent = 'Served';
        stopGoButton.disabled = false;
        
        addSystemMessage(`Stop & Go penalty sent to team ${offenderTeamNumber} for ${duration} seconds`, 'info');
      }).catch(error => {
        console.error('Failed to sign message:', error);
        addSystemMessage('Failed to send Stop & Go penalty', 'danger');
      });
    }
  } else if (stopAndGoState === 'active') {
    // Force complete penalty
    if (stopAndGoSocket) {
      const message = {
        type: 'force_complete_penalty',
        timestamp: new Date().toISOString()
      };
      
      signMessage(message).then(signedMessage => {
        stopAndGoSocket.send(JSON.stringify(signedMessage));
        addSystemMessage('Force completing penalty...', 'info');
      }).catch(error => {
        console.error('Failed to sign message:', error);
        addSystemMessage('Failed to force complete penalty', 'danger');
      });
    }
  }
}

/**
 * Handle Toggle Fence button click
 */
function handleToggleFenceClick() {
  if (stopAndGoSocket && fenceEnabled !== null) {
    const newState = !fenceEnabled;
    
    const message = {
      type: 'set_fence',
      enabled: newState,
      timestamp: new Date().toISOString()
    };
    
    signMessage(message).then(signedMessage => {
      stopAndGoSocket.send(JSON.stringify(signedMessage));
      addSystemMessage(`${newState ? 'Enabling' : 'Disabling'} fence...`, 'info');
    }).catch(error => {
      console.error('Failed to sign message:', error);
      addSystemMessage('Failed to toggle fence', 'danger');
    });
  }
}

/**
 * Query fence status from stop and go station
 */
function queryFenceStatus() {
  if (stopAndGoSocket) {
    const message = {
      type: 'get_fence_status',
      timestamp: new Date().toISOString()
    };
    
    signMessage(message).then(signedMessage => {
      stopAndGoSocket.send(JSON.stringify(signedMessage));
    }).catch(error => {
      console.error('Failed to sign message:', error);
      addSystemMessage('Failed to query fence status', 'danger');
    });
  }
}

/**
 * Handle incoming Stop & Go WebSocket messages
 */
function handleStopAndGoMessage(data) {
  console.log('Stop & Go message received:', data);
  
  switch (data.type) {
    case 'penalty_served':
      // Penalty has been served, reset form
      resetStopAndGoForm();
      addSystemMessage(`Penalty served by team ${data.team}`, 'success');
      
      // Send acknowledgment back to station
      if (stopAndGoSocket) {
        const ackMessage = {
          type: 'penalty_acknowledged',
          team: data.team,
          timestamp: new Date().toISOString()
        };
        
        signMessage(ackMessage).then(signedMessage => {
          stopAndGoSocket.send(JSON.stringify(signedMessage));
          console.log('Sent penalty acknowledgment for team', data.team);
        }).catch(error => {
          console.error('Failed to sign acknowledgment:', error);
        });
      }
      break;
      
    case 'fence_status':
      // Update fence button based on status
      fenceEnabled = data.enabled;
      updateFenceButton();
      break;
      
    case 'penalty_completed':
      // Penalty force completed
      resetStopAndGoForm();
      addSystemMessage(`Penalty completed for team ${data.team}`, 'success');
      break;
  }
}

/**
 * Reset Stop & Go form to initial state
 */
function resetStopAndGoForm() {
  const offenderSelect = document.getElementById('offenderSelect');
  const victimSelect = document.getElementById('victimSelect');
  const reasonSelect = document.getElementById('reasonSelect');
  const durationInput = document.getElementById('durationInput');
  const stopGoButton = document.getElementById('stopGoButton');
  
  // Reset dropdowns
  offenderSelect.value = '';
  victimSelect.value = '';
  reasonSelect.value = '';
  
  // Disable victim and reason
  victimSelect.disabled = true;
  reasonSelect.disabled = true;
  
  // Clear victim options
  victimSelect.innerHTML = '<option value="">Select victim team...</option>';
  
  // Reset duration
  durationInput.value = '20';
  
  // Reset button to idle state
  stopAndGoState = 'idle';
  stopGoButton.disabled = true;
  stopGoButton.style.backgroundColor = '#6c757d';
  stopGoButton.style.color = '#fff';
  stopGoButton.textContent = 'Stop & Go';
}

/**
 * Update fence button appearance based on fence status
 */
function updateFenceButton() {
  const toggleFenceButton = document.getElementById('toggleFenceButton');
  
  if (toggleFenceButton && fenceEnabled !== null) {
    if (fenceEnabled) {
      toggleFenceButton.style.backgroundColor = '#28a745';
      toggleFenceButton.style.color = 'black';
      toggleFenceButton.textContent = 'Toggle Fence';
    } else {
      toggleFenceButton.style.backgroundColor = '#fd7e14';
      toggleFenceButton.style.color = 'black';
      toggleFenceButton.textContent = 'Toggle Fence';
    }
  }
}
