import { FrontendRebuilder } from '../frontend/FrontendRebuilder';

/**
 * The rebuilder runs one build at a time: requests made during a build
 * collapse into one more build, and a rejected build neither stops nor
 * wedges it.
 *
 * Expected values are hand-written literals.
 */

/** Let every pending promise callback run. */
async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('FrontendRebuilder', () => {
    test('requests during a held build collapse into one more build', async () => {
        let releaseFirst: () => void = () => {};
        const firstBuild = new Promise<void>((resolve) => {
            releaseFirst = resolve;
        });
        let builds = 0;
        const rebuilder = new FrontendRebuilder(async () => {
            builds += 1;
            if (builds === 1) {
                await firstBuild;
            }
        }, jest.fn());

        rebuilder.request();
        rebuilder.request();
        rebuilder.request();
        rebuilder.request();
        releaseFirst();
        await settle();

        expect(builds).toBe(2);
    });

    test('a rejected build is reported and the next request still builds', async () => {
        const failure = new Error('build failed');
        let builds = 0;
        const onError = jest.fn();
        const rebuilder = new FrontendRebuilder(async () => {
            builds += 1;
            if (builds === 1) {
                throw failure;
            }
        }, onError);

        rebuilder.request();
        await settle();
        rebuilder.request();
        await settle();

        expect(onError.mock.calls).toStrictEqual([[failure]]);
        expect(builds).toBe(2);
    });
});
