import {
    AppliedCameraState,
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
import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { CrossSectionWidget } from '../widgets/crossSectionWidget.ts';
import { BoundingBoxWidget } from '../widgets/boundingBoxWidget.ts';
import { OrthographicWidget } from '../widgets/orthographicWidget.ts';
import { FullscreenWidget } from '../widgets/fullscreenWidget.ts';
import { EdgesWidget } from '../widgets/edgesWidget.ts';

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
        this.#triggerSender = triggerSender;

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

        // Widgets that only need vtkScene are built here. BoundingBoxWidget and
        // EdgesWidget need the live scene graph and are built in attachSceneGraph.
        this.#crossSectionWidget = new CrossSectionWidget(vtkScene, {
            planeWasmId: wasmPlaneId,
            representationWasmId: wasmPlaneRepId,
            widgetWasmId: wasmPlaneWidgetId,
        });
        this.#orthographicWidget = new OrthographicWidget(vtkScene);
        this.#fullscreenWidget = new FullscreenWidget();

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
         * Deliberately not defensive: `#sendWidgetTriggerAsync` already
         * swallows and logs a send rejection, and a `catch` around the two
         * reads would turn a broken representation read into a silent
         * no-report, which is the one outcome that reads as "the observer was
         * never wired".
         */
        planeWidget.observe('EndInteractionEvent', async () => {
            await this.#sendWidgetTriggerAsync('sync_cross_section_plane', {
                origin: await this.#crossSectionWidget.getOriginAsync(),
                normal: await this.#crossSectionWidget.getNormalAsync(),
            });
        });

        // Bounding-box ids are stashed for attachSceneGraph, which is the
        // point at which the live sceneGraph (needed by BoundingBoxWidget)
        // becomes available.
        this.#wasmBoundingBoxActorId = annotation.widgets.boundingBoxOutlineActorId;
        this.#wasmBoundingBoxAxesActorId = annotation.widgets.boundingBoxAxesActorId;
        this.#boundingBoxBoxAlgorithmWasmId = annotation.widgets.boundingBoxAlgorithmId;

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
    readonly #triggerSender: TrameTriggerSender | null;
    readonly #actorIdToNodeId = new Map<number, NodeId>();
    readonly #nodeIdToHandles = new Map<NodeId, WasmNodeHandles>();
    readonly #crossSectionWidget: CrossSectionWidget;
    readonly #orthographicWidget: OrthographicWidget;
    readonly #fullscreenWidget: FullscreenWidget;
    readonly #wasmBoundingBoxActorId: number;
    readonly #wasmBoundingBoxAxesActorId: number;
    readonly #boundingBoxBoxAlgorithmWasmId: number;
    #boundingBoxWidget: BoundingBoxWidget | null = null;
    #edgesWidget: EdgesWidget | null = null;

    #requireSceneGraphAttached(methodName: string): void {
        if (this.#boundingBoxWidget == null || this.#edgesWidget == null) {
            throw new Error(
                `WasmRenderer.${methodName} called before attachSceneGraph(). ` +
                    'VisorFrontend must call attachSceneGraph immediately after CreateVisorSceneGraph.'
            );
        }
    }

    // ---- Canvas / lifecycle -------------------------------------------------
    readonly domElement: HTMLDivElement;

    attachSceneGraph(sceneGraph: VisorSceneNodeExtended): void {
        this.#boundingBoxWidget = new BoundingBoxWidget(this.#vtkScene, sceneGraph, {
            outlineActorId: this.#wasmBoundingBoxActorId,
            axesActorId: this.#wasmBoundingBoxAxesActorId,
            boxAlgorithmWasmId: this.#boundingBoxBoxAlgorithmWasmId,
            outlineQueryId: this.#wasmBoundingBoxActorId,
        });
        this.#edgesWidget = new EdgesWidget(sceneGraph, this);
    }

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

    async setCameraStateAsync(state: AppliedCameraState): Promise<void> {
        // Sequential, not Promise.all, to preserve the observable ordering of
        // camera events any FPS/camera-changed listener sees (§11).
        await this.setCameraPositionAsync(state.position);
        await this.setCameraFocalPointAsync(state.focalPoint);
        await this.setCameraViewUpAsync(state.viewUp);
        await this.setCameraClippingRangeAsync(state.clippingRange);
        await this.setCameraParallelProjectionAsync(state.parallelProjection);
        await this.setCameraViewAngleAsync(state.viewAngle);
        await this.setCameraParallelScaleAsync(state.parallelScale);
    }

    async resetCameraAsync(bounds?: readonly number[]): Promise<void> {
        if (bounds != null) {
            await this.#vtkScene.renderer.ResetCamera(bounds);
        } else {
            await this.#vtkScene.renderer.ResetCamera();
        }
    }

    // ---- Subscriptions ----------------------------------------------------
    addCameraChangedListener(callback: (state: VisorCameraState) => void): () => void {
        return this.#vtkScene.addCameraChangedListener(async (_) => {
            callback(await this.getCameraStateAsync());
        });
    }

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

    async setColorVariableAsync(
        nodeId: NodeId,
        descriptor: ColorVariableDescriptor
    ): Promise<void> {
        const handles = this.#nodeIdToHandles.get(nodeId);
        if (handles == null) {
            return;
        }
        const wasmMapper = this.#vtkScene.getVtkObject(handles.mapperId);
        if (descriptor.spectrumType === 'POINT') {
            await wasmMapper.SetScalarModeToUsePointFieldData();
        } else {
            await wasmMapper.SetScalarModeToUseCellFieldData();
        }
        await wasmMapper.SetScalarRange(descriptor.min, descriptor.max);
        await wasmMapper.SetColorModeToMapScalars();
        await wasmMapper.ColorByArrayComponent(descriptor.spectrumName, descriptor.component);
        await wasmMapper.SetScalarVisibility(1);
        // Force creation of LUT if not already done. (Alternatively, after 9.5.20250802.dev0, you can call mapper.SetLookupTable(null))
        await wasmMapper.CreateDefaultLookupTable();
        const lut = await wasmMapper.GetLookupTable();
        await lut.SetHueRange(0.667, 0.0);
        await lut.SetVectorModeToMagnitude();
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
    /**
     * Send one per-part payload to its server trigger.
     *
     * No sender injected -> no-op. This is the state every non-browser context
     * is in, and it is deliberate rather than defensive: the renderer is
     * constructible without a transport.
     *
     * A rejection is logged and swallowed, never rethrown. These sends run
     * inside UI handlers that behaved a certain way before this call existed,
     * and both stacks currently apply the same mutation independently, so a
     * transport failure must not change what the user sees or break an
     * interaction. The catch is deliberately unnarrowed: any rejection, of any
     * shape, is a failed send. The log line below is therefore the *only*
     * signal that a send failed -- the render will look correct either way --
     * so its prefix is fixed and greppable, and it names both the trigger and
     * the node so a failure can be attributed without a debugger.
     */
    async #sendTriggerAsync(
        triggerName: string,
        nodeId: NodeId,
        payload: Record<string, unknown>
    ): Promise<void> {
        if (this.#triggerSender == null) {
            return;
        }
        try {
            await this.#triggerSender(triggerName, payload);
        } catch (err) {
            console.error(
                `[VISOR] per-part trigger send failed: trigger='${triggerName}' nodeId=${nodeId}`,
                err
            );
        }
    }

    /**
     * Send one view-level widget payload to its server trigger.
     *
     * Sibling of `#sendTriggerAsync` above; same no-sender/no-op and
     * logged-and-swallowed-rejection rationale, not repeated here.
     *
     * Separate only because a widget trigger has no `nodeId` to name in the
     * error line, so the log prefix here is distinct and greppable on its own.
     */
    async #sendWidgetTriggerAsync(
        triggerName: string,
        payload: Record<string, unknown>
    ): Promise<void> {
        if (this.#triggerSender == null) {
            return;
        }
        try {
            await this.#triggerSender(triggerName, payload);
        } catch (err) {
            console.error(`[VISOR] widget trigger send failed: trigger='${triggerName}'`, err);
        }
    }

    async sendPartVisibilityAsync(nodeId: NodeId, visible: boolean): Promise<void> {
        await this.#sendTriggerAsync('set_part_visibility', nodeId, {
            nodeId,
            visible,
        });
    }

    async sendPartOpacityAsync(nodeId: NodeId, opacity: number): Promise<void> {
        await this.#sendTriggerAsync('set_part_opacity', nodeId, {
            nodeId,
            opacity,
        });
    }

    async sendPartDiffuseColorAsync(
        nodeId: NodeId,
        diffuseRgb: readonly number[] | null
    ): Promise<void> {
        // The key is always present: `diffuseRgb: null` is how a reset is
        // expressed. Omitting it is a different message, and not a valid one.
        await this.#sendTriggerAsync('set_part_diffuse_color', nodeId, {
            nodeId,
            diffuseRgb,
        });
    }

    async sendPartSelectedAsync(nodeId: NodeId, selected: boolean): Promise<void> {
        // No colour crosses this trigger by design; the server reads the
        // part's stored colour from its own record.
        await this.#sendTriggerAsync('set_part_selected', nodeId, {
            nodeId,
            selected,
        });
    }

    async sendPartColorVariableAsync(
        nodeId: NodeId,
        descriptor: ColorVariableDescriptor
    ): Promise<void> {
        // `variableId` is the client-built opaque token, forwarded verbatim;
        // nothing on either side parses it. The association travels as its own
        // typed 'POINT'|'CELL' field, and the array name as its own field,
        // precisely so that no one has to.
        await this.#sendTriggerAsync('set_part_color_variable', nodeId, {
            nodeId,
            variableId: descriptor.spectrumId,
            association: descriptor.spectrumType,
            arrayName: descriptor.spectrumName,
            component: descriptor.component,
            min: descriptor.min,
            max: descriptor.max,
        });
    }

    async sendClearPartColorVariableAsync(nodeId: NodeId): Promise<void> {
        await this.#sendTriggerAsync('clear_part_color_variable', nodeId, {
            nodeId,
        });
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
        await this.#sendWidgetTriggerAsync('set_cross_section_visibility', {
            visible: this.isCrossSectionVisible(),
        });
    }

    isCrossSectionVisible(): boolean {
        return this.#crossSectionWidget.enabled;
    }

    async updateCrossSectionBoundsAsync(): Promise<void> {
        await this.#crossSectionWidget.updateBoundsAsync();
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
        this.#requireSceneGraphAttached('setBoundingBoxVisibilityAsync');
        await this.#boundingBoxWidget!.setVisibilityAsync(visible);
        await this.#sendWidgetTriggerAsync('set_bounding_box_visibility', {
            visible: this.isBoundingBoxVisible(),
        });
    }

    isBoundingBoxVisible(): boolean {
        this.#requireSceneGraphAttached('isBoundingBoxVisible');
        return this.#boundingBoxWidget!.enabled;
    }

    async updateBoundingBoxBoundsAsync(): Promise<void> {
        this.#requireSceneGraphAttached('updateBoundingBoxBoundsAsync');
        await this.#boundingBoxWidget!.updateBoundsAsync();
    }

    async setOrthographicModeAsync(enable?: boolean): Promise<void> {
        await this.#orthographicWidget.setOrthographicModeAsync(enable);
        await this.#sendWidgetTriggerAsync('set_projection', {
            parallel: this.isOrthographicEnabled(),
        });
    }

    isOrthographicEnabled(): boolean {
        return this.#orthographicWidget.enabled;
    }

    async setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void> {
        this.#requireSceneGraphAttached('setEdgeVisibilityGlobalAsync');
        await this.#edgesWidget!.setEdgesVisibleAsync(visible);
        await this.#sendWidgetTriggerAsync('set_edges_visible', {
            visible: this.#edgesWidget!.enabled,
        });
    }

    areEdgesVisibleGlobally(): boolean {
        this.#requireSceneGraphAttached('areEdgesVisibleGlobally');
        return this.#edgesWidget!.enabled;
    }

    async toggleFullScreenAsync(): Promise<void> {
        await this.#fullscreenWidget.setFullScreenAsync();
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
