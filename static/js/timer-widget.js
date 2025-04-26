// timer-widget.js
// Global Timer Registry to manage all timers
const timerRegistry = {
    allTimers: [],
    countdownTimers: [],
    byDriverId: {},

    registerTimer: function(timer) {
        this.allTimers.push(timer);

        // Register by type
        if (timer.countDirection === 'down') {
            this.countdownTimers.push(timer);
        }

        // Register by driver ID
        if (timer.targetId) {
            if (!this.byDriverId[timer.targetId]) {
                this.byDriverId[timer.targetId] = [];
            }
            this.byDriverId[timer.targetId].push(timer);
        }
    }
};

class TimerWidget {
    constructor(options) {
        this.element = document.getElementById(options.elementId);
        this.startValue = options.startValue || 0; // In seconds
        this.countDirection = options.countDirection || 'up'; // 'up' or 'down'
        this.paused = options.initialPaused || false;
        this.targetId = options.targetId; // Store driver ID for session updates
        this.precision = options.precision || 0; // Decimal places
        this.currentValue = this.startValue;
        this.lastUpdateTime = null;
        this.timerType = options.timerType || 'countdownDisplay'; // 'totaltime', 'sessiontime', 'countdownDisplay'
        if ( this.timerType == 'countdownDisplay' ) {
            this.isactive = true;
        } else {
            if ( this.paused ) {
                this.isactive = false;
            } else {
                this.isactive=true;
            }
        }

        // Format options
        this.showHours = options.showHours !== undefined ? options.showHours : true;
        this.showMinutes = options.showMinutes !== undefined ? options.showMinutes : true;
        this.showSeconds = true;
        // Frozen state

        // Initial render
        this.render();

        // Start timer if not paused
        if (!this.paused) {
            this.start();
        }

        // Register with the global registry
        timerRegistry.registerTimer(this);
    }

    start() {
        if ( this.isactive ) {
            this.paused = false;
            this.lastUpdateTime = Date.now();
            this.tick();
        }
    }

    pause() {
        this.paused = true;
    }

    resume() {
        if ( this.isactive && this.paused ) {
            this.paused = false;
            this.lastUpdateTime = Date.now();
            this.tick();
        }
    }

    activate() {
        if ( this.targetId ) {
            this.isactive = true;
            if ( ! this.paused ) {
                this.lastUpdateTime = Date.now();
                this.tick();
            }
        }
    }

    deactivate() {
        if ( this.targetId ) {
            this.isactive = false;
            this.paused = true;
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
                if (this.countDirection === 'up') {
                    this.element.classList.add('timer-frozen');
                } else {
                    this.element.classList.add('timer-paused');
                }
            } else {
                if (this.countDirection === 'up') {
                    this.element.classList.remove('timer-frozen');
                } else {
                    this.element.classList.remove('timer-paused');
                }
            }
        }
    }

    updatePauseState(isPaused) {
        if (isPaused) {
            this.pause();
        } else {
            this.resume();
        }
    }

    updateRemainingTime(seconds) {
        if (this.countDirection === 'down') {
            this.currentValue = seconds;
            this.render();
        }
    }

    handleSessionUpdate(status,tspent) {
        if (this.timerType === 'sessiontime') {
            if (status === "start") {
                this.reset(0);
                this.activate();
                this.start();
            } else if (status === "end"){
                this.deactivate();
                if (this.element) {
                    this.element.style.visibility = 'hidden';
                }
            } else if (status === "register"){
                if (this.element) {
                    this.element.style.visibility = 'visible';
                }
            } else { //reset
                this.deactivate();
                this.reset(0)
            }
        } else if (this.timerType === 'totaltime') {
            if (status === "start") {
                this.activate();
                this.reset(tspent);
                this.start();
            } else if (status === "end"){
                this.deactivate();
            } else if (status === "reset"){
                this.deactivate();
                if (this.element) {
                    this.element.style.visibility = 'hidden';
                }
                this.reset(0)
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
            targetId: config.targetId,
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
                    targetId: config.targetId,
                    timerType: config.timerType,
                    showHours: config.showHours,
                    showMinutes: config.showMinutes
                });
            });
        }
    }
});
