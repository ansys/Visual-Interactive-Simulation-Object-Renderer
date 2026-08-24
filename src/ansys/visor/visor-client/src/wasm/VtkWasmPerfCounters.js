/**
 * VtkWasmPerfCounters.js
 * -------------------
 * Perf instrumentation for RemoteVtkScene's network fetch cycle.
 *
 * Used only when perf_logging is enabled (set via the server-side
 * .visor config, propagated to the client through trame state).
 *
 * All log lines use the [PERF] prefix to match the server-side format,
 * so they stand out consistently in the browser console.
 */

const SLOW_BLOB_MS = 100;

export class VtkWasmPerfCounter {
    constructor() {
        this.reset();
    }

    /** @type {number} */
    stateCount = 0;
    /** @type {number} */
    stateTotalBytes = 0;
    /** @type {number} */
    blobCount = 0;
    /** @type {number} */
    blobTotalBytes = 0;
    /** @type {number} */
    blobMaxBytes = 0;
    /** @type {number} */
    blobMaxDur = 0;

    /**
     * Reset all counters to zero in-place.
     * Called by updateAsync at the start of each wasm update cycle.
     */
    reset() {
        this.stateCount = 0;
        this.stateTotalBytes = 0;
        this.blobCount = 0;
        this.blobTotalBytes = 0;
        this.blobMaxBytes = 0;
        this.blobMaxDur = 0;
    }

    /**
     * Accumulate one state fetch result.
     * @param {any} res
     */
    recordStateFetch(res) {
        this.stateCount++;
        this.stateTotalBytes += res?.byteLength ?? res?.length ?? 0;
    }

    /**
     * Accumulate one blob fetch result into the counters.
     * Also logs individually if the transfer was slow (≥ SLOW_BLOB_MS), so a
     * specific anomalous blob can be identified by hash — the aggregate summary
     * from logUpdateAsyncPerf already covers total/max across all blobs.
     * @param {string} hash
     * @param {any} res
     * @param {number} dur  elapsed ms
     */
    recordBlobFetch(hash, res, dur) {
        const size = res?.byteLength ?? res?.length ?? 0;
        this.blobCount++;
        this.blobTotalBytes += size;
        if (size > this.blobMaxBytes) this.blobMaxBytes = size;
        if (dur > this.blobMaxDur) this.blobMaxDur = dur;
        if (dur >= SLOW_BLOB_MS) {
            console.log(`[PERF] netFetchBlob hash=${hash} size=${size} dur=${dur.toFixed(2)}ms`);
        }
    }

    /**
     * Log the per-status-fetch timing.
     * @param {number} vtkId
     * @param {number} dur  elapsed ms
     */
    logStatusFetch(vtkId, dur) {
        console.log(`[PERF] netFetchStatus vtkId=${vtkId} dur=${dur.toFixed(2)}ms`);
    }

    /**
     * Emit the single [PERF] summary line for one updateAsync cycle and return
     * the counters snapshot so the caller can forward it to the server.
     * @param {number} wasmMs   elapsed ms for the wasm update step
     * @param {number} resizeMs elapsed ms for the resize step
     * @return {{ stateCount:number, stateTotalBytes:number, blobCount:number, blobTotalBytes:number, blobMaxBytes:number, blobMaxDur:number, wasmMs:number, resizeMs:number, totalMs:number }}
     */
    logUpdateAsyncPerf(wasmMs, resizeMs) {
        const totalMs = wasmMs + resizeMs;
        console.log(
            `[PERF] updateAsync` +
                ` | states=${this.stateCount} (${(this.stateTotalBytes / 1e6).toFixed(3)} MB)` +
                ` | blobs=${this.blobCount} (${(this.blobTotalBytes / 1e6).toFixed(3)} MB total` +
                `, largest=${(this.blobMaxBytes / 1e6).toFixed(3)} MB in ${this.blobMaxDur.toFixed(2)}ms)` +
                ` | wasm=${wasmMs.toFixed(2)}ms resize=${resizeMs.toFixed(2)}ms total=${totalMs.toFixed(2)}ms`
        );
        return {
            stateCount: this.stateCount,
            stateTotalBytes: this.stateTotalBytes,
            blobCount: this.blobCount,
            blobTotalBytes: this.blobTotalBytes,
            blobMaxBytes: this.blobMaxBytes,
            blobMaxDur: this.blobMaxDur,
            wasmMs,
            resizeMs,
            totalMs,
        };
    }
}
