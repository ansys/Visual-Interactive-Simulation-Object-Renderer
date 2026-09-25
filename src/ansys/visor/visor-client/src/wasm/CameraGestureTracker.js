/**
 * @desc Debounces raw camera `ModifiedEvent`s into a single "settled" report,
 * and tags each report to `gesture` or `programmatic`.
 *
 * Called from the camera `ModifiedEvent` handler in `VtkScene.#setupCamera`,
 * not through `addCameraChangedListener`, since that wrapper reads the whole
 * wasm camera back on every intermediate event.
 *
 * - A drag or zoom raises many camera events in a row.  Each one restarts a
 *   timer.  When CAMERA_SETTLE_MS pass with no new event, the gesture is taken
 *   to be over and one report is sent.
 *
 * - The report is tagged `gesture` if the user was providing input while the
 *   events were coming in, and `programmatic` if not (for example, a camera the
 *   server pushed).  "Providing input" means a mouse button is held on the
 *   canvas, or a wheel event or z/r keydown happened within the last CAMERA_SETTLE_MS.
 *
 * - That input check runs on every event as it arrives, and the result is
 *   remembered until the report.  It cannot run when the timer fires,
 *   because by then the user has let go of the mouse and every drag would
 *   look programmatic.
 *
 * - The wasm wheel handler and `VtkScene`'s keydown handler run before this
 *   tracker's own listeners. So for a single wheel notch or a single z/r press,
 *   the camera event can arrive before the tracker has noticed the input.
 *   To cover that, a wheel event or a z/r keydown arriving while a report is
 *   pending marks that report `gesture` as well.
 *
 * - The orientation widget is not a DOM input at all: its face click reaches
 *   the camera inside wasm, and only after the release. A real, bubbling
 *   release on the canvas itself therefore arms the window too, which covers
 *   that face click without the tracker knowing the widget exists.
 */

/**
 * The settle debounce, in milliseconds, and equally the window during which a
 * wheel event or a z/r keydown counts as active input.
 *
 * Tests pin the literal 300 and must not import this constant, so that changing
 * it here fails a test rather than silently redefining what the tests assert.
 *
 * @type{number}
 */
export const CAMERA_SETTLE_MS = 300;

/**
 * Keys whose keydown arms the input window.
 *
 * Kept in step with the `z` / `r` cases of `VtkScene.#setupCamera`'s window
 * `keydown` handler, which is what actually mutates the camera. If a key is
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
            // A release on the canvas arms the window, so a move that only
            // reaches the camera afterwards -- an orientation-widget face
            // click -- still reports as a gesture. Both checks are needed:
            // UI over the canvas is not the canvas, and `applyMouseEvent`
            // fires non-bubbling `mouseup`s at the canvas on every press,
            // release and mouseout, which must not arm anything.
            if (e.target === canvas && e.bubbles) {
                this.#markImpulse();
            }
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
        const onKeyDown = /**@param {KeyboardEvent} e*/ (e) => {
            // Ctrl+R, Cmd+R and auto-repeat must not move the camera.
            // VtkScene applies the same rule: change both together.
            if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) {
                return;
            }

            if (e.key != null && CAMERA_KEYS.includes(e.key.toLowerCase())) {
                this.#markImpulse();
            }
        };

        this.#addListener(canvasDiv, 'mousedown', onMouseDown, true);
        this.#addListener(canvasDiv, 'mouseup', onMouseUp, true);
        this.#addListener(canvasDiv, 'mouseout', onInputLost, true);
        this.#addListener(canvas, 'wheel', onWheel, { passive: true });
        this.#addListener(window, 'keydown', onKeyDown, false);
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
     * and, because the camera event these raise may already have been noted
     * before this handler ran, retroactively marks a pending settle window as
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
