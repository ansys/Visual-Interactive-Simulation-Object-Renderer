/** Converts a viewport-normalised coordinate to a render-window device pixel. */
export class ViewportPixel {
    /** The pixel under a normalised coordinate on an axis of the given size, clamped to [0, size - 1]. */
    static of(norm: number, size: number): number {
        return Math.min(Math.max(Math.floor(norm * size), 0), size - 1);
    }
}
