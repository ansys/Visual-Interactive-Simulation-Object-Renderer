/** How the client applies one server update: with or without rebuilding the frontend. */
export class WasmUpdateOptions {
    /** The update-option key that marks an update as data-only. */
    static readonly DATA_ONLY_KEY = 'dataOnly';

    /** Whether the server-updated listeners fire once this update is applied. */
    readonly rebuildsFrontend: boolean;

    private constructor(rebuildsFrontend: boolean) {
        this.rebuildsFrontend = rebuildsFrontend;
    }

    /** The options an update's argument carries; only an object whose dataOnly is true skips the rebuild. */
    static parse(value: unknown): WasmUpdateOptions {
        const dataOnly =
            value != null &&
            typeof value === 'object' &&
            (value as Record<string, unknown>)[WasmUpdateOptions.DATA_ONLY_KEY] === true;
        return new WasmUpdateOptions(!dataOnly);
    }
}
