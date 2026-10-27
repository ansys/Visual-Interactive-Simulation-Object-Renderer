import { useEffect, useState } from 'react';
import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { RCA_AREA_NAME, ServerCanvas, type RcaSession } from '../rca/ServerCanvas';
import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { TrameTriggerSender } from '../renderer/IRenderer';
import { buildFrontendAsync } from '../buildFrontendAsync';
import { FrontendRebuilder } from '../frontend/FrontendRebuilder';
import type { VisorArgs } from './useVisorArgs';

/** State key the server bumps after each scene change; must equal server_state_publisher.py's. */
export const SCENE_VERSION_KEY = 'scene_version';

/** What the server-mode hook gives App. */
export type ServerVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** A built server-mode frontend and the renderer it was built over, released together when replaced. */
class ServerFrontendBuild {
    constructor(frontend: VisorFrontend, renderer: ServerRenderer) {
        this.#frontend = frontend;
        this.#renderer = renderer;
    }

    readonly #frontend: VisorFrontend;
    readonly #renderer: ServerRenderer;

    /** Remove the frontend's renderer listeners, then dispose the renderer. */
    release(): void {
        this.#frontend.release();
        this.#renderer.dispose();
    }
}

/** Over the probe's session: stream frames, and rebuild the frontend on every scene_version change; idle when trame is null. */
export function useServerVtk(trame: Trame | null, visorArgs: VisorArgs): ServerVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);

    useEffect(() => {
        if (trame == null) {
            return;
        }
        // Under StrictMode the effect runs twice in development: each run
        // disposes only the canvas and builds it created, and a build that
        // finishes after cleanup disposes its own renderer.
        let cancelled = false;
        let current: ServerFrontendBuild | null = null;
        const state = stateOf(trame);
        // Subscribed before anything can make the server render, so the frame
        // that render produces reaches the canvas.
        const canvas = new ServerCanvas(sessionOf(trame), RCA_AREA_NAME);
        const sender: TrameTriggerSender = (triggerName, payload) =>
            trame.trigger(triggerName, [payload]);
        const buildAsync = async (): Promise<void> => {
            // A build requested before cleanup but started after it sends nothing.
            if (cancelled) {
                return;
            }
            if (visorArgs.darkMode != null) {
                await sendDarkThemeAsync(trame, visorArgs.darkMode);
            }
            // No arguments: the trigger takes none, and a sender would pass one.
            const sceneDetailsJson = await trame.trigger('get_visor_scene_details_json');
            const built: { renderer: ServerRenderer | null } = { renderer: null };
            let newFrontend: VisorFrontend;
            try {
                newFrontend = await buildFrontendAsync(
                    sceneDetailsJson,
                    async () => {
                        built.renderer = new ServerRenderer(canvas, state, sender);
                        return built.renderer;
                    },
                    sender,
                    visorArgs.darkMode
                );
            } catch (err) {
                built.renderer?.dispose();
                if (err instanceof SchemaVersionMismatchError) {
                    // The current frontend is kept, as in client mode.
                    if (!cancelled) {
                        setSchemaMismatchError(err);
                    }
                    return;
                }
                throw err;
            }
            const renderer = built.renderer!;
            if (cancelled) {
                // Built after cleanup ran, so cleanup could not dispose it.
                renderer.dispose();
                return;
            }
            current?.release();
            current = new ServerFrontendBuild(newFrontend, renderer);
            setSchemaMismatchError(null);
            setVisorFrontend(newFrontend);
        };
        const rebuilder = new FrontendRebuilder(buildAsync, (err) =>
            console.error('[VISOR] server-mode rebuild failed', err)
        );
        // `watch` also calls back at once, which is the initial build.
        const unwatch = state.watch([SCENE_VERSION_KEY], () => rebuilder.request());
        return () => {
            cancelled = true;
            unwatch();
            current?.release();
            current = null;
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
