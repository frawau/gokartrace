// timer-widget.js

class TimerWidget {
    constructor(options) {
        this.element = document.getElementById(options.elementId);
        if (!this.element) {
            console.error(`TimerWidget Error: Element with ID "${options.elementId}" not found.`);
            this.element = document.createElement('span'); // Dummy element
            this.paused = true;
        }
        this.startValue = options.startValue || 0;
        this.countDirection = options.countDirection || 'up';
        // initialPaused from config reflects the state *at page load*
        this.initialPaused = options.initialPaused || false;
        this.paused = this.initialPaused; // Set current pause state initially
        this.roundId = options.roundId;
        this.driverId = options.driverId;
        this.precision = options.precision || 0;
        this.currentValue = this.startValue;
        this.lastUpdateTime = null;
        this.timerType = options.timerType || 'default';
        this.animationFrameId = null;

        // Track the driver's active state internally for logic
        // Initialize based on initialPaused if it's a driver timer
        this.isDriverActive = (this.driverId && !this.initialPaused);

        this.showHours = options.showHours !== undefined ? options.showHours : true;
        this.showMinutes = options.showMinutes !== undefined ? options.showMinutes : true;
        this.showSeconds = true;

        this.render();
        timerRegistry.registerTimer(this);

        // Start timer only if it shouldn't be paused initially
        if (!this.paused && this.element.id) {
            this.start();
        }
    }

    // --- start, pause, resume, reset, tick, formatTime, render ---
    // (Keep these methods as in the previous version, ensuring 'pause'
    // cancels the animation frame and 'resume'/'start' request it)

    start() {
        if (!this.element || !this.element.id) return;
        // This method implies the timer *should* run if called.
        // We manage the *decision* to call start/pause elsewhere.
        this.paused = false;
        this.lastUpdateTime = Date.now();
        if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
        this.tick();
        this.render();
    }

    pause() {
        if (!this.element || !this.element.id) return;
        // This method implies the timer *should* pause if called.
        if (!this.paused) { // Only log/cancel if actually changing state
            this.paused = true;
            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
                this.animationFrameId = null;
            }
            this.render();
        }
    }

    resume() {
        // This method implies the timer *should* resume if called.
        if (this.paused && this.element && this.element.id) {
            this.paused = false;
            this.lastUpdateTime = Date.now();
            if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
            this.tick();
            this.render();
        }
    }

    reset(newStartValue) {
        if (!this.element || !this.element.id) return;
        this.currentValue = newStartValue !== undefined ? newStartValue : this.startValue;
        if(!this.paused) {
            this.lastUpdateTime = Date.now();
        }
        this.render();
    }

    tick() {
        if (this.paused || !this.element || !document.getElementById(this.element.id)) {
            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
                this.animationFrameId = null;
            }
            return;
        }

        const now = Date.now();
        if (this.lastUpdateTime === null) this.lastUpdateTime = now;
        const delta = (now - this.lastUpdateTime) / 1000;
        this.lastUpdateTime = now;

        if (this.countDirection === 'up') {
            this.currentValue += delta;
        } else {
            this.currentValue -= delta;
            if (this.currentValue <= 0) {
                this.currentValue = 0;
                this.pause();
            }
        }

        this.render();
        this.animationFrameId = requestAnimationFrame(() => this.tick());
    }

    formatTime(totalSeconds) {
        const totalSecondsRounded = Math.round(totalSeconds);
        const totalSecondsAbs = Math.abs(totalSecondsRounded);
        const hours = Math.floor(totalSecondsAbs / 3600);
        const minutes = Math.floor((totalSecondsAbs % 3600) / 60);
        const seconds = totalSecondsAbs % 60;
        let parts = [];
        if (this.showHours) parts.push(String(hours).padStart(2, '0'));
        if (this.showMinutes) parts.push(String(minutes).padStart(2, '0'));
        if (this.showSeconds || parts.length === 0) parts.push(String(seconds).padStart(2, '0'));
        let formattedTime = parts.join(':');
        return totalSecondsRounded < 0 ? '-' + formattedTime : formattedTime;
    }

    render() {
        if (this.element && document.getElementById(this.element.id)) {
            this.element.textContent = this.formatTime(this.currentValue);
            this.element.classList.toggle('timer-ended', this.currentValue <= 0 && this.countDirection === 'down');
            this.element.classList.toggle('timer-paused', this.paused);
            // Add visibility control for session timer based on driver active state
            if (this.timerType === 'sessiontime') {
                this.element.style.visibility = this.isDriverActive ? 'visible' : 'hidden';
            }

        } else if (this.element && !document.getElementById(this.element.id)) {
            console.warn(`Timer element ${this.element.id} removed. Stopping.`);
            this.pause();
        }
    }

    // --- Logic Methods ---

    /**
     * Updates the timer's state based on the overall race pause status.
     * @param {boolean} isRacePaused - True if the race is paused, false otherwise.
     */
    updatePauseState(isRacePaused) {
        if (!this.element || !this.element.id) return;
        console.log(`Timer ${this.element.id} (Type: ${this.timerType}): updatePauseState called with isRacePaused=${isRacePaused}. Driver active state: ${this.isDriverActive}`);

        if (isRacePaused) {
            // If race pauses, *all* timers pause.
            this.pause();
        } else {
            // If race resumes, timer should run *only if* it's supposed to be active.
            // Countdown timers always resume (if value > 0).
            // Driver timers resume only if their driver is active.
            const shouldBeRunning =
            this.timerType === 'countdownDisplay' ? (this.currentValue > 0) : // Countdown runs if > 0
            (this.driverId ? this.isDriverActive : true); // Driver timers run if active, others always run

            if (shouldBeRunning) {
                this.resume();
            } else {
                // Ensure it remains paused if it shouldn't be running
                this.pause();
            }
        }
        this.render(); // Update visual state
    }

    /**
     * Updates the timer's state based on the specific driver's active status.
     * This primarily affects session timer reset and visibility, and whether
     * driver-specific timers (session/total) should run *if* the race is active.
     * @param {boolean} isActive - True if the driver is now active, false otherwise.
     */
    handleSessionUpdate(isActive) {
        if (!this.element || !this.element.id || !this.driverId) return; // Only for driver timers
        console.log(`Timer ${this.element.id} (Type: ${this.timerType}): handleSessionUpdate called with isActive=${isActive}.`);

        // Update internal driver active state
        this.isDriverActive = isActive;

        // --- Session Timer Specific Logic ---
        if (this.timerType === 'sessiontime') {
            if (isActive) {
                // Reset session timer to 0 when driver becomes active
                console.log(`Timer ${this.element.id}: Session timer activating. Resetting to 0.`);
                this.reset(0);
                // Visibility is handled in render() based on this.isDriverActive
            } else {
                // If driver becomes inactive, pause the session timer.
                console.log(`Timer ${this.element.id}: Session timer deactivating. Pausing.`);
                this.pause();
                // Optionally reset to 0 when inactive, but pausing is usually sufficient
                // this.reset(0);
            }
        }

        // --- Determine if timer should run based on new state ---
        // Check the global race pause state (needs access, e.g., via registry)
        let isRacePaused = timerRegistry.countdownTimers.length > 0 ? timerRegistry.countdownTimers[0].paused : true; // Example check

        const shouldBeRunning = this.isDriverActive && !isRacePaused;

        if (shouldBeRunning) {
            // If driver is active AND race is not paused, resume timer
            console.log(`Timer ${this.element.id}: Driver active and race active. Resuming.`);
            this.resume();
        } else {
            // Otherwise, pause the timer
            console.log(`Timer ${this.element.id}: Pausing (Driver active: ${this.isDriverActive}, Race paused: ${isRacePaused}).`);
            this.pause();
        }

        this.render(); // Update visual state (including session timer visibility)
    }

    updateRemainingTime(seconds) {
        if (!this.element || !this.element.id) return;
        if (this.countDirection === 'down') {
            const newTime = parseFloat(seconds);
            if (!isNaN(newTime)) {
                this.currentValue = newTime;
                // If time hits 0, pause should be handled in tick()
                this.render();
            } else {
                console.warn(`Timer ${this.element.id}: Invalid remaining time: ${seconds}`);
            }
        }
    }

    destroy() {
        this.pause();
        timerRegistry.deregisterTimer(this);
        this.element = null;
    }
}

