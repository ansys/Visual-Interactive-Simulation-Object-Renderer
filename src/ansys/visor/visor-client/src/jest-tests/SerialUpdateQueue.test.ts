import { SerialUpdateQueue } from '../wasm/SerialUpdateQueue';

/**
 * Server updates run one at a time.  Updates arriving while one runs merge
 * into one pending update, which keeps the latest options and rebuilds if any
 * arrival was structural.  A failed update never rebuilds and never blocks
 * the next one.
 *
 * The fake apply records `start:<tag>` and is held on a promise the test
 * settles; the fake rebuild records `rebuild`.  Expected records are literals.
 */

type Update = Readonly<{ tag: string; dataOnly?: boolean }>;
type Held = { resolve: () => void; reject: (reason: unknown) => void };

function makeQueue() {
    const record: string[] = [];
    const held: Held[] = [];
    const queue = new SerialUpdateQueue(
        (bindCanvas: unknown) => {
            record.push(`start:${(bindCanvas as Update).tag}`);
            return new Promise<void>((resolve, reject) => held.push({ resolve, reject }));
        },
        () => {
            record.push('rebuild');
        }
    );
    return { record, held, queue };
}

const flushAsync = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('SerialUpdateQueue', () => {
    test('second update starts only after the first fulfils', async () => {
        const { record, held, queue } = makeQueue();

        queue.run({ tag: 'A' });
        queue.run({ tag: 'B' });
        await flushAsync();
        expect(record).toEqual(['start:A']);

        held[0].resolve();
        await flushAsync();
        expect(record).toEqual(['start:A', 'rebuild', 'start:B']);
    });

    test('second update starts only after the first rejects', async () => {
        const { record, held, queue } = makeQueue();

        const first = queue.run({ tag: 'A' });
        const firstRejects = expect(first).rejects.toThrow('A failed');
        queue.run({ tag: 'B' });
        await flushAsync();
        expect(record).toEqual(['start:A']);

        held[0].reject(new Error('A failed'));
        await flushAsync();
        expect(record).toEqual(['start:A', 'start:B']);
        await firstRejects;
    });

    test('updates arriving during a held update merge into one', async () => {
        const { record, held, queue } = makeQueue();

        queue.run({ tag: 'A' });
        const b = queue.run({ tag: 'B' });
        const c = queue.run({ tag: 'C' });
        const d = queue.run({ tag: 'D' });
        expect(c).toBe(b);
        expect(d).toBe(b);

        held[0].resolve();
        await flushAsync();
        expect(record).toEqual(['start:A', 'rebuild', 'start:D']);
    });

    test('merged update does not rebuild when every arrival was data-only', async () => {
        const { record, held, queue } = makeQueue();

        queue.run({ tag: 'A', dataOnly: true });
        queue.run({ tag: 'B', dataOnly: true });
        queue.run({ tag: 'C', dataOnly: true });
        queue.run({ tag: 'D', dataOnly: true });
        held[0].resolve();
        await flushAsync();
        held[1].resolve();
        await flushAsync();

        expect(record).toEqual(['start:A', 'start:D']);
    });

    test('merged update rebuilds once when any arrival was structural', async () => {
        const { record, held, queue } = makeQueue();

        queue.run({ tag: 'A', dataOnly: true });
        queue.run({ tag: 'B', dataOnly: true });
        queue.run({ tag: 'C' });
        queue.run({ tag: 'D', dataOnly: true });
        held[0].resolve();
        await flushAsync();
        expect(record).toEqual(['start:A', 'start:D']);

        held[1].resolve();
        await flushAsync();
        expect(record).toEqual(['start:A', 'start:D', 'rebuild']);
    });

    test('an arrival after the pending update started waits for it', async () => {
        const { record, held, queue } = makeQueue();

        queue.run({ tag: 'A', dataOnly: true });
        queue.run({ tag: 'B', dataOnly: true });
        held[0].resolve();
        await flushAsync();
        queue.run({ tag: 'E', dataOnly: true });
        await flushAsync();
        expect(record).toEqual(['start:A', 'start:B']);

        held[1].resolve();
        await flushAsync();
        expect(record).toEqual(['start:A', 'start:B', 'start:E']);
    });
});
