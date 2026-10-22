import {
    CameraOrigin,
    ColorVariableDescriptor,
    GeometryPickMode,
    IRenderer,
    NodeId,
    PickGeometryResult,
    TrameTriggerSender,
    VisorCameraState,
} from './IRenderer';
import VtkScene from '../wasm/VtkScene';
import { WasmNodeHandles, WasmRendererAnnotation } from './RendererAnnotation';
import { CrossSectionWidget } from '../widgets/crossSectionWidget.ts';
import { BoundingBoxWidget } from '../widgets/boundingBoxWidget.ts';
import { OrthographicWidget } from '../widgets/orthographicWidget.ts';
import { EdgesWidget } from '../widgets/edgesWidget.ts';
import { SceneTriggerSends } from './SceneTriggerSends';

const SELECTION_TINT_RGB: Readonly<number[]> = [0 / 255, 62 / 255, 111 / 255];

/**
 * Local-wasm implementation of {@link IRenderer}. Method bodies here are
 * moved verbatim (extraction, not a rewrite) from `VisorFrontend.tsx` and its
 * widget classes. `VisorFrontend.tsx` still has its own copies of all of
 * this — nothing imports `WasmRenderer` yet.
 */
export class WasmRenderer implements IRenderer {
    private constructor(
        vtkScene: VtkScene,
        annotation: WasmRendererAnnotation,
        triggerSender: TrameTriggerSender | null
    ) {
        this.#vtkScene = vtkScene;
        this.#sends = new SceneTriggerSends(triggerSender);

        const wasmPlaneId = annotation.widgets.crossSectionPlaneId;
        const wasmPlaneRepId = annotation.widgets.crossSectionPlaneRepresentationId;
        const wasmPlaneWidgetId = annotation.widgets.crossSectionPlaneWidgetId;

        // Both maps are built once, here, from the annotation's per-node
        // handles. The actorIdToNodeId map is used to translate the wasm pick result
        // to a nodeId. The nodeIdToHandles map is used to look up the handles for
        // any nodeId when applying per-node visual state.
        for (const [nodeIdKey, handles] of Object.entries(annotation.nodes)) {
            const nodeId: NodeId = Number(nodeIdKey);
            this.#actorIdToNodeId.set(handles.actorId, nodeId);
            this.#nodeIdToHandles.set(nodeId, handles);
        }

        this.#crossSectionWidget = new CrossSectionWidget(vtkScene, {
            planeWasmId: wasmPlaneId,
            representationWasmId: wasmPlaneRepId,
            widgetWasmId: wasmPlaneWidgetId,
        });
        this.#orthographicWidget = new OrthographicWidget(vtkScene);
        this.#boundingBoxWidget = new BoundingBoxWidget(vtkScene, {
            outlineActorId: annotation.widgets.boundingBoxOutlineActorId,
            axesActorId: annotation.widgets.boundingBoxAxesActorId,
            outlineQueryId: annotation.widgets.boundingBoxOutlineActorId,
        });
        this.#edgesWidget = new EdgesWidget(this);

        const planeWidget = vtkScene.getVtkObject(wasmPlaneWidgetId);
        planeWidget.observe('InteractionEvent', this.#crossSectionWidget.interactionHandler);

        /**
         * Report the settled plane to the server, once per handle release.
         *
         * `EndInteractionEvent`, not `InteractionEvent`: the per-motion event
         * fires many times across one drag, and a report bound to it passes
         * every other gate and floods the trigger channel. The end event
         * fires once when the handle is released, and not on a camera orbit.
         *
         * A bare click on the handle with no drag also releases it, so it
         * also reports -- carrying the plane the server already holds. That
         * arrival is accepted as idempotent and is deliberately **not**
         * suppressed: there is no last-sent cache and no debounce here, so a
         * drag that produced no arrival means the observer is not wired,
         * rather than meaning a filter swallowed it.
         *
         * The values come from `getOriginAsync` / `getNormalAsync`, which read
         * the **representation** -- the object the handle actually moved, and
         * the one whose values the client would otherwise save. The payload
         * keys are `origin` and `normal`, snake_case and unaliased, three
         * floats each, which is what the server's payload model requires.
         *
         * Deliberately not defensive: `SceneTriggerSends` already
         * swallows and logs a send rejection, and a `catch` around the two
         * reads would turn a broken representation read into a silent
         * no-report, which is the one outcome that reads as "the observer was
         * never wired".
         */
        planeWidget.observe('EndInteractionEvent', async () => {
            const origin = await this.#crossSectionWidget.getOriginAsync();
            const normal = await this.#crossSectionWidget.getNormalAsync();
            await this.#sends.sendCrossSectionPlaneAsync(origin, normal);
        });

        /**
         * Attribute an orientation-widget camera move to the user.
         *
         * Clicking a face of the cube moves the camera entirely inside wasm,
         * with no DOM input `CameraGestureTracker` can see, so without this
         * mark the move settles as `programmatic` and the server drops it.
         * `EndInteractionEvent` (not `InteractionEvent`) fires once per
         * interaction rather than per animation frame. The callback only
         * marks the gesture; the report itself is still the settle's,
         * unchanged, via `sync_camera`.
         */
        const orientationWidget = vtkScene.getVtkObject(annotation.widgets.orientationWidgetId);
        orientationWidget.observe('EndInteractionEvent', () => {
            vtkScene.noteWidgetGesture();
        });

        this.domElement = vtkScene.canvasDiv;
    }

    static async createAsync(
        vtkScene: VtkScene,
        annotation: WasmRendererAnnotation,
        triggerSender: TrameTriggerSender | null = null
    ): Promise<WasmRenderer> {
        const renderer = new WasmRenderer(vtkScene, annotation, triggerSender);
        await renderer.#seedOrthographicFlagAsync();
        return renderer;
    }

    /**
     * Read the orthographic flag out of the wasm camera, once, at construction.
     *
     * The only async seam in building a renderer: without it, the
     * orthographic widget's cached flag starts `false` regardless of what the
     * camera says. `createAsync` runs after the wasm state fetch completes,
     * so this reads the *delivered* camera -- making `isOrthographicEnabled()`
     * a projection of server state, not an independent source.
     *
     * Deliberately not defensive: swallowing a failure here would leave the
     * flag at `false` against a parallel camera -- the exact save-corrupting
     * fault this seed exists to remove -- invisibly to every gate.
     */
    async #seedOrthographicFlagAsync(): Promise<void> {
        await this.#orthographicWidget.seedFromCameraAsync();
    }

    readonly #vtkScene: VtkScene;
    readonly #sends: SceneTriggerSends;
    readonly #actorIdToNodeId = new Map<number, NodeId>();
    readonly #nodeIdToHandles = new Map<NodeId, WasmNodeHandles>();
    readonly #crossSectionWidget: CrossSectionWidget;
    readonly #orthographicWidget: OrthographicWidget;
    readonly #boundingBoxWidget: BoundingBoxWidget;
    readonly #edgesWidget: EdgesWidget;

    // ---- Canvas / lifecycle -------------------------------------------------
    readonly domElement: HTMLDivElement;

    async renderAsync(): Promise<void> {
        this.#vtkScene.render();
    }

    async resizeAsync(): Promise<void> {
        await this.#vtkScene.resizeAsync();
        this.#vtkScene.render();
    }

    dispose(): void {
        this.#vtkScene.clearObserversAndEventListeners();
    }

    // ---- Camera ---------------------------------------------------------------
    async getCameraStateAsync(): Promise<VisorCameraState> {
        const camera = this.#vtkScene.camera;
        const parallelScale = await camera.GetParallelScale();
        const viewPortHeight = await this.#vtkScene.getViewPortHeightAsync();
        const parallelProjectionRaw = await camera.GetParallelProjection();
        return {
            distance: await camera.GetDistance(),
            orthographic: !!parallelProjectionRaw,
            orthographicScale: parallelScale,
            // unitsPerPixel is only accurate in orthographic mode
            unitsPerPixel: parallelScale / (0.5 * viewPortHeight),
            viewPortHeight,
            position: await camera.GetPosition(),
            focalPoint: await camera.GetFocalPoint(),
            viewUp: await camera.GetViewUp(),
            clippingRange: await camera.GetClippingRange(),
            parallelProjection: parallelProjectionRaw === 1,
            viewAngle: await camera.GetViewAngle(),
            parallelScale,
        };
    }

    async setCameraPositionAsync(position: readonly number[]): Promise<void> {
        await this.#vtkScene.camera.setPosition(position);
    }

    async setCameraFocalPointAsync(focalPoint: readonly number[]): Promise<void> {
        await this.#vtkScene.camera.setFocalPoint(focalPoint);
    }

    async setCameraViewUpAsync(viewUp: readonly number[]): Promise<void> {
        await this.#vtkScene.camera.setViewUp(viewUp);
    }

    async setCameraClippingRangeAsync(clippingRange: readonly number[]): Promise<void> {
        await this.#vtkScene.camera.setClippingRange(clippingRange);
    }

    async setCameraParallelProjectionAsync(enabled: boolean): Promise<void> {
        await this.#vtkScene.camera.setParallelProjection(enabled ? 1 : 0);
    }

    async setCameraViewAngleAsync(angle: number): Promise<void> {
        await this.#vtkScene.camera.setViewAngle(angle);
    }

    async setCameraParallelScaleAsync(scale: number): Promise<void> {
        await this.#vtkScene.camera.setParallelScale(scale);
    }

    // ---- Subscriptions ----------------------------------------------------
    addCameraChangedListener(callback: (state: VisorCameraState) => void): () => void {
        return this.#vtkScene.addCameraChangedListener(async (_) => {
            callback(await this.getCameraStateAsync());
        });
    }

    /**
     * Fires once per gesture, after the last camera change has stopped changing for
     * CAMERA_SETTLE_MS, with the origin of that change. The callback receives
     * the origin only; read the camera with getCameraStateAsync if needed.
     * A `gesture` report is the user's own camera; a `programmatic` one is a
     * camera the application or the server applied.
     */
    addCameraSettledListener(callback: (origin: CameraOrigin) => void): () => void {
        return this.#vtkScene.addCameraSettledListener(callback);
    }

    addFrameRenderedListener(callback: (fps: number) => void): () => void {
        return this.#vtkScene.addFrameRenderedListener(async (fps) => {
            callback(fps);
        });
    }

    addViewerClickedListener(
        callback: (
            nodeId: NodeId | null,
            ctrlKey: boolean,
            shiftKey: boolean,
            normX: number,
            normY: number
        ) => void
    ): () => void {
        return this.#vtkScene.addViewerClickedListener(
            async (actorWasmId, ctrlKey, shiftKey, normX, normY) => {
                const nodeId = this.#actorIdToNodeId.get(actorWasmId) ?? null;
                callback(nodeId, ctrlKey, shiftKey, normX, normY);
            }
        );
    }

    // ---- Per-part visual state -----------------------------------------------
    async #applyDiffuseColorAsync(
        nodeId: NodeId,
        colorRgb: readonly number[],
        selected: boolean
    ): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmProperty = this.#vtkScene.getVtkObject(handles.propertyId);
        if (selected) {
            await wasmProperty.SetAmbientColor(SELECTION_TINT_RGB);
            await wasmProperty.SetDiffuse(0.5);
            await wasmProperty.SetAmbient(0.5);
        } else {
            await wasmProperty.SetDiffuse(1);
            await wasmProperty.SetAmbient(0);
        }
        await wasmProperty.SetDiffuseColor(...colorRgb);
    }

    async setDiffuseColorRgbAsync(
        nodeId: NodeId,
        r: number,
        g: number,
        b: number,
        selected: boolean
    ): Promise<void> {
        await this.#applyDiffuseColorAsync(nodeId, [r, g, b], selected);
    }

    async resetDiffuseColorAsync(
        nodeId: NodeId,
        defaultRgb: readonly number[],
        selected: boolean
    ): Promise<void> {
        await this.#applyDiffuseColorAsync(nodeId, defaultRgb, selected);
    }

    async setVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmActor = this.#vtkScene.getVtkObject(handles.actorId);
        await wasmActor.SetVisibility(visible ? 1 : 0);
    }

    async setSelectedAsync(
        nodeId: NodeId,
        selected: boolean,
        currentDiffuseRgb: readonly number[]
    ): Promise<void> {
        await this.#applyDiffuseColorAsync(nodeId, currentDiffuseRgb, selected);
    }

    /** The id of every node the annotation gave handles for. */
    nodeIds(): IterableIterator<NodeId> {
        return this.#nodeIdToHandles.keys();
    }

    /** Show or hide one node's edges; the edges widget fans the global toggle out through this. */
    async setEdgeVisibilityAsync(nodeId: NodeId, edgeVisible: boolean): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const rgb = [0, 0, 0];
        const wasmProperty = this.#vtkScene.getVtkObject(handles.propertyId);
        await wasmProperty.SetEdgeColor(rgb);
        if (edgeVisible) {
            await wasmProperty.EdgeVisibilityOn();
        } else {
            await wasmProperty.EdgeVisibilityOff();
        }
    }

    async setOpacityAsync(nodeId: NodeId, opacity: number): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmProperty = this.#vtkScene.getVtkObject(handles.propertyId);
        await wasmProperty.SetOpacity(opacity);
    }

    /** Configure the part's mapper to colour by the descriptor's array; it maps through the table served with the mapper. */
    async setColorVariableAsync(
        nodeId: NodeId,
        descriptor: ColorVariableDescriptor
    ): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmMapper = this.#vtkScene.getVtkObject(handles.mapperId);
        if (descriptor.variableType === 'POINT') {
            await wasmMapper.SetScalarModeToUsePointFieldData();
        } else {
            await wasmMapper.SetScalarModeToUseCellFieldData();
        }
        await wasmMapper.SetScalarRange(descriptor.min, descriptor.max);
        await wasmMapper.SetColorModeToMapScalars();
        await wasmMapper.ColorByArrayComponent(descriptor.variableName, descriptor.component);
        await wasmMapper.SetScalarVisibility(1);
    }

    async clearColorVariableAsync(nodeId: NodeId): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmMapper = this.#vtkScene.getVtkObject(handles.mapperId);
        await wasmMapper.SetScalarVisibility(0);
    }

    async setScalarRangeAsync(nodeId: NodeId, min: number, max: number): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmMapper = this.#vtkScene.getVtkObject(handles.mapperId);
        await wasmMapper.SetScalarRange(min, max);
    }

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

    // ---- View-level widgets -------------------------------------------------
    /**
     * The four methods below report to the server *after* the local write,
     * reading their own widget back rather than forwarding the argument they
     * were given -- required, not stylistic: the toolbar calls all four with
     * **no argument** (`Panel_BottomMiddle.tsx`), so each widget resolves the
     * absent argument by negating its own cached flag, and only it knows what
     * it settled on. The read-back uses the same getter `getAppStateAsync`
     * does, so the value sent and the value saved cannot disagree.
     *
     * Every payload is absolute, never a toggle or delta, so a send that is
     * suppressed, duplicated, or reordered is harmless.
     */
    async setCrossSectionVisibilityAsync(visible?: boolean): Promise<void> {
        await this.#crossSectionWidget.setVisibilityAsync(visible);
        await this.#sends.sendCrossSectionVisibilityAsync(this.isCrossSectionVisible());
    }

    isCrossSectionVisible(): boolean {
        return this.#crossSectionWidget.enabled;
    }

    async applyCrossSectionVisibilityAsync(visible: boolean): Promise<void> {
        await this.#crossSectionWidget.setVisibilityAsync(visible);
    }

    async getCrossSectionOriginAsync(): Promise<readonly number[]> {
        return await this.#crossSectionWidget.getOriginAsync();
    }

    async getCrossSectionNormalAsync(): Promise<readonly number[]> {
        return await this.#crossSectionWidget.getNormalAsync();
    }

    async setCrossSectionOriginAsync(origin: readonly number[]): Promise<void> {
        await this.#crossSectionWidget.setOriginAsync(origin as number[]);
    }

    async setCrossSectionNormalAsync(normal: readonly number[]): Promise<void> {
        await this.#crossSectionWidget.setNormalAsync(normal as number[]);
    }

    async setBoundingBoxVisibilityAsync(visible?: boolean): Promise<void> {
        await this.#boundingBoxWidget.setVisibilityAsync(visible);
        await this.#sends.sendBoundingBoxVisibilityAsync(this.isBoundingBoxVisible());
    }

    isBoundingBoxVisible(): boolean {
        return this.#boundingBoxWidget.enabled;
    }

    async applyBoundingBoxVisibilityAsync(visible: boolean): Promise<void> {
        await this.#boundingBoxWidget.setVisibilityAsync(visible);
    }

    async setOrthographicModeAsync(enable?: boolean): Promise<void> {
        await this.#orthographicWidget.setOrthographicModeAsync(enable);
        await this.#sends.sendProjectionAsync(this.isOrthographicEnabled());
    }

    isOrthographicEnabled(): boolean {
        return this.#orthographicWidget.enabled;
    }

    async applyOrthographicModeAsync(enable: boolean): Promise<void> {
        await this.#orthographicWidget.setOrthographicModeAsync(enable);
    }

    async setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void> {
        await this.#edgesWidget.setEdgesVisibleAsync(visible);
        await this.#sends.sendEdgesVisibleAsync(this.#edgesWidget.enabled);
    }

    areEdgesVisibleGlobally(): boolean {
        return this.#edgesWidget.enabled;
    }

    async applyEdgeVisibilityGlobalAsync(visible: boolean): Promise<void> {
        await this.#edgesWidget.setEdgesVisibleAsync(visible);
    }

    // ---- Picking ------------------------------------------------------------
    async pickGeometryAsync(
        normX: number,
        normY: number,
        mode: GeometryPickMode
    ): Promise<PickGeometryResult> {
        return (await this.#vtkScene.pickGeometryAsync(normX, normY, mode)) as PickGeometryResult;
    }

    async setGeometryHighlightAsync(result: PickGeometryResult): Promise<void> {
        await this.#vtkScene.setGeometryHighlightAsync(result);
    }

    clearGeometryHighlight(): void {
        this.#vtkScene.clearGeometryHighlight();
    }
}
