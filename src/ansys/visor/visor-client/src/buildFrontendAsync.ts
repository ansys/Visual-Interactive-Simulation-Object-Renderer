import { VisorFrontend } from './VisorFrontend.tsx';
import VisorSceneDetails from './state/appstate/VisorSceneDetails.tsx';
import type { StateInput } from './state/appstate/VisorStateCommon.tsx';
import type { IRenderer, TrameTriggerSender } from './renderer/IRenderer';

/** Build and seed a frontend from delivered scene details; throws SchemaVersionMismatchError before any renderer exists. */
export async function buildFrontendAsync(
    sceneDetailsJson: StateInput<VisorSceneDetails>,
    createRenderer: (sceneDetails: VisorSceneDetails) => Promise<IRenderer>,
    triggerSender: TrameTriggerSender,
    darkMode: boolean | undefined
): Promise<VisorFrontend> {
    const sceneDetails = new VisorSceneDetails(sceneDetailsJson);
    const renderer = await createRenderer(sceneDetails);
    const frontend = new VisorFrontend(
        renderer,
        sceneDetails.vtkInfo.sceneGraph,
        sceneDetails.appState.scene,
        triggerSender
    );

    if (darkMode != null) {
        // Explicit Dash prop takes precedence over the server's dark_mode value.
        sceneDetails.appState.ui.setDarkTheme(darkMode);
    }
    await frontend.setAppStateAsync(sceneDetails.appState, false);
    return frontend;
}
