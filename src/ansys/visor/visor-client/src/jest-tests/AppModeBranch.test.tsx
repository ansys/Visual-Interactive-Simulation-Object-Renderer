import { render, waitFor } from '@testing-library/react';
import App from '../App';

/**
 * When the probe reports server rendering, the page never starts the
 * client-mode wasm scene: it streams frames over the probe's session instead.
 *
 * Expected values are hand-written literals.
 */

const mockGetInstanceAsync = jest.fn();
const mockSubscribe = jest.fn(() => ({ unsubscribe: () => {} }));
const mockTrame = {
    client: {
        getConnection: () => ({
            getSession: () => ({ subscribe: mockSubscribe, call: async () => undefined }),
        }),
    },
    trigger: async () => undefined,
};

jest.mock('../wasm/RemoteVtkScene', () => ({
    __esModule: true,
    default: { getInstanceAsync: (...args: unknown[]) => mockGetInstanceAsync(...args) },
}));

jest.mock('../hooks/useRenderingMode', () => ({
    useRenderingMode: () => ({ mode: 'server', trame: mockTrame, error: null }),
}));

const globals = globalThis as unknown as { ResizeObserver: unknown };
let originalResizeObserver: unknown;

beforeEach(() => {
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
    test('server mode never loads the wasm scene', async () => {
        render(<App />);

        await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

        expect(mockGetInstanceAsync).not.toHaveBeenCalled();
    });
});
