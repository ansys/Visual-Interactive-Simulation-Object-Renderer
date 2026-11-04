import type {
    ColorVariableDescriptor,
    GeometryPickMode,
    IRenderer,
    NodeId,
    PickGeometryResult,
    TrameTriggerSender,
    VisorCameraState,
} from './IRenderer';
import type { CanvasClick, IServerCanvas } from '../rca/ServerCanvas';
import { ViewerClickDispatcher } from '../input/ViewerClickDispatcher';
import { SceneTriggerSends } from './SceneTriggerSends';

/** The trame state key the server writes the camera record to. */
export const SERVER_CAMERA_STATE_KEY = 'server_camera_state';

/** The part of trame's state the renderer reads. */
export type ServerStateSource = Readonly<{
    watch(keys: string[], fn: (...values: unknown[]) => void): () => void;
}>;

/** Raised by getCameraStateAsync while any of the seven camera fields has never been delivered. */
export class CameraStateUnavailableError extends Error {
    constructor() {
        super(`The server has not delivered the camera yet`);
        this.name = `CameraStateUnavailableError`;
    }
}

/** Raised by the cross-section plane reads while the plane has never been delivered. */
export class CrossSectionStateUnavailableError extends Error {
    constructor() {
        super(`The server has not delivered the cross-section plane yet`);
        this.name = `CrossSectionStateUnavailableError`;
    }
}

/** Raised by the geometry-pick members: geometry picking is not available when the server renders. */
export class GeometryPickingUnavailableError extends Error {
    constructor() {
        super(`Geometry picking is not available when the server renders`);
        this.name = `GeometryPickingUnavailableError`;
    }
}

/** The seven camera fields the server publishes. */
type CameraRecord = Readonly<{
    position: readonly number[];
    focalPoint: readonly number[];
    viewUp: readonly number[];
    clippingRange: readonly number[];
    parallelProjection: boolean;
    viewAngle: number;
    parallelScale: number;
}>;

/** The seven camera fields the server publishes, cached as they arrive. */
class CameraRecordCache {
    /** Read a server_camera_state value: the record, or null for None/absent; throws TypeError if malformed. */
    static parse(value: unknown): CameraRecord | null {
        if (value == null) {
            return null;
        }
        if (typeof value !== 'object') {
            throw new TypeError(`camera record is not an object`);
        }
        const obj = value as Record<string, unknown>;
        return {
            position: CameraRecordCache.#vector(obj.position, 3, 'position'),
            focalPoint: CameraRecordCache.#vector(obj.focalPoint, 3, 'focalPoint'),
            viewUp: CameraRecordCache.#vector(obj.viewUp, 3, 'viewUp'),
            clippingRange: CameraRecordCache.#vector(obj.clippingRange, 2, 'clippingRange'),
            parallelProjection: CameraRecordCache.#boolean(
                obj.parallelProjection,
                'parallelProjection'
            ),
            viewAngle: CameraRecordCache.#number(obj.viewAngle, 'viewAngle'),
            parallelScale: CameraRecordCache.#number(obj.parallelScale, 'parallelScale'),
        };
    }

    static #vector(value: unknown, length: number, name: string): readonly number[] {
        if (
            !Array.isArray(value) ||
            value.length !== length ||
            !value.every((v) => typeof v === 'number')
        ) {
            throw new TypeError(`camera record ${name} is not ${length} numbers`);
        }
        return [...value];
    }

    static #boolean(value: unknown, name: string): boolean {
        if (typeof value !== 'boolean') {
            throw new TypeError(`camera record ${name} is not a boolean`);
        }
        return value;
    }

    static #number(value: unknown, name: string): number {
        if (typeof value !== 'number') {
            throw new TypeError(`camera record ${name} is not a number`);
        }
        return value;
    }

    /** Overwrite all seven fields. */
    setRecord(record: CameraRecord): void {
        this.#fields = { ...record };
    }

    /** Overwrite one field. */
    set<K extends keyof CameraRecord>(field: K, value: CameraRecord[K]): void {
        this.#fields = { ...this.#fields, [field]: value };
    }

    /** One field, or undefined if never written. */
    field<K extends keyof CameraRecord>(field: K): CameraRecord[K] | undefined {
        return this.#fields[field];
    }

    /** All seven fields, or null while any is unknown. */
    record(): CameraRecord | null {
        const f = this.#fields;
        if (
            f.position === undefined ||
            f.focalPoint === undefined ||
            f.viewUp === undefined ||
            f.clippingRange === undefined ||
            f.parallelProjection === undefined ||
            f.viewAngle === undefined ||
            f.parallelScale === undefined
        ) {
            return null;
        }
        return f as CameraRecord;
    }

    #fields: Partial<CameraRecord> = {};
}

