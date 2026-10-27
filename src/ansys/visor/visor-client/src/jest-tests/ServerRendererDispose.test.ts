import { ServerRenderer, type ServerStateSource } from '../renderer/ServerRenderer';
import type { IServerCanvas } from '../rca/ServerCanvas';

/**
 * A disposed server renderer leaves no frame listener on the canvas, which
 * outlives it: the canvas is shared by every renderer built over it.
 *
 * Expected values are hand-written literals.
 */

const emptyState: ServerStateSource = {
    watch: () => () => {},
};

/** A canvas whose frame listener removers count their calls, in the order the listeners were added. */
function recordingCanvas(): { canvas: IServerCanvas; removerCalls: number[] } {
    const removerCalls: number[] = [];
    const canvas: IServerCanvas = {
        element: document.createElement('div'),
        frameSize: null,
        addFrameListener: () => {
            const index = removerCalls.length;
            removerCalls.push(0);
            return () => {
                removerCalls[index] += 1;
            };
        },
        addClickListener: () => () => {},
        addResizeListener: () => () => {},
    };
    return { canvas, removerCalls };
}

describe('ServerRenderer dispose', () => {
    test('dispose removes the frame listeners the renderer added', () => {
        const { canvas, removerCalls } = recordingCanvas();
        const renderer = new ServerRenderer(canvas, emptyState, jest.fn());
        const removeFirst = renderer.addFrameRenderedListener(() => {});
        renderer.addFrameRenderedListener(() => {});

        removeFirst();
        renderer.dispose();

        expect(removerCalls).toStrictEqual([1, 1]);
    });
});
