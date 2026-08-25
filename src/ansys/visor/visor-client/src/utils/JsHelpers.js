/** @type {number|null} */
let rootFontSize = null;

/**
 * Returns the root element's computed font size in pixels.
 *
 * If the computed font size is not expressed in pixels, the supplied fallback
 * value is returned. The computed value, or the failure to obtain one, is
 * cached for subsequent calls.
 *
 * @param {number} fallback - Value to return when the root font size cannot be
 * determined in pixels. Must be zero or greater.
 * @returns {number} The root font size in pixels, or the fallback value.
 * @throws {Error} If `fallback` is not a non-negative number.
 */
export const getRootFontSize = (fallback) => {
    if (typeof fallback !== 'number' || fallback < 0) {
        throw new Error('fallback must be a number 0 or greater');
    }

    if (rootFontSize == null) {
        const str = getComputedStyle(document.documentElement, null).getPropertyValue('font-size');

        if (/^(?:-?\d+|-?\d*[.,]\d+)px$/i.test(str)) {
            return (rootFontSize = parseFloat(str.slice(0, -2)));
        }

        const msg = `TreeView warning: computed root element font size '${str}'`;

        console.warn(`${msg} is not a pixel value. Using fallback.`);
        rootFontSize = -1;
    }

    if (rootFontSize < 0) {
        return fallback;
    }

    return rootFontSize;
};

/** @type {number} */
const MIN_ID = 1_000_000_000_000_000;

/** @type {number} */
const MAX_ID = Number.MAX_SAFE_INTEGER;

/** @type {number} */
const RANGE = MAX_ID - MIN_ID + 1;

/**
 * Generates a deterministic numeric ID from a string.
 *
 * The resulting value is between {@link MIN_ID} and {@link MAX_ID}, inclusive.
 *
 * @param {string} str - String to hash.
 * @returns {number} A deterministic safe integer derived from the string.
 */
export const hashString = (str) => {
    const h = cyrb53(str);
    return MIN_ID + (h % RANGE);
};

/**
 * Produces a 53-bit hash from a string using the cyrb53 algorithm.
 *
 * @param {string} str - String to hash.
 * @param {number} [seed=0] - Optional numeric seed.
 * @returns {number} A non-negative 53-bit integer.
 */
function cyrb53(str, seed = 0) {
    let h1 = 0xdeadbeef ^ seed;
    let h2 = 0x41c6ce57 ^ seed;

    for (let i = 0; i < str.length; i++) {
        const ch = str.charCodeAt(i);
        h1 = Math.imul(h1 ^ ch, 2654435761);
        h2 = Math.imul(h2 ^ ch, 1597334677);
    }

    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);

    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);

    return 4294967296 * (h2 & 2097151) + (h1 >>> 0);
}

/**
 * Generates a random integer between `min` and `max`, inclusive.
 *
 * By default, `min` is 10^15 and `max` is JavaScript's maximum safe integer,
 * 9007199254740991. This ensures that the generated number is exactly 16
 * digits long, which is useful when displaying IDs in a fixed-width table
 * column.
 *
 * @param {number} [min=1000000000000000] - Minimum possible value.
 * @param {number} [max=Number.MAX_SAFE_INTEGER] - Maximum possible value.
 * @returns {number} A random integer between `min` and `max`, inclusive.
 */
export function randomInt(min = 1000000000000000, max = Number.MAX_SAFE_INTEGER) {
    return Math.floor(Math.random() * (max - min + 1) + min);
}

/**
 * Generates a random HTML element ID.
 *
 * @returns {string} An underscore-prefixed random numeric ID.
 */
export function randomId() {
    return `_${randomInt()}`;
}

/**
 * Rounds a number to a specified number of decimal places.
 *
 * Based on https://stackoverflow.com/a/48764436.
 *
 * @param {number} input - Number to round.
 * @param {number} [places=0] - Number of decimal places.
 * @returns {number} The rounded number.
 */
