import VisorPartState from './VisorPartState.tsx';
import { ensureString, JsonDict, parseState, StateInput } from './VisorStateCommon.tsx';

export default class VisorDatasetState {
    private _id: string = '';
    private _keyedByName: boolean = false;
    private _name: string = '';
    private _partStates: Record<string, VisorPartState> = {};

    constructor(
        state: StateInput<VisorDatasetState> = null,
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

    getPartState(idStr: string): VisorPartState | null {
        ensureString(idStr, 'idStr');
        return this._partStates[idStr] ?? null;
    }

    getPartStates(): VisorPartState[] {
        return Object.values(this._partStates);
    }

    copyPart(
        partState: StateInput<VisorPartState>,
        replace = false,
        key: string | number | null | undefined = null
    ): VisorPartState | null {
        if (partState == null) {
            return null;
        }

        const newState = new VisorPartState(partState, key);

        let existing;
        if (newState.keyedByName) {
            existing = this._partStates[newState.name];
        } else {
            existing = this._partStates[newState.id];
        }

        if (existing) {
            return existing.copy(newState, replace);
        }

        if (newState.keyedByName) {
            return (this._partStates[newState.name] = newState);
        }
        return (this._partStates[newState.id] = newState);
    }

    removePart(idStr: string): boolean {
        return delete this._partStates[idStr];
    }

    copy(
        state: StateInput<VisorDatasetState> = null,
        replace = false,
        key: string | number | null | undefined = null
    ): this {
        if (state != null) {
            let data: JsonDict;

            if (state instanceof VisorDatasetState) {
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

            const partStates = data.partStates;
            if (partStates) {
                for (const [k, v] of Object.entries(partStates)) {
                    this.copyPart(v as JsonDict, replace, k);
                }

                if (replace) {
                    for (const k of Object.keys(this._partStates)) {
                        if (!partStates[k]) {
                            delete this._partStates[k];
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
        const partStates: JsonDict = {};
        for (const [k, v] of Object.entries(this._partStates)) {
            if ((v.keyedByName && k === v.name) || k === v.id) {
                partStates[k] = v.toDict();
            }
        }
        return {
            id: this.id,
            keyedByName: this.keyedByName,
            name: this.name,
            partStates,
        };
    }
}