/** IRenderer for server rendering: frames come from the canvas, writes go to the server, reads come from a cache. */
export class ServerRenderer implements IRenderer {
    /** Watch server_camera_state on state, show canvas, and send every mutation through triggerSender. */
    constructor(
        canvas: IServerCanvas,
        state: ServerStateSource,
        triggerSender: TrameTriggerSender
    ) {
        this.#canvas = canvas;
        this.#triggerSender = triggerSender;
        this.#sends = new SceneTriggerSends(triggerSender);
        this.domElement = canvas.element;
        // `watch` also calls back at once with the key's current value.
        this.#unwatch = state.watch([SERVER_CAMERA_STATE_KEY], this.#onCameraState);
        this.#removeClickListener = canvas.addClickListener(this.#onCanvasClick);
        this.#removeResizeListener = canvas.addResizeListener(this.#onCanvasResize);
    }

    readonly #canvas: IServerCanvas;
    readonly #triggerSender: TrameTriggerSender;
    readonly #sends: SceneTriggerSends;
    readonly #unwatch: () => void;
    readonly #removeClickListener: () => void;
    readonly #removeResizeListener: () => void;
    readonly #camera = new CameraRecordCache();
    readonly #cameraChangedListeners = new Map<() => void, (state: VisorCameraState) => void>();
    readonly #viewerClicks = new ViewerClickDispatcher();
    #crossSectionVisible = false;
    #boundingBoxVisible = false;
    #edgesVisible = false;
    #crossSectionOrigin: readonly number[] | null = null;
    #crossSectionNormal: readonly number[] | null = null;