export function roundFloat(input, places) {
    const p = Math.pow(10, places || 0);
    const n = input * p * (1 + Number.EPSILON);
    return Math.round(n) / p;
}

/** @type {RegExp} */
const reScale = /scale\([^)]+\)|none/gi;

/**
 * Sets the CSS scale transform of an HTML element.
 *
 * Any existing `scale(...)` transform or `none` value is removed before the
 * new scale is prepended. Other transform functions are preserved.
 *
 * @param {HTMLElement} elem - Element whose transform should be updated.
 * @param {number} scale - Horizontal and vertical scale factor.
 * @returns {void}
 */
export const setScale = (elem, scale) => {
    const style = elem.style;
    style.transform = `scale(${scale},${scale}) ${style.transform.replace(reScale, '')}`;
};

/** @type {RegExp} */
const regex_RemoveFloor = /^\d*\.?/gi;

/** @type {RegExp} */
const regex_AddCommas = /(?<=^[^.]+)(?=(?:\d{3})+(?:$|\.))/gi;

/**
 * Adds thousands separators to the integer portion of a numeric string.
 *
 * @param {string} str - Numeric string to format.
 * @returns {string} The string with thousands separators added.
 */
const addCommas = (str) => str.replace(regex_AddCommas, ',');

/**
 * Formats a number with optional rounding, decimal padding, and thousands
 * separators.
 *
 * @param {number} num - Number to format.
 * @param {number} round - Number of decimal places. Pass a negative value to
 * disable rounding.
 * @param {boolean} pad - Whether to pad the fractional part with trailing
 * zeroes.
 * @returns {string} The formatted number.
 */
export const formatNumber = (num, round, pad) => {
    if (round > -1) {
        num = roundFloat(num, round);
    }

    const str = num.toString();

    if (round > 0 && pad) {
        const repeat = round - str.replace(regex_RemoveFloor, '').length;

        if (repeat > 0) {
            const dot = repeat === round ? '.' : '';
            return addCommas(str) + dot + '0'.repeat(repeat);
        }
    }

    return addCommas(str);
};

/**
 * Escapes characters with special meaning in HTML.
 *
 * Null and undefined inputs are treated as empty strings.
 *
 * @param {string|null|undefined} input - String to escape.
 * @returns {string} The HTML-escaped string.
 */
