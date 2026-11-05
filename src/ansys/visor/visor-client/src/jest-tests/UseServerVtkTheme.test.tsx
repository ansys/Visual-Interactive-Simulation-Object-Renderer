import { renderHook, waitFor } from '@testing-library/react';
import type { Trame } from '@kitware/trame/src/trame.js';
import { useServerVtk } from '../hooks/useServerVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';

/**
 * In server mode the page's theme reaches the server once, after the canvas
 * has subscribed to the frame stream, so the frame the theme change renders
 * is not lost, and before the scene details are fetched, so they carry it.
 * With no theme from the page, nothing is sent.  The fetch is answered with
 * an outdated schema, which ends the build before any renderer exists.
 *
 * Expected values are hand-written literals.
 */

const events: string[] = [];
const trigger = jest.fn(async (name: string, ..._args: unknown[]) => {
    events.push(name);
    return name === 'get_visor_scene_details_json' ? { schemaVersion: 3 } : undefined;
});
const session = {
    subscribe: (topic: string) => {
        events.push(`subscribe ${topic}`);
        return { unsubscribe: () => {} };
    },
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

const globals = globalThis as unknown as { ResizeObserver: unknown };
let originalResizeObserver: unknown;

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

beforeEach(() => {
    events.length = 0;
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

describe('useServerVtk theme', () => {
    test('a darkMode prop is sent once, after the canvas subscribes', async () => {
        renderHook(() => useServerVtk(trame, argsWith(true)));
        await waitFor(() => expect(events).toContain('get_visor_scene_details_json'));

        expect(trigger.mock.calls.filter(([name]) => name === 'set_dark_theme')).toStrictEqual([
            ['set_dark_theme', [{ dark: true }]],
        ]);
        expect(events).toEqual([
            'subscribe trame.rca.topic.stream',
            'set_dark_theme',
            'get_visor_scene_details_json',
        ]);
        expect(
            trigger.mock.calls.filter(([name]) => name === 'get_visor_scene_details_json')
        ).toStrictEqual([['get_visor_scene_details_json']]);
    });

    test('no darkMode prop sends no set_dark_theme', async () => {
        renderHook(() => useServerVtk(trame, argsWith(undefined)));
        await waitFor(() => expect(events).toContain('get_visor_scene_details_json'));

        expect(events).not.toContain('set_dark_theme');
    });
});
