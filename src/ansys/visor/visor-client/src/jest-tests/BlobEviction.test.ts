import { BlobEviction, BlobStore } from '../wasm/BlobEviction';

/**
 * Blob eviction keeps every blob a render window last reported in use, and evicts the rest oldest-first
 * until the cache is within budget.
 *
 * Expected values are hand-written literals.
 */

/** A blob store whose memory usage is the sum of its registered blobs' sizes. */
class FakeBlobStore implements BlobStore {
    readonly hashesMTime: Record<string, number> = {};
    readonly unregistered: string[] = [];
    readonly #sizes = new Map<string, number>();
    readonly sceneManager = {
        getTotalBlobMemoryUsage: (): number => {
            let total = 0;
            this.#sizes.forEach((size) => (total += size));
            return total;
        },
        unRegisterBlob: (hash: string): void => {
            this.#sizes.delete(hash);
            this.unregistered.push(hash);
        },
    };

    constructor(readonly currentMTime: number) {}

    /** Register a cached blob of size bytes last in use at mtime. */
    add(hash: string, size: number, mtime: number): void {
        this.#sizes.set(hash, size);
        this.hashesMTime[hash] = mtime;
    }
}

describe('BlobEviction', () => {
    test('a blob the latest status reported in use is kept when the cache is over budget', () => {
        const store = new FakeBlobStore(2);
        store.add('sphere', 300, 1);
        const eviction = new BlobEviction(100);
        eviction.recordInUse(6, ['sphere']);

        eviction.evict(store);

        expect(store.unregistered).toEqual([]);
        expect(store.hashesMTime).toEqual({ sphere: 1 });
    });

    test('unused blobs are evicted oldest first, stopping once the cache is within budget', () => {
        const store = new FakeBlobStore(4);
        store.add('old', 60, 1);
        store.add('mid', 60, 2);
        store.add('live', 60, 3);
        const eviction = new BlobEviction(130);
        eviction.recordInUse(6, ['live']);

        eviction.evict(store);

        expect(store.unregistered).toEqual(['old']);
        expect(store.hashesMTime).toEqual({ mid: 2, live: 3 });
    });

    test("a hash dropped from a render window's latest status can be evicted", () => {
        const store = new FakeBlobStore(2);
        store.add('removed', 300, 1);
        store.add('kept', 300, 1);
        const eviction = new BlobEviction(100);
        eviction.recordInUse(6, ['removed', 'kept']);
        eviction.recordInUse(6, ['kept']);

        eviction.evict(store);

        expect(store.unregistered).toEqual(['removed']);
        expect(store.hashesMTime).toEqual({ kept: 1 });
    });
});
