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

/** Descriptor consumed by setColorVariableAsync. */
export type ColorVariableDescriptor = Readonly<{
    spectrumId: string;
    spectrumType: 'POINT' | 'CELL';
    spectrumName: string;
    component: number; // -1 = magnitude
    min: number;
    max: number;
}>;

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
     * Apply an entire camera snapshot in one RPC. WasmRenderer implements it
     * by delegating to the seven per-field setters above. See §11 for the
     * Story 3.2 rationale (server-tracked camera + sync-back).
     */
    setCameraStateAsync(state: VisorCameraState): Promise<void>;
    /** Frame the scene on the given bounds; used by scene-graph rebuilds. */
    resetCameraAsync(bounds?: readonly number[]): Promise<void>;

    // ---- Subscriptions (return unsubscribe closures) ------------------------
    /** Fires whenever the camera changes. Callback receives a full snapshot. */
    addCameraChangedListener(callback: (state: VisorCameraState) => void): () => void;
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

    // ---- View-level widgets (state is renderer-owned; see arch rule (a)) ---
    setCrossSectionVisibilityAsync(visible?: boolean): Promise<void>;
    isCrossSectionVisible(): boolean; // cached bool, sync
    updateCrossSectionBoundsAsync(): Promise<void>;
    getCrossSectionOriginAsync(): Promise<readonly number[]>;
    getCrossSectionNormalAsync(): Promise<readonly number[]>;
    setCrossSectionOriginAsync(origin: readonly number[]): Promise<void>;
    setCrossSectionNormalAsync(normal: readonly number[]): Promise<void>;

    setBoundingBoxVisibilityAsync(visible?: boolean): Promise<void>;
    isBoundingBoxVisible(): boolean;
    updateBoundingBoxBoundsAsync(): Promise<void>;

    setOrthographicModeAsync(enable?: boolean): Promise<void>;
    isOrthographicEnabled(): boolean;

    setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void>;
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
