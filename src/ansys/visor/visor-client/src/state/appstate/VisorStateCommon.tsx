export type JsonDict = { [key: string]: any };
export type StateInput<T> = T | string | JsonDict | null;

export function ensureNumberArray(val: any, name: string, ensureLen?: number): any[] {
    ensureArray(val, name, ensureLen);
    for (const num of val) {
        ensureNumber(num, name);
    }
    return val;
}

export function ensureArray(val: any, name: string, ensureLen?: number): any[] {
    if (!Array.isArray(val)) {
        throw new TypeError(`${name} must be an array`);
    }
    if (ensureLen != null && ensureLen >= 0 && val.length > ensureLen) {
        throw new TypeError(`${name} must have exactly ${ensureLen} element(s)`);
    }
    return val;
}

export function ensureString(val: any, name: string): string {
    if (typeof val !== 'string') {
        throw new TypeError(`${name} must be a string`);
    }
    return val;
}

export function ensureStringOrNull(val: any, name: string): string {
    if (val !== null && typeof val !== 'string') {
        throw new TypeError(`${name} must be a string or null`);
    }
    return val;
}

export function ensureBoolean(val: any, name: string): boolean {
    if (typeof val !== 'boolean') {
        throw new TypeError(`${name} must be a boolean`);
    }
    return val;
}

export function ensureNumber(val: any, name: string): number {
    if (typeof val !== 'number') {
        throw new TypeError(`${name} must be a number`);
    }
    return val;
}

export function parseState<T>(state: StateInput<T>): JsonDict | null {
    if (state == null) return null;
    if (typeof state === 'string') {
        const obj = JSON.parse(state);
        if (typeof obj !== 'object' || obj === null) {
            throw new Error('JSON string must deserialize to object');
        }
        return obj;
    }
    if (typeof state === 'object') {
        return state as JsonDict;
    }
    throw new TypeError('State must be object, JSON string, or null');
}
