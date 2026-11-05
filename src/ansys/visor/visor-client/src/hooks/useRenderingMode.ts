import { useEffect, useState } from 'react';
import { Trame } from '@kitware/trame/src/trame.js';
import { trameWebSocketUrl } from '../trameWebSocketUrl';

/** The rendering_mode wire values. */
export type RenderingMode = 'client' | 'server';

/** Raised when the server's rendering_mode is missing or not a known wire value. */
export class UnknownRenderingModeError extends Error {
    constructor(value: unknown) {
        super(`Unknown rendering_mode: ${JSON.stringify(value) ?? String(value)}`);
        this.name = `UnknownRenderingModeError`;
        this.value = value;
    }

    readonly value: unknown;
}

/** Map a rendering_mode state value to a mode; throws UnknownRenderingModeError for anything else. */
export function parseRenderingMode(value: unknown): RenderingMode {
    if (value === 'client' || value === 'server') {
        return value;
    }
    throw new UnknownRenderingModeError(value);
}

/** The probe's outcome: exactly one of mode and error is set once it settles; trame is set in server mode only. */
export type RenderingModeProbe = Readonly<{
    mode: RenderingMode | null;
    trame: Trame | null;
    error: Error | null;
}>;

/** Connect once on the page's ws/wss scheme, read rendering_mode, and keep the session only in server mode. */
export function useRenderingMode(host: string, port: number): RenderingModeProbe {
    const [probe, setProbe] = useState<RenderingModeProbe>({
        mode: null,
        trame: null,
        error: null,
    });

    useEffect(() => {
        // Under StrictMode the effect runs twice in development: each run owns
        // its own connection, and a cancelled run drops its result.
        let cancelled = false;
        const trame = new Trame();
        (async () => {
            try {
                await trame.connect({
                    application: 'trame',
                    sessionURL: trameWebSocketUrl(host, port),
                });
                if (cancelled) {
                    trame.disconnect();
                    return;
                }
                const mode = parseRenderingMode(trame.state?.get('rendering_mode'));
                if (mode === 'client') {
                    // The client-mode scene opens its own connection.
                    trame.disconnect();
                    setProbe({ mode, trame: null, error: null });
                } else {
                    setProbe({ mode, trame, error: null });
                }
            } catch (err) {
                trame.disconnect();
                if (!cancelled) {
                    const error = err instanceof Error ? err : new Error(String(err));
                    setProbe({ mode: null, trame: null, error });
                }
            }
        })();
        return () => {
            cancelled = true;
            trame.disconnect();
        };
    }, [host, port]);

    return probe;
}
