/** A render-window size in device pixels, never 0 on either side. */
export class CanvasPixelSize {
    /** The device-pixel size of a CSS box at a pixel ratio, or null when either side rounds to 0. */
    static of(cssWidth: number, cssHeight: number, pixelRatio: number): CanvasPixelSize | null {
        const width = Math.floor(cssWidth * pixelRatio + 0.5);
        const height = Math.floor(cssHeight * pixelRatio + 0.5);
        if (width <= 0 || height <= 0) {
            return null;
        }
        return new CanvasPixelSize(width, height);
    }

    private constructor(width: number, height: number) {
        this.width = width;
        this.height = height;
    }

    readonly width: number;
    readonly height: number;
}
