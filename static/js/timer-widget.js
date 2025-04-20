// timer-widget.js
class TimerWidget {
    constructor(options) {
        this.element = document.getElementById(options.elementId);
        this.startValue = options.startValue || 0; // In seconds
        this.countDirection = options.countDirection || 'up'; // 'up' or 'down'
        this.paused = options.initialPaused || false;
        this.roundId = options.roundId;
        this.driverId = options.driverId; // Store driver ID for session updates
        this.precision = options.precision || 0; // Decimal places
        this.currentValue = this.startValue;
        this.lastUpdateTime = null;
        this.timerType = options.timerType || 'default'; // 'totaltime', 'sessiontime', 'countdownDisplay'

        // Format options
        this.showHours = options.showHours !== undefined ? options.showHours : true;
        this.showMinutes = options.showMinutes !== undefined ? options.showMinutes : true;
        this.showSeconds = true;

        // Setup WebSocket if roundId is provided
        if (this.roundId) {
            this.setupWebSocket();
        }

        // Initial render
        this.render();

        // Start timer if not paused
        if (!this.paused) {
            this.start();
        }
    }

    setupWebSocket() {
        const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsPath = `${wsScheme}://${window.location.host}/ws/round/${this.roundId}/`;

        this.socket = new WebSocket(wsPath);

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'round_update') {
                // Handle pause/resume
                if (data.is_paused) {
                    this.pause();
                } else {
                    this.resume();
                }

                // If we're a countdown timer, sync with server time
                if (this.countDirection === 'down' && data.remaining_seconds !== undefined) {
                    this.currentValue = data.remaining_seconds;
                    this.render();
                }

                // Handle session updates
                if (data.session_update && this.driverId) {
                    // If this message is about our driver
                    if (data.driver_id == this.driverId) {
                        if (this.timerType === 'sessiontime') {
                            // For session timers, reset when a driver starts a new session
                            if (data.driver_active) {
                                this.reset(0);
                                this.paused = false;
                                this.start();
                            } else {
                                this.pause();
                            }
                        } else if (this.timerType === 'totaltime') {
                            // For total time timers, update pause state based on driver activity
                            this.paused = !data.driver_active || data.is_paused;
                            if (!this.paused) {
                                this.start();
                            }
                        }
                    }
                }
            }
        };

        this.socket.onclose = () => {
            console.warn('Timer WebSocket connection closed');
            // Try to reconnect after 5 seconds
            setTimeout(() => this.setupWebSocket(), 5000);
        };
    }

    start() {
        this.paused = false;
        this.lastUpdateTime = Date.now();
        this.tick();
    }

    pause() {
        this.paused = true;
    }

    resume() {
        if (this.paused) {
            this.paused = false;
            this.lastUpdateTime = Date.now();
            this.tick();
        }
    }

    reset(newStartValue) {
        this.currentValue = newStartValue !== undefined ? newStartValue : this.startValue;
        this.render();
    }

    tick() {
        if (this.paused) return;

        const now = Date.now();
        const delta = (now - this.lastUpdateTime) / 1000;
        this.lastUpdateTime = now;

        if (this.countDirection === 'up') {
            this.currentValue += delta;
        } else {
            this.currentValue -= delta;
            // Don't go below zero for countdown timers
            if (this.currentValue < 0) {
                this.currentValue = 0;
                this.pause();
            }
        }

        this.render();
        requestAnimationFrame(() => this.tick());
    }

    formatTime(totalSeconds) {
        const totalSecondsAbs = Math.abs(totalSeconds);
        const hours = Math.floor(totalSecondsAbs / 3600);
        const minutes = Math.floor((totalSecondsAbs % 3600) / 60);
        const seconds = totalSecondsAbs % 60;

        let formattedTime = '';

        if (this.showHours) {
            formattedTime += String(hours).padStart(2, '0') + ':';
        }

        if (this.showMinutes) {
            formattedTime += String(minutes).padStart(2, '0') + ':';
        }

        if (this.precision > 0) {
            formattedTime += seconds.toFixed(this.precision).padStart(3 + this.precision, '0');
        } else {
            formattedTime += String(Math.floor(seconds)).padStart(2, '0');
        }

        return totalSeconds < 0 ? '-' + formattedTime : formattedTime;
    }

    render() {
        if (this.element) {
            this.element.textContent = this.formatTime(this.currentValue);

            // Add classes for styling
            if (this.currentValue <= 0 && this.countDirection === 'down') {
                this.element.classList.add('timer-ended');
            } else {
                this.element.classList.remove('timer-ended');
            }

            if (this.paused) {
                this.element.classList.add('timer-paused');
            } else {
                this.element.classList.remove('timer-paused');
            }
        }
    }
}

// This function creates all timer widgets on a page and registers them with their driver IDs
function initializeTimers() {
    // Find all timer placeholders
    const timerPlaceholders = document.querySelectorAll('[data-timer]');

    timerPlaceholders.forEach(placeholder => {
        const config = JSON.parse(placeholder.getAttribute('data-config'));

        // Create the timer
        new TimerWidget({
            elementId: placeholder.id,
            startValue: config.startValue || 0,
            countDirection: config.countDirection || 'up',
            initialPaused: config.initialPaused || false,
            roundId: config.roundId,
            driverId: config.driverId,
            timerType: config.timerType,
            showHours: config.showHours,
            showMinutes: config.showMinutes
        });
    });
}

// Initialize all timers when the DOM is ready
document.addEventListener('DOMContentLoaded', initializeTimers);

// Listen for custom event to refresh a specific team's timers
document.addEventListener('refreshTeamTimers', function(e) {
    if (e.detail && e.detail.teamId) {
        const teamContainer = document.querySelector(`#team-slide-${e.detail.teamId}`);
        if (teamContainer) {
            // Find all timer placeholders in this team's container
            const timerPlaceholders = teamContainer.querySelectorAll('[data-timer]');

            timerPlaceholders.forEach(placeholder => {
                const config = JSON.parse(placeholder.getAttribute('data-config'));

                // Create the timer
                new TimerWidget({
                    elementId: placeholder.id,
                    startValue: config.startValue || 0,
                    countDirection: config.countDirection || 'up',
                    initialPaused: config.initialPaused || false,
                    roundId: config.roundId,
                    driverId: config.driverId,
                    timerType: config.timerType,
                    showHours: config.showHours,
                    showMinutes: config.showMinutes
                });
            });
        }
    }
});
