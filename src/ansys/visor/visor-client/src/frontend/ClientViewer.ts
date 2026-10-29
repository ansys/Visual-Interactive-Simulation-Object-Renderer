import type { VisorFrontend } from '../VisorFrontend.tsx';
import VisorSceneDetails, {
    SchemaVersionMismatchError,
} from '../state/appstate/VisorSceneDetails.tsx';
import VisorAppState from '../state/appstate/VisorAppState.tsx';
import RemoteVtkScene from '../wasm/RemoteVtkScene';
import { WasmRenderer } from '../renderer/WasmRenderer';
import { requireWasmAnnotation } from '../renderer/RendererAnnotation';
import { attachCameraSyncReporter } from '../CameraSyncReporter';
import { buildFrontendAsync } from '../buildFrontendAsync';
import { trameWebSocketUrl } from '../trameWebSocketUrl';
import type { VisorArgs } from '../hooks/useVisorArgs';
import {
    CurrentFrontend,
    type FrontendBuild,
    type FrontendChangeListener,
} from './CurrentFrontend';

/** A client-mode frontend over the shared wasm scene; releasing it removes only the frontend's own listeners. */
class ClientFrontendBuild implements FrontendBuild {
    constructor(frontend: VisorFrontend) {
        this.frontend = frontend;
    }

    readonly frontend: VisorFrontend;

    /** Release the frontend; the renderer is kept, because its dispose clears the scene the next build shares. */
    release(): void {
        this.frontend.release();
    }
}

/** A client-mode view over the wasm scene: rebuilds on each server update and applies set_state to the current frontend. */
export class ClientViewer {
    /** Connect the wasm scene, listen for server updates and run the first build; both parameters required. */
    static async connectAsync(
        visorArgs: VisorArgs,
        onChange: FrontendChangeListener
    ): Promise<ClientViewer> {
        const { host, port } = visorArgs;
        const secure = window.location.protocol === 'https:';
        const wasm = await RemoteVtkScene.getInstanceAsync({
            wasmIdsStateKey: 'wasm_ids',
            refNameStateKey: 'wasm_ref_name',
            wasmUrl: `http${secure ? 's' : ''}://${host}:${port}/wasm`,
            webSocketUrl: trameWebSocketUrl(host, port),
        });
        const viewer = new ClientViewer(wasm, visorArgs.darkMode, onChange);
        wasm.addServerUpdatedListener(viewer.#onServerUpdated);
        await viewer.#rebuildAsync();
        return viewer;
    }

    private constructor(
        wasm: RemoteVtkScene,
        darkMode: boolean | undefined,
        onChange: FrontendChangeListener
    ) {
        this.#wasm = wasm;
        this.#darkMode = darkMode;
        this.#current = new CurrentFrontend(onChange);
    }

    readonly #wasm: RemoteVtkScene;
    readonly #darkMode: boolean | undefined;
    readonly #current: CurrentFrontend;
    #cameraSyncRemover: (() => void) | null = null;
    readonly #onServerUpdated = () => this.#rebuildAsync();
    readonly #onSetState = (payload: unknown) => this.#applySetStateAsync(payload);

    /** Rebuild from fresh scene details; the update and set_state listeners are registered again however it ends. */
    async #rebuildAsync(): Promise<void> {
        const wasm = this.#wasm;
        const perfLogging = wasm.trameGetState('perf_logging') === true;
        const t0 = perfLogging ? performance.now() : 0;
        if (perfLogging) console.log(`[PERF] onServerUpdateAsync start`);

        wasm.clearObserversAndEventListeners();
        let newFrontend: VisorFrontend;
        // The listeners cleared above are registered again however this
        // block ends, so a failed rebuild still receives the next server
        // update, and `set_state` keeps reaching the current frontend.
        try {
            const sceneDetailsJson = await wasm.trameTriggerAsync('get_visor_scene_details_json');
            try {
                newFrontend = await buildFrontendAsync(
                    sceneDetailsJson,
                    (sceneDetails) => this.#createRendererAsync(sceneDetails),
                    wasm.trameTriggerAsync,
                    this.#darkMode
                );
            } catch (err) {
                if (err instanceof SchemaVersionMismatchError) {
                    this.#current.showMismatch(err);
                    return;
                }
                throw err;
            }
            // Dash snapshots the frontend named here; it is written before
            // React commits the new frontend, as App writes it only after.
            (window as any).__visorState = newFrontend;
            this.#current.swapTo(new ClientFrontendBuild(newFrontend));
        } finally {
            wasm.addServerUpdatedListener(this.#onServerUpdated);
            wasm.addSetStateListener(this.#onSetState);
        }
        setTimeout(() => {
            wasm.vtkScene.resizeAsync();
        }, 100);
        if (perfLogging) {
            const handlerMs = performance.now() - t0;
            console.log(`[PERF] onServerUpdateAsync total=${handlerMs.toFixed(2)}ms`);
            wasm.trameTriggerAsync('perf_report_server_update', { handlerMs }).catch(() => {});
        }
    }

    /** Create the build's renderer and move the camera-sync reporter onto it, with no await between attach and remove. */
    async #createRendererAsync(sceneDetails: VisorSceneDetails): Promise<WasmRenderer> {
        const wasm = this.#wasm;
        const renderer = await WasmRenderer.createAsync(
            wasm.vtkScene,
            requireWasmAnnotation(sceneDetails.vtkInfo.rendererAnnotation),
            wasm.trameTriggerAsync
        );
        // Report each settled camera window to the server, from exactly
        // one renderer.  The `VtkScene` behind both renderers is the same
        // object across a rebuild, so a subscription left live reports
        // every later gesture once per surviving renderer, each report
        // individually valid.  There is deliberately no `await` between
        // attaching the new reporter and removing the old one, so no
        // suspension point sees two.
        const releaseOldReporter = this.#cameraSyncRemover;
        this.#cameraSyncRemover = attachCameraSyncReporter(renderer, wasm.trameTriggerAsync);
        releaseOldReporter?.();
        return renderer;
    }

    /** Apply a set_state payload to the current frontend, the darkMode prop winning over the stored theme. */
    async #applySetStateAsync(payload: any): Promise<void> {
        const newAppState = new VisorAppState(payload?.appState);
        if (this.#darkMode != null) {
            // Explicit Dash prop takes precedence over the theme stored in saved state.
            newAppState.ui.setDarkTheme(this.#darkMode);
        }
        const frontend = this.#current.frontend;
        if (frontend == null) {
            throw new Error(`set_state arrived before any frontend was built`);
        }
        await frontend.setAppStateAsync(newAppState, true);
    }
}
