import { renderHook, waitFor } from '@testing-library/react';
import {
    parseRenderingMode,
    UnknownRenderingModeError,
    useRenderingMode,
} from '../hooks/useRenderingMode';

/**
 * The probe reads `rendering_mode` from one trame connection, keeps that
 * connection only when the server renders, and reports anything other than
 * the two wire values as a named error.
 *
 * Expected values are hand-written literals.
 */

const mockProbe = {
    renderingMode: undefined as unknown,
    trame: null as null | {
        connect: jest.Mock;
        disconnect: jest.Mock;
        state: { get: (key: string) => unknown };
    },
};

jest.mock('@kitware/trame/src/trame.js', () => ({
    Trame: jest.fn().mockImplementation(() => {
        mockProbe.trame = {
            connect: jest.fn(async () => ({})),
            disconnect: jest.fn(),
            state: {
                get: (key: string) =>
                    key === 'rendering_mode' ? mockProbe.renderingMode : undefined,
            },
        };
        return mockProbe.trame;
    }),
}));

beforeEach(() => {
    mockProbe.renderingMode = undefined;
    mockProbe.trame = null;
});

describe('parseRenderingMode', () => {
    test('maps each wire value to its mode', () => {
        expect(parseRenderingMode('client')).toBe('client');
        expect(parseRenderingMode('server')).toBe('server');
    });

    test.each([['local'], [undefined], ['SERVER']])(
        'rejects %p with UnknownRenderingModeError carrying the value',
        (value) => {
            let thrown: unknown = null;
            try {
                parseRenderingMode(value);
            } catch (err) {
                thrown = err;
            }
            expect(thrown).toBeInstanceOf(UnknownRenderingModeError);
            expect((thrown as UnknownRenderingModeError).value).toBe(value);
        }
    );
});

describe('useRenderingMode', () => {
    test('client mode disconnects the probe and hands on no session', async () => {
        mockProbe.renderingMode = 'client';

        const { result } = renderHook(() => useRenderingMode('localhost', 8080));
        await waitFor(() => expect(result.current.mode).toBe('client'));

        expect(mockProbe.trame!.disconnect).toHaveBeenCalledTimes(1);
        expect(result.current.trame).toBeNull();
    });

    test('server mode keeps the probe connection', async () => {
        mockProbe.renderingMode = 'server';

        const { result } = renderHook(() => useRenderingMode('localhost', 8080));
        await waitFor(() => expect(result.current.mode).toBe('server'));

        expect(mockProbe.trame!.disconnect).not.toHaveBeenCalled();
        expect(result.current.trame).toBe(mockProbe.trame);
    });

    test('an unknown mode is reported as an error and the probe disconnected', async () => {
        mockProbe.renderingMode = 'local';

        const { result } = renderHook(() => useRenderingMode('localhost', 8080));
        await waitFor(() => expect(result.current.error).not.toBeNull());

        expect(result.current.error).toBeInstanceOf(UnknownRenderingModeError);
        expect(result.current.mode).toBeNull();
        expect(result.current.trame).toBeNull();
        expect(mockProbe.trame!.disconnect).toHaveBeenCalledTimes(1);
    });
});
