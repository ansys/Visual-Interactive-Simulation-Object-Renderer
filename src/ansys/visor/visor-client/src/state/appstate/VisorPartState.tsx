import {
    ensureBoolean,
    ensureNumber,
    ensureString,
    ensureStringOrNull,
    ensureNumberArray,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';

export default class VisorPartState {
    private _id: string = '';
    private _keyedByName: boolean = false;
    private _name: string = '';
    private _opacity: number | undefined = undefined;
    private _visible: boolean | undefined = undefined;
    private _diffuseRgb: Readonly<number[]> | number[] | undefined = undefined;
    private _selected: boolean | undefined = undefined;
    private _spectrumId: string | null | undefined = undefined;
    private _spectrumComponent: number | undefined = undefined;

    constructor(
        state: StateInput<VisorPartState> = null,
        key: string | number | null | undefined = null
    ) {
        this.copy(state, false, key);
    }

    get id(): string {
        return this._id;
    }

    setId(val: string | number | null | undefined): void {
        if (val != null) {
            this._id = val.toString();
        }
    }

    get keyedByName(): boolean {
        return this._keyedByName;
    }

    setKeyedByName(val: boolean | null | undefined): void {
        this._keyedByName = val ?? false;
    }

    get name(): string {
        return this._name;
    }

    setName(val: string): void {
        if (val != null) {
            this._name = val;
        }
    }

    get opacity(): number | undefined {
        return this._opacity;
    }

    setOpacity(val: number | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._opacity = val;
            }
        } else {
            ensureNumber(val, 'val');
            this._opacity = val;
        }
    }

    get visible(): boolean | undefined {
        return this._visible;
    }

    setVisible(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._visible = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._visible = val;
        }
    }

    get diffuseRgb(): Readonly<number[]> | number[] | undefined {
        return this._diffuseRgb;
    }

    setDiffuseRgb(val: Readonly<number[]> | number[] | undefined, replace = false): void {
        if (val == undefined) {
            if (replace) {
                this._diffuseRgb = val;
            }
        } else {
            ensureNumberArray(val, 'val');
            const [r, g, b] = val;
            if (r < 0 || r > 1) {
                throw new Error('diffuseRgb[0] (r) must be between 0 and 1');
            } else if (g < 0 || g > 1) {
                throw new Error('diffuseRgb[1] (g) must be between 0 and 1');
            } else if (b < 0 || b > 1) {
                throw new Error('diffuseRgb[2] (b) must be between 0 and 1');
            }
            this._diffuseRgb = val;
        }
    }

    get selected(): boolean | undefined {
        return this._selected;
    }

    setSelected(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._selected = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._selected = val;
        }
    }

    get spectrumId(): string | null | undefined {
        return this._spectrumId;
    }

    setSpectrumId(val: string | null | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._spectrumId = val;
            }
        } else {
            ensureStringOrNull(val, 'val');
            this._spectrumId = val;
        }
    }

    get spectrumComponent(): number | undefined {
        return this._spectrumComponent;
    }

    setSpectrumComponent(val: number | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._spectrumComponent = val;
            }
        } else {
            ensureNumber(val, 'val');
            this._spectrumComponent = val;
        }
    }

    copy(
        state: StateInput<VisorPartState> = null,
        replace = false,
        key: string | number | null | undefined = null
    ): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorPartState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            const keyedByName = data.keyedByName ?? false;
            const thisId = (data.id ?? this._id)?.toString();
            const thisName = (data.name ?? this._name)?.toString();

            if ((key = key?.toString()) != null) {
                if (keyedByName) {
                    if (key !== thisName) {
                        throw new Error(
                            `Part state with name '${thisName}' does not equal key '${key}'`
                        );
                    }
                } else {
                    if (key !== thisId) {
                        throw new Error(
                            `Part state with id '${thisId}' does not equal key '${key}'`
                        );
                    }
                }
            }

            this.setId(thisId);
            this.setKeyedByName(keyedByName);
            this.setName(thisName);
            this.setOpacity(data.opacity === undefined ? this._opacity : data.opacity, replace);
            this.setVisible(data.visible === undefined ? this._visible : data.visible, replace);
            this.setDiffuseRgb(
                data.diffuseRgb === undefined ? this._diffuseRgb : data.diffuseRgb,
                replace
            );
            this.setSelected(data.selected === undefined ? this._selected : data.selected, replace);
            this.setSpectrumId(
                data.spectrumId === undefined ? this._spectrumId : data.spectrumId,
                replace
            );
            this.setSpectrumComponent(
                data.spectrumComponent === undefined
                    ? this._spectrumComponent
                    : data.spectrumComponent,
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
            id: this.id,
            keyedByName: this.keyedByName,
            name: this.name,
            opacity: this.opacity,
            visible: this.visible,
            diffuseRgb: this.diffuseRgb,
            selected: this.selected,
            spectrumId: this.spectrumId,
            spectrumComponent: this.spectrumComponent,
        };
    }
}
