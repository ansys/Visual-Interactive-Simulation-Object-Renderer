/**
 * @desc Debounces raw camera `ModifiedEvent`s into a single "settled" report,
 * and attributes each report to `gesture` or `programmatic`.
 *
 * Story 3.2, Increment 6. The binding point is the `ModifiedEvent` fan-out in
 * `VtkScene.#setupCamera` (decision D1-a): the fan-out is the only camera-event
 * source, and it is the one place that sees orbit, pan, wheel zoom, the z/r
 * keyboard resets and the client-side `vtkCameraOrientationWidget` alike.
 * Subscribing through `addCameraChangedListener` instead would pay that
 * wrapper's per-event nine-await read-back of the wasm camera on every
 * intermediate event of a gesture.
 *
 * Two rules matter and are easy to get wrong:
 *
 * 1. **Origin is recorded per event, at event time, never at settle time.**
 *    The settle fires 300 ms after the *last* event, by which time a gesture
 *    has ended and a programmatic apply has finished. An origin computed when
 *    the timer fires is mislabelled in both directions.
 *
 * 2. **Origin is attributed by user input, not by apply depth.** An event is
 *    `gesture` only while user input is active: a mouse button held on the
 *    canvas, within 300 ms of a wheel event, or within 300 ms of a z/r keyup.
 *    Pointer movement with no button held is not input. Everything else is
 *    `programmatic`, whatever its source. The settle reports `gesture` if
 *    *any* event in its window was `gesture`.
 *
 * The wasm wheel handler and `VtkScene`'s own window keyup handler are
 * registered before this tracker, so the camera event raised by a single wheel
 * notch or a single z/r press reaches `noteCameraEvent()` *before* this
 * tracker's own handler has marked input active. Rather than depend on
 * listener registration order, a wheel event or a z/r keyup arriving while a
 * settle is already pending marks that window `gesture` as well. The mouse
 * path needs no such rule: the press always precedes the moves it causes.
 */

/**
 * The settle debounce, in milliseconds, and equally the window during which a
 * wheel event or a z/r keyup counts as active input.
 *
 * This is a ruling, not a measurement. Tests pin the literal 300 and must not
 * import this constant, so that changing it here fails a test rather than
 * silently redefining what the tests assert.
 *
 * @type{number}
 */
export const CAMERA_SETTLE_MS = 300;

/**
 * Keys whose keyup arms the input window.
 *
 * Kept in step with the `z` / `r` cases of `VtkScene.#setupCamera`'s window
 * `keyup` handler, which is what actually mutates the camera. If a key is
 * added there, add it here.
 *
 * @type{ReadonlyArray<string>}
 */
const CAMERA_KEYS = ['z', 'r'];

export default class CameraGestureTracker {
    /**
     * Attaches its own input listeners. Every one of them is removed by
     * `dispose()`.
     *
     * Mouse buttons are tracked on `canvasDiv`, in the capture phase, which is
     * where the real user events land. They are deliberately *not* tracked on
     * `canvas`: `VtkScene.#setupCamera`'s `applyMouseEvent` dispatches three
     * synthetic `mouseup`s and a synthetic `mousedown` onto `canvas` for every
     * real button event, so a canvas-side tracker would see releases that
     * never happened.
     *
     * The wheel is tracked on `canvas`, which the synthetic mouse traffic does
     * not touch.
     *
     * @param {HTMLElement} canvasDiv - the container that receives real mouse events
     * @param {HTMLElement} canvas - the wasm render canvas
     */
    constructor(canvasDiv, canvas) {
        const onMouseDown = /**@param {MouseEvent} e*/ (e) => {
            this.#heldButtons.add(e.button);
        };
        const onMouseUp = /**@param {MouseEvent} e*/ (e) => {
            this.#heldButtons.delete(e.button);
        };
        // A `mouseout` is the existing sticky-mousedown release, and a window
        // `blur` means the page no longer owns the input. Both clear *every*
        // held button rather than only the one this event names: a MouseEvent
        // for `mouseout` carries button 0, so clearing per-button would leave a
        // middle- or right-drag latched as "input active" forever, and every
        // later programmatic apply would be reported as a gesture.
        const onInputLost = () => {
            this.#heldButtons.clear();
        };
        const onWheel = () => {
            this.#markImpulse();
        };
        const onKeyUp = /**@param {KeyboardEvent} e*/ (e) => {
            if (e.key != null && CAMERA_KEYS.includes(e.key.toLowerCase())) {
                this.#markImpulse();
            }
        };

        this.#addListener(canvasDiv, 'mousedown', onMouseDown, true);
        this.#addListener(canvasDiv, 'mouseup', onMouseUp, true);
        this.#addListener(canvasDiv, 'mouseout', onInputLost, true);
        this.#addListener(canvas, 'wheel', onWheel, { passive: true });
        this.#addListener(window, 'keyup', onKeyUp, false);
        this.#addListener(window, 'blur', onInputLost, false);
    }

