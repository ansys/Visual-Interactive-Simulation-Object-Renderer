import { FrontendUpdateQueue } from '../frontend/FrontendUpdateQueue';

/**
 * The queue runs one rebuild or data refresh at a time.  Requests made while
 * one runs merge into one pending item, which is a rebuild if any merged
 * request was; a refresh requested while a rebuild runs still runs after it,
 * whether that rebuild fulfilled or rejected.
 *
 * Expected values are hand-written literals.
 */

/** Let every pending promise callback run. */
async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

/** A promise the test settles, with its resolve and reject. */
function held(): { promise: Promise<void>; resolve: () => void; reject: (e: unknown) => void } {
    let resolve: () => void = () => {};
    let reject: (e: unknown) => void = () => {};
    const promise = new Promise<void>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

describe('FrontendUpdateQueue', () => {
    test('requests during a held build collapse into one more build', async () => {
        const firstBuild = held();
        let builds = 0;
        const queue = new FrontendUpdateQueue(
            async () => {
                builds += 1;
                if (builds === 1) {
                    await firstBuild.promise;
                }
            },
            async () => {},
            jest.fn()
        );

        queue.requestRebuild();
        queue.requestRebuild();
        queue.requestRebuild();
        queue.requestRebuild();
        firstBuild.resolve();
        await settle();

        expect(builds).toBe(2);
    });

    test('a rejected build is reported and the next request still builds', async () => {
        const failure = new Error('build failed');
        let builds = 0;
        const onError = jest.fn();
        const queue = new FrontendUpdateQueue(
            async () => {
                builds += 1;
                if (builds === 1) {
                    throw failure;
                }
            },
            async () => {},
            onError
        );

        queue.requestRebuild();
        await settle();
        queue.requestRebuild();
        await settle();

        expect(onError.mock.calls).toStrictEqual([[failure]]);
        expect(builds).toBe(2);
    });

    test('a pending rebuild absorbs a refresh requested before it starts', async () => {
        const firstBuild = held();
        const record: string[] = [];
        const queue = new FrontendUpdateQueue(
            async () => {
                record.push('rebuild');
                if (record.length === 1) {
                    await firstBuild.promise;
                }
            },
            async () => {
                record.push('refresh');
            },
            jest.fn()
        );

        queue.requestRebuild();
        queue.requestDataRefresh();
        queue.requestRebuild();
        firstBuild.resolve();
        await settle();

        expect(record).toEqual(['rebuild', 'rebuild']);
    });

    test('a refresh requested during a failed rebuild runs after it', async () => {
        const build = held();
        const record: string[] = [];
        const queue = new FrontendUpdateQueue(
            async () => {
                record.push('rebuild');
                await build.promise;
            },
            async () => {
                record.push('refresh');
            },
            jest.fn()
        );

        queue.requestRebuild();
        queue.requestDataRefresh();
        await settle();
        expect(record).toEqual(['rebuild']);

        build.reject(new Error('build failed'));
        await settle();

        expect(record).toEqual(['rebuild', 'refresh']);
    });
});
