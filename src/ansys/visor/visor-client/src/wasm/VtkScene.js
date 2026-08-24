/**
 * @desc `VtkScene` represents an interface to a VTK WASM instance
 * running locally in the browser. `VtkScene` can be initialized with
 * a "standalone" VTK namespace, or a `RemoteVtkConnection` can be
 * provided to the constructor to initialize the scene from an existing
 * remote one.
 */
export default class VtkScene {
    /**
     * @private
     */
    constructor() {
        if (!VtkScene.#allowConstruction) {
            const msg = `Constructor is private.`;
            throw new Error(`${msg} Use getInstanceAsync().`);
        }
    }

    /**@type{boolean}*/
    static #allowConstruction = false;

    /**
     * @param {?FrontendVtkObject?} vtk - Use a standalone VTK namespace for this scene.
     * @param {?RemoteVtkScene?} remoteVtkScene - Base this scene off of an existing remote VTK scene.
     */
    static getInstanceAsync = async (vtk, remoteVtkScene) => {
        this.#allowConstruction = true;
        /**@type{VtkScene}*/
        let instance;
        try {
            instance = new VtkScene();
        } finally {
            this.#allowConstruction = false;
        }
        await this.#init.call(instance, vtk, remoteVtkScene);
        Object.freeze(instance);
        return instance;
    };

