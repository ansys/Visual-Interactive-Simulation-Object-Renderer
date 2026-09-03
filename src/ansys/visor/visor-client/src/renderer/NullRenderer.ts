import {
    ColorVariableDescriptor,
    GeometryPickMode,
    IRenderer,
    NodeId,
    PickGeometryResult,
    VisorCameraState,
} from './IRenderer';
import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';

const NULL_CAMERA_STATE: VisorCameraState = {
    distance: 0,
    orthographic: false,
    orthographicScale: 1,
    unitsPerPixel: 1,
    viewPortHeight: 0,
    position: [0, 0, 0],
    focalPoint: [0, 0, 0],
    viewUp: [0, 0, 0],
    clippingRange: [0, 0],
    parallelProjection: false,
    viewAngle: 30,
    parallelScale: 1,
};

/**
 * No-op implementation of IRenderer. Used to confirm the interface is
 * buildable and to serve as a placeholder renderer until a concrete one is
 * wired in. Nothing imports this yet.
 */
export class NullRenderer implements IRenderer {
    readonly domElement: HTMLDivElement = document.createElement('div');

    attachSceneGraph(_sceneGraph: VisorSceneNodeExtended): void {
        // no-op
    }

    async renderAsync(): Promise<void> {
        // no-op
    }

    async resizeAsync(): Promise<void> {
        // no-op
    }

    dispose(): void {
        // no-op
    }

    async getCameraStateAsync(): Promise<VisorCameraState> {
        return NULL_CAMERA_STATE;
    }

    async setCameraPositionAsync(_position: readonly number[]): Promise<void> {
        // no-op
    }

    async setCameraFocalPointAsync(_focalPoint: readonly number[]): Promise<void> {
        // no-op
    }

    async setCameraViewUpAsync(_viewUp: readonly number[]): Promise<void> {
        // no-op
    }

    async setCameraClippingRangeAsync(_clippingRange: readonly number[]): Promise<void> {
        // no-op
    }

    async setCameraParallelProjectionAsync(_enabled: boolean): Promise<void> {
        // no-op
    }

    async setCameraViewAngleAsync(_angle: number): Promise<void> {
        // no-op
    }

    async setCameraParallelScaleAsync(_scale: number): Promise<void> {
        // no-op
    }

    async setCameraStateAsync(_state: VisorCameraState): Promise<void> {
        // no-op
    }

    async resetCameraAsync(_bounds?: readonly number[]): Promise<void> {
        // no-op
    }

    addCameraChangedListener(_callback: (state: VisorCameraState) => void): () => void {
        return () => {
            // no-op unsubscribe
        };
    }

    addFrameRenderedListener(_callback: (fps: number) => void): () => void {
        return () => {
            // no-op unsubscribe
        };
    }

    addViewerClickedListener(
        _callback: (
            nodeId: NodeId | null,
            ctrlKey: boolean,
            shiftKey: boolean,
            normX: number,
            normY: number
        ) => void
    ): () => void {
        return () => {
            // no-op unsubscribe
        };
    }

    async setDiffuseColorRgbAsync(
        _nodeId: NodeId,
        _r: number,
        _g: number,
        _b: number,
        _selected: boolean
    ): Promise<void> {
        // no-op
    }

    async resetDiffuseColorAsync(
        _nodeId: NodeId,
        _defaultRgb: readonly number[],
        _selected: boolean
    ): Promise<void> {
        // no-op
    }

    async setVisibilityAsync(_nodeId: NodeId, _visible: boolean): Promise<void> {
        // no-op
    }

    async setSelectedAsync(
        _nodeId: NodeId,
        _selected: boolean,
        _currentDiffuseRgb: readonly number[]
    ): Promise<void> {
        // no-op
    }

    async setEdgeVisibilityAsync(_nodeId: NodeId, _edgeVisible: boolean): Promise<void> {
        // no-op
    }

    async setOpacityAsync(_nodeId: NodeId, _opacity: number): Promise<void> {
        // no-op
    }

    async setColorVariableAsync(
        _nodeId: NodeId,
        _descriptor: ColorVariableDescriptor
    ): Promise<void> {
        // no-op
    }

    async clearColorVariableAsync(_nodeId: NodeId): Promise<void> {
        // no-op
    }

    async setScalarRangeAsync(_nodeId: NodeId, _min: number, _max: number): Promise<void> {
        // no-op
    }

    // ---- Per-part mutations routed to the server -----------------------------
    // A renderer with no server behind it sends nothing. These are no-ops for
    // the same reason every other method here is: the null renderer has no
    // transport, exactly as it has no wasm objects.

    async sendPartVisibilityAsync(_nodeId: NodeId, _visible: boolean): Promise<void> {
        // no-op
    }

    async sendPartOpacityAsync(_nodeId: NodeId, _opacity: number): Promise<void> {
        // no-op
    }

    async sendPartDiffuseColorAsync(
        _nodeId: NodeId,
        _diffuseRgb: readonly number[] | null
    ): Promise<void> {
        // no-op
    }

    async sendPartSelectedAsync(_nodeId: NodeId, _selected: boolean): Promise<void> {
        // no-op
    }

    async sendPartColorVariableAsync(
        _nodeId: NodeId,
        _descriptor: ColorVariableDescriptor
    ): Promise<void> {
        // no-op
    }

    async sendClearPartColorVariableAsync(_nodeId: NodeId): Promise<void> {
        // no-op
    }

    async setCrossSectionVisibilityAsync(_visible?: boolean): Promise<void> {
        // no-op
    }

    isCrossSectionVisible(): boolean {
        return false;
    }

    async updateCrossSectionBoundsAsync(): Promise<void> {
        // no-op
    }

    async getCrossSectionOriginAsync(): Promise<readonly number[]> {
        return [0, 0, 0];
    }

    async getCrossSectionNormalAsync(): Promise<readonly number[]> {
        return [0, 0, 1];
    }

    async setCrossSectionOriginAsync(_origin: readonly number[]): Promise<void> {
        // no-op
    }

    async setCrossSectionNormalAsync(_normal: readonly number[]): Promise<void> {
        // no-op
    }

    async setBoundingBoxVisibilityAsync(_visible?: boolean): Promise<void> {
        // no-op
    }

    isBoundingBoxVisible(): boolean {
        return false;
    }

    async updateBoundingBoxBoundsAsync(): Promise<void> {
        // no-op
    }

    async setOrthographicModeAsync(_enable?: boolean): Promise<void> {
        // no-op
    }

    isOrthographicEnabled(): boolean {
        return false;
    }

    async setEdgeVisibilityGlobalAsync(_visible?: boolean): Promise<void> {
        // no-op
    }

    areEdgesVisibleGlobally(): boolean {
        return false;
    }

    async toggleFullScreenAsync(): Promise<void> {
        // no-op
    }

    async pickGeometryAsync(
        _normX: number,
        _normY: number,
        _mode: GeometryPickMode
    ): Promise<PickGeometryResult> {
        return { found: false };
    }

    async setGeometryHighlightAsync(_result: PickGeometryResult): Promise<void> {
        // no-op
    }

    clearGeometryHighlight(): void {
        // no-op
    }
}
