import { useEffect, useState } from 'react';
import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { RCA_AREA_NAME, ServerCanvas, type RcaSession } from '../rca/ServerCanvas';
import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { TrameTriggerSender } from '../renderer/IRenderer';
import { buildFrontendAsync } from '../buildFrontendAsync';
import type { VisorArgs } from './useVisorArgs';

/** What the server-mode hook gives App. */
export type ServerVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Over the probe's session: send the page theme, stream frames and build the frontend; idle when trame is null. */
export function useServerVtk(trame: Trame | null, visorArgs: VisorArgs): ServerVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);

    useEffect(() => {
        if (trame == null) {
            return;
        }
        // Under StrictMode the effect runs twice in development: each run
        // disposes only the canvas and renderer it created, and a cancelled
        // run drops its frontend.
        let cancelled = false;
        let renderer: ServerRenderer | null = null;
        const disposeRenderer = () => {
            renderer?.dispose();
            renderer = null;
        };
        // Subscribed before anything can make the server render, so the frame
        // that render produces reaches the canvas.
        const canvas = new ServerCanvas(sessionOf(trame), RCA_AREA_NAME);
        const sender: TrameTriggerSender = (triggerName, payload) =>
            trame.trigger(triggerName, [payload]);
        (async () => {
            if (visorArgs.darkMode != null) {
                await sendDarkThemeAsync(trame, visorArgs.darkMode);
            }
            // No arguments: the trigger takes none, and a sender would pass one.
            const sceneDetailsJson = await trame.trigger('get_visor_scene_details_json');
            let newFrontend: VisorFrontend;
            try {
                newFrontend = await buildFrontendAsync(
                    sceneDetailsJson,
                    async () => {
                        renderer = new ServerRenderer(canvas, stateOf(trame), sender);
                        return renderer;
                    },
                    sender,
                    visorArgs.darkMode
                );
            } catch (err) {
                if (err instanceof SchemaVersionMismatchError) {
                    if (!cancelled) {
                        setSchemaMismatchError(err);
                    }
                    return;
                }
                throw err;
            }
            if (cancelled) {
                // Built after cleanup ran, so cleanup could not dispose it.
                disposeRenderer();
                return;
            }
            setSchemaMismatchError(null);
            setVisorFrontend(newFrontend);
        })();
        return () => {
            cancelled = true;
            disposeRenderer();
            canvas.dispose();
            setVisorFrontend(null);
            setSchemaMismatchError(null);
        };
    }, [trame]);

    return { visorFrontend, schemaMismatchError };
}

/** The wslink session of a connected trame client. */
function sessionOf(trame: Trame): RcaSession {
    const session = trame.client?.getConnection()?.getSession();
    if (session == null) {
        throw new Error(`trame has no open session`);
    }
    return session;
}

/** The state of a connected trame client. */
function stateOf(trame: Trame): ServerStateSource {
    const state = trame.state;
    if (state == null) {
        throw new Error(`trame has no state`);
    }
    return state;
}

/** Tell the server the theme the page shows, so its rendered background matches; a failed send is logged. */
async function sendDarkThemeAsync(trame: Trame, dark: boolean): Promise<void> {
    try {
        await trame.trigger('set_dark_theme', [{ dark }]);
    } catch (err) {
        console.error('[VISOR] set_dark_theme send failed', err);
    }
}
