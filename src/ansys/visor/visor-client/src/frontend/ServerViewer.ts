import type { Trame } from '@kitware/trame/src/trame.js';
import type { VisorFrontend } from '../VisorFrontend.tsx';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import { RCA_AREA_NAME, ServerCanvas, type RcaSession } from '../rca/ServerCanvas';
import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { TrameTriggerSender } from '../renderer/IRenderer';
import { buildFrontendAsync } from '../buildFrontendAsync';
import { FrontendRebuilder } from './FrontendRebuilder';
import {
    CurrentFrontend,
    type FrontendBuild,
    type FrontendChangeListener,
} from './CurrentFrontend';

/** State key the server bumps after each scene change; must equal server_state_publisher.py's. */
export const SCENE_VERSION_KEY = 'scene_version';

/** A server-mode frontend and the renderer it was built over, released together when replaced. */
class ServerFrontendBuild implements FrontendBuild {
    constructor(frontend: VisorFrontend, renderer: ServerRenderer) {
        this.frontend = frontend;
        this.#renderer = renderer;
    }

    readonly frontend: VisorFrontend;
    readonly #renderer: ServerRenderer;

    /** Remove the frontend's renderer listeners, then dispose the renderer. */
    release(): void {
        this.frontend.release();
        this.#renderer.dispose();
    }
}

/** A server-mode view over the probe's trame: streams frames and rebuilds the frontend on every scene_version change. */
export class ServerViewer {
    /** Subscribe the canvas, watch scene_version and start the first build; all parameters required. */
    constructor(trame: Trame, darkMode: boolean | undefined, onChange: FrontendChangeListener) {
        this.#trame = trame;
        this.#darkMode = darkMode;
        this.#current = new CurrentFrontend(onChange);
        this.#state = stateOf(trame);
        // Subscribed before anything can make the server render, so the frame
        // that render produces reaches the canvas.
        this.#canvas = new ServerCanvas(sessionOf(trame), RCA_AREA_NAME);
        this.#sender = (triggerName, payload) => trame.trigger(triggerName, [payload]);
        const rebuilder = new FrontendRebuilder(
            () => this.#buildAsync(),
            (err) => console.error('[VISOR] server-mode rebuild failed', err)
        );
        // `watch` also calls back at once, which is the initial build.
        this.#unwatch = this.#state.watch([SCENE_VERSION_KEY], () => rebuilder.request());
    }

    readonly #trame: Trame;
    readonly #darkMode: boolean | undefined;
    readonly #current: CurrentFrontend;
    readonly #state: ServerStateSource;
    readonly #canvas: ServerCanvas;
    readonly #sender: TrameTriggerSender;
    readonly #unwatch: () => void;
    #disposed = false;

    /** Stop rebuilding, release the current build and the canvas; a build in progress drops its result. */
    dispose(): void {
        this.#disposed = true;
        this.#unwatch();
        this.#current.clear();
        this.#canvas.dispose();
    }

    /** One build: theme, scene-details fetch, frontend over a new renderer; becomes current unless disposed. */
    async #buildAsync(): Promise<void> {
        // A build requested before dispose but started after it sends nothing.
        if (this.#disposed) {
            return;
        }
        if (this.#darkMode != null) {
            await sendDarkThemeAsync(this.#trame, this.#darkMode);
        }
        // No arguments: the trigger takes none, and a sender would pass one.
        const sceneDetailsJson = await this.#trame.trigger('get_visor_scene_details_json');
        const built: { renderer: ServerRenderer | null } = { renderer: null };
        let newFrontend: VisorFrontend;
        try {
            newFrontend = await buildFrontendAsync(
                sceneDetailsJson,
                async () => {
                    built.renderer = new ServerRenderer(this.#canvas, this.#state, this.#sender);
                    return built.renderer;
                },
                this.#sender,
                this.#darkMode
            );
        } catch (err) {
            built.renderer?.dispose();
            if (err instanceof SchemaVersionMismatchError) {
                // The current frontend is kept, as in client mode.
                if (!this.#disposed) {
                    this.#current.showMismatch(err);
                }
                return;
            }
            throw err;
        }
        const renderer = built.renderer!;
        if (this.#disposed) {
            // Built after dispose ran, so dispose could not release it.
            renderer.dispose();
            return;
        }
        this.#current.swapTo(new ServerFrontendBuild(newFrontend, renderer));
    }
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
