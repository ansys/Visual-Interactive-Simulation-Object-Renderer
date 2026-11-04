import type { NodeId } from './IRenderer';

/** Reads a part pick result from the server. */
export class PartPickReader {
    /** Read a part-pick trigger result: the node id, or null for no part; throws TypeError otherwise. */
    static parse(value: unknown, trigger: string): NodeId | null {
        if (value === null || Number.isInteger(value)) {
            return value as NodeId | null;
        }
        throw new TypeError(`${trigger} result is not a node id or null: ${String(value)}`);
    }
}
