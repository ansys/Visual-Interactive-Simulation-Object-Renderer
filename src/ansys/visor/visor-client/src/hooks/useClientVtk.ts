import { useEffect, useRef, useState } from 'react';
import { VisorFrontend } from '../VisorFrontend.tsx';
import { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';
import VisorAppState from '../state/appstate/VisorAppState.tsx';
import RemoteVtkScene from '../wasm/RemoteVtkScene';
import { WasmRenderer } from '../renderer/WasmRenderer';
import { requireWasmAnnotation } from '../renderer/RendererAnnotation';
import { attachCameraSyncReporter } from '../CameraSyncReporter';
import { buildFrontendAsync } from '../buildFrontendAsync';
import { trameWebSocketUrl } from '../trameWebSocketUrl';
import { VisorArgs } from './useVisorArgs';

/** What the client-mode hook gives App. */
export type ClientVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Connect the wasm scene, rebuild the frontend on each server update, and apply set_state; idle until active. */
export function useClientVtk(visorArgs: VisorArgs, active: boolean): ClientVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);
    const wasmView = useRef<RemoteVtkScene | null>(null);
    const cameraSyncRemover = useRef<(() => void) | null>(null);

    useEffect(() => {
        if (!active) {
            return;
        }
        (async () => {
            if (wasmView.current == null) {
                const { host, port } = visorArgs;
                const secure = window.location.protocol === 'https:';
                wasmView.current = await RemoteVtkScene.getInstanceAsync({
                    wasmIdsStateKey: 'wasm_ids',
                    refNameStateKey: 'wasm_ref_name',
                    wasmUrl: `http${secure ? 's' : ''}://${host}:${port}/wasm`,
                    webSocketUrl: trameWebSocketUrl(host, port),
                });
                wasmView.current.addServerUpdatedListener(onServerUpdateAsync);
                await onServerUpdateAsync();
            }
        })();
    }, [active]);

    async function onServerUpdateAsync() {
        if (wasmView.current == null) {
            throw new Error(`wasmView should not be null here`);
        }
        const perfLogging = wasmView.current.trameGetState('perf_logging') === true;
        const t0 = perfLogging ? performance.now() : 0;
        if (perfLogging) console.log(`[PERF] onServerUpdateAsync start`);

        wasmView.current.clearObserversAndEventListeners();
        const oldFrontend: VisorFrontend = (window as any).__visorState;
        let newFrontend: VisorFrontend;
        // The listeners cleared above are registered again however this
        // block ends, so a failed rebuild still receives the next server
        // update, and `set_state` keeps reaching the frontend named by
        // `__visorState`, which is switched only after the first pass.
        try {
            const sceneDetailsJson = await wasmView.current.trameTriggerAsync(
                'get_visor_scene_details_json'
            );
            const wasm = wasmView.current;
            try {
                newFrontend = await buildFrontendAsync(
                    sceneDetailsJson,
                    async (sceneDetails) => {
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
                        const releaseOldReporter = cameraSyncRemover.current;
                        cameraSyncRemover.current = attachCameraSyncReporter(
                            renderer,
                            wasm.trameTriggerAsync
                        );
                        releaseOldReporter?.();
                        return renderer;
                    },
                    wasm.trameTriggerAsync,
                    visorArgs.darkMode
                );
            } catch (err) {
                if (err instanceof SchemaVersionMismatchError) {
                    setSchemaMismatchError(err);
                    return;
                }
                throw err;
            }
            if (oldFrontend != null) {
                oldFrontend.release();
            }
            (window as any).__visorState = newFrontend;
            setSchemaMismatchError(null);
            setVisorFrontend(newFrontend); // rebuild/remount React UI
        } finally {
            wasmView.current.addServerUpdatedListener(onServerUpdateAsync);
            wasmView.current.addSetStateListener(onSetStateAsync);
        }
        const view = wasmView.current;
        setTimeout(() => {
            view.vtkScene.resizeAsync();
        }, 100);
        if (perfLogging) {
            const handlerMs = performance.now() - t0;
            console.log(`[PERF] onServerUpdateAsync total=${handlerMs.toFixed(2)}ms`);
            wasmView.current
                .trameTriggerAsync('perf_report_server_update', { handlerMs })
                .catch(() => {});
        }
    }

    async function onSetStateAsync(payload: any) {
        if (wasmView.current == null) {
            throw new Error(`wasmView should not be null here`);
        }
        const newAppState = new VisorAppState(payload?.appState);
        if (visorArgs.darkMode != null) {
            // Explicit Dash prop takes precedence over the theme stored in saved state.
            newAppState.ui.setDarkTheme(visorArgs.darkMode);
        }
        const oldFrontend: VisorFrontend = (window as any).__visorState;
        await oldFrontend.setAppStateAsync(newAppState, true);
    }

    return { visorFrontend, schemaMismatchError };
}
