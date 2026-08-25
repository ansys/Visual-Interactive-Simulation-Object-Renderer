/** @jest-environment jsdom */

import VisorColor from '../utils/VisorColor.tsx';

describe('VisorColor', () => {
    describe('constructor', () => {
        test('creates a white color by default', () => {
            const color = new VisorColor();

            expect(color.hex).toBe('#ffffff');
            expect(color.rgb).toEqual([255, 255, 255]);
            expect(color.rgbNormalized).toEqual([1, 1, 1]);
        });

        test('creates frozen RGB arrays', () => {
            const color = new VisorColor();

            expect(Object.isFrozen(color.rgb)).toBe(true);
            expect(Object.isFrozen(color.rgbNormalized)).toBe(true);
        });
    });

    describe('setHex', () => {
        test('sets a six-digit hex color', () => {
            const color = new VisorColor();

            color.setHex('#336699');

            expect(color.hex).toBe('#336699');
            expect(color.rgb).toEqual([51, 102, 153]);
            expect(color.rgbNormalized[0]).toBeCloseTo(51 / 255);
            expect(color.rgbNormalized[1]).toBeCloseTo(102 / 255);
            expect(color.rgbNormalized[2]).toBeCloseTo(153 / 255);
        });

        test('accepts a six-digit hex color without a hash', () => {
            const color = new VisorColor();

            color.setHex('ff8000');

            expect(color.hex).toBe('ff8000');
            expect(color.rgb).toEqual([255, 128, 0]);
            expect(color.rgbNormalized).toEqual([1, 128 / 255, 0]);
        });

        test('expands a three-digit shorthand hex color', () => {
            const color = new VisorColor();

            color.setHex('#03F');

            expect(color.hex).toBe('#03F');
            expect(color.rgb).toEqual([0, 51, 255]);
            expect(color.rgbNormalized).toEqual([0, 51 / 255, 1]);
        });

        test('accepts shorthand hex without a hash', () => {
            const color = new VisorColor();

            color.setHex('abc');

            expect(color.hex).toBe('abc');
            expect(color.rgb).toEqual([170, 187, 204]);
        });

        test('accepts uppercase hex characters', () => {
            const color = new VisorColor();

            color.setHex('#A1B2C3');

            expect(color.hex).toBe('#A1B2C3');
            expect(color.rgb).toEqual([161, 178, 195]);
        });

        test.each([
            '',
            '#',
            '#12',
            '#1234',
            '#12345',
            '#1234567',
            '#gggggg',
            'not-a-color',
            'rgb(1, 2, 3)',
            ' #ffffff',
            '#ffffff ',
        ])('throws for invalid hex input %p', (hex) => {
            const color = new VisorColor();

            expect(() => color.setHex(hex)).toThrow(`invalid hex string: ${hex}`);
        });

        test('does not change the color when given invalid input', () => {
            const color = new VisorColor();

            color.setHex('#123456');

            expect(() => color.setHex('invalid')).toThrow();

            expect(color.hex).toBe('#123456');
            expect(color.rgb).toEqual([18, 52, 86]);
            expect(color.rgbNormalized).toEqual([18 / 255, 52 / 255, 86 / 255]);
        });

        test('replaces the frozen RGB arrays', () => {
            const color = new VisorColor();
            const originalRgb = color.rgb;
            const originalNormalized = color.rgbNormalized;

            color.setHex('#000000');

            expect(color.rgb).not.toBe(originalRgb);
            expect(color.rgbNormalized).not.toBe(originalNormalized);
            expect(Object.isFrozen(color.rgb)).toBe(true);
            expect(Object.isFrozen(color.rgbNormalized)).toBe(true);

            expect(originalRgb).toEqual([255, 255, 255]);
            expect(originalNormalized).toEqual([1, 1, 1]);
        });

        test('returns the color instance to support chaining', () => {
            const color = new VisorColor();

            expect(color.setHex('#123456')).toBe(color);
        });
    });

    describe('setRgb with normalized values', () => {
        test('uses normalized values by default', () => {
            const color = new VisorColor();

            color.setRgb(0.5, 0.25, 1);

            expect(color.hex).toBe('#7f3fff');
            expect(color.rgb).toEqual([127, 63, 255]);
            expect(color.rgbNormalized).toEqual([0.5, 0.25, 1]);
        });

        test('converts black correctly', () => {
            const color = new VisorColor();

            color.setRgb(0, 0, 0);

            expect(color.hex).toBe('#000000');
            expect(color.rgb).toEqual([0, 0, 0]);
            expect(color.rgbNormalized).toEqual([0, 0, 0]);
        });

        test('converts white correctly', () => {
            const color = new VisorColor();

            color.setRgb(1, 1, 1);

            expect(color.hex).toBe('#ffffff');
            expect(color.rgb).toEqual([255, 255, 255]);
            expect(color.rgbNormalized).toEqual([1, 1, 1]);
        });

        test('floors converted byte values', () => {
            const color = new VisorColor();

            color.setRgb(0.999, 0.501, 0.001);

            expect(color.rgb).toEqual([
                Math.floor(0.999 * 255),
                Math.floor(0.501 * 255),
                Math.floor(0.001 * 255),
            ]);
            expect(color.hex).toBe('#fe7f00');
        });

        test('freezes both RGB arrays', () => {
            const color = new VisorColor();

            color.setRgb(0.1, 0.2, 0.3);

            expect(Object.isFrozen(color.rgb)).toBe(true);
            expect(Object.isFrozen(color.rgbNormalized)).toBe(true);
        });
    });

    describe('setRgb with byte values', () => {
        test('sets a color using byte RGB values', () => {
            const color = new VisorColor();

            color.setRgb(12, 34, 56, false);

            expect(color.hex).toBe('#0c2238');
            expect(color.rgb).toEqual([12, 34, 56]);
            expect(color.rgbNormalized).toEqual([12 / 255, 34 / 255, 56 / 255]);
        });

        test('pads one-digit hexadecimal components with zeroes', () => {
            const color = new VisorColor();

            color.setRgb(1, 2, 3, false);

            expect(color.hex).toBe('#010203');
        });

        test('accepts the minimum byte values', () => {
            const color = new VisorColor();

            color.setRgb(0, 0, 0, false);

            expect(color.hex).toBe('#000000');
        });

        test('accepts the maximum byte values', () => {
            const color = new VisorColor();

            color.setRgb(255, 255, 255, false);

            expect(color.hex).toBe('#ffffff');
        });

        test('returns the color instance to support chaining', () => {
            const color = new VisorColor();

            expect(color.setRgb(1, 2, 3, false)).toBe(color);
        });
    });

    describe('setRgb validation', () => {
        test.each([
            [-1, 0, 0, 'r must be between 0 and 255'],
            [256, 0, 0, 'r must be between 0 and 255'],
            [0, -1, 0, 'g must be between 0 and 255'],
            [0, 256, 0, 'g must be between 0 and 255'],
            [0, 0, -1, 'b must be between 0 and 255'],
            [0, 0, 256, 'b must be between 0 and 255'],
        ])('rejects byte RGB values (%p, %p, %p)', (r, g, b, expectedMessage) => {
            const color = new VisorColor();

            expect(() => color.setRgb(r, g, b, false)).toThrow(expectedMessage);
        });

        test.each([
            [-0.01, 0, 0, 'r must be between 0 and 255'],
            [1.01, 0, 0, 'r must be between 0 and 255'],
            [0, -0.01, 0, 'g must be between 0 and 255'],
            [0, 1.01, 0, 'g must be between 0 and 255'],
            [0, 0, -0.01, 'b must be between 0 and 255'],
            [0, 0, 1.01, 'b must be between 0 and 255'],
        ])('rejects normalized RGB values (%p, %p, %p)', (r, g, b, expectedMessage) => {
            const color = new VisorColor();

            expect(() => color.setRgb(r, g, b)).toThrow(expectedMessage);
        });

        test('does not change the color after invalid RGB input', () => {
            const color = new VisorColor();

            color.setRgb(10, 20, 30, false);

            expect(() => color.setRgb(256, 20, 30, false)).toThrow();

            expect(color.hex).toBe('#0a141e');
            expect(color.rgb).toEqual([10, 20, 30]);
            expect(color.rgbNormalized).toEqual([10 / 255, 20 / 255, 30 / 255]);
        });
    });

    describe('successive updates', () => {
        test('can update from hex to RGB', () => {
            const color = new VisorColor();

            color.setHex('#ff0000');
            color.setRgb(0, 255, 0, false);

            expect(color.hex).toBe('#00ff00');
            expect(color.rgb).toEqual([0, 255, 0]);
            expect(color.rgbNormalized).toEqual([0, 1, 0]);
        });

        test('can update from RGB to hex', () => {
            const color = new VisorColor();

            color.setRgb(0, 0, 255, false);
            color.setHex('#ffff00');

            expect(color.hex).toBe('#ffff00');
            expect(color.rgb).toEqual([255, 255, 0]);
            expect(color.rgbNormalized).toEqual([1, 1, 0]);
        });
    });
});
