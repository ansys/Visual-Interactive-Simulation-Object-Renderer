/** Rebuilds the frontend on request, one build at a time; requests during a build collapse into one more build. */
export class FrontendRebuilder {
    /** Rebuild with build; a rejected build goes to onError. Both required. */
    constructor(build: () => Promise<void>, onError: (err: unknown) => void) {
        this.#build = build;
        this.#onError = onError;
    }

    readonly #build: () => Promise<void>;
    readonly #onError: (err: unknown) => void;
    #building = false;
    #requested = false;

    /** Build now if idle, otherwise build once more after the current build. */
    request(): void {
        if (this.#building) {
            this.#requested = true;
            return;
        }
        void this.#buildAsync();
    }

    /** Build until no request arrived during the last build; the building flag is cleared in finally. */
    async #buildAsync(): Promise<void> {
        this.#building = true;
        try {
            do {
                this.#requested = false;
                try {
                    await this.#build();
                } catch (err) {
                    this.#onError(err);
                }
            } while (this.#requested);
        } finally {
            this.#building = false;
        }
    }
}
