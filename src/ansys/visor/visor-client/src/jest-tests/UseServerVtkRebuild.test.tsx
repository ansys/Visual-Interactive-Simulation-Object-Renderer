import { act, renderHook, waitFor } from '@testing-library/react';
import type { Trame } from '@kitware/trame/src/trame.js';
import { useServerVtk } from '../hooks/useServerVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';

/**
 * In server mode every change of scene_version rebuilds the frontend from
 * freshly fetched scene details, one build at a time, and the replaced
 * build's renderer stops listening.
 *
 * Expected values are hand-written literals.
 */

/** A minimal v4 scene-details payload as a server-rendering server delivers it. */
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

type Watcher = (...values: unknown[]) => void;

/** A trame state that records its live watchers per key and notifies them on demand. */
class RecordingState {
    readonly #watchers = new Map<string, Set<Watcher>>();

    watch(keys: string[], fn: Watcher): () => void {
        for (const key of keys) {
            if (!this.#watchers.has(key)) {
                this.#watchers.set(key, new Set());
            }
            this.#watchers.get(key)!.add(fn);
        }
        fn();
        return () => {
            for (const key of keys) {
                this.#watchers.get(key)?.delete(fn);
            }
        };
    }

    liveWatchers(key: string): number {
        return this.#watchers.get(key)?.size ?? 0;
    }

    notify(key: string): void {
        for (const fn of [...(this.#watchers.get(key) ?? [])]) {
            fn(1);
        }
    }
}

/** Fetches of the scene details, each held until the test answers it. */
let fetchAnswers: ((payload: unknown) => void)[];
let triggerNames: string[];
let state: RecordingState;
let trame: Trame;

const session = {
    subscribe: () => ({ unsubscribe: () => {} }),
    call: async () => undefined,
};

function argsWith(darkMode: boolean | undefined): VisorArgs {
    return {
        host: 'localhost',
        port: 8080,
        aspectRatio: 1,
        pixelDensity: 1000,
        basePath: '',
        darkMode,
    } as VisorArgs;
}

/** Answer the n-th scene-details fetch and let the build it feeds run. */
async function answerFetchAsync(n: number, payload: unknown): Promise<void> {
    await waitFor(() => expect(fetchAnswers.length).toBeGreaterThan(n));
    await act(async () => {
        fetchAnswers[n](payload);
    });
}

const globals = globalThis as unknown as { ResizeObserver: unknown; fetch: unknown };
let originalResizeObserver: unknown;
let originalFetch: unknown;

beforeEach(() => {
    fetchAnswers = [];
    triggerNames = [];
    state = new RecordingState();
    trame = {
        client: { getConnection: () => ({ getSession: () => session }) },
        state,
        trigger: async (name: string) => {
            triggerNames.push(name);
            if (name !== 'get_visor_scene_details_json') {
                return undefined;
            }
            return new Promise((resolve) => fetchAnswers.push(resolve));
        },
    } as unknown as Trame;
    originalResizeObserver = globals.ResizeObserver;
    globals.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
    // A dark theme makes the frontend load the theme stylesheets.
    originalFetch = globals.fetch;
    globals.fetch = async () => ({ text: async () => '' });
});

afterEach(() => {
    globals.ResizeObserver = originalResizeObserver;
    globals.fetch = originalFetch;
});

describe('useServerVtk rebuild', () => {
    test('a burst of scene_version changes during a build ends in one more build', async () => {
        const { result } = renderHook(() => useServerVtk(trame, argsWith(undefined)));
        act(() => {
            state.notify('scene_version');
            state.notify('scene_version');
        });
        await answerFetchAsync(0, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        const first = result.current.visorFrontend;

        await answerFetchAsync(1, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBe(first));

        expect(fetchAnswers.length).toBe(2);
    });

    test('a rebuild leaves one live server_camera_state watcher', async () => {
        const { result } = renderHook(() => useServerVtk(trame, argsWith(undefined)));
        await answerFetchAsync(0, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        const first = result.current.visorFrontend;

        act(() => state.notify('scene_version'));
        await answerFetchAsync(1, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBe(first));

        expect(state.liveWatchers('server_camera_state')).toBe(1);
    });

    test('a mismatch on rebuild sets schemaMismatchError and keeps the frontend', async () => {
        const { result } = renderHook(() => useServerVtk(trame, argsWith(undefined)));
        await answerFetchAsync(0, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        const first = result.current.visorFrontend;

        act(() => state.notify('scene_version'));
        await answerFetchAsync(1, { schemaVersion: 3 });
        await waitFor(() => expect(result.current.schemaMismatchError).not.toBeNull());

        expect(result.current.visorFrontend).toBe(first);
    });

    test('each build sends set_dark_theme before its fetch', async () => {
        const { result } = renderHook(() => useServerVtk(trame, argsWith(true)));
        await answerFetchAsync(0, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBeNull());
        const first = result.current.visorFrontend;

        act(() => state.notify('scene_version'));
        await answerFetchAsync(1, sceneDetailsPayload());
        await waitFor(() => expect(result.current.visorFrontend).not.toBe(first));

        expect(
            triggerNames.filter(
                (name) => name === 'set_dark_theme' || name === 'get_visor_scene_details_json'
            )
        ).toEqual([
            'set_dark_theme',
            'get_visor_scene_details_json',
            'set_dark_theme',
            'get_visor_scene_details_json',
        ]);
    });

    test('unmounting during a build with a request pending fetches no more', async () => {
        const { unmount } = renderHook(() => useServerVtk(trame, argsWith(undefined)));
        await waitFor(() => expect(fetchAnswers.length).toBe(1));
        act(() => state.notify('scene_version'));

        unmount();
        await act(async () => {
            fetchAnswers[0](sceneDetailsPayload());
        });

        expect(fetchAnswers.length).toBe(1);
    });

    test('a build that fails after creating its renderer disposes it', async () => {
        // The theme stylesheet load runs after the renderer exists, so its failure fails the build there.
        globals.fetch = async () => {
            throw new Error('stylesheet unavailable');
        };
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        try {
            renderHook(() => useServerVtk(trame, argsWith(true)));
            await answerFetchAsync(0, sceneDetailsPayload());
            await waitFor(() =>
                expect(consoleError).toHaveBeenCalledWith(
                    '[VISOR] server-mode rebuild failed',
                    expect.any(Error)
                )
            );

            expect(state.liveWatchers('server_camera_state')).toBe(0);
        } finally {
            consoleError.mockRestore();
        }
    });
});
