/** @jest-environment jsdom */

import {
    completeAssign,
    escapeHtml,
    formatNumber,
    getCookie,
    getPromiseResolver,
    hashString,
    isNumeric,
    lazy,
    randomId,
    randomInt,
    roundFloat,
    setScale,
    tryParseFloat,
} from '../utils/JsHelpers.js';

/**
 * getRootFontSize caches module-level state, so each test needs a fresh
 * instance of the module.
 *
 * @returns {Promise<(fallback: number) => number>}
 */
async function loadFreshGetRootFontSize() {
    jest.resetModules();
    const module = await import('../utils/JsHelpers.js');
    return module.getRootFontSize;
}

function clearCookies() {
    document.cookie.split(';').forEach((cookie) => {
        const separator = cookie.indexOf('=');
        const name = separator >= 0 ? cookie.slice(0, separator).trim() : cookie.trim();

        if (name) {
            document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
        }
    });
}

afterEach(() => {
    jest.restoreAllMocks();
});

describe('getRootFontSize', () => {
    test.each([undefined, null, '16', {}, -1, -0.01])(
        'throws when fallback is invalid: %p',
        async (fallback) => {
            const getRootFontSize = await loadFreshGetRootFontSize();
            const getComputedStyleSpy = jest.spyOn(globalThis, 'getComputedStyle');

            expect(() => getRootFontSize(fallback)).toThrow(
                'fallback must be a number 0 or greater'
            );
            expect(getComputedStyleSpy).not.toHaveBeenCalled();
        }
    );

    test('returns the computed root font size when it is a pixel value', async () => {
        const getRootFontSize = await loadFreshGetRootFontSize();
        const getPropertyValue = jest.fn().mockReturnValue('18.5px');

        const getComputedStyleSpy = jest
            .spyOn(globalThis, 'getComputedStyle')
            .mockReturnValue({ getPropertyValue });

        expect(getRootFontSize(16)).toBe(18.5);
        expect(getComputedStyleSpy).toHaveBeenCalledWith(document.documentElement, null);
        expect(getPropertyValue).toHaveBeenCalledWith('font-size');
    });

    test('accepts a zero-pixel root font size', async () => {
        const getRootFontSize = await loadFreshGetRootFontSize();

        jest.spyOn(globalThis, 'getComputedStyle').mockReturnValue({
            getPropertyValue: jest.fn().mockReturnValue('0px'),
        });

        expect(getRootFontSize(16)).toBe(0);
    });

    test('caches a valid computed font size', async () => {
        const getRootFontSize = await loadFreshGetRootFontSize();
        const getPropertyValue = jest.fn().mockReturnValue('18px');

        const getComputedStyleSpy = jest
            .spyOn(globalThis, 'getComputedStyle')
            .mockReturnValue({ getPropertyValue });

        expect(getRootFontSize(16)).toBe(18);

        getPropertyValue.mockReturnValue('24px');

        expect(getRootFontSize(12)).toBe(18);
        expect(getComputedStyleSpy).toHaveBeenCalledTimes(1);
        expect(getPropertyValue).toHaveBeenCalledTimes(1);
    });

    test('warns and returns the fallback when the font size is not in pixels', async () => {
        const getRootFontSize = await loadFreshGetRootFontSize();
        const warningSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

        const getComputedStyleSpy = jest.spyOn(globalThis, 'getComputedStyle').mockReturnValue({
            getPropertyValue: jest.fn().mockReturnValue('1.25rem'),
        });

        expect(getRootFontSize(16)).toBe(16);
        expect(warningSpy).toHaveBeenCalledWith(
            'TreeView warning: computed root element font size ' +
                "'1.25rem' is not a pixel value. Using fallback."
        );
        expect(getComputedStyleSpy).toHaveBeenCalledTimes(1);
    });

    test('uses the current fallback on each call after a non-pixel value is found', async () => {
        const getRootFontSize = await loadFreshGetRootFontSize();

        const getComputedStyleSpy = jest.spyOn(globalThis, 'getComputedStyle').mockReturnValue({
            getPropertyValue: jest.fn().mockReturnValue('normal'),
        });

        jest.spyOn(console, 'warn').mockImplementation(() => {});

        expect(getRootFontSize(16)).toBe(16);
        expect(getRootFontSize(20)).toBe(20);
        expect(getComputedStyleSpy).toHaveBeenCalledTimes(1);
    });
});

