import { GeometryPickReader } from '../renderer/GeometryPickReader';

/**
 * A pick_geometry_at result is read into one of the four pick shapes, keeping
 * only that shape's keys; anything else is refused.
 *
 * Expected values are hand-written literals.
 */

describe('GeometryPickReader', () => {
    test('a face result reads as its area and corners', () => {
        const value = {
            found: true,
            mode: 'face',
            area: 0.5,
            points: [
                [0, 0, 0],
                [1, 0, 0],
                [0, 1, 0],
            ],
            extra: 1,
        };

        expect(GeometryPickReader.parse(value)).toStrictEqual({
            found: true,
            mode: 'face',
            area: 0.5,
            points: [
                [0, 0, 0],
                [1, 0, 0],
                [0, 1, 0],
            ],
        });
    });

    test('an edge result without pointB throws TypeError', () => {
        const value = { found: true, mode: 'edge', pointA: [0, 0, 0], length: 1 };

        expect(() => GeometryPickReader.parse(value)).toThrow(TypeError);
    });
});
