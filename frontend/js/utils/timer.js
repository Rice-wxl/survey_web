/**
 * Timer utility for tracking time spent on questions.
 */

class StudyTimer {
    constructor() {
        this.startTime = null;
        this.elapsedSeconds = 0;
        this.intervalId = null;
        this.onTickCallback = null;
        this.events = [];
    }
    
    /**
     * Start the timer.
     */
    start() {
        if (this.intervalId) {
            this.stop();
        }
        
        this.startTime = Date.now();
        this.elapsedSeconds = 0;
        this.events = [];
        
        this.logEvent('timer_start');
        
        this.intervalId = setInterval(() => {
            this.elapsedSeconds = Math.floor((Date.now() - this.startTime) / 1000);
            
            if (this.onTickCallback) {
                this.onTickCallback(this.elapsedSeconds, this.formatTime(this.elapsedSeconds));
            }
        }, 1000);
    }
    
    /**
     * Stop the timer.
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        
        this.logEvent('timer_stop');
        
        return this.getTimingData();
    }
    
    /**
     * Reset the timer.
     */
    reset() {
        this.stop();
        this.startTime = null;
        this.elapsedSeconds = 0;
        this.events = [];
    }
    
    /**
     * Set callback for timer ticks.
     */
    onTick(callback) {
        this.onTickCallback = callback;
    }
    
    /**
     * Log a timed event.
     */
    logEvent(eventType, data = {}) {
        const event = {
            type: eventType,
            timestamp: new Date().toISOString(),
            elapsed_seconds: this.elapsedSeconds,
            ...data
        };
        this.events.push(event);
        return event;
    }
    
    /**
     * Get elapsed time in seconds.
     */
    getElapsedSeconds() {
        return this.elapsedSeconds;
    }
    
    /**
     * Format seconds as MM:SS.
     */
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    /**
     * Get formatted elapsed time.
     */
    getFormattedTime() {
        return this.formatTime(this.elapsedSeconds);
    }
    
    /**
     * Get all timing data for submission.
     */
    getTimingData() {
        return {
            start_time: this.startTime ? new Date(this.startTime).toISOString() : null,
            end_time: new Date().toISOString(),
            total_seconds: this.elapsedSeconds,
            events: this.events
        };
    }
}

// Singleton instance for the study
const studyTimer = new StudyTimer();

// Make timer globally available
window.StudyTimer = StudyTimer;
window.studyTimer = studyTimer;