describe('hashString', () => {
    test('returns the same hash for the same string', () => {
        expect(hashString('TreeView')).toBe(hashString('TreeView'));
    });

    test('produces stable regression values', () => {
        expect(hashString('')).toBe(4338908027751811);
        expect(hashString('hello')).toBe(5625896200565286);
        expect(hashString('TreeView')).toBe(4180486618474600);
        expect(hashString('some-multiblock-file.vtm')).toBe(2654834946646323);
    });

    test('returns a safe integer in the configured ID range', () => {
        const values = [
            hashString('a'),
            hashString('b'),
            hashString('a longer value'),
            hashString('Unicode: 你好'),
            hashString('🚀'),
        ];

        values.forEach((value) => {
            expect(Number.isSafeInteger(value)).toBe(true);
            expect(value).toBeGreaterThanOrEqual(1_000_000_000_000_000);
            expect(value).toBeLessThanOrEqual(Number.MAX_SAFE_INTEGER);
        });
    });

    test('normally produces different hashes for different strings', () => {
        const values = [
            hashString('one'),
            hashString('two'),
            hashString('three'),
            hashString('four'),
        ];

        expect(new Set(values).size).toBe(values.length);
    });
});

describe('randomInt', () => {
    test('returns the minimum when Math.random returns zero', () => {
        jest.spyOn(Math, 'random').mockReturnValue(0);

        expect(randomInt(10, 20)).toBe(10);
    });

    test('can return the maximum value', () => {
        jest.spyOn(Math, 'random').mockReturnValue(0.95);

        expect(randomInt(10, 20)).toBe(20);
    });

    test('returns an integer within a custom range', () => {
        jest.spyOn(Math, 'random').mockReturnValue(0.5);

        const result = randomInt(10, 20);

        expect(result).toBe(15);
        expect(Number.isInteger(result)).toBe(true);
        expect(result).toBeGreaterThanOrEqual(10);
        expect(result).toBeLessThanOrEqual(20);
    });

    test('uses the documented default minimum', () => {
        jest.spyOn(Math, 'random').mockReturnValue(0);

        expect(randomInt()).toBe(1_000_000_000_000_000);
    });
});

describe('randomId', () => {
    test('returns an underscore followed by a random integer', () => {
        jest.spyOn(Math, 'random').mockReturnValue(0);

        expect(randomId()).toBe('_1000000000000000');
    });
});

describe('roundFloat', () => {
    test.each([
        [1.005, 2, 1.01],
        [123.456, 2, 123.46],
        [1.2345, 3, 1.235],
        [-1.005, 2, -1.01],
        [123.4, 0, 123],
    ])('rounds %p to %p places', (input, places, expected) => {
        expect(roundFloat(input, places)).toBe(expected);
    });

    test('rounds to an integer when places is omitted', () => {
        expect(roundFloat(123.5)).toBe(124);
    });
});

