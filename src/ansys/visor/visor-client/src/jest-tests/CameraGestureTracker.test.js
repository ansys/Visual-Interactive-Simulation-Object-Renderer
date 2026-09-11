/**
 * Story 3.2, Increment 6 — the camera settle debounce and its origin capture.
 *
 * The tracker is tested directly rather than through VtkScene: VtkScene's
 * construction awaits four wasm proxies and starts a requestAnimationFrame
 * loop, so a fake large enough to build one would be what the tests measured.
 *
 * The debounce is 300 ms. That literal is written out in every assertion here
 * and the production constant is deliberately not imported, so that changing
 * it fails these tests instead of silently redefining what they assert.
 */
import CameraGestureTracker from '../wasm/CameraGestureTracker.js';

describe('CameraGestureTracker', () => {
    /**@type{HTMLElement}*/
    let canvasDiv;
    /**@type{HTMLElement}*/
    let canvas;
    /**@type{CameraGestureTracker}*/
    let tracker;
    /**@type{jest.Mock}*/
    let onSettled;

    beforeEach(() => {
        jest.useFakeTimers();
        canvasDiv = document.createElement('div');
        canvas = document.createElement('canvas');
        canvasDiv.appendChild(canvas);
        document.body.appendChild(canvasDiv);
        tracker = new CameraGestureTracker(canvasDiv, canvas);
        onSettled = jest.fn();
        tracker.addSettledListener(onSettled);
    });

    afterEach(() => {
        tracker.dispose();
        document.body.removeChild(canvasDiv);
        jest.useRealTimers();
    });

    const mouseDown = (button) =>
        canvasDiv.dispatchEvent(new MouseEvent('mousedown', { button, bubbles: true }));
    const mouseUp = (button) =>
        canvasDiv.dispatchEvent(new MouseEvent('mouseup', { button, bubbles: true }));
    const mouseOut = () => canvasDiv.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }));
    const mouseMove = () => canvasDiv.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));
    const wheel = () => canvas.dispatchEvent(new Event('wheel'));
    const keyUp = (key) => window.dispatchEvent(new KeyboardEvent('keyup', { key }));
    const blur = () => window.dispatchEvent(new Event('blur'));

    // ---- the debounce ------------------------------------------------------

    test('no report at 299 ms and exactly one report at 300 ms', () => {
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(299);
        expect(onSettled).not.toHaveBeenCalled();

        jest.advanceTimersByTime(1);
        expect(onSettled).toHaveBeenCalledTimes(1);
    });

    test('a second event before the deadline restarts the debounce', () => {
        tracker.noteCameraEvent();
        jest.advanceTimersByTime(200);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(299);
        expect(onSettled).not.toHaveBeenCalled();

        jest.advanceTimersByTime(1);
        expect(onSettled).toHaveBeenCalledTimes(1);
    });

    // ---- origin, captured at event time ------------------------------------

    test('an event with no input reports programmatic', () => {
        tracker.noteCameraEvent();
        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    test('an event while a button is held reports gesture even though the button is released before the deadline', () => {
        mouseDown(0);
        tracker.noteCameraEvent();
        mouseUp(0);

        jest.advanceTimersByTime(300);

        // An origin computed when the timer fires would say 'programmatic'
        // here, because by then the button is up.
        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    test('one gesture event makes the whole window gesture', () => {
        mouseDown(0);
        tracker.noteCameraEvent();
        mouseUp(0);
        jest.advanceTimersByTime(100);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    // ---- what counts as input ----------------------------------------------

    test('pointer movement with no button held is not input', () => {
        mouseMove();
        tracker.noteCameraEvent();
        mouseMove();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    test('a mouseout ends the hold', () => {
        mouseDown(2);
        mouseOut();
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    test('a window blur ends the hold', () => {
        mouseDown(1);
        blur();
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    test('an event within 300 ms of a wheel reports gesture', () => {
        wheel();
        jest.advanceTimersByTime(299);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    test('an event 300 ms after a wheel reports programmatic', () => {
        wheel();
        jest.advanceTimersByTime(300);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    test('an event within 300 ms of a z keyup reports gesture', () => {
        keyUp('z');
        jest.advanceTimersByTime(299);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    test('an event within 300 ms of an r keyup reports gesture', () => {
        keyUp('r');
        jest.advanceTimersByTime(299);
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    test('a keyup that is not z or r does not arm input', () => {
        keyUp('a');
        tracker.noteCameraEvent();

        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledWith('programmatic');
    });

    // ---- listener management and teardown ----------------------------------

    test('the remover returned by addSettledListener stops reports', () => {
        const second = jest.fn();
        const remove = tracker.addSettledListener(second);
        remove();

        tracker.noteCameraEvent();
        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(second).not.toHaveBeenCalled();
    });

    test('a settle armed before teardown produces no report', () => {
        tracker.noteCameraEvent();
        tracker.dispose();

        jest.advanceTimersByTime(300);

        expect(onSettled).not.toHaveBeenCalled();
    });

    test('after teardown a further event produces no report', () => {
        tracker.dispose();

        tracker.noteCameraEvent();
        jest.advanceTimersByTime(300);

        expect(onSettled).not.toHaveBeenCalled();
    });
});

/**
 * The wasm canvas's own wheel handler and VtkScene's window keyup handler are
 * registered before the tracker is constructed, so the camera event raised by a
 * single wheel notch or a single z/r press reaches noteCameraEvent() before the
 * tracker's own handler has marked input active.
 *
 * Each test here reproduces that order exactly: a stand-in listener is
 * registered on the same target *before* the tracker exists, and calls
 * noteCameraEvent() synchronously from inside its own handler.
 */
describe('CameraGestureTracker, when the camera event precedes the tracker handler', () => {
    /**@type{HTMLElement}*/
    let canvasDiv;
    /**@type{HTMLElement}*/
    let canvas;
    /**@type{CameraGestureTracker|null}*/
    let tracker;
    /**@type{jest.Mock}*/
    let onSettled;
    /**@type{Array<()=>void>}*/
    let standIns;

    beforeEach(() => {
        jest.useFakeTimers();
        canvasDiv = document.createElement('div');
        canvas = document.createElement('canvas');
        canvasDiv.appendChild(canvas);
        document.body.appendChild(canvasDiv);
        tracker = null;
        onSettled = jest.fn();
        standIns = [];
    });

    afterEach(() => {
        for (const remove of standIns) {
            remove();
        }
        if (tracker != null) {
            tracker.dispose();
        }
        document.body.removeChild(canvasDiv);
        jest.useRealTimers();
    });

    /**
     * Registers a handler that raises one camera event, before the tracker is
     * constructed, so that it runs first.
     */
    const standInBefore = (target, type) => {
        const handler = () => tracker.noteCameraEvent();
        target.addEventListener(type, handler);
        standIns.push(() => target.removeEventListener(type, handler));
    };

    test('a single wheel event reports gesture', () => {
        standInBefore(canvas, 'wheel');
        tracker = new CameraGestureTracker(canvasDiv, canvas);
        tracker.addSettledListener(onSettled);

        canvas.dispatchEvent(new Event('wheel'));
        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(onSettled).toHaveBeenCalledWith('gesture');
    });

    test('a single r keyup reports gesture', () => {
        standInBefore(window, 'keyup');
        tracker = new CameraGestureTracker(canvasDiv, canvas);
        tracker.addSettledListener(onSettled);

        window.dispatchEvent(new KeyboardEvent('keyup', { key: 'r' }));
        jest.advanceTimersByTime(300);

        expect(onSettled).toHaveBeenCalledTimes(1);
        expect(onSettled).toHaveBeenCalledWith('gesture');
    });
});
