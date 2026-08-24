import {
    ensureArray,
    ensureNumberArray,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';

export default class VisorSpectrumState {
    private _id: string = '';
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
            magnitudeRange: this.magnitudeRange,
            ranges: this.ranges,
        };
    }
}
