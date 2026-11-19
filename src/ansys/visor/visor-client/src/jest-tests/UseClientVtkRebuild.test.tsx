import { act, renderHook, waitFor } from '@testing-library/react';
import { useClientVtk } from '../hooks/useClientVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';
import type { Trame } from '@kitware/trame/src/trame.js';

/**
 * In client mode every structural server update rebuilds the frontend over the
 * same wasm scene, and a data-only update fetches the variable records and keeps
 * it.  A successful rebuild releases the replaced frontend and names the new
 * one on `window.__visorState`; a schema mismatch keeps the current frontend
 * and reports the error.  The scene connects over the session the hook is given.
 *
 * Expected values are hand-written literals.
 */

const mockScene = {
    serverUpdated: null as null | (() => void),
    dataUpdated: null as null | (() => void),
    payloads: [] as unknown[],
    fetches: 0,
    recordsFetches: 0,
    renderers: [] as { liveCanvasClicks: Set<() => void> }[],
    configs: [] as { trame?: unknown }[],
};

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: {
        getInstanceAsync: async (config: { trame?: unknown }) => {
            mockScene.configs.push(config);
            return mockMakeWasmView();
        },
    },
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

/** The client-mode scene connection: keeps the latest listeners, answers each details fetch in turn and counts records fetches. */
function mockMakeWasmView() {
    return {
        trameGetState: () => false,
        clearObserversAndEventListeners: () => {},
        addServerUpdatedListener: (handler: () => void) => {
            mockScene.serverUpdated = handler;
            return () => {};
        },
        addDataUpdatedListener: (listener: () => void) => {
            mockScene.dataUpdated = listener;
        },
        addSetStateListener: () => () => {},
        trameTriggerAsync: async (name: string) => {
            if (name === 'get_visor_scene_details_json') {
                return mockScene.payloads[mockScene.fetches++];
            }
            if (name === 'get_variable_records_json') {
                mockScene.recordsFetches++;
                return '{}';
            }
            return undefined;
        },
        vtkScene: { resizeAsync: async () => undefined },
    };
}

/** A renderer that records the canvas-click listeners still registered on it. */
function mockMakeRenderer() {
    const record = { liveCanvasClicks: new Set<() => void>() };
    mockScene.renderers.push(record);
    return {
        domElement: document.createElement('div'),
        clearGeometryHighlight: () => {},
        addCameraSettledListener: () => () => {},
        addCanvasClickListener: () => {
            const remover = () => {
                record.liveCanvasClicks.delete(remover);
            };
            record.liveCanvasClicks.add(remover);
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

/** The probe's session; the scene connection is mocked, so it is only handed on. */
const TRAME = {} as Trame;

/** Mount the hook and wait for its first frontend. */
async function mountBuiltAsync() {
    const hook = renderHook(() => useClientVtk(ARGS, TRAME));
    await waitFor(() => expect(hook.result.current.visorFrontend).not.toBeNull());
    return hook;
}

/** Let every pending promise chain, including a queued rebuild or refresh, run out. */
async function drain() {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

/** Deliver one server update and let its queued rebuild finish. */
async function serverUpdateAsync() {
    await act(async () => {
        mockScene.serverUpdated!();
        await drain();
    });
}

beforeEach(() => {
    mockScene.serverUpdated = null;
    mockScene.dataUpdated = null;
    mockScene.payloads = [];
    mockScene.fetches = 0;
    mockScene.recordsFetches = 0;
    mockScene.renderers = [];
    mockScene.configs = [];
});

afterEach(() => {
    delete (window as any).__visorState;
});

describe('useClientVtk rebuild', () => {
    test('the scene connects over the session the hook is given', async () => {
        mockScene.payloads = [mockSceneDetailsPayload()];
        await mountBuiltAsync();

        expect(mockScene.configs).toHaveLength(1);
        expect(mockScene.configs[0].trame).toBe(TRAME);
    });
    test('a client rebuild releases the old frontend', async () => {
        mockScene.payloads = [mockSceneDetailsPayload(), mockSceneDetailsPayload()];
        await mountBuiltAsync();

        await serverUpdateAsync();

        expect(mockScene.renderers.length).toBe(2);
        expect(mockScene.renderers[0].liveCanvasClicks.size).toBe(0);
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

    test('a data update fetches the records and does not rebuild', async () => {
        mockScene.payloads = [mockSceneDetailsPayload()];
        const { result } = await mountBuiltAsync();
        const first = result.current.visorFrontend;

        await act(async () => {
            mockScene.dataUpdated!();
            await drain();
        });

        expect(mockScene.recordsFetches).toBe(1);
        expect(mockScene.fetches).toBe(1);
        expect(result.current.visorFrontend).toBe(first);
    });
});
