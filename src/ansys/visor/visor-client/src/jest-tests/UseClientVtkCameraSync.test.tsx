import { act, renderHook, waitFor } from '@testing-library/react';
import { useClientVtk } from '../hooks/useClientVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';
import type { CameraOrigin, VisorCameraState } from '../renderer/IRenderer';

/**
 * The client-mode hook reports each settled camera window to the server from
 * exactly one renderer.  Every renderer it builds sits on the same `VtkScene`,
 * so a reporter left attached across a rebuild reports each later gesture
 * once more, and every one of those reports is individually valid.
 *
 * The doubles stand in for that shared scene: every renderer registers its
 * settle listeners into one map, and a settle fans out to whoever is still
 * registered there.
 *
 * Expected values are hand-written literals.
 */

const mockScene = {
    settledListeners: new Map<() => void, (origin: CameraOrigin) => void>(),
    serverUpdated: null as null | (() => Promise<void>),
    trameTriggerAsync: jest.fn(),
    renderersBuilt: 0,
    settleDuringFirstSeed: false,
};

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: async () => mockMakeWasmView() },
}));

jest.mock('../renderer/WasmRenderer', () => ({
    WasmRenderer: { createAsync: async () => mockMakeRenderer() },
}));

/** Fan one settle out to every listener still registered on the shared scene. */
function mockSettle(origin: CameraOrigin) {
    for (const callback of mockScene.settledListeners.values()) {
        callback(origin);
    }
}

/** A minimal v4 scene-details payload: one root node and a complete wasm annotation. */
function mockSceneDetailsPayload() {
    return {
        schemaVersion: 4,
        ui: {},
        scene: { unit: '', orthographicEnabled: null },
        vtkInfo: {
            sceneGraph: {
                id: 0,
                dataArrays: [],
                name: '',
                isGroupNode: true,
                isActorNode: false,
                nodeType: 'root',
                diffuseColor: [1, 1, 1],
                bounds: [],
                children: [],
            },
            rendererAnnotation: {
                rendererKind: 'wasm',
                nodes: {},
                widgets: {
                    orientationWidgetId: 1,
                    crossSectionPlaneId: 2,
                    crossSectionPlaneWidgetId: 3,
                    crossSectionPlaneRepresentationId: 4,
                    boundingBoxAlgorithmId: 5,
                    boundingBoxOutlineActorId: 6,
                    boundingBoxAxesActorId: 7,
                },
            },
        },
    };
}

/** The client-mode scene connection: keeps the latest server-updated listener and records every trigger. */
function mockMakeWasmView() {
    return {
        trameGetState: () => false,
        clearObserversAndEventListeners: () => {},
        addServerUpdatedListener: (handler: () => Promise<void>) => {
            mockScene.serverUpdated = handler;
            return () => {};
        },
        addSetStateListener: () => () => {},
        trameTriggerAsync: mockScene.trameTriggerAsync,
        vtkScene: { resizeAsync: async () => undefined },
    };
}

function mockCameraSnapshot(): VisorCameraState {
    return {
        distance: 20.0,
        orthographic: false,
        orthographicScale: 21.0,
        unitsPerPixel: 22.0,
        viewPortHeight: 23.0,
        position: [11.0, 12.0, 13.0],
        focalPoint: [14.0, 15.0, 16.0],
        viewUp: [0.0, 1.0, 0.0],
        clippingRange: [17.0, 18.0],
        parallelProjection: false,
        viewAngle: 30.0,
        parallelScale: 19.0,
    };
}

/**
 * A renderer over the shared scene.  `resizeAsync` is the last call the state
 * seed makes; on the first renderer it can fire a settle there, inside the seed.
 */
function mockMakeRenderer() {
    const index = mockScene.renderersBuilt++;
    return {
        domElement: document.createElement('div'),
        addCameraSettledListener: (callback: (origin: CameraOrigin) => void) => {
            const remover = () => {
                mockScene.settledListeners.delete(remover);
            };
            mockScene.settledListeners.set(remover, callback);
            return remover;
        },
        addViewerClickedListener: () => () => {},
        getCameraStateAsync: async () => mockCameraSnapshot(),
        resizeAsync: async () => {
            if (index === 0 && mockScene.settleDuringFirstSeed) {
                mockSettle('programmatic');
            }
        },
    };
}

const ARGS = {
    host: 'localhost',
    port: 8080,
    aspectRatio: 1,
    pixelDensity: 1000,
    basePath: '',
} as VisorArgs;

function syncCameraSendCount(): number {
    return mockScene.trameTriggerAsync.mock.calls.filter((call) => call[0] === 'sync_camera')
        .length;
}

/** Let every pending promise chain, including the reporter's read and send, run out. */
async function drain() {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

beforeEach(() => {
    mockScene.settledListeners.clear();
    mockScene.serverUpdated = null;
    mockScene.renderersBuilt = 0;
    mockScene.settleDuringFirstSeed = false;
    mockScene.trameTriggerAsync.mockReset();
    mockScene.trameTriggerAsync.mockImplementation(async (name: string) =>
        name === 'get_visor_scene_details_json' ? mockSceneDetailsPayload() : undefined
    );
});

afterEach(() => {
    delete (window as any).__visorState;
});

describe('useClientVtk camera sync', () => {
    test('one gesture settle after two rebuilds sends one sync_camera', async () => {
        const { result } = renderHook(() => useClientVtk(ARGS));
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        await act(async () => {
            await mockScene.serverUpdated!();
        });
        await act(async () => {
            await mockScene.serverUpdated!();
        });

        await act(async () => {
            mockSettle('gesture');
            await drain();
        });

        expect(syncCameraSendCount()).toBe(1);
    });

    test('a settle during the first build state seed is reported once', async () => {
        mockScene.settleDuringFirstSeed = true;

        const { result } = renderHook(() => useClientVtk(ARGS));
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        await act(async () => {
            await drain();
        });

        expect(syncCameraSendCount()).toBe(1);
    });
});
