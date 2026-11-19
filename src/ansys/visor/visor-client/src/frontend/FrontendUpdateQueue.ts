/** One queued unit of work: a rebuild when any merged request was a rebuild, otherwise a data refresh. */
type PendingWork = { rebuild: boolean };

/** Serializes awaited frontend rebuilds and in-place data refreshes, merging pending requests. */
export class FrontendUpdateQueue {
    /** Build the queue over an awaited rebuild, an awaited data refresh and an error sink; all required. */
    constructor(
        rebuild: () => Promise<void>,
        refreshData: () => Promise<void>,
        onError: (error: unknown) => void
    ) {
        this.#rebuild = rebuild;
        this.#refreshData = refreshData;
        this.#onError = onError;
    }

    readonly #rebuild: () => Promise<void>;
    readonly #refreshData: () => Promise<void>;
    readonly #onError: (error: unknown) => void;
    #running = false;
    #pending: PendingWork | null = null;

    /** Request a frontend rebuild; merges with any pending request. */
    requestRebuild(): void {
        this.#enqueue(true);
    }

    /** Request an in-place data refresh; absorbed by a pending rebuild. */
    requestDataRefresh(): void {
        this.#enqueue(false);
    }

    /** Run at once when idle; otherwise OR the rebuild flag into the pending work. */
    #enqueue(rebuild: boolean): void {
        if (this.#running) {
            if (this.#pending === null) {
                this.#pending = { rebuild };
            } else {
                this.#pending.rebuild ||= rebuild;
            }
            return;
        }
        void this.#drainAsync({ rebuild });
    }

    /** Run work one item at a time until none is pending; a failure goes to onError and the loop continues. */
    async #drainAsync(first: PendingWork): Promise<void> {
        this.#running = true;
        try {
            let work: PendingWork | null = first;
            while (work !== null) {
                try {
                    await (work.rebuild ? this.#rebuild() : this.#refreshData());
                } catch (error) {
                    this.#onError(error);
                }
                work = this.#pending;
                this.#pending = null;
            }
        } finally {
            this.#running = false;
        }
    }
}
