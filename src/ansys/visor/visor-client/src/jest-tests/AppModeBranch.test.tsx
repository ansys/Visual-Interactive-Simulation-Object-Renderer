import { render, waitFor } from '@testing-library/react';
import App from '../App';

/**
 * When the probe reports a streamed mode (server or paraview), the page never
 * starts the client-mode wasm scene: it streams frames over the probe's session
 * instead.
 *
 * Expected values are hand-written literals.
 */

const mockMode = { value: 'server' as 'server' | 'paraview' };
const mockGetInstanceAsync = jest.fn();
const mockSubscribe = jest.fn(() => ({ unsubscribe: () => {} }));
const mockTrame = {
    client: {
        getConnection: () => ({
            getSession: () => ({ subscribe: mockSubscribe, call: async () => undefined }),
        }),
    },
    // Calls back at once with no values, as trame's watch does before any state arrives.
    state: {
        watch: (_keys: string[], fn: (...values: unknown[]) => void) => {
            fn();
            return () => {};
        },
    },
    // The scene-details fetch never answers, so the server frontend is never
    // built: this test is about which scene loads, not what the server sends.
    trigger: () => new Promise(() => {}),
};

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: (...args: unknown[]) => mockGetInstanceAsync(...args) },
}));

jest.mock('../hooks/useRenderingMode', () => ({
    useRenderingMode: () => ({ mode: mockMode.value, trame: mockTrame, error: null }),
}));

const globals = globalThis as unknown as { ResizeObserver: unknown };
let originalResizeObserver: unknown;

beforeEach(() => {
    mockSubscribe.mockClear();
    mockGetInstanceAsync.mockClear();
    originalResizeObserver = globals.ResizeObserver;
    globals.ResizeObserver = class {
        observe() {}
        disconnect() {}
    };
});

afterEach(() => {
    globals.ResizeObserver = originalResizeObserver;
});

describe('App mode branch', () => {
    test.each([['server'], ['paraview']] as const)(
        '%s mode never loads the wasm scene',
        async (mode) => {
            mockMode.value = mode;
            render(<App />);

            await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

            expect(mockGetInstanceAsync).not.toHaveBeenCalled();
        }
    );
});
