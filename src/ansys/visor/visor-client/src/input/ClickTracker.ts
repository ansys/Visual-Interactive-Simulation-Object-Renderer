/** Recognises a click: a press and a release at the same client position with no leave or blur between them. */
export class ClickTracker {
    /** Record a press at (clientX, clientY). */
    press(clientX: number, clientY: number): void {
        this.#pressX = clientX;
        this.#pressY = clientY;
    }

    /** Forget any press; called on mouseout and blur. */
    reset(): void {
        this.#pressX = null;
        this.#pressY = null;
    }

    /** True if a release at (clientX, clientY) completes a click; always forgets the press. */
    release(clientX: number, clientY: number): boolean {
        const isClick = this.#pressX === clientX && this.#pressY === clientY;
        this.reset();
        return isClick;
    }

    #pressX: number | null = null;
    #pressY: number | null = null;
}
