import {
    ensureBoolean,
    ensureNumber,
    ensureNumberArray,
    JsonDict,
    parseState,
    StateInput,
} from './VisorStateCommon.tsx';

export default class VisorCameraState {
    private _position: number[] | undefined = undefined;
    private _focalPoint: number[] | undefined = undefined;
    private _viewUp: number[] | undefined = undefined;
    private _clippingRange: number[] | undefined = undefined;
    private _parallelProjection: boolean | undefined = undefined;
    private _viewAngle: number | undefined = undefined;
    private _parallelScale: number | undefined = undefined;

    constructor(state: StateInput<VisorCameraState> = null) {
        this.copy(state);
    }

    get position(): number[] | undefined {
        return this._position;
    }

    setPosition(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._position = val;
            }
        } else {
            ensureNumberArray(val, 'val', 3);
            this._position = val;
        }
    }

    get focalPoint(): number[] | undefined {
        return this._focalPoint;
    }

    setFocalPoint(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._focalPoint = val;
            }
        } else {
            ensureNumberArray(val, 'val', 3);
            this._focalPoint = val;
        }
    }

    get viewUp(): number[] | undefined {
        return this._viewUp;
    }

    setViewUp(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._viewUp = val;
            }
        } else {
            ensureNumberArray(val, 'val', 3);
            this._viewUp = val;
        }
    }

    get clippingRange(): number[] | undefined {
        return this._clippingRange;
    }

    setClippingRange(val: number[] | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._clippingRange = val;
            }
        } else {
            ensureNumberArray(val, 'val', 2);
            this._clippingRange = val;
        }
    }

    get parallelProjection(): boolean | undefined {
        return this._parallelProjection;
    }

    setParallelProjection(val: boolean | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._parallelProjection = val;
            }
        } else {
            ensureBoolean(val, 'val');
            this._parallelProjection = val;
        }
    }

    get viewAngle(): number | undefined {
        return this._viewAngle;
    }

    setViewAngle(val: number | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._viewAngle = val;
            }
        } else {
            ensureNumber(val, 'val');
            this._viewAngle = val;
        }
    }

    get parallelScale(): number | undefined {
        return this._parallelScale;
    }

    setParallelScale(val: number | undefined, replace = false): void {
        if (val === undefined) {
            if (replace) {
                this._parallelScale = val;
            }
        } else {
            ensureNumber(val, 'val');
            this._parallelScale = val;
        }
    }

    copy(state: StateInput<VisorCameraState> = null, replace = false): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorCameraState) {
                data = state.toDict();
            } else {
                data = parseState(state)!;
            }

            this.setPosition(data.position === undefined ? this._position : data.position, replace);
            this.setFocalPoint(
                data.focalPoint === undefined ? this._focalPoint : data.focalPoint,
                replace
            );
            this.setViewUp(data.viewUp === undefined ? this._viewUp : data.viewUp, replace);
            this.setClippingRange(
                data.clippingRange === undefined ? this._clippingRange : data.clippingRange,
                replace
            );
            this.setParallelProjection(
                data.parallelProjection === undefined
                    ? this._parallelProjection
                    : data.parallelProjection,
                replace
            );
            this.setViewAngle(
                data.viewAngle === undefined ? this._viewAngle : data.viewAngle,
                replace
            );
            this.setParallelScale(
                data.parallelScale === undefined ? this._parallelScale : data.parallelScale,
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
            position: this.position,
            focalPoint: this.focalPoint,
            viewUp: this.viewUp,
            clippingRange: this.clippingRange,
            parallelProjection: this.parallelProjection,
            viewAngle: this.viewAngle,
            parallelScale: this.parallelScale,
        };
    }
}
