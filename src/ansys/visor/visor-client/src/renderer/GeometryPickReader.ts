import type { PickGeometryResult } from './IRenderer';

/** Reads a geometry pick result from the server into one of the four PickGeometryResult shapes. */
export class GeometryPickReader {
    /** The result as not found, or a vertex, edge or face; throws TypeError for any other value. */
    static parse(value: unknown): PickGeometryResult {
        if (value == null || typeof value !== 'object') {
            throw new TypeError(`geometry pick result is not an object: ${String(value)}`);
        }
        const obj = value as Record<string, unknown>;
        if (obj.found === false) {
            return { found: false };
        }
        if (obj.found !== true) {
            throw new TypeError(`geometry pick result found is not a boolean`);
        }
        switch (obj.mode) {
            case 'vertex':
                return {
                    found: true,
                    mode: 'vertex',
                    position: GeometryPickReader.#point(obj.position, 'position'),
                };
            case 'edge':
                return {
                    found: true,
                    mode: 'edge',
                    pointA: GeometryPickReader.#point(obj.pointA, 'pointA'),
                    pointB: GeometryPickReader.#point(obj.pointB, 'pointB'),
                    length: GeometryPickReader.#number(obj.length, 'length'),
                };
            case 'face':
                if (!Array.isArray(obj.points)) {
                    throw new TypeError(`geometry pick result points is not a list`);
                }
                return {
                    found: true,
                    mode: 'face',
                    area: GeometryPickReader.#number(obj.area, 'area'),
                    points: obj.points.map((p, i) => GeometryPickReader.#point(p, `points[${i}]`)),
                };
            default:
                throw new TypeError(`geometry pick result mode is unknown: ${String(obj.mode)}`);
        }
    }

    /** A list of three numbers; throws TypeError naming the field otherwise. */
    static #point(value: unknown, name: string): readonly number[] {
        if (
            !Array.isArray(value) ||
            value.length !== 3 ||
            !value.every((v) => typeof v === 'number')
        ) {
            throw new TypeError(`geometry pick result ${name} is not 3 numbers`);
        }
        return [...value];
    }

    /** A number; throws TypeError naming the field otherwise. */
    static #number(value: unknown, name: string): number {
        if (typeof value !== 'number') {
            throw new TypeError(`geometry pick result ${name} is not a number`);
        }
        return value;
    }
}
