/** The parts of vtk-wasm's remote handler that blob eviction reads and writes. */
export interface BlobStore {
    /** Each cached blob's hash and the update count at which it was last in use. */
    readonly hashesMTime: Record<string, number>;
    /** The update count the next update stamps its blobs with. */
    readonly currentMTime: number;
    readonly sceneManager: {
        getTotalBlobMemoryUsage(): number | bigint;
        unRegisterBlob(hash: string): void;
    };
}

/**
 * Evicts cached wasm blobs oldest-first down to a byte budget, never one a render window last reported in use.
 *
 * This is a workaround for vtk-wasm 1.7.3, whose own `freeMemory` evicts in-use blobs as well, so a scene larger
 * than the budget is fetched again in full on every update.  It reproduces the upstream fix released in vtk-wasm
 * 3.0.3, "fix(blob): prevent blob eviction when used from cache" (https://github.com/Kitware/vtk-wasm/pull/68).
 *
 * It reads and writes internal members of the 1.7.3 handler, so it is only valid while `package.json` pins
 * `@kitware/vtk-wasm` to exactly 1.7.3.  Once vtk-wasm is 3.0.3 or later, delete this class and call the handler's
 * own `freeMemory` again.
 */
export class BlobEviction {
    readonly #budgetBytes: number;
    readonly #inUse = new Map<number, ReadonlySet<string>>();

    /** Eviction down to budgetBytes of cached blob memory. */
    constructor(budgetBytes: number) {
        this.#budgetBytes = budgetBytes;
    }

    /** Replace the blob hashes a render window's latest status reported in use. */
    recordInUse(renderWindowId: number, hashes: readonly string[]): void {
        this.#inUse.set(renderWindowId, new Set(hashes));
    }

    /** Evict unused blobs from store, oldest first, until it is within budget or only newer or in-use blobs remain. */
    evict(store: BlobStore): void {
        const sceneManager = store.sceneManager;
        if (!this.#overBudget(store)) {
            return;
        }
        const inUse = this.#inUseHashes();
        const byMTime = new Map<number, string[]>();
        let oldest = store.currentMTime;
        for (const [hash, mtime] of Object.entries(store.hashesMTime)) {
            oldest = Math.min(oldest, mtime);
            const group = byMTime.get(mtime);
            if (group) {
                group.push(hash);
            } else {
                byMTime.set(mtime, [hash]);
            }
        }
        for (let mtime = oldest; mtime < store.currentMTime && this.#overBudget(store); mtime++) {
            for (const hash of byMTime.get(mtime) ?? []) {
                if (!inUse.has(hash)) {
                    sceneManager.unRegisterBlob(hash);
                    delete store.hashesMTime[hash];
                }
            }
        }
    }

    /** True while the store's cached blob memory exceeds the budget. */
    #overBudget(store: BlobStore): boolean {
        return Number(store.sceneManager.getTotalBlobMemoryUsage()) > this.#budgetBytes;
    }

    /** Every hash any render window last reported in use. */
    #inUseHashes(): Set<string> {
        const hashes = new Set<string>();
        for (const windowHashes of this.#inUse.values()) {
            windowHashes.forEach((hash) => hashes.add(hash));
        }
        return hashes;
    }
}