describe('setScale', () => {
    test('adds a scale transform to an element', () => {
        const element = document.createElement('div');
        element.style.transform = 'rotate(45deg)';

        setScale(element, 2);

        expect(element.style.transform).toContain('scale(2,2)');
        expect(element.style.transform).toContain('rotate(45deg)');
    });

    test('replaces an existing scale without removing other transforms', () => {
        const element = document.createElement('div');
        element.style.transform = 'translateX(10px) scale(2) rotate(45deg)';

        setScale(element, 3);

        expect(element.style.transform).toContain('scale(3,3)');
        expect(element.style.transform).not.toContain('scale(2)');
        expect(element.style.transform).toContain('translateX(10px)');
        expect(element.style.transform).toContain('rotate(45deg)');

        const scaleMatches = element.style.transform.match(/scale\(/gi);
        expect(scaleMatches).toHaveLength(1);
    });

    test('does not accumulate scale transforms across calls', () => {
        const element = document.createElement('div');
        element.style.transform = 'rotate(20deg)';

        setScale(element, 2);
        setScale(element, 4);

        expect(element.style.transform).toContain('scale(4,4)');
        expect(element.style.transform).not.toContain('scale(2,2)');

        const scaleMatches = element.style.transform.match(/scale\(/gi);
        expect(scaleMatches).toHaveLength(1);
    });

    test('removes a none transform', () => {
        const element = document.createElement('div');
        element.style.transform = 'none';

        setScale(element, 1.5);

        expect(element.style.transform.trim()).toBe('scale(1.5,1.5)');
    });
});

describe('formatNumber', () => {
    test.each([
        [1234567.891, 2, false, '1,234,567.89'],
        [1234, 2, true, '1,234.00'],
        [1234.5, 2, true, '1,234.50'],
        [0.5, 3, true, '0.500'],
        [1234.6, 0, true, '1,235'],
        [1234.567, -1, true, '1,234.567'],
        [-1234567.89, -1, false, '-1,234,567.89'],
    ])('formats %p with round=%p and pad=%p', (num, round, pad, expected) => {
        expect(formatNumber(num, round, pad)).toBe(expected);
    });

    test('does not add decimal padding when pad is false', () => {
        expect(formatNumber(1234.5, 3, false)).toBe('1,234.5');
    });
});

describe('escapeHtml', () => {
    test('escapes HTML special characters', () => {
        expect(escapeHtml(`&<>"'`)).toBe('&amp;&lt;&gt;&quot;&apos;');
    });

    test('escapes ampersands before other characters', () => {
        expect(escapeHtml('&amp;')).toBe('&amp;amp;');
    });

    test.each([
        [null, ''],
        [undefined, ''],
        ['', ''],
    ])('converts %p to an empty string', (input, expected) => {
        expect(escapeHtml(input)).toBe(expected);
    });

    test('leaves ordinary text unchanged', () => {
        expect(escapeHtml('TreeView node 123')).toBe('TreeView node 123');
    });
});

describe('completeAssign', () => {
    test('returns the original target', () => {
        const target = {};
        const result = completeAssign(target, false, { value: 1 });

        expect(result).toBe(target);
        expect(target.value).toBe(1);
    });

    test('copies a getter without invoking it', () => {
        const getter = jest.fn().mockReturnValue(42);
        const source = {};

        Object.defineProperty(source, 'value', {
            get: getter,
            enumerable: true,
            configurable: true,
        });

        const target = completeAssign({}, false, source);

        expect(getter).not.toHaveBeenCalled();

        const descriptor = Object.getOwnPropertyDescriptor(target, 'value');

        expect(descriptor.get).toBe(getter);
        expect(descriptor.enumerable).toBe(true);
        expect(descriptor.configurable).toBe(true);

        expect(target.value).toBe(42);
        expect(getter).toHaveBeenCalledTimes(1);
    });

    test('copies non-enumerable and symbol properties', () => {
        const symbol = Symbol('test');
        const source = {};

        Object.defineProperty(source, 'hidden', {
            value: 'hidden value',
            enumerable: false,
            writable: true,
            configurable: true,
        });

        Object.defineProperty(source, symbol, {
            value: 'symbol value',
            enumerable: false,
            writable: true,
            configurable: true,
        });

        const target = completeAssign({}, false, source);

        expect(target.hidden).toBe('hidden value');
        expect(target[symbol]).toBe('symbol value');

        expect(Object.getOwnPropertyDescriptor(target, 'hidden').enumerable).toBe(false);
    });

    test('makes copied data properties non-writable when seal is true', () => {
        const source = {};

        Object.defineProperty(source, 'value', {
            value: 10,
            enumerable: true,
            writable: true,
            configurable: true,
        });

        const target = completeAssign({}, true, source);
        const descriptor = Object.getOwnPropertyDescriptor(target, 'value');

        expect(descriptor.value).toBe(10);
        expect(descriptor.writable).toBe(false);
        expect(descriptor.configurable).toBe(false);
    });

    test('makes copied accessor properties non-configurable when sealed', () => {
        const getter = jest.fn().mockReturnValue(10);
        const source = {};

        Object.defineProperty(source, 'value', {
            get: getter,
            enumerable: true,
            configurable: true,
        });

        const target = completeAssign({}, true, source);
        const descriptor = Object.getOwnPropertyDescriptor(target, 'value');

        expect(descriptor.get).toBe(getter);
        expect(descriptor.configurable).toBe(false);
    });

    test('throws when target is null or undefined', () => {
        expect(() => completeAssign(null, false, {})).toThrow(
            new TypeError('target cannot be null')
        );

        expect(() => completeAssign(undefined, false, {})).toThrow(
            new TypeError('target cannot be null')
        );
    });

    test.each([null, undefined, 0, 1, 'true', {}])(
        'throws when seal is not a boolean: %p',
        (seal) => {
            expect(() => completeAssign({}, seal, {})).toThrow(TypeError);
        }
    );

    test('throws when source is null or undefined', () => {
        expect(() => completeAssign({}, false, null)).toThrow(
            new TypeError('source cannot be null')
        );

        expect(() => completeAssign({}, false, undefined)).toThrow(
            new TypeError('source cannot be null')
        );
    });
});

describe('lazy', () => {
    test('does not call the factory until value is accessed', () => {
        const factory = jest.fn().mockReturnValue('result');
        const shell = lazy(factory);

        expect(factory).not.toHaveBeenCalled();

        expect(shell.value).toBe('result');
        expect(factory).toHaveBeenCalledTimes(1);
    });

    test('calls the factory only once and caches its result', () => {
        const result = {};
        const factory = jest.fn().mockReturnValue(result);
        const shell = lazy(factory);

        expect(shell.value).toBe(result);
        expect(shell.value).toBe(result);
        expect(shell.value).toBe(result);
        expect(factory).toHaveBeenCalledTimes(1);
    });

    test('can cache null and undefined values', () => {
        const nullFactory = jest.fn().mockReturnValue(null);
        const undefinedFactory = jest.fn().mockReturnValue(undefined);

        const nullShell = lazy(nullFactory);
        const undefinedShell = lazy(undefinedFactory);

        expect(nullShell.value).toBeNull();
        expect(nullShell.value).toBeNull();
        expect(nullFactory).toHaveBeenCalledTimes(1);

        expect(undefinedShell.value).toBeUndefined();
        expect(undefinedShell.value).toBeUndefined();
        expect(undefinedFactory).toHaveBeenCalledTimes(1);
    });

    test('throws when assigning to value', () => {
        const shell = lazy(() => 'result');

        expect(() => {
            shell.value = 'replacement';
        }).toThrow('the value property is readonly');
    });

    test('prevents accessing the lazy value from its factory', () => {
        let shell;
        shell = lazy(() => shell.value);

        expect(() => shell.value).toThrow('cannot access a lazy value from within its factory');
    });

    test('retries the factory after the factory throws', () => {
        const factory = jest
            .fn()
            .mockImplementationOnce(() => {
                throw new Error('factory failed');
            })
            .mockReturnValue('success');

        const shell = lazy(factory);

        expect(() => shell.value).toThrow('factory failed');
        expect(shell.value).toBe('success');
        expect(shell.value).toBe('success');
        expect(factory).toHaveBeenCalledTimes(2);
    });
});

describe('getPromiseResolver', () => {
    test('provides a promise and external resolver', async () => {
        const result = getPromiseResolver();

        expect(result.promise).toBeInstanceOf(Promise);
        expect(typeof result.resolver).toBe('function');
        expect(result.isSet()).toBe(false);

        result.resolver('resolved value');

        expect(result.isSet()).toBe(true);
        await expect(result.promise).resolves.toBe('resolved value');
    });

    test('the promise retains the first resolved value', async () => {
        const result = getPromiseResolver();

        result.resolver('first');
        result.resolver('second');

        await expect(result.promise).resolves.toBe('first');
        expect(result.isSet()).toBe(true);
    });
});

describe('getCookie', () => {
    beforeEach(() => {
        clearCookies();
    });

    afterEach(() => {
        clearCookies();
    });

    test('returns the value of an existing cookie', () => {
        document.cookie = 'testCookie=testValue; path=/';

        expect(getCookie('testCookie')).toBe('testValue');
    });

    test('finds a cookie between other cookies', () => {
        document.cookie = 'first=one; path=/';
        document.cookie = 'target=two; path=/';
        document.cookie = 'last=three; path=/';

        expect(getCookie('target')).toBe('two');
    });

    test('encodes the requested cookie key', () => {
        document.cookie = 'display%20name=TreeView; path=/';

        expect(getCookie('display name')).toBe('TreeView');
    });

    test('returns the stored cookie value without decoding it', () => {
        document.cookie = 'encodedValue=hello%20world%21; path=/';

        expect(getCookie('encodedValue')).toBe('hello%20world%21');
    });
});

describe('isNumeric', () => {
    test.each([0, 1, -1, 1.5, -1.5])('returns true for the number %p', (value) => {
        expect(isNumeric(value)).toBe(true);
    });

    test.each(['0', '123', '-123', '1.5', '-1.5', '.5', '-.5', '1,5', '-1,5'])(
        'returns true for the numeric string %p',
        (value) => {
            expect(isNumeric(value)).toBe(true);
        }
    );

    test.each([
        '',
        ' ',
        'abc',
        '1e3',
        '0x10',
        '1.',
        '.',
        '+1',
        '--1',
        '1,2,3',
        null,
        undefined,
        true,
        false,
        {},
        [],
    ])('returns false for the non-numeric value %p', (value) => {
        expect(isNumeric(value)).toBe(false);
    });
});

describe('tryParseFloat', () => {
    test.each([
        ['12', 12],
        ['12.5', 12.5],
        ['-0.25', -0.25],
        ['.75', 0.75],
        ['12px', 12],
        ['', null],
        ['   ', null],
        ['not a number', null],
    ])('parses string %p as %p', (input, expected) => {
        expect(tryParseFloat(input)).toBe(expected);
    });

    test('returns number inputs unchanged', () => {
        expect(tryParseFloat(12.5)).toBe(12.5);
        expect(tryParseFloat(-10)).toBe(-10);
        expect(tryParseFloat(Number.POSITIVE_INFINITY)).toBe(Number.POSITIVE_INFINITY);
        expect(tryParseFloat(Number.NaN)).toBeNaN();
    });

    test('returns null and undefined unchanged', () => {
        expect(tryParseFloat(null)).toBeNull();
        expect(tryParseFloat(undefined)).toBeUndefined();
    });

    test.each([true, false, {}, [], () => {}])('throws for unsupported input %p', (input) => {
        expect(() => tryParseFloat(input)).toThrow(
            'input must be a string, number, null, or undefined'
        );
    });
});
