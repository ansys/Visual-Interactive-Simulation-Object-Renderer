import { useEffect, useState } from 'react';
import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import type { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { RCA_AREA_NAME, ServerCanvas, type RcaSession } from '../rca/ServerCanvas';
import type { VisorArgs } from './useVisorArgs';

/** What the server-mode hook gives App. */
export type ServerVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
    serverCanvas: ServerCanvas | null;
}>;

/** Over the probe's session: stream frames and send the page theme; idle when trame is null. */
export function useServerVtk(trame: Trame | null, visorArgs: VisorArgs): ServerVtk {
    const [serverCanvas, setServerCanvas] = useState<ServerCanvas | null>(null);

    useEffect(() => {
        if (trame == null) {
            return;
        }
        // Subscribed before anything can make the server render, so the frame
        // that render produces reaches the canvas.
        const canvas = new ServerCanvas(sessionOf(trame), RCA_AREA_NAME);
        setServerCanvas(canvas);
        (async () => {
            if (visorArgs.darkMode != null) {
                await sendDarkThemeAsync(trame, visorArgs.darkMode);
            }
        })();
        return () => {
            canvas.dispose();
            setServerCanvas(null);
        };
    }, [trame]);

    return { visorFrontend: null, schemaMismatchError: null, serverCanvas };
}

/** The wslink session of a connected trame client. */
function sessionOf(trame: Trame): RcaSession {
    const session = trame.client?.getConnection()?.getSession();
    if (session == null) {
        throw new Error(`trame has no open session`);
    }
    return session;
}

/** Tell the server the theme the page shows, so its rendered background matches; a failed send is logged. */
async function sendDarkThemeAsync(trame: Trame, dark: boolean): Promise<void> {
    try {
        await trame.trigger('set_dark_theme', [{ dark }]);
    } catch (err) {
        console.error('[VISOR] set_dark_theme send failed', err);
    }
}
