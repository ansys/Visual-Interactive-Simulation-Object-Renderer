import { renderHook, waitFor } from '@testing-library/react';
import type { Trame } from '@kitware/trame/src/trame.js';
import { useServerVtk } from '../hooks/useServerVtk';
import type { VisorArgs } from '../hooks/useVisorArgs';

/**
 * In server mode the page's theme reaches the server once, after the canvas
 * has subscribed to the frame stream, so the frame the theme change renders
 * is not lost.  With no theme from the page, nothing is sent.
 *
 * Expected values are hand-written literals.
 */

const events: string[] = [];
const trigger = jest.fn(async (name: string) => {
    events.push(name);
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
        await waitFor(() => expect(trigger).toHaveBeenCalled());

        expect(trigger).toHaveBeenCalledTimes(1);
        expect(trigger).toHaveBeenCalledWith('set_dark_theme', [{ dark: true }]);
        expect(events).toEqual(['subscribe trame.rca.topic.stream', 'set_dark_theme']);
    });

    test('no darkMode prop sends no set_dark_theme', async () => {
        const { result } = renderHook(() => useServerVtk(trame, argsWith(undefined)));
        await waitFor(() => expect(result.current.serverCanvas).not.toBeNull());

        expect(trigger).not.toHaveBeenCalled();
    });
});
