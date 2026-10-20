import VisorUiState from './VisorUiState.tsx';
import VisorSceneState from './VisorSceneState.tsx';
import { JsonDict, parseState, StateInput } from './VisorStateCommon.tsx';

export default class VisorAppState {
    private _ui: VisorUiState = new VisorUiState();
    private _scene: VisorSceneState = new VisorSceneState();

    constructor(state: StateInput<VisorAppState> = null) {
        this.copy(state);
    }

    get ui(): VisorUiState {
        return this._ui;
    }

    get scene(): VisorSceneState {
        return this._scene;
    }

    copy(state: StateInput<VisorAppState> = null, replace = false): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorAppState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            this._ui.copy(data.ui, replace);
            this._scene.copy(data.scene, replace);
            // The camera and the plane arrive under view and are held on the
            // scene's camera and crossSection records.
            this._scene.camera.copy(data.view?.camera, replace);
            this._scene.crossSection.copy(data.view?.crossSection, replace);
        }
        return this;
    }

    serialize(): string {
        return JSON.stringify(this.toDict());
    }

    toDict(): JsonDict {
        return {
            ui: this.ui.toDict(),
            scene: this.scene.toDict(),
            view: {
                camera: this.scene.camera.toDict(),
                crossSection: this.scene.crossSection.toDict(),
            },
        };
    }
}
