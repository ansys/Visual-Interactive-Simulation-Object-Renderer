import { UiScaffold, UiScaffoldUtil } from './components/UiScaffold.tsx';
import { CSSProperties, RefObject, useEffect, useRef, useState } from 'react';
import { VisorFrontend } from './VisorFrontend.tsx';
import VisorSceneDetails, {
    SchemaVersionMismatchError,
} from './state/appstate/VisorSceneDetails.tsx';
import VisorAppState from './state/appstate/VisorAppState.tsx';
import RemoteVtkScene from './wasm/RemoteVtkScene';
import { WasmRenderer } from './renderer/WasmRenderer';
import { requireWasmAnnotation } from './renderer/RendererAnnotation';
import { randomInt } from './utils/JsHelpers';

type VisorArgs = {
    host: string;
    port: number;
    aspectRatio: number;
    pixelDensity: number;
    darkMode: boolean;
    basePath: string;
};

function App() {
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
    const visorContainerStyle: CSSProperties =
        visorArgs.current.aspectRatio > 0
            ? {
                  position: 'relative',
                  aspectRatio: `${visorArgs.current.aspectRatio}`,
                  maxHeight: '100%',
                  margin: '0 auto',
              }
            : {
                  position: 'relative',
                  minHeight: '100px',
                  width: `100%`,
                  height: `100%`,
                  margin: '0 auto',
              };
    const uiScaffoldUtil: RefObject<UiScaffoldUtil> = useRef(null!);
    const [visorState, setVisorFrontend] = useState<VisorFrontend>(null!);
    const [schemaMismatchError, setSchemaMismatchError] =
        useState<SchemaVersionMismatchError | null>(null);
    const wasmView = useRef<RemoteVtkScene | null>(null);

    useEffect(() => {
        (async () => {
            if (wasmView.current == null) {
                const { host, port } = visorArgs.current;
                const secure = window.location.protocol === 'https:';
                wasmView.current = await RemoteVtkScene.getInstanceAsync({
                    wasmIdsStateKey: 'wasm_ids',
                    refNameStateKey: 'wasm_ref_name',
                    wasmUrl: `http${secure ? 's' : ''}://${host}:${port}/wasm`,
                    webSocketUrl: `ws${secure ? 's' : ''}://${host}:${port}/ws`,
                });
                wasmView.current.addServerUpdatedListener(onServerUpdateAsync);
                await onServerUpdateAsync();
                return;
            } else if (uiScaffoldUtil.current == null) {
                throw new Error(`uiScaffoldUtil.current should not be null here`);
            }
            (window as any).__visorState = visorState;
            //////////////////////////////////////////////////////////////////////////
            // Set UiScaffold params.
            uiScaffoldUtil.current.pixelDensity = visorArgs.current.pixelDensity;
        })();
        return () => {
            // Cleanup
            delete (window as any).__visorState;
        };
    }, [visorState]);

    async function onServerUpdateAsync() {
        if (wasmView.current == null) {
            throw new Error(`wasmView should not be null here`);
        }
        const perfLogging = wasmView.current.trameGetState('perf_logging') === true;
        const t0 = perfLogging ? performance.now() : 0;
        if (perfLogging) console.log(`[PERF] onServerUpdateAsync start`);

        wasmView.current.clearObserversAndEventListeners();
        const oldFrontend: VisorFrontend = (window as any).__visorState;
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
        const newFrontend = new VisorFrontend(renderer, sceneDetails.vtkInfo.sceneGraph);
        if (visorArgs.current.darkMode != null) {
            // Explicit Dash prop takes precedence over the server's dark_mode value.
            sceneDetails.appState.ui.setDarkTheme(visorArgs.current.darkMode);
        }
        (window as any).__visorState = newFrontend;
        await newFrontend.setAppStateAsync(sceneDetails.appState, false);
        setVisorFrontend(newFrontend); // rebuild/remount React UI
        wasmView.current.addServerUpdatedListener(onServerUpdateAsync);
        wasmView.current.addGetStateListener(onGetState);
        wasmView.current.addSetStateListener(onSetStateAsync);
        if (oldFrontend != null) {
            const oldAppState = await oldFrontend.getAppStateAsync();
            await newFrontend.setAppStateAsync(oldAppState);
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

    async function onGetState(payload: any) {
        if (wasmView.current == null) {
            throw new Error(`wasmView should not be null here`);
        }
        const oldFrontend: VisorFrontend = (window as any).__visorState;
        const appState = await oldFrontend.getAppStateAsync();
        const response = {
            requestId: payload.requestId,
            appState: appState.toDict(),
        };
        await wasmView.current.trameTriggerAsync(
            'save_state_response',
            payload.requestId,
            response
        );
    }

    async function onSetStateAsync(payload: any) {
        if (wasmView.current == null) {
            throw new Error(`wasmView should not be null here`);
        }
        const newAppState = new VisorAppState(payload?.appState);
        if (visorArgs.current.darkMode != null) {
            // Explicit Dash prop takes precedence over the theme stored in saved state.
            newAppState.ui.setDarkTheme(visorArgs.current.darkMode);
        }
        const oldFrontend: VisorFrontend = (window as any).__visorState;
        await oldFrontend.setAppStateAsync(newAppState, true);
    }

    return (
        <div style={visorContainerStyle}>
            {schemaMismatchError != null ? (
                <div>
                    {`Scene details schema version mismatch: payload is version ` +
                        `${schemaMismatchError.payloadVersion}, client expects version ` +
                        `${schemaMismatchError.expectedVersion}.`}
                </div>
            ) : (
                visorState != null && (
                    <UiScaffold
                        key={randomInt()}
                        visorState={visorState}
                        onLoad={(u) => {
                            uiScaffoldUtil.current = u;
                        }}
                    />
                )
            )}
        </div>
    );
}

export default App;
