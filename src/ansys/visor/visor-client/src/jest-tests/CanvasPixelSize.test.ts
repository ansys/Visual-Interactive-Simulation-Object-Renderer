import { CanvasPixelSize } from '../wasm/CanvasPixelSize';

/**
 * The wasm render window is sized from its container's CSS box at the
 * device pixel ratio.  A box that rounds to 0 on either side gives no size,
 * so the window keeps its last one: a 0-sized window is never set.
 */

describe('CanvasPixelSize.of', () => {
    test('scales the CSS box by the pixel ratio and rounds to the nearest pixel', () => {
        const size = CanvasPixelSize.of(400.3, 300.2, 2);
        expect(size).not.toBeNull();
        expect([size!.width, size!.height]).toEqual([801, 600]);
    });

    test.each([
        ['a zero-sized box', 0, 0],
        ['a zero width', 0, 300],
        ['a zero height', 400, 0],
        ['a box that rounds to zero', 0.2, 0.2],
    ])('gives no size for %s', (_name, width, height) => {
        expect(CanvasPixelSize.of(width, height, 1)).toBeNull();
    });
});

describe('CanvasPixelSize.equals', () => {
    test('is true for the same size and false for a different width, height or null', () => {
        const size = CanvasPixelSize.of(400, 300, 1)!;
        expect(size.equals(CanvasPixelSize.of(400, 300, 1))).toBe(true);
        expect(size.equals(CanvasPixelSize.of(401, 300, 1))).toBe(false);
        expect(size.equals(CanvasPixelSize.of(400, 301, 1))).toBe(false);
        expect(size.equals(null)).toBe(false);
    });
});