    /**@type{Array<()=>void>}*/
    #listenerRemovers = [];
    /**
     * Mouse buttons currently held down, by `MouseEvent.button` number. A Set
     * rather than three booleans, so buttons 3 and 4 are handled the same way.
     * @type{Set<number>}
     */
    #heldButtons = new Set();
    /**@type{boolean}*/
    #impulseActive = false;
    /**@type{*}*/
    #impulseTimer = null;
    /**@type{*}*/
    #settleTimer = null;
    /**
     * Whether any event in the pending settle window was a gesture. This is
     * the whole of the "origin at event time" mechanism.
     * @type{boolean}
     */
    #sawGesture = false;
    /**@type{boolean}*/
    #disposed = false;
    /**@type{Map<Function,(origin:'gesture'|'programmatic')=>void>}*/
    #settledListeners = new Map();

    /**
     * @param {EventTarget} target
     * @param {string} type
     * @param {(e:any)=>void} handler
     * @param {boolean|AddEventListenerOptions} options
     */
    #addListener = (target, type, handler, options) => {
        target.addEventListener(type, handler, options);
        this.#listenerRemovers.push(() => target.removeEventListener(type, handler, options));
    };

    /**
     * A wheel notch or a z/r press. Arms the input window for CAMERA_SETTLE_MS,
     * and — because the camera event these raise may already have been noted
     * before this handler ran — retroactively marks a pending settle window as
     * a gesture.
     */
    #markImpulse = () => {
        if (this.#disposed) {
            return;
        }
        this.#impulseActive = true;
        if (this.#impulseTimer != null) {
            clearTimeout(this.#impulseTimer);
        }
        this.#impulseTimer = setTimeout(() => {
            this.#impulseTimer = null;
            this.#impulseActive = false;
        }, CAMERA_SETTLE_MS);
        if (this.#settleTimer != null) {
            this.#sawGesture = true;
        }
    };

    /**
     * @return {boolean} whether user input is active right now.
     */
    #isInputActive = () => {
        return this.#heldButtons.size > 0 || this.#impulseActive;
    };

    /**
     * Called from the `ModifiedEvent` fan-out, once per raw camera event.
     * Records this event's origin immediately, then restarts the debounce.
     * @return {void}
     */
    noteCameraEvent = () => {
        if (this.#disposed) {
            return;
        }
        if (this.#isInputActive()) {
            this.#sawGesture = true;
        }
        if (this.#settleTimer != null) {
            clearTimeout(this.#settleTimer);
        }
        this.#settleTimer = setTimeout(this.#reportSettled, CAMERA_SETTLE_MS);
    };

    /**
     * @return {void}
     */
    #reportSettled = () => {
        const origin = this.#sawGesture ? 'gesture' : 'programmatic';
        this.#settleTimer = null;
        this.#sawGesture = false;
        for (const callback of this.#settledListeners.values()) {
            callback(origin);
        }
    };

    /**
     * @param {(origin:'gesture'|'programmatic')=>void} handler
     * @return {()=>void} a remover
     */
    addSettledListener = (handler) => {
        const remover = () => this.#settledListeners.delete(remover);
        this.#settledListeners.set(remover, handler);
        return remover;
    };

    /**
     * Teardown. Clears the settled-listener map, the pending settle timer and
     * the window's recorded origins, resets the input state, and removes every
     * listener this class added. Idempotent.
     *
     * A settle armed before a scene rebuild must not fire afterwards: it would
     * report a camera belonging to the previous scene, tagged as a user
     * gesture, and the server would record it.
     *
     * @return {void}
     */
    dispose = () => {
        this.#disposed = true;
        if (this.#settleTimer != null) {
            clearTimeout(this.#settleTimer);
            this.#settleTimer = null;
        }
        if (this.#impulseTimer != null) {
            clearTimeout(this.#impulseTimer);
            this.#impulseTimer = null;
        }
        this.#sawGesture = false;
        this.#impulseActive = false;
        this.#heldButtons.clear();
        this.#settledListeners.clear();
        for (const remover of this.#listenerRemovers) {
            remover();
        }
        this.#listenerRemovers = [];
    };
}
