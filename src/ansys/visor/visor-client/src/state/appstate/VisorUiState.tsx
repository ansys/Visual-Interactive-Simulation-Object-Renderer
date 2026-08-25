import {
    ensureBoolean,
    ensureNumber,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';

export default class VisorUiState {
    private _darkTheme: boolean | undefined = undefined;
    private _panelTopLeftPanelCollapsed: boolean | undefined = undefined;
    private _panelTopRightPanelCollapsed: boolean | undefined = undefined;
    private _panelTopRightLegendCollapsed: boolean | undefined = undefined;
    private _panelTopRightTabIndex: number | undefined = undefined;

    constructor(state: StateInput<VisorUiState> = null) {
        this.copy(state);
    }

    get darkTheme(): boolean | undefined {
        return this._darkTheme;
    }

    setDarkTheme(val: boolean | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._darkTheme = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._darkTheme = val;
        }
    }

    get panelTopLeftPanelCollapsed(): boolean | undefined {
        return this._panelTopLeftPanelCollapsed;
    }

    setPanelTopLeftPanelCollapsed(val: boolean | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._panelTopLeftPanelCollapsed = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._panelTopLeftPanelCollapsed = val;
        }
    }

    get panelTopRightPanelCollapsed(): boolean | undefined {
        return this._panelTopRightPanelCollapsed;
    }

    setPanelTopRightPanelCollapsed(val: boolean | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._panelTopRightPanelCollapsed = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._panelTopRightPanelCollapsed = val;
        }
    }

    get panelTopRightLegendCollapsed(): boolean | undefined {
        return this._panelTopRightLegendCollapsed;
    }

    setPanelTopRightLegendCollapsed(val: boolean | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._panelTopRightLegendCollapsed = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._panelTopRightLegendCollapsed = val;
        }
    }

    get panelTopRightTabIndex(): number | undefined {
        return this._panelTopRightTabIndex;
    }

    setPanelTopRightTabIndex(val: number | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._panelTopRightTabIndex = val;
            }
        } else {
            ensureNumber(val, 'val');
            this._panelTopRightTabIndex = val;
        }
    }

    copy(state: StateInput<VisorUiState> = null, replace = false): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorUiState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            this.setDarkTheme(
                data.darkTheme === undefined ? this._darkTheme : data.darkTheme,
                replace
            );
            this.setPanelTopLeftPanelCollapsed(
                data.panelTopLeftPanelCollapsed === undefined
                    ? this._panelTopLeftPanelCollapsed
                    : data.panelTopLeftPanelCollapsed,
                replace
            );
            this.setPanelTopRightPanelCollapsed(
                data.panelTopRightPanelCollapsed === undefined
                    ? this._panelTopRightPanelCollapsed
                    : data.panelTopRightPanelCollapsed,
                replace
            );
            this.setPanelTopRightLegendCollapsed(
                data.panelTopRightLegendCollapsed === undefined
                    ? this._panelTopRightLegendCollapsed
                    : data.panelTopRightLegendCollapsed,
                replace
            );
            this.setPanelTopRightTabIndex(
                data.panelTopRightTabIndex === undefined
                    ? this._panelTopRightTabIndex
                    : data.panelTopRightTabIndex,
                replace
            );
        }
        return this;
    }

    serialize(): string {
        return JSON.stringify(this.toDict());
    }

    toDict(): JsonDict {
        return {
            darkTheme: this.darkTheme,
            panelTopLeftPanelCollapsed: this.panelTopLeftPanelCollapsed,
            panelTopRightPanelCollapsed: this.panelTopRightPanelCollapsed,
            panelTopRightLegendCollapsed: this.panelTopRightLegendCollapsed,
            panelTopRightTabIndex: this.panelTopRightTabIndex,
        };
    }
}