export function escapeHtml(input) {
    input ??= '';
    input = input.replace(/&/g, '&amp;');
    input = input.replace(/</g, '&lt;');
    input = input.replace(/>/g, '&gt;');
    input = input.replace(/"/g, '&quot;');
    input = input.replace(/'/g, '&apos;');
    return input;
}

/**
 * Copies all own property descriptors from a source object to a target object.
 *
 * Unlike `Object.assign()` and the object spread operator, this function copies
 * accessor properties themselves rather than copying only their current return
 * values.
 *
 * When `seal` is true, copied descriptors are made non-configurable and copied
 * data properties are made non-writable.
 *
 * Based on:
 * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/assign#copying_accessors
 *
 * @template {object} T
 * @param {T} target - Object that will receive the source properties.
 * @param {boolean} seal - Whether copied descriptors should be made immutable.
 * @param {object} source - Object whose own property descriptors will be copied.
 * @returns {T} The modified target object.
 * @throws {TypeError} If `target` or `source` is null or undefined.
 * @throws {TypeError} If `seal` is not a boolean.
 * @public
 */
export function completeAssign(target, seal, source) {
    if (target == null) {
        throw new TypeError('target cannot be null');
    } else if (typeof seal !== 'boolean') {
        throw new TypeError('seal must be a boolean or null');
    } else if (source == null) {
        throw new TypeError('source cannot be null');
    }

    const descriptors = Object.getOwnPropertyDescriptors(source);

    if (seal) {
        for (const key of Reflect.ownKeys(descriptors)) {
            const d = descriptors[key];
            d.configurable = false;

            if ('writable' in d) {
                d.writable = false;
            }
        }
    }

    Object.defineProperties(target, descriptors);
    return target;
}

/**
 * Wraps an object factory in a lazy-loading shell.
 *
 * The factory is invoked the first time the shell's `value` property is read.
 * Subsequent reads return the cached value. The value cannot be assigned
 * directly, and recursive access from within the factory throws an error.
 *
 * @template T
 * @param {() => T} factory - Function that creates the lazily loaded value.
 * @returns {{readonly value: T}} A shell exposing the cached value.
 * @throws {Error} If the value is accessed recursively from within its factory.
 * @throws {Error} If an attempt is made to assign to the `value` property.
 * @public
 */
export function lazy(factory) {
    /** @type {boolean} */
    let isSet = false;

    /** @type {boolean} */
    let setting = false;

    /** @type {T|null} */
    let obj = null;

    return {
        get value() {
            if (isSet) {
                return /** @type {T} */ (obj);
            } else if (setting) {
                throw new Error('cannot access a lazy value from within its factory');
            }

            setting = true;

            try {
                obj = factory();
            } finally {
                setting = false;
            }

            isSet = true;
            return obj;
        },

        set value(x) {
            throw new Error('the value property is readonly');
        },
    };
}

/**
 * Creates a promise together with an externally accessible resolver function.
 *
 * The returned `isSet` function reports whether the resolver has been called.
 *
 * @template T
 * @returns {{
 *     isSet: () => boolean,
 *     promise: Promise<T>,
 *     resolver: (value: T | PromiseLike<T>) => void
 * }} The promise, its resolver, and a function reporting its resolution state.
 */
export function getPromiseResolver() {
    /** @type {(value: T|PromiseLike<T>) => void} */
    let resolver;

    /** @type {boolean} */
    let isSet = false;

    const promise = new Promise((resolve) => {
        resolver = function (value) {
            isSet = true;
            resolve(value);
        };
    });

    return {
        isSet() {
            return isSet;
        },
        promise,
        resolver,
    };
}

/**
 * Retrieves a cookie value by name.
 *
 * The cookie name is escaped for use in a regular expression and then
 * URI-encoded before the cookie string is searched.
 *
 * @param {string|null|undefined} key - Cookie name.
 * @returns {string} The matching encoded cookie value, or the original cookie
 * string when no match is found.
 */
export function getCookie(key) {
    // Escape key for regex.
    key = key?.replace(/[.?*+^$[\]\\(){}|-]/g, '\\$&') ?? '';

    // Encode key for cookie.
    key = encodeURIComponent(key);

    const re = new RegExp(`^(?:.*;\\s*)?${key}=([^;]*).*$`, 'gsi');
    return document.cookie.replace(re, '$1');
}

/**
 * Determines whether a value is a number or a numeric string.
 *
 * Numeric strings may contain an optional leading minus sign and either a
 * period or comma as the decimal separator.
 *
 * @param {unknown} val - Value to inspect.
 * @returns {boolean} Whether the value is numeric.
 */
export function isNumeric(val) {
    if (typeof val === 'number') {
        return true;
    } else if (typeof val !== 'string') {
        return false;
    }

    return /^-?\d+$|^-?\d*[.,]\d+$/.test(val);
}

/**
 * Attempts to convert a string to a floating-point number.
 *
 * Numbers, null, and undefined are returned unchanged. A string that cannot be
 * parsed returns null. All other input types cause an error.
 *
 * @param {string|number|null|undefined} input - Value to parse.
 * @returns {number|null|undefined} The parsed number, the original number,
 * null, or undefined.
 * @throws {Error} If the input is not a string, number, null, or undefined.
 */
export function tryParseFloat(input) {
    if (typeof input === 'string') {
        const num = parseFloat(input);
        return isNaN(num) ? null : num;
    } else if (typeof input === 'number' || input == null) {
        return input;
    }

    throw new Error('input must be a string, number, null, or undefined');
}
