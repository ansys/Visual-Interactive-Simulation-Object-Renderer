import { WasmUpdateOptions } from './WasmUpdateOptions';

/** One update to apply: the latest arrival's options, the OR of every arrival's rebuild flag, one promise for all callers. */
class PendingUpdate {
    #bindCanvas: unknown;
    #rebuildsFrontend: boolean;
    readonly #resolve: () => void;
    readonly #reject: (reason: unknown) => void;

    /** The promise every caller merged into this update receives. */
    readonly promise: Promise<void>;

    /** A pending update holding its first arrival. */
    constructor(bindCanvas: unknown) {
        this.#bindCanvas = bindCanvas;
        this.#rebuildsFrontend = WasmUpdateOptions.parse(bindCanvas).rebuildsFrontend;
        let resolve!: () => void;
        let reject!: (reason: unknown) => void;
        this.promise = new Promise<void>((res, rej) => {
            resolve = res;
            reject = rej;
        });
        this.#resolve = resolve;
        this.#reject = reject;
    }

    /** The latest arrival's options. */
    get bindCanvas(): unknown {
        return this.#bindCanvas;
    }

    /** True when any merged arrival was structural. */
    get rebuildsFrontend(): boolean {
        return this.#rebuildsFrontend;
    }

    /** Keep this arrival's options and OR in its rebuild flag. */
    merge(bindCanvas: unknown): void {
        this.#bindCanvas = bindCanvas;
        this.#rebuildsFrontend ||= WasmUpdateOptions.parse(bindCanvas).rebuildsFrontend;
    }

    /** Settle every merged caller's promise as applied settles. */
    settleWith(applied: Promise<void>): void {
        applied.then(this.#resolve, this.#reject);
    }
}

/** Applies server updates one at a time; updates arriving while one runs merge into a single pending update. */
export class SerialUpdateQueue {
    readonly #applyWasmAsync: (bindCanvas: unknown) => Promise<void>;
    readonly #rebuild: () => void;
    #running: Promise<void> | null = null;
    #pending: PendingUpdate | null = null;

    /** applyAsync applies one wasm update; rebuild fires the server-updated listeners once. */
    constructor(applyAsync: (bindCanvas: unknown) => Promise<void>, rebuild: () => void) {
        this.#applyWasmAsync = applyAsync;
        this.#rebuild = rebuild;
    }

    /** Starts at once on an idle queue; otherwise merges into the pending update; returns that update's promise. */
    run(bindCanvas: unknown): Promise<void> {
        if (this.#running === null) {
            const update = new PendingUpdate(bindCanvas);
            this.#start(update);
            return update.promise;
        }
        if (this.#pending === null) {
            this.#pending = new PendingUpdate(bindCanvas);
        } else {
            this.#pending.merge(bindCanvas);
        }
        return this.#pending.promise;
    }

    /** Apply one update; rebuild once if its flag is set and the apply fulfilled. */
    async #applyAsync(update: PendingUpdate): Promise<void> {
        await this.#applyWasmAsync(update.bindCanvas);
        if (update.rebuildsFrontend) {
            this.#rebuild();
        }
    }

    /** Begin applying an update and hold it as the running one. */
    #start(update: PendingUpdate): void {
        const applied = this.#applyAsync(update);
        update.settleWith(applied);
        this.#track(applied);
    }

    /** When the running update settles, fulfilled or rejected, start the pending one or go idle. */
    #track(running: Promise<void>): void {
        this.#running = running;
        const next = () => {
            const pending = this.#pending;
            this.#pending = null;
            if (pending === null) {
                this.#running = null;
            } else {
                this.#start(pending);
            }
        };
        running.then(next, next);
    }
}
