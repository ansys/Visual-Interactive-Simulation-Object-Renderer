import { renderHook, waitFor } from '@testing-library/react';
import type { Trame } from '@kitware/trame/src/trame.js';
import { useServerVtk } from '../hooks/useServerVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';

/**
 * The server-mode frontend sends each mutation through the probe's session
 * as one positional payload, the shape every server trigger takes.
 *
 * Expected values are hand-written literals.
 */

/** A minimal v4 scene-details payload as a server-rendering server delivers it: no renderer annotation. */
function sceneDetailsPayload() {
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
            rendererAnnotation: null,
        },
    };
}

const trigger = jest.fn(async (name: string, ..._args: unknown[]) =>
    name === 'get_visor_scene_details_json' ? sceneDetailsPayload() : undefined
);
const session = {
    subscribe: () => ({ unsubscribe: () => {} }),
    call: async () => undefined,
};
const trame = {
    client: { getConnection: () => ({ getSession: () => session }) },
    // Calls back at once with no values, as trame's watch does before any state arrives.
    state: {
        watch: (_keys: string[], fn: (...values: unknown[]) => void) => {
            fn();
            return () => {};
        },
    },
    trigger,
} as unknown as Trame;

const args = {
    host: 'localhost',
    port: 8080,
    aspectRatio: 1,
    pixelDensity: 1000,
    basePath: '',
} as VisorArgs;

const globals = globalThis as unknown as { ResizeObserver: unknown };
let originalResizeObserver: unknown;

beforeEach(() => {
    trigger.mockClear();
    originalResizeObserver = globals.ResizeObserver;
    globals.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
});

afterEach(() => {
    globals.ResizeObserver = originalResizeObserver;
});

describe('useServerVtk build', () => {
    test('a toolbar toggle reaches the server as one positional payload', async () => {
        const { result } = renderHook(() => useServerVtk(trame, args));
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());

        await result.current.visorFrontend!.setBoundingBoxVisibilityAsync(true);

        expect(
            trigger.mock.calls.filter(([name]) => name === 'set_bounding_box_visibility')
        ).toStrictEqual([['set_bounding_box_visibility', [{ visible: true }]]]);
    });
});
