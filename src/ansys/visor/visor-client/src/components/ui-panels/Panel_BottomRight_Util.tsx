export class Panel_BottomRight_Util {
    constructor(setPickResult: (result: any) => void, clearPickResult: () => void) {
        this.setPickResult = setPickResult;
        this.clearPickResult = clearPickResult;
    }

    readonly setPickResult: (result: any) => void;
    readonly clearPickResult: () => void;
}
