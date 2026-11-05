import { RefObject, useRef } from 'react';

/** Arguments the host page passes on window.__visorArgs, after defaults. */
export type VisorArgs = {
    host: string;
    port: number;
    aspectRatio: number;
    pixelDensity: number;
    darkMode: boolean;
    basePath: string;
};

/** Read window.__visorArgs once, fill defaults, validate, and return the same object on every render. */
export function useVisorArgs(): VisorArgs {
    const visorArgs: RefObject<VisorArgs> = useRef(null!);
    if (visorArgs.current == null) {
        // Get current args object from window.
        // If the args object was not found on
        // the window, create a new object.
        const args = (visorArgs.current = (window as any).__visorArgs ?? {});
        // Delete args object from window if it existed there.
        // BHB update 2025-11-21: don't delete the args object here,
        // as they might actually need to be preserved across App.tsx remounts.
        // Need to investigate.
        // delete (window as any).__visorArgs;
        // Set default values for args if any were not set.
        args.host ??= location.hostname;
        if (args.port == null) {
            if (location.port === '') {
                args.port = location.protocol === 'https:' ? 443 : 80;
            } else {
                args.port = parseInt(location.port);
            }
        }
        args.aspectRatio ??= 800 / 600;
        args.pixelDensity ??= 1000;
        args.basePath ??= '';
        // Sanity-check each argument's value.
        if ((typeof args.host as any) !== 'string' || args.host === '') {
            throw new Error(`host must be a non-empty string`);
        } else if ((typeof args.port as any) !== 'number' || args.port <= 0) {
            throw new Error(`port must be a number greater than 0`);
        } else if ((typeof args.aspectRatio as any) !== 'number' || args.aspectRatio <= 0) {
            throw new Error(`aspectRatio must be a number greater than 0`);
        } else if ((typeof args.pixelDensity as any) !== 'number' || args.pixelDensity <= 0) {
            throw new Error(`pixelDensity must be a number greater than 0`);
        }
    }
    return visorArgs.current;
}
