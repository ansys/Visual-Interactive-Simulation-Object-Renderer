import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';

/** Stable integer id of an addressable scene-graph node (part or block). */
export type NodeId = number;

/**
 * Renderer-agnostic camera snapshot. Superset of what UI panels read and what
 * getAppStateAsync/setAppStateAsync round-trip. Every field is a plain value
 * so a RemoteRenderer can cache and serve it without querying a wasm object.
 */
export type VisorCameraState = Readonly<{
    // Derived display properties (UI panels, camera-changed listeners)
    distance: number;
    orthographic: boolean;
    orthographicScale: number;
    unitsPerPixel: number;
    viewPortHeight: number;
    // Full VTK camera (needed for save / restore)
    position: readonly number[];
    focalPoint: readonly number[];
    viewUp: readonly number[];
    clippingRange: readonly number[];
    parallelProjection: boolean;
    viewAngle: number;
    parallelScale: number;
}>;

/** The seven camera fields that can be applied. No derived fields. */
export type AppliedCameraState = Readonly<{
    position: readonly number[];
    focalPoint: readonly number[];
    viewUp: readonly number[];
    clippingRange: readonly number[];
    parallelProjection: boolean;
    viewAngle: number;
    parallelScale: number;
}>;

/**
 * Where a settled camera change came from: `gesture` if user input was
 * active during the change, `programmatic` otherwise.
 * See `wasm/CameraGestureTracker.js`.
 */
export type CameraOrigin = 'gesture' | 'programmatic';

/** Descriptor consumed by setColorVariableAsync. */
export type ColorVariableDescriptor = Readonly<{
    spectrumId: string;
    spectrumType: 'POINT' | 'CELL';
    spectrumName: string;
    component: number; // -1 = magnitude
    min: number;
    max: number;
}>;

/**
 * The transport a renderer uses to send a per-part mutation to the server.
 *
 * This is the existing trame trigger call surface, nothing new:
 * `RemoteVtkScene.trameTriggerAsync(name, ...args)`, which forwards one
 * positional argument -- the payload object -- to the named server trigger.
 * It is *injected* into the concrete renderer at construction rather than
 * imported by it, so that this module stays types-only and compiles to an
 * empty module: a value import here would be inherited by every importer,
 * including the wasm transport, and would drag the scene graph and React
 * into module graphs that must not have them.
 *
 * A renderer constructed without a sender performs no send. It does not
 * throw and does not queue.
 */
export type TrameTriggerSender = (triggerName: string, payload: unknown) => Promise<unknown>;

/** Result returned by pickGeometryAsync. Discriminated by `mode`. */
export type PickGeometryResult =
    | { found: false }
    | { found: true; mode: 'vertex'; position: readonly number[] }
    | {
          found: true;
          mode: 'edge';
          pointA: readonly number[];
          pointB: readonly number[];
          length: number;
      }
    | { found: true; mode: 'face'; area: number; points: ReadonlyArray<readonly number[]> };

/** Geometry pick mode. */
export type GeometryPickMode = 'vertex' | 'edge' | 'face';

export interface IRenderer {
    // ---- Canvas / lifecycle -------------------------------------------------
    /** DOM element hosting the render output (canvas + overlay). */
    readonly domElement: HTMLDivElement;
    /**
     * Hand the live scene graph to the renderer.  Called by VisorFrontend immediately
     * after CreateVisorSceneGraph.  Temporary: exists because the bounding-box and
     * edges widgets read live per-node bounds and visibility.
     * A RemoteRenderer gets those from the server and implements this as a no-op.
     * TODO: Remove after user wire contract is updated to allow further decoupling.
     */
    attachSceneGraph(sceneGraph: VisorSceneNodeExtended): void;
    /** Kick a frame flush. Wasm: wasm.update() + Render(). Remote: no-op / RPC. */
    renderAsync(): Promise<void>;
    /** Resize output to its container. Call after container size changes. */
    resizeAsync(): Promise<void>;
    /** Drop listeners, wasm observers, overlay canvas, RPC sessions, etc. */
    dispose(): void;

