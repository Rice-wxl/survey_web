/**
 * Unit tests for the Timer utility module (timer.js).
 *
 * Tests cover:
 * - Timer start/stop/reset functionality
 * - Time formatting
 * - Event logging
 * - Callback handling
 * - Timing data retrieval
 */

// Load the timer module
const fs = require('fs');
const path = require('path');

// Read and evaluate the timer module in our test environment
const timerCode = fs.readFileSync(
    path.join(__dirname, '../../js/utils/timer.js'),
    'utf8'
);
eval(timerCode);

describe('StudyTimer Class', () => {
    let timer;

    // Use fake timers for precise control
    beforeEach(() => {
        jest.useFakeTimers();
        timer = new StudyTimer();
    });

    afterEach(() => {
        timer.stop(); // Clean up any running timers
        jest.useRealTimers();
    });

    describe('Initialization', () => {
        /**
         * Tests that a new timer starts in a clean state.
         */
        test('should initialize with default values', () => {
            expect(timer.startTime).toBeNull();
            expect(timer.elapsedSeconds).toBe(0);
            expect(timer.intervalId).toBeNull();
            expect(timer.events).toEqual([]);
        });

        /**
         * Tests that callback is null by default.
         */
        test('should have no tick callback by default', () => {
            expect(timer.onTickCallback).toBeNull();
        });
    });

    describe('start method', () => {
        /**
         * Tests that start initializes the timer correctly.
         */
        test('should set startTime when started', () => {
            const beforeStart = Date.now();
            timer.start();
            const afterStart = Date.now();

            expect(timer.startTime).toBeGreaterThanOrEqual(beforeStart);
            expect(timer.startTime).toBeLessThanOrEqual(afterStart);
        });

        /**
         * Tests that start resets elapsed seconds to 0.
         */
        test('should reset elapsedSeconds to 0', () => {
            timer.elapsedSeconds = 100; // Simulate previous state
            timer.start();

            expect(timer.elapsedSeconds).toBe(0);
        });

        /**
         * Tests that start logs a timer_start event.
         */
        test('should log timer_start event', () => {
            timer.start();

            expect(timer.events).toHaveLength(1);
            expect(timer.events[0].type).toBe('timer_start');
        });

        /**
         * Tests that start creates an interval.
         */
        test('should create an interval for tracking time', () => {
            timer.start();

            expect(timer.intervalId).not.toBeNull();
        });

        /**
         * Tests that elapsed seconds increment correctly.
         */
        test('should increment elapsedSeconds every second', () => {
            timer.start();

            expect(timer.elapsedSeconds).toBe(0);

            // Advance 3 seconds
            jest.advanceTimersByTime(3000);

            expect(timer.elapsedSeconds).toBe(3);
        });

        /**
         * Tests that starting again stops the previous timer.
         */
        test('should stop previous timer when started again', () => {
            timer.start();
            const firstIntervalId = timer.intervalId;

            timer.start();
            const secondIntervalId = timer.intervalId;

            expect(secondIntervalId).not.toBe(firstIntervalId);
        });
    });

    describe('stop method', () => {
        /**
         * Tests that stop clears the interval.
         */
        test('should clear the interval', () => {
            timer.start();
            expect(timer.intervalId).not.toBeNull();

            timer.stop();
            expect(timer.intervalId).toBeNull();
        });

        /**
         * Tests that stop logs a timer_stop event.
         */
        test('should log timer_stop event', () => {
            timer.start();
            timer.stop();

            const stopEvent = timer.events.find(e => e.type === 'timer_stop');
            expect(stopEvent).toBeDefined();
        });

        /**
         * Tests that stop returns timing data.
         */
        test('should return timing data', () => {
            timer.start();
            jest.advanceTimersByTime(5000);
            const result = timer.stop();

            expect(result).toHaveProperty('start_time');
            expect(result).toHaveProperty('end_time');
            expect(result).toHaveProperty('total_seconds', 5);
            expect(result).toHaveProperty('events');
        });

        /**
         * Tests that stop does not error when called on stopped timer.
         */
        test('should handle being called when already stopped', () => {
            timer.stop(); // Not started

            // Should not throw
            expect(() => timer.stop()).not.toThrow();
        });
    });

    describe('reset method', () => {
        /**
         * Tests that reset clears all state.
         */
        test('should clear all state', () => {
            timer.start();
            jest.advanceTimersByTime(2000);
            timer.logEvent('test_event');

            timer.reset();

            expect(timer.startTime).toBeNull();
            expect(timer.elapsedSeconds).toBe(0);
            expect(timer.events).toEqual([]);
            expect(timer.intervalId).toBeNull();
        });
    });

    describe('onTick method', () => {
        /**
         * Tests that callback is called every second with correct values.
         */
        test('should call callback every second with elapsed and formatted time', () => {
            const callback = jest.fn();
            timer.onTick(callback);
            timer.start();

            jest.advanceTimersByTime(3000);

            expect(callback).toHaveBeenCalledTimes(3);
            expect(callback).toHaveBeenLastCalledWith(3, '0:03');
        });

        /**
         * Tests that callback receives correctly formatted time for longer durations.
         */
        test('should format time correctly for minutes', () => {
            const callback = jest.fn();
            timer.onTick(callback);
            timer.start();

            // Advance 65 seconds (1:05)
            jest.advanceTimersByTime(65000);

            expect(callback).toHaveBeenLastCalledWith(65, '1:05');
        });
    });

    describe('logEvent method', () => {
        /**
         * Tests that events are logged with correct structure.
         */
        test('should log event with correct structure', () => {
            timer.start();
            jest.advanceTimersByTime(2000);

            const event = timer.logEvent('custom_event', { extra: 'data' });

            expect(event.type).toBe('custom_event');
            expect(event.elapsed_seconds).toBe(2);
            expect(event.extra).toBe('data');
            expect(event.timestamp).toBeDefined();
        });

        /**
         * Tests that events are added to events array.
         */
        test('should add event to events array', () => {
            timer.logEvent('event1');
            timer.logEvent('event2');

            expect(timer.events).toHaveLength(2);
        });

        /**
         * Tests that custom data is merged into event.
         */
        test('should merge custom data into event', () => {
            const event = timer.logEvent('test', {
                action: 'click',
                target: 'button'
            });

            expect(event.action).toBe('click');
            expect(event.target).toBe('button');
        });
    });

    describe('getElapsedSeconds method', () => {
        /**
         * Tests that getElapsedSeconds returns current elapsed time.
         */
        test('should return current elapsed seconds', () => {
            timer.start();
            jest.advanceTimersByTime(10000);

            expect(timer.getElapsedSeconds()).toBe(10);
        });
    });

    describe('formatTime method', () => {
        /**
         * Tests formatting for various time values.
         */
        test('should format 0 seconds as 0:00', () => {
            expect(timer.formatTime(0)).toBe('0:00');
        });

        test('should format 5 seconds as 0:05', () => {
            expect(timer.formatTime(5)).toBe('0:05');
        });

        test('should format 30 seconds as 0:30', () => {
            expect(timer.formatTime(30)).toBe('0:30');
        });

        test('should format 60 seconds as 1:00', () => {
            expect(timer.formatTime(60)).toBe('1:00');
        });

        test('should format 90 seconds as 1:30', () => {
            expect(timer.formatTime(90)).toBe('1:30');
        });

        test('should format 3661 seconds (1h 1m 1s) as 61:01', () => {
            expect(timer.formatTime(3661)).toBe('61:01');
        });
    });

    describe('getFormattedTime method', () => {
        /**
         * Tests that getFormattedTime uses current elapsed seconds.
         */
        test('should return formatted current elapsed time', () => {
            timer.start();
            jest.advanceTimersByTime(125000); // 2:05

            expect(timer.getFormattedTime()).toBe('2:05');
        });
    });

    describe('getTimingData method', () => {
        /**
         * Tests that timing data has correct structure.
         */
        test('should return complete timing data', () => {
            timer.start();
            jest.advanceTimersByTime(5000);
            timer.logEvent('test_event');

            const data = timer.getTimingData();

            expect(data).toHaveProperty('start_time');
            expect(data).toHaveProperty('end_time');
            expect(data).toHaveProperty('total_seconds', 5);
            expect(data).toHaveProperty('events');
            expect(data.events.length).toBeGreaterThan(0);
        });

        /**
         * Tests that start_time is null if timer was never started.
         */
        test('should have null start_time if never started', () => {
            const data = timer.getTimingData();

            expect(data.start_time).toBeNull();
            expect(data.total_seconds).toBe(0);
        });

        /**
         * Tests that events are included in timing data.
         */
        test('should include all logged events', () => {
            timer.start();
            timer.logEvent('event1');
            timer.logEvent('event2');
            timer.logEvent('event3');

            const data = timer.getTimingData();

            // Should have timer_start plus the 3 custom events
            expect(data.events.length).toBe(4);
        });
    });
});

describe('Singleton Instance (studyTimer)', () => {
    /**
     * Tests that a global singleton instance is available.
     */
    test('should export singleton instance as studyTimer', () => {
        expect(studyTimer).toBeDefined();
        expect(studyTimer).toBeInstanceOf(StudyTimer);
    });

    /**
     * Tests that StudyTimer class is also globally available.
     */
    test('should export StudyTimer class', () => {
        expect(StudyTimer).toBeDefined();
        expect(typeof StudyTimer).toBe('function');
    });
});
