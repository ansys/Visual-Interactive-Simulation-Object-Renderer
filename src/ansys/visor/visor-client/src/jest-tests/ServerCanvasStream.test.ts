import { RCA_AREA_NAME, ServerCanvas } from '../rca/ServerCanvas';

/**
 * The server canvas shows only the frames addressed to its own area, from the
 * frame bytes alone, and reports its element's size to the server, which is
 * what starts the stream.
 *
 * jsdom has neither `ResizeObserver` nor `URL.createObjectURL`; both are
 * replaced by doubles that record what they are given.
 *
 * Expected values are hand-written literals.
 */

type StreamCallback = (args: unknown[]) => void;

const resizeCallbacks: ((entries: unknown[]) => void)[] = [];
const createdBlobs: Blob[] = [];
const globals = globalThis as unknown as { ResizeObserver: unknown };
const urlStatics = URL as unknown as {
    createObjectURL: unknown;
    revokeObjectURL: unknown;
};
let originalResizeObserver: unknown;
let originalCreateObjectURL: unknown;
let originalRevokeObjectURL: unknown;

/** A session double that keeps the stream callback and records calls. */
function makeSession() {
    const session = {
        streamCallback: null as StreamCallback | null,
        topics: [] as string[],
        unsubscribe: jest.fn(),
        call: jest.fn(async () => undefined),
        subscribe(topic: string, callback: StreamCallback) {
            session.topics.push(topic);
            session.streamCallback = callback;
            return { unsubscribe: session.unsubscribe };
        },
    };
    return session;
}

/** Report one element size to every observer created so far. */
function observeSize(width: number, height: number) {
    for (const callback of resizeCallbacks) {
        callback([{ contentRect: { width, height } }]);
    }
}

beforeEach(() => {
    resizeCallbacks.length = 0;
    createdBlobs.length = 0;
    originalResizeObserver = globals.ResizeObserver;
    globals.ResizeObserver = class {
        constructor(callback: (entries: unknown[]) => void) {
            resizeCallbacks.push(callback);
        }
        observe() {}
        disconnect() {}
    };
    originalCreateObjectURL = urlStatics.createObjectURL;
    originalRevokeObjectURL = urlStatics.revokeObjectURL;
    urlStatics.createObjectURL = (blob: Blob) => {
        createdBlobs.push(blob);
        return `blob:frame-${createdBlobs.length}`;
    };
    urlStatics.revokeObjectURL = () => {};
});

afterEach(() => {
    globals.ResizeObserver = originalResizeObserver;
    urlStatics.createObjectURL = originalCreateObjectURL;
    urlStatics.revokeObjectURL = originalRevokeObjectURL;
});

describe('ServerCanvas stream', () => {
    test('RCA_AREA_NAME is "view"', () => {
        expect(RCA_AREA_NAME).toBe('view');
    });

    test('a frame for its own area creates one object URL from the content bytes only', () => {
        const session = makeSession();
        new ServerCanvas(session, 'view');
        // Three frame bytes inside an eight-byte message buffer.
        const content = new Uint8Array(new ArrayBuffer(8), 2, 3);

        session.streamCallback!([{ name: 'view', meta: {}, content }]);

        expect(session.topics).toEqual(['trame.rca.topic.stream']);
        expect(createdBlobs.length).toBe(1);
        expect(createdBlobs[0].size).toBe(3);
    });

    test('a frame for another area creates none', () => {
        const session = makeSession();
        new ServerCanvas(session, 'view');

        session.streamCallback!([{ name: 'other', meta: {}, content: new Uint8Array(3) }]);

        expect(createdBlobs.length).toBe(0);
    });

    test('dispose unsubscribes from the stream', () => {
        const session = makeSession();
        const canvas = new ServerCanvas(session, 'view');

        canvas.dispose();

        expect(session.unsubscribe).toHaveBeenCalledTimes(1);
    });

    test('a non-zero element size is sent to the area', () => {
        const session = makeSession();
        new ServerCanvas(session, 'view');

        observeSize(400.4, 300);

        expect(session.call).toHaveBeenCalledTimes(1);
        expect(session.call).toHaveBeenCalledWith('trame.rca.size', [
            'view',
            'ServerCanvas',
            { w: 400, h: 300, p: 1 },
        ]);
    });

    test('a zero element size sends nothing', () => {
        const session = makeSession();
        new ServerCanvas(session, 'view');

        observeSize(0, 300);

        expect(session.call).not.toHaveBeenCalled();
    });

    test('a resize listener hears each non-zero element size and no zero one', () => {
        const session = makeSession();
        const canvas = new ServerCanvas(session, 'view');
        const listener = jest.fn();
        canvas.addResizeListener(listener);

        observeSize(0, 300);
        observeSize(400, 300);

        expect(listener).toHaveBeenCalledTimes(1);
    });
});
