/** VTK button a gesture drives: 0 left (rotate), 1 middle (pan), 2 right (zoom). */
export type VtkButton = 0 | 1 | 2;

/** Which physical buttons are held, and the one VTK button they drive together. */
export class MouseButtonState {
    /** Record that DOM button (0 left, 1 middle, 2 right) went down or up; other values are ignored. */
    setButton(button: number, down: boolean): void {
        if (button === 0) {
            this.#left = down;
        } else if (button === 1) {
            this.#middle = down;
        } else if (button === 2) {
            this.#right = down;
        }
    }

    /** Whether DOM button (0 left, 1 middle, 2 right) is held; false for any other value. */
    isDown(button: number): boolean {
        if (button === 0) {
            return this.#left;
        } else if (button === 1) {
            return this.#middle;
        } else if (button === 2) {
            return this.#right;
        }
        return false;
    }

    /** The VTK button the held buttons drive: left+right 1, right 2, left 0, middle 0, none null. */
    effectiveButton(): VtkButton | null {
        if (this.#left && this.#right) {
            return 1;
        } else if (this.#right) {
            return 2;
        } else if (this.#left) {
            return 0;
        } else if (this.#middle) {
            return 0;
        }
        return null;
    }

    #left = false;
    #middle = false;
    #right = false;
}
