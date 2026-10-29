import { act, renderHook, waitFor } from '@testing-library/react';
import { useClientVtk } from '../hooks/useClientVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';

/**
 * In client mode every server update rebuilds the frontend over the same wasm
 * scene.  A successful rebuild releases the replaced frontend and names the new
 * one on `window.__visorState`; a schema mismatch keeps the current frontend
 * and reports the error.
 *
 * Expected values are hand-written literals.
 */

const mockScene = {
    serverUpdated: null as null | (() => Promise<void>),
    payloads: [] as unknown[],
    fetches: 0,
    renderers: [] as { liveViewerClicks: Set<() => void> }[],
};

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: async () => mockMakeWasmView() },
}));

jest.mock('../renderer/WasmRenderer', () => ({
    WasmRenderer: { createAsync: async () => mockMakeRenderer() },
}));

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

/** The client-mode scene connection: keeps the latest server-updated listener and answers each fetch in turn. */
function mockMakeWasmView() {
    return {
        trameGetState: () => false,
        clearObserversAndEventListeners: () => {},
        addServerUpdatedListener: (handler: () => Promise<void>) => {
            mockScene.serverUpdated = handler;
            return () => {};
        },
        addSetStateListener: () => () => {},
        trameTriggerAsync: async (name: string) =>
            name === 'get_visor_scene_details_json'
                ? mockScene.payloads[mockScene.fetches++]
                : undefined,
        vtkScene: { resizeAsync: async () => undefined },
    };
}

/** A renderer that records the viewer-click listeners still registered on it. */
function mockMakeRenderer() {
    const record = { liveViewerClicks: new Set<() => void>() };
    mockScene.renderers.push(record);
    return {
        domElement: document.createElement('div'),
        clearGeometryHighlight: () => {},
        addCameraSettledListener: () => () => {},
        addViewerClickedListener: () => {
            const remover = () => {
                record.liveViewerClicks.delete(remover);
            };
            record.liveViewerClicks.add(remover);
            return remover;
        },
        getCameraStateAsync: async () => undefined,
        resizeAsync: async () => undefined,
    };
}

const ARGS = {
    host: 'localhost',
    port: 8080,
    aspectRatio: 1,
    pixelDensity: 1000,
    basePath: '',
} as VisorArgs;

/** Mount the hook and wait for its first frontend. */
async function mountBuiltAsync() {
    const hook = renderHook(() => useClientVtk(ARGS, true));
    await waitFor(() => expect(hook.result.current.visorFrontend).not.toBeNull());
    return hook;
}

/** Deliver one server update and let its rebuild finish. */
async function serverUpdateAsync() {
    await act(async () => {
        await mockScene.serverUpdated!();
    });
}

beforeEach(() => {
    mockScene.serverUpdated = null;
    mockScene.payloads = [];
    mockScene.fetches = 0;
    mockScene.renderers = [];
});

afterEach(() => {
    delete (window as any).__visorState;
});

describe('useClientVtk rebuild', () => {
    test('a client rebuild releases the old frontend', async () => {
        mockScene.payloads = [mockSceneDetailsPayload(), mockSceneDetailsPayload()];
        await mountBuiltAsync();

        await serverUpdateAsync();

        expect(mockScene.renderers.length).toBe(2);
        expect(mockScene.renderers[0].liveViewerClicks.size).toBe(0);
    });

    test('a mismatch on client rebuild sets schemaMismatchError and keeps the frontend', async () => {
        mockScene.payloads = [mockSceneDetailsPayload(), { schemaVersion: 3 }];
        const { result } = await mountBuiltAsync();
        const first = result.current.visorFrontend;

        await serverUpdateAsync();

        expect(result.current.schemaMismatchError?.payloadVersion).toBe(3);
        expect(result.current.visorFrontend).toBe(first);
    });

    test('after a client rebuild window.__visorState is the new frontend', async () => {
        mockScene.payloads = [mockSceneDetailsPayload(), mockSceneDetailsPayload()];
        const { result } = await mountBuiltAsync();
        const first = result.current.visorFrontend;

        await serverUpdateAsync();

        expect(result.current.visorFrontend).not.toBe(first);
        expect((window as any).__visorState).toBe(result.current.visorFrontend);
    });
});
