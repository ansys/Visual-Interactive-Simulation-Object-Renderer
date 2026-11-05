import type { VisorFrontend } from '../VisorFrontend.tsx';
import type { SchemaVersionMismatchError } from '../state/appstate/VisorSceneDetails.tsx';

/** Receives the frontend App should show and the schema mismatch to show instead, if any. */
export type FrontendChangeListener = (
    frontend: VisorFrontend | null,
    mismatch: SchemaVersionMismatchError | null
) => void;

/** A built frontend and what must be released with it when it is replaced. */
export interface FrontendBuild {
    readonly frontend: VisorFrontend;
    /** Remove everything this build registered; idempotent. */
    release(): void;
}

/** The current frontend build: swaps in a new one, releases the old, keeps it on a schema mismatch. */
export class CurrentFrontend {
    /** Report every change of frontend or mismatch through onChange; required. */
    constructor(onChange: FrontendChangeListener) {
        this.#onChange = onChange;
    }

    readonly #onChange: FrontendChangeListener;
    #build: FrontendBuild | null = null;

    /** The current frontend, or null before the first build. */
    get frontend(): VisorFrontend | null {
        return this.#build?.frontend ?? null;
    }

    /** Release the previous build, then report build.frontend with no mismatch. */
    swapTo(build: FrontendBuild): void {
        this.#build?.release();
        this.#build = build;
        this.#onChange(build.frontend, null);
    }

    /** Keep the current frontend and report it with the mismatch. */
    showMismatch(err: SchemaVersionMismatchError): void {
        this.#onChange(this.frontend, err);
    }

    /** Release the current build and report no frontend and no mismatch. */
    clear(): void {
        this.#build?.release();
        this.#build = null;
        this.#onChange(null, null);
    }
}
