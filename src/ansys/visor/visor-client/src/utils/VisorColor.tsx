/**
 * Represents an RGB color with hexadecimal, integer RGB, and normalized RGB
 * representations.
 *
 * @example
 * const color = new VisorColor()
 *     .setHex("#03f");
 *
 * console.log(color.hex);
 * console.log(color.rgb);
 * console.log(color.rgbNormalized);
 */
class VisorColor {
    /**
     * Converts a hexadecimal color string to its RGB components.
     *
     * Supports both six-digit hexadecimal colors, such as `#0033ff`, and
     * three-digit shorthand colors, such as `#03f`.
     *
     * @param hex - The hexadecimal color string to convert.
     * @returns The red, green, and blue components in the range 0–255, or
     * `null` when the input is not a valid hexadecimal color.
     */
    static #hexToRgb: (hex: string) => number[] | null;

    static {
        const re1 = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
        const re2 = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i;

        /**
         * Expands each component of a three-digit hexadecimal color.
         *
         * @param m - The full regular-expression match.
         * @param r - The red hexadecimal digit.
         * @param g - The green hexadecimal digit.
         * @param b - The blue hexadecimal digit.
         * @returns The expanded six-digit hexadecimal value without a leading
         * hash.
         */
        function replacer(m: string, r: string, g: string, b: string): string {
            return r + r + g + g + b + b;
        }

        this.#hexToRgb = (hex: string) => {
            // A version of hexToRgb() that also parses a shorthand hex triplet
            // such as "#03F".
            // From https://stackoverflow.com/questions/5623838/rgb-to-hex-and-hex-to-rgb
            hex = (hex ?? '').replace(re1, replacer);
            const result = re2.exec(hex);

            return result == null
                ? null
                : [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)];
        };
    }

    /**
     * Converts integer RGB components to a hexadecimal color string.
     *
     * @param r - The red component in the range 0–255.
     * @param g - The green component in the range 0–255.
     * @param b - The blue component in the range 0–255.
     * @returns A six-digit, lowercase hexadecimal color string.
     *
     * @throws {Error} If any component is outside the range 0–255.
     */
    static #rgbToHex(r: number, g: number, b: number): string {
        if (r < 0 || r > 255) {
            throw new Error(`r must be between 0 and 255`);
        } else if (g < 0 || g > 255) {
            throw new Error(`g must be between 0 and 255`);
        } else if (b < 0 || b > 255) {
            throw new Error(`b must be between 0 and 255`);
        }

        return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
    }

    /** The current hexadecimal color representation. */
    #hex: string;

    /** The current RGB components, each in the range 0–255. */
    #rgb: Readonly<number[]>;

    /** The current normalized RGB components, each in the range 0–1. */
    #rgbNormalized: Readonly<number[]>;

    /**
     * Creates a color initialized to white.
     */
    constructor() {
        this.#hex = '#ffffff';
        this.#rgb = Object.freeze([255, 255, 255]);
        this.#rgbNormalized = Object.freeze([1, 1, 1]);
    }

    /**
     * Gets the hexadecimal representation of the color.
     *
     * @returns The hexadecimal color string.
     */
    get hex(): string {
        return this.#hex;
    }

    /**
     * Gets the integer RGB representation of the color.
     *
     * @returns A read-only array containing the red, green, and blue
     * components in the range 0–255.
     */
    get rgb(): Readonly<number[]> {
        return this.#rgb;
    }

    /**
     * Gets the normalized RGB representation of the color.
     *
     * @returns A read-only array containing the red, green, and blue
     * components in the range 0–1.
     */
    get rgbNormalized(): Readonly<number[]> {
        return this.#rgbNormalized;
    }

    /**
     * Sets the color from a hexadecimal color string.
     *
     * Supports both six-digit hexadecimal colors, such as `#0033ff`, and
     * three-digit shorthand colors, such as `#03f`.
     *
     * @param hex - The hexadecimal color string.
     * @returns This color instance for method chaining.
     *
     * @throws {Error} If `hex` is not a valid hexadecimal color string.
     */
    setHex(hex: string): this {
        const temp = VisorColor.#hexToRgb(hex);

        if (temp == null) {
            throw new Error(`invalid hex string: ${hex}`);
        }

        this.#hex = hex;
        this.#rgb = Object.freeze(temp);
        this.#rgbNormalized = Object.freeze([
            this.#rgb[0] / 255,
            this.#rgb[1] / 255,
            this.#rgb[2] / 255,
        ]);

        return this;
    }

    /**
     * Sets the color from RGB components.
     *
     * When `normalized` is `true`, each component is expected to be in the
     * range 0–1. Otherwise, each component is expected to be in the range
     * 0–255.
     *
     * @param r - The red component.
     * @param g - The green component.
     * @param b - The blue component.
     * @param normalized - Whether the supplied components are normalized to
     * the range 0–1.
     * @returns This color instance for method chaining.
     *
     * @throws {Error} If a converted RGB component is outside the range 0–255.
     */
    setRgb(r: number, g: number, b: number, normalized: boolean = true): this {
        // rgbToHex() will throw an error if the color is invalid,
        // so no need to validate arguments here.
        if (normalized === true) {
            const _r = Math.floor(r * 255);
            const _g = Math.floor(g * 255);
            const _b = Math.floor(b * 255);

            this.#hex = VisorColor.#rgbToHex(_r, _g, _b);
            this.#rgb = Object.freeze([_r, _g, _b]);
            this.#rgbNormalized = Object.freeze([r, g, b]);
        } else {
            this.#hex = VisorColor.#rgbToHex(r, g, b);
            this.#rgb = Object.freeze([r, g, b]);
            this.#rgbNormalized = Object.freeze([r / 255, g / 255, b / 255]);
        }

        return this;
    }
}

export default VisorColor;