    // ---- Camera (all reads async; state may live off-thread / off-box) ------
    getCameraStateAsync(): Promise<VisorCameraState>;
    setCameraPositionAsync(position: readonly number[]): Promise<void>;
    setCameraFocalPointAsync(focalPoint: readonly number[]): Promise<void>;
    setCameraViewUpAsync(viewUp: readonly number[]): Promise<void>;
    setCameraClippingRangeAsync(clippingRange: readonly number[]): Promise<void>;
    setCameraParallelProjectionAsync(enabled: boolean): Promise<void>;
    setCameraViewAngleAsync(angle: number): Promise<void>;
    setCameraParallelScaleAsync(scale: number): Promise<void>;
    /**
     * Apply the seven applied camera fields in one RPC. WasmRenderer implements it
     * by delegating to the seven per-field setters above. See §11 for the
     * Story 3.2 rationale (server-tracked camera + sync-back).
     */
    setCameraStateAsync(state: AppliedCameraState): Promise<void>;
    /** Frame the scene on the given bounds; used by scene-graph rebuilds. */
    resetCameraAsync(bounds?: readonly number[]): Promise<void>;

    // ---- Subscriptions (return unsubscribe closures) ------------------------
    /** Fires whenever the camera changes. Callback receives a full snapshot. */
    addCameraChangedListener(callback: (state: VisorCameraState) => void): () => void;
    /**
     * Fires once per gesture, after the last camera change has stopped changing for
     * CAMERA_SETTLE_MS, with the origin of that change. The callback receives
     * the origin only; read the camera with getCameraStateAsync if needed.
     * A `gesture` report is the user's own camera; a `programmatic` one is a
     * camera the application or the server applied.
     */
    addCameraSettledListener(callback: (origin: CameraOrigin) => void): () => void;
    /** Fires each frame with the current FPS. */
    addFrameRenderedListener(callback: (fps: number) => void): () => void;
    /**
     * Fires on left-click. `nodeId` is already resolved (actor→NodeId mapping
     * is the renderer's private responsibility — see §3). `null` = background.
     * `normX`/`normY` are viewport-normalised coords so the caller can drive
     * pickGeometryAsync if needed.
     */
    addViewerClickedListener(
        callback: (
            nodeId: NodeId | null,
            ctrlKey: boolean,
            shiftKey: boolean,
            normX: number,
            normY: number
        ) => void
    ): () => void;

    // ---- Per-part visual state ---------------------------------------------
    /**
     * r/g/b are normalised (0..1), matching setSelectedAsync's currentDiffuseRgb.
     * `selected` is the caller's current selection state for the node: the renderer
     * holds no per-part state, and the applied property values depend on it.
     */
    setDiffuseColorRgbAsync(
        nodeId: NodeId,
        r: number,
        g: number,
        b: number,
        selected: boolean
    ): Promise<void>;
    /** defaultRgb is normalised (0..1). `selected` as above. */
    resetDiffuseColorAsync(
        nodeId: NodeId,
        defaultRgb: readonly number[],
        selected: boolean
    ): Promise<void>;
    setVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void>;
    setSelectedAsync(
        nodeId: NodeId,
        selected: boolean,
        currentDiffuseRgb: readonly number[]
    ): Promise<void>;
    setEdgeVisibilityAsync(nodeId: NodeId, edgeVisible: boolean): Promise<void>;
    setOpacityAsync(nodeId: NodeId, opacity: number): Promise<void>;
    setColorVariableAsync(nodeId: NodeId, descriptor: ColorVariableDescriptor): Promise<void>;
    clearColorVariableAsync(nodeId: NodeId): Promise<void>;
    setScalarRangeAsync(nodeId: NodeId, min: number, max: number): Promise<void>;