// Ensure the timerRegistry and initializeTimers function are also present
// (Copied from previous response for completeness, assuming no changes needed there)

const timerRegistry = {
    byDriverId: {},
    byRoundId: {},
    countdownTimers: [],
    byId: {},

    registerTimer: function(timer) {
        this.byId[timer.element.id] = timer;
        if (timer.driverId) {
            if (!this.byDriverId[timer.driverId]) this.byDriverId[timer.driverId] = [];
            if (!this.byDriverId[timer.driverId].includes(timer)) this.byDriverId[timer.driverId].push(timer);
        }
        if (timer.roundId) {
            if (!this.byRoundId[timer.roundId]) this.byRoundId[timer.roundId] = [];
            if (!this.byRoundId[timer.roundId].includes(timer)) this.byRoundId[timer.roundId].push(timer);
        }
        if (timer.countDirection === 'down') {
            if (!this.countdownTimers.includes(timer)) this.countdownTimers.push(timer);
        }
    },

    deregisterTimer: function(timer) {
        delete this.byId[timer.element.id];
        if (timer.driverId && this.byDriverId[timer.driverId]) {
            this.byDriverId[timer.driverId] = this.byDriverId[timer.driverId].filter(t => t !== timer);
        }
        if (timer.roundId && this.byRoundId[timer.roundId]) {
            this.byRoundId[timer.roundId] = this.byRoundId[timer.roundId].filter(t => t !== timer);
        }
        this.countdownTimers = this.countdownTimers.filter(t => t !== timer);
    }
};

function initializeTimers() {
    const timerPlaceholders = document.querySelectorAll('[data-timer]');
    timerPlaceholders.forEach(placeholder => {
        if (timerRegistry.byId[placeholder.id]) {
            // console.log(`Timer already initialized for ${placeholder.id}, skipping.`);
            return;
        }
        try {
            const config = JSON.parse(placeholder.getAttribute('data-config'));
            if (!config || typeof config.startValue === 'undefined' || !config.timerType) {
                console.error(`Invalid config for timer ${placeholder.id}:`, placeholder.getAttribute('data-config'));
                return;
            }
            new TimerWidget(config); // Pass config directly
        } catch (e) {
            console.error(`Error parsing/init timer for ${placeholder.id}:`, e, placeholder.getAttribute('data-config'));
        }
    });
}

document.addEventListener('DOMContentLoaded', initializeTimers);
