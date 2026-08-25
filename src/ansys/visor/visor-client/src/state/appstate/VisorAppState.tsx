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
        };
    }
}
