import {
    ensureArray,
    ensureNumberArray,
    ensureNumber,
    ensureString,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';
import type { FieldAssociation } from './vtkInfo/VisorVtkDataArray.tsx';

export default class VisorSpectrumState {
    private _id: string = '';
    private _arrayName: string = '';
    private _type: FieldAssociation | undefined = undefined;
    private _numComponents: number = 0;
    private _magnitudeRange: number[] | undefined = undefined;
    private _ranges: (number[] | undefined)[] = [];

    constructor(
        state: StateInput<VisorSpectrumState> = null,
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

    get arrayName(): string {
        return this._arrayName;
    }

    setArrayName(val: string | null | undefined): void {
        if (val != null) {
            this._arrayName = ensureString(val, 'val');
        }
    }

    get type(): FieldAssociation | undefined {
        return this._type;
    }

    setType(val: FieldAssociation | null | undefined): void {
        if (val != null) {
            this._type = val;
        }
    }

    get numComponents(): number {
        return this._numComponents;
    }

    setNumComponents(val: number | null | undefined): void {
        if (val != null) {
            this._numComponents = ensureNumber(val, 'val');
        }
    }

    get magnitudeRange(): number[] | undefined {
        return this._magnitudeRange;
    }

    setMagnitudeRange(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._magnitudeRange = undefined;
            }
        } else {
            ensureNumberArray(val, 'val', 2);
            this._magnitudeRange = val;
        }
    }

    get ranges(): (number[] | undefined)[] {
        return this._ranges;
    }

    setRanges(val: (number[] | undefined)[], replace = false): void {
        ensureArray(val, 'val');
        for (let i = 0; i < val.length; i++) {
            const minmax = val[i];
            if (minmax == undefined) {
                if (replace) {
                    this._ranges[i] = minmax;
                }
            } else {
                ensureNumberArray(minmax, 'minmax', 2);
                this._ranges[i] = minmax;
            }
        }
    }

    copy(
        state: StateInput<VisorSpectrumState> = null,
        replace = false,
        key: string | number | null | undefined = null
    ): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorSpectrumState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            const thisId = (data.id ?? this._id)?.toString();

            if ((key = key?.toString()) != null && key !== thisId) {
                throw new Error(`Spectrum state with id '${thisId}' does not equal key '${key}'`);
            }

            this.setId(thisId);
            this.setArrayName(data.arrayName === undefined ? this._arrayName : data.arrayName);
            this.setType(data.type === undefined ? this._type : data.type);
            this.setNumComponents(
                data.numComponents === undefined ? this._numComponents : data.numComponents
            );
            this.setMagnitudeRange(
                data.magnitudeRange === undefined ? this._magnitudeRange : data.magnitudeRange,
                replace
            );
            this.setRanges(data.ranges === undefined ? this._ranges : data.ranges, replace);
        }
        return this;
    }

    serialize(): string {
        return JSON.stringify(this.toDict());
    }

    toDict(): JsonDict {
        return {
            id: this.id,
            arrayName: this.arrayName,
            type: this.type,
            numComponents: this.numComponents,
            magnitudeRange: this.magnitudeRange,
            ranges: this.ranges,
        };
    }
}
