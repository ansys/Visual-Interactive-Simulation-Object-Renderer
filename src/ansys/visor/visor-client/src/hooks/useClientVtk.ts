import { useEffect, useRef, useState } from 'react';
import { VisorFrontend } from '../VisorFrontend.tsx';
import VisorSceneDetails, {
    SchemaVersionMismatchError,
} from '../state/appstate/VisorSceneDetails.tsx';
import VisorAppState from '../state/appstate/VisorAppState.tsx';
import RemoteVtkScene from '../wasm/RemoteVtkScene';
import { WasmRenderer } from '../renderer/WasmRenderer';
import { requireWasmAnnotation } from '../renderer/RendererAnnotation';
import { VisorArgs } from './useVisorArgs';

/** What the client-mode hook gives App. */
export type ClientVtk = Readonly<{
    visorFrontend: VisorFrontend | null;
    schemaMismatchError: SchemaVersionMismatchError | null;
}>;

/** Connect the wasm scene, rebuild the frontend on each server update, and apply set_state. */
export function useClientVtk(visorArgs: VisorArgs): ClientVtk {
    const [visorFrontend, setVisorFrontend] = useState<VisorFrontend | null>(null);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);
    const wasmView = useRef<RemoteVtkScene | null>(null);

    useEffect(() => {
        (async () => {
            if (wasmView.current == null) {
                const { host, port } = visorArgs;
                const secure = window.location.protocol === 'https:';
                wasmView.current = await RemoteVtkScene.getInstanceAsync({
                    wasmIdsStateKey: 'wasm_ids',
                    refNameStateKey: 'wasm_ref_name',
                    wasmUrl: `http${secure ? 's' : ''}://${host}:${port}/wasm`,
                    webSocketUrl: `ws${secure ? 's' : ''}://${host}:${port}/ws`,
                });
                wasmView.current.addServerUpdatedListener(onServerUpdateAsync);
                await onServerUpdateAsync();
            }
        })();
    }, []);

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
            let sceneDetails: VisorSceneDetails;
            try {
                sceneDetails = new VisorSceneDetails(sceneDetailsJson);
            } catch (err) {
                if (err instanceof SchemaVersionMismatchError) {
                    setSchemaMismatchError(err);
                    return;
                }
                throw err;
            }
            const renderer = await WasmRenderer.createAsync(
                wasmView.current.vtkScene,
                requireWasmAnnotation(sceneDetails.vtkInfo.rendererAnnotation),
                wasmView.current.trameTriggerAsync
            );
            newFrontend = new VisorFrontend(
                renderer,
                sceneDetails.vtkInfo.sceneGraph,
                sceneDetails.appState.scene,
                wasmView.current.trameTriggerAsync
            );
            // Release the frontend being replaced, here and not later: the
            // `VtkScene` behind both renderers is the same object across a
            // rebuild, so an unreleased subscription stays live and the next
            // gesture is reported once per surviving frontend.  There is
            // deliberately no `await` between the new frontend subscribing (the
            // constructor above) and the old one releasing, so the window in
            // which two subscriptions coexist contains no suspension point.
            if (oldFrontend != null) {
                oldFrontend.releaseCameraSettledListener();
            }

            if (visorArgs.darkMode != null) {
                // Explicit Dash prop takes precedence over the server's dark_mode value.
                sceneDetails.appState.ui.setDarkTheme(visorArgs.darkMode);
            }
            await newFrontend.setAppStateAsync(sceneDetails.appState, false);
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
