import { ensureNumberArray, JsonDict, parseState, StateInput } from './VisorStateCommon.tsx';

export default class VisorCrossSectionState {
    private _origin: number[] | undefined = undefined;
    private _normal: number[] | undefined = undefined;

    constructor(state: StateInput<VisorCrossSectionState> = null) {
        this.copy(state);
    }

    get origin(): number[] | undefined {
        return this._origin;
    }

    setOrigin(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._origin = val;
            }
        } else {
            ensureNumberArray(val, 'val', 3);
            this._origin = val;
        }
    }

    get normal(): number[] | undefined {
        return this._normal;
    }

    setNormal(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._normal = val;
            }
        } else {
            ensureNumberArray(val, 'val', 3);
            this._normal = val;
        }
    }

    copy(state: StateInput<VisorCrossSectionState> = null, replace = false): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorCrossSectionState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            this.setOrigin(data.origin === undefined ? this._origin : data.origin, replace);
            this.setNormal(data.normal === undefined ? this._normal : data.normal, replace);
        }
        return this;
    }

    serialize(): string {
        return JSON.stringify(this.toDict());
    }

    toDict(): JsonDict {
        return {
            origin: this.origin,
            normal: this.normal,
        };
    }
}
