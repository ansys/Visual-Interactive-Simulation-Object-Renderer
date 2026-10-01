import VisorDatasetState from './VisorDatasetState.tsx';
import {
    ensureBoolean,
    ensureString,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';
import VisorVariableState from './VisorVariableState.tsx';
import VisorCameraState from './VisorCameraState.tsx';
import VisorCrossSectionState from './VisorCrossSectionState.tsx';

export default class VisorSceneState {
    private _unit: string | undefined = undefined;
    private _camera: VisorCameraState = new VisorCameraState();
    private _crossSection: VisorCrossSectionState = new VisorCrossSectionState();
    private _datasetStates: Record<string, VisorDatasetState> = {};
    private _variableStates: Record<string, VisorVariableState> = {};
    private _orthographicEnabled: boolean | undefined = undefined;
    private _crossSectionEnabled: boolean | undefined = undefined;
    private _edgesEnabled: boolean | undefined = undefined;
    private _boundingBoxEnabled: boolean | undefined = undefined;

    constructor(state: StateInput<VisorSceneState> = null) {
        this.copy(state, false);
    }

    get camera(): VisorCameraState {
        return this._camera;
    }

    get crossSection(): VisorCrossSectionState {
        return this._crossSection;
    }

    get unit(): string | undefined {
        return this._unit;
    }

    setUnit(val: string | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._unit = val;
            }
        } else {
            ensureString(val, 'val');
            this._unit = val;
        }
    }

    getDatasetState(idStr: string): VisorDatasetState | null {
        ensureString(idStr, 'idStr');
        return this._datasetStates[idStr] ?? null;
    }

    getDatasetStates(): VisorDatasetState[] {
        return Object.values(this._datasetStates);
    }

    copyDataset(
        datasetState: StateInput<VisorDatasetState>,
        replace = false,
        key: string | number | null | undefined = null
    ): VisorDatasetState | null {
        if (datasetState == null) {
            return null;
        }

        const newState = new VisorDatasetState(datasetState, key);

        let existing;
        if (newState.keyedByName) {
            existing = this._datasetStates[newState.name];
        } else {
            existing = this._datasetStates[newState.id];
        }

        if (existing) {
            return existing.copy(newState, replace);
        }
        if (newState.keyedByName) {
            return (this._datasetStates[newState.name] = newState);
        }
        return (this._datasetStates[newState.id] = newState);
    }

    removeDataset(idStr: string): boolean {
        return delete this._datasetStates[idStr];
    }

    getVariableState(idStr: string): VisorVariableState | null {
        ensureString(idStr, 'idStr');
        return this._variableStates[idStr] ?? null;
    }

    getVariableStates(): VisorVariableState[] {
        return Object.values(this._variableStates);
    }

    removeVariable(idStr: string): boolean {
        return delete this._variableStates[idStr];
    }

    copyVariable(
        variableState: StateInput<VisorVariableState>,
        replace = false,
        key: string | number | null | undefined = null
    ): VisorVariableState | null {
        if (variableState == null) {
            return null;
        }

        const newState = new VisorVariableState(variableState, key);
        const existing = this._variableStates[newState.id];

        if (existing) {
            return existing.copy(newState, replace);
        }

        this._variableStates[newState.id] = newState;
        return newState;
    }

    get orthographicEnabled(): boolean | undefined {
        return this._orthographicEnabled;
    }

    setOrthographicEnabled(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._orthographicEnabled = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._orthographicEnabled = val;
        }
    }

    get crossSectionEnabled(): boolean | undefined {
        return this._crossSectionEnabled;
    }

    setCrossSectionEnabled(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._crossSectionEnabled = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._crossSectionEnabled = val;
        }
    }

    get edgesEnabled(): boolean | undefined {
        return this._edgesEnabled;
    }

    setEdgesEnabled(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._edgesEnabled = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._edgesEnabled = val;
        }
    }

    get boundingBoxEnabled(): boolean | undefined {
        return this._boundingBoxEnabled;
    }

    setBoundingBoxEnabled(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._boundingBoxEnabled = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._boundingBoxEnabled = val;
        }
    }

    copy(state: StateInput<VisorSceneState> = null, replace = false): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorSceneState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            this._camera.copy(data.camera, replace);

            this._crossSection.copy(data.crossSection, replace);

            this.setUnit(data.unit === undefined ? this._unit : data.unit, replace);
            this.setCrossSectionEnabled(
                data.crossSectionEnabled === undefined
                    ? this._crossSectionEnabled
                    : data.crossSectionEnabled,
                replace
            );
            this.setBoundingBoxEnabled(
                data.boundingBoxEnabled === undefined
                    ? this._boundingBoxEnabled
                    : data.boundingBoxEnabled,
                replace
            );
            this.setEdgesEnabled(
                data.edgesEnabled === undefined ? this._edgesEnabled : data.edgesEnabled,
                replace
            );
            this.setOrthographicEnabled(
                data.orthographicEnabled === undefined
                    ? this._orthographicEnabled
                    : data.orthographicEnabled,
                replace
            );

            const datasetStates = data.datasetStates;
            if (datasetStates) {
                for (const [k, v] of Object.entries(datasetStates)) {
                    this.copyDataset(v as JsonDict, replace, k);
                }

                if (replace) {
                    for (const k of Object.keys(this._datasetStates)) {
                        if (!datasetStates[k]) {
                            delete this._datasetStates[k];
                        }
                    }
                }
            }

            const variableStates = data.variableStates;
            if (variableStates) {
                for (const [k, v] of Object.entries(variableStates)) {
                    this.copyVariable(v as JsonDict, replace, k);
                }
                if (replace) {
                    for (const k of Object.keys(this._variableStates)) {
                        if (!variableStates[k]) {
                            delete this._variableStates[k];
                        }
                    }
                }
            }
        }
        return this;
    }

    serialize(): string {
        return JSON.stringify(this.toDict());
    }

    toDict(): JsonDict {
        const variableStates: JsonDict = {};
        for (const [k, v] of Object.entries(this._variableStates)) {
            if (k === v.id) {
                variableStates[k] = v.toDict();
            }
        }
        const datasetStates: JsonDict = {};
        for (const [k, v] of Object.entries(this._datasetStates)) {
            if ((v.keyedByName && k === v.name) || k === v.id) {
                datasetStates[k] = v.toDict();
            }
        }
        return {
            unit: this.unit,
            camera: this.camera.toDict(),
            crossSection: this.crossSection.toDict(),
            orthographicEnabled: this.orthographicEnabled,
            crossSectionEnabled: this.crossSectionEnabled,
            edgesEnabled: this.edgesEnabled,
            boundingBoxEnabled: this.boundingBoxEnabled,
            variableStates,
            datasetStates,
        };
    }
}
