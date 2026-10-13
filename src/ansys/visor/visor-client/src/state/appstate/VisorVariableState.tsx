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

export default class VisorVariableState {
    private _id: string = '';
    private _arrayName: string = '';
    private _type: FieldAssociation | undefined = undefined;
    private _numComponents: number = 0;
    private _partIds: number[] | undefined = undefined;
    private _defaultMagnitudeRange: number[] | undefined = undefined;
    private _defaultRanges: (number[] | undefined)[] | undefined = undefined;
    private _magnitudeRange: number[] | undefined = undefined;
    private _ranges: (number[] | undefined)[] = [];

    constructor(
        state: StateInput<VisorVariableState> = null,
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

    /** Ids of the parts that carry this variable's data array. */
    get partIds(): number[] | undefined {
        return this._partIds;
    }

    /** Sets the carrying part ids; `undefined` clears them only when `replace` is set. */
    setPartIds(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._partIds = undefined;
            }
        } else {
            ensureNumberArray(val, 'val');
            this._partIds = [...val];
        }
    }

    /** Magnitude range computed from the data, before any custom range is applied. */
    get defaultMagnitudeRange(): number[] | undefined {
        return this._defaultMagnitudeRange;
    }

    /** Sets the default magnitude range; `undefined` clears it only when `replace` is set. */
    setDefaultMagnitudeRange(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._defaultMagnitudeRange = undefined;
            }
        } else {
            ensureNumberArray(val, 'val', 2);
            this._defaultMagnitudeRange = val;
        }
    }

    /** Per-component ranges computed from the data, before any custom range is applied. */
    get defaultRanges(): (number[] | undefined)[] | undefined {
        return this._defaultRanges;
    }

    /** Sets the per-component default ranges; `undefined` clears them only when `replace` is set. */
    setDefaultRanges(val: (number[] | undefined)[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._defaultRanges = undefined;
            }
            return;
        }
        ensureArray(val, 'val');
        const defaultRanges = this._defaultRanges ?? [];
        for (let i = 0; i < val.length; i++) {
            const minmax = val[i];
            if (minmax == undefined) {
                if (replace) {
                    defaultRanges[i] = minmax;
                }
            } else {
                ensureNumberArray(minmax, 'minmax', 2);
                defaultRanges[i] = minmax;
            }
        }
        this._defaultRanges = defaultRanges;
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
        state: StateInput<VisorVariableState> = null,
        replace = false,
        key: string | number | null | undefined = null
    ): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorVariableState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            const thisId = (data.id ?? this._id)?.toString();

            if ((key = key?.toString()) != null && key !== thisId) {
                throw new Error(`Variable state with id '${thisId}' does not equal key '${key}'`);
            }

            this.setId(thisId);
            this.setArrayName(data.arrayName === undefined ? this._arrayName : data.arrayName);
            this.setType(data.type === undefined ? this._type : data.type);
            this.setNumComponents(
                data.numComponents === undefined ? this._numComponents : data.numComponents
            );
            this.setPartIds(data.partIds === undefined ? this._partIds : data.partIds, replace);
            this.setDefaultMagnitudeRange(
                data.defaultMagnitudeRange === undefined
                    ? this._defaultMagnitudeRange
                    : data.defaultMagnitudeRange,
                replace
            );
            this.setDefaultRanges(
                data.defaultRanges === undefined ? this._defaultRanges : data.defaultRanges,
                replace
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
            partIds: this.partIds,
            defaultMagnitudeRange: this.defaultMagnitudeRange,
            defaultRanges: this.defaultRanges,
            magnitudeRange: this.magnitudeRange,
            ranges: this.ranges,
        };
    }
}