    /**
     * Take the server's camera record into the cache. Nothing is sent from
     * here: the record is also the echo of this client's own camera writes,
     * and answering it would loop.
     */
    #onCameraState = (value: unknown): void => {
        let record: CameraRecord | null;
        try {
            record = CameraRecordCache.parse(value);
        } catch (err) {
            console.error('[VISOR] server_camera_state malformed', err);
            return;
        }
        if (record == null) {
            return;
        }
        this.#camera.setRecord(record);
        this.#fireCameraChanged();
    };

    /** Pick the part under a click on the last frame, then tell every viewer-clicked listener once. */
    #onCanvasClick = (click: CanvasClick): void => {
        const frameSize = this.#canvas.frameSize;
        if (frameSize == null) {
            console.error('[VISOR] click dropped: no frame drawn yet');
            return;
        }
        // The frame is the render window as last drawn, in device pixels.
        const x = ServerRenderer.#framePixel(click.normX, frameSize.width);
        const y = ServerRenderer.#framePixel(click.normY, frameSize.height);
        this.#viewerClicks
            .dispatchAsync(click, async () =>
                ServerRenderer.#parsePickResult(await this.#triggerSender('pick_part_at', { x, y }))
            )
            .catch((err) => console.error('[VISOR] pick_part_at failed', err));
    };

    /** Give every camera listener the snapshot at the canvas's new height. */
    #onCanvasResize = (): void => {
        this.#fireCameraChanged();
    };

    /** The render-window pixel under a normalised coordinate on an axis of the given size, clamped to the window. */
    static #framePixel(norm: number, size: number): number {
        return Math.min(Math.max(Math.floor(norm * size), 0), size - 1);
    }

    /** Read a pick_part_at result: the node id, or null for no part; throws TypeError otherwise. */
    static #parsePickResult(value: unknown): NodeId | null {
        if (value === null || Number.isInteger(value)) {
            return value as NodeId | null;
        }
        throw new TypeError(`pick_part_at result is not a node id or null: ${String(value)}`);
    }

    /** Write one camera field and tell the camera listeners. */
    #writeCamera<K extends keyof CameraRecord>(field: K, value: CameraRecord[K]): void {
        this.#camera.set(field, value);
        this.#fireCameraChanged();
    }

    /** Give every camera listener the full snapshot, once all seven fields are known. */
    #fireCameraChanged(): void {
        const record = this.#camera.record();
        if (record == null) {
            return;
        }
        const snapshot = ServerRenderer.#snapshot(record, this.#viewPortHeight());
        for (const callback of this.#cameraChangedListeners.values()) {
            callback(snapshot);
        }
    }

    /** The render window's height in device pixels: CSS height times pixel ratio, truncated as the server sizes it. */
    #viewPortHeight(): number {
        return Math.floor(this.domElement.clientHeight * (window.devicePixelRatio ?? 1));
    }

    /** The full snapshot: record plus distance, orthographic, orthographicScale, unitsPerPixel, viewPortHeight. */
    static #snapshot(record: CameraRecord, viewPortHeight: number): VisorCameraState {
        const [px, py, pz] = record.position;
        const [fx, fy, fz] = record.focalPoint;
        return {
            distance: Math.hypot(px - fx, py - fy, pz - fz),
            orthographic: record.parallelProjection,
            orthographicScale: record.parallelScale,
            // unitsPerPixel is only accurate in orthographic mode
            unitsPerPixel: record.parallelScale / (0.5 * viewPortHeight),
            viewPortHeight,
            position: record.position,
            focalPoint: record.focalPoint,
            viewUp: record.viewUp,
            clippingRange: record.clippingRange,
            parallelProjection: record.parallelProjection,
            viewAngle: record.viewAngle,
            parallelScale: record.parallelScale,
        };
    }

    // ---- Canvas / lifecycle -------------------------------------------------
    readonly domElement: HTMLDivElement;

    /** The server renders after every write it receives. */
    async renderAsync(): Promise<void> {}

    /** The canvas reports its own size to the server and tells this renderer, which refreshes the camera listeners. */
    async resizeAsync(): Promise<void> {}

    dispose(): void {
        this.#unwatch();
        this.#removeClickListener();
        this.#removeResizeListener();
        this.#cameraChangedListeners.clear();
        this.#viewerClicks.clear();
    }

    // ---- Camera ---------------------------------------------------------------
    async getCameraStateAsync(): Promise<VisorCameraState> {
        const record = this.#camera.record();
        if (record == null) {
            throw new CameraStateUnavailableError();
        }
        return ServerRenderer.#snapshot(record, this.#viewPortHeight());
    }

    // The camera setters only seed the cache from delivered state; the
    // server already holds the camera they carry, so they send nothing.

    async setCameraPositionAsync(position: readonly number[]): Promise<void> {
        this.#writeCamera('position', [...position]);
    }

    async setCameraFocalPointAsync(focalPoint: readonly number[]): Promise<void> {
        this.#writeCamera('focalPoint', [...focalPoint]);
    }

    async setCameraViewUpAsync(viewUp: readonly number[]): Promise<void> {
        this.#writeCamera('viewUp', [...viewUp]);
    }

    async setCameraClippingRangeAsync(clippingRange: readonly number[]): Promise<void> {
        this.#writeCamera('clippingRange', [...clippingRange]);
    }

    async setCameraParallelProjectionAsync(enabled: boolean): Promise<void> {
        this.#writeCamera('parallelProjection', enabled);
    }

    async setCameraViewAngleAsync(angle: number): Promise<void> {
        this.#writeCamera('viewAngle', angle);
    }

    async setCameraParallelScaleAsync(scale: number): Promise<void> {
        this.#writeCamera('parallelScale', scale);
    }

    // ---- Subscriptions ----------------------------------------------------
    addCameraChangedListener(callback: (state: VisorCameraState) => void): () => void {
        const remover = () => {
            this.#cameraChangedListeners.delete(remover);
        };
        this.#cameraChangedListeners.set(remover, callback);
        return remover;
    }

    addFrameRenderedListener(callback: (fps: number) => void): () => void {
        return this.#canvas.addFrameListener(callback);
    }

    /** Add a listener called once per click with the part pick_part_at found under it, or null; returns its remover. */
    addViewerClickedListener(
        callback: (
            nodeId: NodeId | null,
            ctrlKey: boolean,
            shiftKey: boolean,
            normX: number,
            normY: number
        ) => void
    ): () => void {
        return this.#viewerClicks.addListener(callback);
    }

    // ---- Per-part visual state -----------------------------------------------
    // The server applies each of these through the paired send below; there
    // is no client-side object to write.

    async setDiffuseColorRgbAsync(
        _nodeId: NodeId,
        _r: number,
        _g: number,
        _b: number,
        _selected: boolean
    ): Promise<void> {}

    async resetDiffuseColorAsync(
        _nodeId: NodeId,
        _defaultRgb: readonly number[],
        _selected: boolean
    ): Promise<void> {}

    async setVisibilityAsync(_nodeId: NodeId, _visible: boolean): Promise<void> {}

    async setSelectedAsync(
        _nodeId: NodeId,
        _selected: boolean,
        _currentDiffuseRgb: readonly number[]
    ): Promise<void> {}

    async setOpacityAsync(_nodeId: NodeId, _opacity: number): Promise<void> {}

    async setColorVariableAsync(
        _nodeId: NodeId,
        _descriptor: ColorVariableDescriptor
    ): Promise<void> {}

    async clearColorVariableAsync(_nodeId: NodeId): Promise<void> {}

    async setScalarRangeAsync(_nodeId: NodeId, _min: number, _max: number): Promise<void> {}

    // ---- Per-part mutations routed to the server -----------------------------
    async sendPartVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void> {
        await this.#sends.sendPartVisibilityAsync(nodeId, visible);
    }

    async sendPartOpacityAsync(nodeId: NodeId, opacity: number): Promise<void> {
        await this.#sends.sendPartOpacityAsync(nodeId, opacity);
    }

    async sendPartDiffuseColorAsync(
        nodeId: NodeId,
        diffuseRgb: readonly number[] | null
    ): Promise<void> {
        await this.#sends.sendPartDiffuseColorAsync(nodeId, diffuseRgb);
    }

    async sendPartSelectedAsync(nodeId: NodeId, selected: boolean): Promise<void> {
        await this.#sends.sendPartSelectedAsync(nodeId, selected);
    }

    async sendPartColorVariableAsync(
        nodeId: NodeId,
        descriptor: ColorVariableDescriptor
    ): Promise<void> {
        await this.#sends.sendPartColorVariableAsync(nodeId, descriptor);
    }

    async sendClearPartColorVariableAsync(nodeId: NodeId): Promise<void> {
        await this.#sends.sendClearPartColorVariableAsync(nodeId);
    }

    // ---- View-level widgets ---------------------------------------------------
    // A setter called with no argument toggles the cached flag and sends the
    // value it settled on: the payload is always absolute.

    async setCrossSectionVisibilityAsync(visible?: boolean): Promise<void> {
        const resolved = visible ?? !this.#crossSectionVisible;
        this.#crossSectionVisible = resolved;
        await this.#sends.sendCrossSectionVisibilityAsync(resolved);
    }

    async applyCrossSectionVisibilityAsync(visible: boolean): Promise<void> {
        this.#crossSectionVisible = visible;
    }

    isCrossSectionVisible(): boolean {
        return this.#crossSectionVisible;
    }

    async getCrossSectionOriginAsync(): Promise<readonly number[]> {
        if (this.#crossSectionOrigin == null) {
            throw new CrossSectionStateUnavailableError();
        }
        return this.#crossSectionOrigin;
    }

    async getCrossSectionNormalAsync(): Promise<readonly number[]> {
        if (this.#crossSectionNormal == null) {
            throw new CrossSectionStateUnavailableError();
        }
        return this.#crossSectionNormal;
    }

    /** Seeds the cache only; the server already holds the plane. */
    async setCrossSectionOriginAsync(origin: readonly number[]): Promise<void> {
        this.#crossSectionOrigin = [...origin];
    }

    /** Seeds the cache only; the server already holds the plane. */
    async setCrossSectionNormalAsync(normal: readonly number[]): Promise<void> {
        this.#crossSectionNormal = [...normal];
    }

    async setBoundingBoxVisibilityAsync(visible?: boolean): Promise<void> {
        const resolved = visible ?? !this.#boundingBoxVisible;
        this.#boundingBoxVisible = resolved;
        await this.#sends.sendBoundingBoxVisibilityAsync(resolved);
    }

    async applyBoundingBoxVisibilityAsync(visible: boolean): Promise<void> {
        this.#boundingBoxVisible = visible;
    }

    isBoundingBoxVisible(): boolean {
        return this.#boundingBoxVisible;
    }

    async setOrthographicModeAsync(enable?: boolean): Promise<void> {
        const resolved = enable ?? !this.isOrthographicEnabled();
        this.#writeCamera('parallelProjection', resolved);
        await this.#sends.sendProjectionAsync(resolved);
    }

    async applyOrthographicModeAsync(enable: boolean): Promise<void> {
        this.#writeCamera('parallelProjection', enable);
    }

    /** The cached camera's parallelProjection; false until delivered. */
    isOrthographicEnabled(): boolean {
        return this.#camera.field('parallelProjection') ?? false;
    }

    async setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void> {
        const resolved = visible ?? !this.#edgesVisible;
        this.#edgesVisible = resolved;
        await this.#sends.sendEdgesVisibleAsync(resolved);
    }

    async applyEdgeVisibilityGlobalAsync(visible: boolean): Promise<void> {
        this.#edgesVisible = visible;
    }

    areEdgesVisibleGlobally(): boolean {
        return this.#edgesVisible;
    }

    // ---- Picking ------------------------------------------------------------
    async pickGeometryAsync(
        _normX: number,
        _normY: number,
        _mode: GeometryPickMode
    ): Promise<PickGeometryResult> {
        throw new GeometryPickingUnavailableError();
    }

    /** Rejects rather than doing nothing, so a caller that skips the pick fails loudly. */
    async setGeometryHighlightAsync(_result: PickGeometryResult): Promise<void> {
        throw new GeometryPickingUnavailableError();
    }

    /** There is never a highlight to clear. */
    clearGeometryHighlight(): void {}
}