    /**
     * @this {VtkScene}
     * @param {?FrontendVtkObject?} vtk
     * @param {?RemoteVtkScene?} remoteVtkScene
     */
    static async #init(vtk, remoteVtkScene) {
        /**@type{FrontendVtkObject}*/
        let camera;
        /**@type{FrontendVtkObject}*/
        let interactor;
        /**@type{FrontendVtkObject}*/
        let picker;
        if (vtk != null) {
            throw new Error('standalone sessions not yet supported');
        } else if (remoteVtkScene == null) {
            throw new Error('if the VTK namespace is null, remoteVtkScene must be provided');
        }
        const { renderer, renderWindow, canvasDiv, canvas } = remoteVtkScene;
        camera = await renderer.GetActiveCamera();
        interactor = await renderWindow.GetInteractor();
        picker = await interactor.GetPicker();
        this.#remoteVtkScene = remoteVtkScene;
        this.canvas = canvas;
        this.canvasDiv = canvasDiv;
        this.camera = camera;
        this.renderer = renderer;
        this.renderWindow = renderWindow;
        this.interactor = interactor;
        this.picker = picker;
        this.#setupFpsMonitor();
        this.#setupCamera();
        this.#setupPicker();
        this.#setupHighlightOverlay();
    }

    /**@type{RemoteVtkScene}*/
    #remoteVtkScene;
    /**@type{HTMLCanvasElement}*/
    canvas;
    /**@type{HTMLDivElement}*/
    canvasDiv;
    /** Last WASM display coords from mouseup – used by pickGeometryAsync. */
    #lastPickDisplayPos = null;
    /**@type{FrontendVtkObject}*/
    camera;
    /**@type{FrontendVtkObject}*/
    renderer;
    /**@type{FrontendVtkObject}*/
    renderWindow;
    /**@type{FrontendVtkObject}*/
    interactor;
    /**@type{FrontendVtkObject}*/
    picker;
    /**
     * @param {number} wasmId
     * @return {FrontendVtkObject}
     */
    getVtkObject = (wasmId) => {
        return this.#remoteVtkScene.getVtkObject(wasmId);
    };
    getViewPortHeightAsync = async () => {
        // renderWindow.GetSize() returns something like [300, 300]
        const windowSize = await this.renderWindow.GetSize();
        const viewport = await this.renderer.GetViewport();
        return windowSize[1] * (viewport[3] - viewport[1]);
    };
    /**
     * @return {boolean}
     */
    render = async () => {
        return this.#remoteVtkScene.render();
    };
    /**
     * @return {Promise<void>}
     */
    resizeAsync = async () => {
        await this.#remoteVtkScene.resizeAsync();
    };
    /**
     * @return {void}
     */
    clearObserversAndEventListeners = () => {
        for (const remover of this.#userObserverRemovers.values()) {
            remover();
        }
        this.#cameraChangedListeners.clear();
        this.#viewerClickedListeners.clear();
        this.#frameRenderedListeners.clear();
    };
    /**@type{Map<Function,()=>void>}*/
    #userObserverRemovers = new Map();
    /**@type{Map<Function,(actorId:number,ctrlKey:boolean,shiftKey:boolean,normX:number,normY:number)=>void>}*/
    #viewerClickedListeners = new Map();
    /**@type{Map<Function,(camera:FrontendVtkObject)=>void>}*/
    #cameraChangedListeners = new Map();
    /**@type{Map<Function,(fps:number)=>void>}*/
    #frameRenderedListeners = new Map();
    /**
     * @param {(cameraState:TrameStateValue)=>void} handler
     * @return {()=>void}
     */
    addCameraChangedListener = (handler) => {
        const remover = () => this.#cameraChangedListeners.delete(remover);
        this.#cameraChangedListeners.set(remover, handler);
        return remover;
    };
    /**
     * @param {(actorId:number,ctrlKey:boolean,shiftKey:boolean,normX:number,normY:number)=>void} handler
     * @return {()=>void}
     */
    addViewerClickedListener = (handler) => {
        const remover = () => this.#viewerClickedListeners.delete(remover);
        this.#viewerClickedListeners.set(remover, handler);
        return remover;
    };
    /**
     * Pick geometry at the last clicked position.
     *
     * The interactor's picker is a vtkCellPicker (set server-side), which
     * returns the exact hit cell via GetCellId().  The actor's WASM object ID
     * is retrieved from the actor proxy.  Both are forwarded to the server so
     * it can look up the cell vertices directly
     *
     * @param {number} normX - Normalized x [0..1] (kept for API compatibility)
     * @param {number} normY - Normalized y [0..1] bottom→top (VTK convention)
     * @param {string} mode  - 'vertex' | 'edge' | 'face'
     * @return {Promise<{found:boolean, mode?:string, position?:number[], pointA?:number[], pointB?:number[], length?:number, area?:number, points?:number[][]}>}
     */
    pickGeometryAsync = async (normX, normY, mode) => {
        const displayPos = this.#lastPickDisplayPos;
        if (!displayPos) return { found: false };
        const [dx, dy] = displayPos;

        // Re-pick at the exact WASM display coordinates.
        const found = await this.picker.Pick([dx, dy, 0], this.renderer);
        if (!found) return { found: false };

        const rawPos = await this.picker.GetPickPosition();
        const position = [rawPos[0], rawPos[1], rawPos[2]];

        // For all modes (vertex, edge, face): use vtkCellPicker's exact cell ID
        // and actor WASM ID so the server can snap to the nearest vertex / edge / face.
        try {
            const cellId = await this.picker.GetCellId();
            if (cellId < 0) return { found: false };
            const actorProxy = await this.picker.GetActor();
            const actorWasmId = actorProxy?.id ?? null;
            if (actorWasmId == null) return { found: false };
            return await this.#remoteVtkScene.trameTriggerAsync(
                'pick_geometry',
                actorWasmId,
                cellId,
                mode,
                position[0],
                position[1],
                position[2]
            );
        } catch (_) {
            return { found: false };
        }
    };

    // ── Client-side geometry highlight (Canvas 2D overlay) ──────────────────
    /**@type{HTMLCanvasElement|null}*/
    #highlightCanvas = null;
    /**@type{any|null}*/
    #highlightResult = null;

    #setupHighlightOverlay = () => {
        const overlay = document.createElement('canvas');
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.pointerEvents = 'none';
        this.canvasDiv.appendChild(overlay);
        this.#highlightCanvas = overlay;
        // Redraw when camera moves so the projected positions stay correct.
        this.addCameraChangedListener(() => {
            this.#drawHighlight().catch(() => {});
        });
    };

    /**
     * Project a world-space point to overlay canvas pixels (top-left origin).
     * @param {number[]} worldPt  [x, y, z]
     * @return {Promise<number[]>}  [canvasX, canvasY]
     */
    #projectWorldToCanvas = async (worldPt) => {
        await this.renderer.SetWorldPoint(worldPt[0], worldPt[1], worldPt[2], 1.0);
        await this.renderer.WorldToDisplay();
        const dp = await this.renderer.GetDisplayPoint();
        // dp: [x, y, z] — VTK display coords (x left→right, y bottom→top, in render-window pixels)
        const winSize = await this.renderWindow.GetSize();
        const normX = dp[0] / winSize[0];
        const normY = dp[1] / winSize[1]; // 0 = bottom
        const overlay = this.#highlightCanvas;
        const canvasX = normX * overlay.width;
        const canvasY = (1 - normY) * overlay.height; // flip Y for canvas2d
        return [canvasX, canvasY];
    };

    #drawHighlight = async () => {
        const canvas = this.#highlightCanvas;
        if (!canvas) return;
        // Match canvas size to its CSS display size
        const rect = this.canvasDiv.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const result = this.#highlightResult;
        if (!result || !result.found) return;

        ctx.strokeStyle = 'rgba(255, 165, 0, 1)'; // orange
        ctx.fillStyle = 'rgba(255, 165, 0, 0.35)';
        ctx.lineWidth = 3;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        if (result.mode === 'vertex') {
            // Project the exact snapped vertex world position to canvas.
            const [cx, cy] = await this.#projectWorldToCanvas(result.position);
            ctx.beginPath();
            ctx.arc(cx, cy, 9, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
        } else if (result.mode === 'edge') {
            const [ax, ay] = await this.#projectWorldToCanvas(result.pointA);
            const [bx, by] = await this.#projectWorldToCanvas(result.pointB);
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.stroke();
            // endpoint dots
            ctx.beginPath();
            ctx.arc(ax, ay, 5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(bx, by, 5, 0, 2 * Math.PI);
            ctx.fill();
        } else if (result.mode === 'face' && result.points && result.points.length >= 3) {
            const screenPts = [];
            for (const p of result.points) {
                screenPts.push(await this.#projectWorldToCanvas(p));
            }
            ctx.beginPath();
            ctx.moveTo(screenPts[0][0], screenPts[0][1]);
            for (let i = 1; i < screenPts.length; i++) {
                ctx.lineTo(screenPts[i][0], screenPts[i][1]);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
    };

    /**
     * Draw a highlight overlay for a pick result returned by pickGeometryAsync.
     * @param {any} result
     * @return {Promise<void>}
     */
    setGeometryHighlightAsync = async (result) => {
        this.#highlightResult = result;
        await this.#drawHighlight();
    };

    /**
     * Clear the geometry highlight overlay.
     */
    clearGeometryHighlight = () => {
        this.#highlightResult = null;
        const canvas = this.#highlightCanvas;
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    };
    // ────────────────────────────────────────────────────────────────────────

    /**
     * @param {(fps:number)=>void} handler
     * @return {()=>void}
     */
    addFrameRenderedListener = (handler) => {
        const remover = () => this.#frameRenderedListeners.delete(remover);
        this.#frameRenderedListeners.set(remover, handler);
        return remover;
    };
    /**
     */
    #setupPicker = () => {
        const { renderer, interactor, picker, canvasDiv } = this;
        const viewerClickedListeners = this.#viewerClickedListeners;
        ///////////////////////////////////////////
        ///////////////////////////////////////////
        let pickingPending = false;
        /**@type{number|null}*/
        let lastMouseX = null;
        /**@type{number|null}*/
        let lastMouseY = null;
        ///////////////////////////////////////////
        ///////////////////////////////////////////
        canvasDiv.addEventListener('blur', (e) => (lastMouseX = lastMouseY = null));
        canvasDiv.addEventListener('mouseout', (e) => (lastMouseX = lastMouseY = null));
        canvasDiv.addEventListener('mousedown', (e) => {
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
        });
        canvasDiv.addEventListener('mouseup', async (e) => {
            try {
                if (lastMouseX == null || lastMouseY == null || pickingPending) {
                    return;
                } else {
                    const margin = 0;
                    if (e.clientX < lastMouseX - margin || e.clientX > lastMouseX + margin) {
                        return;
                    } else if (e.clientY < lastMouseY - margin || e.clientY > lastMouseY + margin) {
                        return;
                    }
                }
                pickingPending = true;
                const rect = canvasDiv.getBoundingClientRect();
                const normX = (e.clientX - rect.left) / rect.width;
                const normY_vtk = 1.0 - (e.clientY - rect.top) / rect.height;
                const [x, y] = await interactor.GetEventPosition();
                this.#lastPickDisplayPos = [x, y];
                const found = await picker.Pick([x, y, 0], renderer);
                const actor = found ? await picker.getActor() : null;
                for (const callback of viewerClickedListeners.values()) {
                    callback(actor?.id ?? null, e.ctrlKey, e.shiftKey, normX, normY_vtk);
                }
            } finally {
                lastMouseX = lastMouseY = null;
                pickingPending = false;
            }
        });
    };

    /**
     */
    #setupCamera = () => {
        const { renderer, renderWindow, camera, canvasDiv, canvas } = this;
        const cameraChangedListeners = this.#cameraChangedListeners;

        camera.observe('ModifiedEvent', () => {
            for (const callback of cameraChangedListeners.values()) {
                callback(camera);
            }
        });

        /**@type{boolean}*/
        let eventFiring = false;
        /**@type{boolean}*/
        let mouseLeftDown = false;
        /**@type{boolean}*/
        let mouseMiddleDown = false;
        /**@type{boolean}*/
        let mouseRightDown = false;

        /**
         * @param {MouseEvent} e
         * @param {number} buttonNumber
         * @return {MouseEventInit}
         */
        function getEventDict(e, buttonNumber) {
            return {
                clientX: e.clientX,
                clientY: e.clientY,
                button: buttonNumber,
                bubbles: false,
                cancelable: true,
            };
        }

        /**
         * @param {MouseEvent} e
         * @param {boolean} down
         */
        function applyMouseEvent(e, down) {
            if (eventFiring) {
                return;
            }
            try {
                eventFiring = true;
                if (e.button === 0) {
                    mouseLeftDown = down;
                } else if (e.button === 1) {
                    mouseMiddleDown = down;
                } else if (e.button === 2) {
                    mouseRightDown = down;
                }
                canvas.dispatchEvent(new MouseEvent('mouseup', getEventDict(e, 0)));
                canvas.dispatchEvent(new MouseEvent('mouseup', getEventDict(e, 1)));
                canvas.dispatchEvent(new MouseEvent('mouseup', getEventDict(e, 2)));
                if (mouseLeftDown && mouseRightDown) {
                    canvas.dispatchEvent(new MouseEvent('mousedown', getEventDict(e, 1)));
                    e.stopPropagation();
                } else if (mouseRightDown) {
                    canvas.dispatchEvent(new MouseEvent('mousedown', getEventDict(e, 2)));
                    e.stopPropagation();
                } else if (mouseLeftDown) {
                    canvas.dispatchEvent(new MouseEvent('mousedown', getEventDict(e, 0)));
                    // don't call e.stopPropagation() here because we need to
                    // send the left-mouse-button event to the VTK canvas.
                } else if (mouseMiddleDown) {
                    canvas.dispatchEvent(new MouseEvent('mousedown', getEventDict(e, 0)));
                    e.stopPropagation();
                }
            } finally {
                eventFiring = false;
            }
        }

        canvasDiv.addEventListener(
            'mousedown',
            async (e) => {
                applyMouseEvent(e, true);
            },
            true
        );
        canvasDiv.addEventListener(
            'contextmenu',
            async (e) => {
                // disable context menu
                e.preventDefault();
                e.stopImmediatePropagation();
            },
            true
        );
        canvasDiv.addEventListener(
            'mouseup',
            async (e) => {
                applyMouseEvent(e, false);
            },
            true
        );

        // TODO: need to remove this event listener when the user disposes the WasmView object
        window.addEventListener('keyup', async (e) => {
            switch (e.key.toLowerCase()) {
                case 'z':
                    await renderer.ResetCamera();
                    await renderWindow.Render();
                    return;
                case 'r':
                    await camera.SetPosition(0, 0, 1);
                    await camera.SetFocalPoint(0, 0, 0);
                    await camera.SetViewUp(0, 1, 0);
                    await renderer.ResetCameraClippingPlane();
                    await renderer.ResetCamera();
                    await renderWindow.Render();
                    return;
            }
        });
        canvasDiv.addEventListener(
            'mouseout',
            async (e) => {
                // This resolves the "sticky mousedown" issue.
                // "Sticky mousedown" arises when the user holds left-click to rotate the
                // mesh, but then moves the cursor out of the browser viewport while rotating,
                // and releases the mouse button outside the viewport. When the user moves the
                // cursor back into the viewport, the mesh continues to be rotated, even though
                // the user is no longer holding down the mouse button. It's "sticky".
                applyMouseEvent(e, false);
            },
            true
        );
    };

    #setupFpsMonitor = () => {
        const self = this;
        const arr = /**@type{number[]}*/ [];
        requestAnimationFrame(frame);

        function frame() {
            const now = performance.now();
            arr.unshift(now);
            if (arr.length >= 500) {
                throw new Error(`array is too big: ${arr.length}`);
            }
            const nowMinusOneSecond = now - 1000;
            for (let i = arr.length - 1; i >= 0; i--) {
                if (arr[i] >= nowMinusOneSecond) {
                    arr.length = i + 1;
                    let dt = 0;
                    if (i > 0) {
                        dt = (arr[0] - arr[i]) / i;
                    }
                    const fps = 1000 / dt;
                    for (const callback of self.#frameRenderedListeners.values()) {
                        callback(fps);
                    }
                    requestAnimationFrame(frame);
                    return;
                }
            }
            throw new Error('array should not be empty');
        }
    };
}