    // ---- Per-part mutations routed to the server -----------------------------
    /**
     * These six carry a per-part mutation to the matching server trigger. They
     * are *not* a second way to render: they neither read nor touch any wasm
     * object, and they are called in addition to -- never instead of -- the
     * per-part apply methods above, which keep applying to the client's own
     * objects for now.
     *
     * Each payload is absolute, never relative: it carries the target value,
     * so a send that is suppressed upstream, duplicated, or reordered is
     * harmless. `nodeId` is always a part (actor) node; a group node fans out
     * to its actor descendants before any of these is called.
     *
     * A send never rejects. With no sender injected it is a no-op; with one,
     * a transport failure is logged and swallowed, because these run inside UI
     * handlers whose behaviour must not change.
     */
    sendPartVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void>;
    sendPartOpacityAsync(nodeId: NodeId, opacity: number): Promise<void>;
    /** `null` clears the custom colour; absence of a colour is absence, not a default. */
    sendPartDiffuseColorAsync(nodeId: NodeId, diffuseRgb: readonly number[] | null): Promise<void>;
    /** Carries no colour: the server reads the part's stored colour from its own record. */
    sendPartSelectedAsync(nodeId: NodeId, selected: boolean): Promise<void>;
    sendPartColorVariableAsync(nodeId: NodeId, descriptor: ColorVariableDescriptor): Promise<void>;
    sendClearPartColorVariableAsync(nodeId: NodeId): Promise<void>;

    // ---- View-level widgets (state is renderer-owned; see arch rule (a)) ---
    //
    // The four cached-bool getters below (isCrossSectionVisible,
    // isBoundingBoxVisible, isOrthographicEnabled, areEdgesVisibleGlobally)
    // share one contract: each returns the last value the server delivered,
    // or the last value this client set locally, whichever happened later.
    // Each widget's cached flag is a projection of that value, not an
    // independent source. A write followed by an immediate read returns the
    // **pre-push** value -- the write is local and the server's confirmation
    // arrives on a later fetch, so none of these is a read-after-write on the
    // server's store.

    setCrossSectionVisibilityAsync(visible?: boolean): Promise<void>;
    /** Whether the cross-section plane is shown. See contract note above. */
    isCrossSectionVisible(): boolean; // cached bool, sync
    updateCrossSectionBoundsAsync(): Promise<void>;
    getCrossSectionOriginAsync(): Promise<readonly number[]>;
    getCrossSectionNormalAsync(): Promise<readonly number[]>;
    setCrossSectionOriginAsync(origin: readonly number[]): Promise<void>;
    setCrossSectionNormalAsync(normal: readonly number[]): Promise<void>;

    setBoundingBoxVisibilityAsync(visible?: boolean): Promise<void>;
    /** Whether the bounding-box outline is shown. See contract note above. */
    isBoundingBoxVisible(): boolean;
    updateBoundingBoxBoundsAsync(): Promise<void>;

    setOrthographicModeAsync(enable?: boolean): Promise<void>;
    /**
     * Whether the view is in parallel (orthographic) projection. See contract
     * note above; additionally, the server-delivered value is seeded from the
     * wasm camera when the renderer is built. The camera is the single place
     * projection lives -- this flag only reflects it.
     */
    isOrthographicEnabled(): boolean;

    setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void>;
    /** Whether edges are shown on every part in the scene. See contract note above. */
    areEdgesVisibleGlobally(): boolean;

    toggleFullScreenAsync(): Promise<void>;

    // ---- Picking (geometry pick — the vertex/edge/face path) ---------------
    /**
     * Perform a geometry pick at the given viewport-normalised coordinates.
     * Actor→NodeId resolution and cell extraction are the renderer's job.
     * Returns a discriminated result; caller updates UI. Highlight rendering
     * is initiated by setGeometryHighlightAsync.
     */
    pickGeometryAsync(
        normX: number,
        normY: number,
        mode: GeometryPickMode
    ): Promise<PickGeometryResult>;
    /** Draw the overlay for the last pick (vertex dot, edge line, face poly). */
    setGeometryHighlightAsync(result: PickGeometryResult): Promise<void>;
    /** Remove the overlay. */
    clearGeometryHighlight(): void;
}
