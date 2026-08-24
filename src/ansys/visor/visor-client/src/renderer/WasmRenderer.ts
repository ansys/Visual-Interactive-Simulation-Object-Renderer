import {
    ColorVariableDescriptor,
    GeometryPickMode,
    IRenderer,
    NodeId,
    PickGeometryResult,
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
    private constructor(vtkScene: VtkScene, annotation: WasmRendererAnnotation) {
        this.#vtkScene = vtkScene;

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
        annotation: WasmRendererAnnotation
    ): Promise<WasmRenderer> {
        return new WasmRenderer(vtkScene, annotation);
    }

    readonly #vtkScene: VtkScene;
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
        this.#edgesWidget = new EdgesWidget(sceneGraph);
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

    async setCameraStateAsync(state: VisorCameraState): Promise<void> {
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

    // ---- View-level widgets -------------------------------------------------
    async setCrossSectionVisibilityAsync(visible?: boolean): Promise<void> {
        await this.#crossSectionWidget.setVisibilityAsync(visible);
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
    }

    isOrthographicEnabled(): boolean {
        return this.#orthographicWidget.enabled;
    }

    async setEdgeVisibilityGlobalAsync(visible?: boolean): Promise<void> {
        this.#requireSceneGraphAttached('setEdgeVisibilityGlobalAsync');
        await this.#edgesWidget!.setEdgesVisibleAsync(visible);
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
