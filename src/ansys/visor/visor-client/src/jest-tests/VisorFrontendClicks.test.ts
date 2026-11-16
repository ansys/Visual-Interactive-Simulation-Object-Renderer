import { VisorFrontend } from '../VisorFrontend';
import type { IRenderer } from '../renderer/IRenderer';
import type { CanvasClick } from '../rca/ServerCanvas';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import { deliveredPart, deliveredScene } from './deliveredSceneFixture.ts';

/**
 * The frontend decides what a canvas click picks, by the selection mode at the
 * click.  In part mode it asks the renderer for a part pick and tells every
 * viewer-clicked listener the picked node; a click while a part pick is
 * running is dropped.  Outside part mode it runs a geometry pick and asks for
 * no part pick.
 *
 * The renderer is a double whose part pick reports node 7; the scene holds
 * one part, node 7.  Expected values are hand-written literals.
 */

const CLICK: CanvasClick = { normX: 0.5, normY: 0.25, ctrlKey: true, shiftKey: false };

function makeSceneGraphNode() {
    return {
        id: 0,
        dataArrays: [],
        name: '',
        isGroupNode: true,
        isActorNode: false,
        nodeType: 'root',
        diffuseColor: [1, 1, 1],
        bounds: [],
        children: [
            {
                id: 7,
                dataArrays: [],
                name: 'part-7',
                isGroupNode: false,
                isActorNode: true,
                nodeType: 'vtkUnstructuredGrid',
                diffuseColor: [1, 1, 1],
                bounds: [],
                children: [],
            },
        ],
    };
}

/** A frontend over a renderer double, the double, and the click listener the constructor registered. */
function makeFrontend(pickPartAsync: (normX: number, normY: number) => Promise<number | null>) {
    const renderer = {
        domElement: document.createElement('div'),
        addCanvasClickListener: jest.fn(() => jest.fn()),
        clearGeometryHighlight: jest.fn(),
        pickPartAsync: jest.fn(pickPartAsync),
        pickGeometryAsync: jest.fn(async () => null),
        setGeometryHighlightAsync: jest.fn(async () => undefined),
    };
    const frontend = new VisorFrontend(
        renderer as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        deliveredScene(deliveredPart(7)),
        jest.fn(async () => undefined)
    );
    const clickListener = (renderer.addCanvasClickListener.mock.calls[0] as unknown[])[0] as (
        click: CanvasClick
    ) => void;
    return { frontend, renderer, clickListener };
}

async function settle() {
    await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('VisorFrontend clicks', () => {
    test('a part-mode click part-picks at the click and reports the picked node', async () => {
        const { frontend, renderer, clickListener } = makeFrontend(async () => 7);
        const listener = jest.fn();
        frontend.addViewerClickedListener(listener);

        clickListener(CLICK);
        await settle();

        expect(renderer.pickPartAsync.mock.calls).toEqual([[0.5, 0.25]]);
        expect(
            listener.mock.calls.map(([node, ctrlKey, shiftKey]) => [node?.name, ctrlKey, shiftKey])
        ).toEqual([['part-7', true, false]]);
    });

    test('a part-mode click on nothing reports null', async () => {
        const { frontend, clickListener } = makeFrontend(async () => null);
        const listener = jest.fn();
        frontend.addViewerClickedListener(listener);

        clickListener(CLICK);
        await settle();

        expect(listener.mock.calls).toEqual([[null, true, false]]);
    });

    test('a click while a part pick is running asks for no second pick', async () => {
        let resolvePick: (nodeId: number | null) => void = () => {};
        const { frontend, renderer, clickListener } = makeFrontend(
            () => new Promise((resolve) => (resolvePick = resolve))
        );
        const listener = jest.fn();
        frontend.addViewerClickedListener(listener);

        clickListener(CLICK);
        clickListener(CLICK);
        resolvePick(7);
        await settle();

        expect(renderer.pickPartAsync).toHaveBeenCalledTimes(1);
        expect(listener).toHaveBeenCalledTimes(1);
    });

    test('a failed part pick is logged and reaches no listener', async () => {
        const error = new Error('x');
        const { frontend, clickListener } = makeFrontend(async () => {
            throw error;
        });
        const listener = jest.fn();
        frontend.addViewerClickedListener(listener);
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        try {
            clickListener(CLICK);
            await settle();

            expect(consoleError).toHaveBeenCalledWith('[VISOR] part pick failed', error);
            expect(listener).not.toHaveBeenCalled();
        } finally {
            consoleError.mockRestore();
        }
    });

    test('a geometry-mode click geometry-picks and sends no part pick', async () => {
        const { frontend, renderer, clickListener } = makeFrontend(async () => 7);
        const listener = jest.fn();
        frontend.addViewerClickedListener(listener);
        frontend.setSelectionMode('vertex');

        clickListener(CLICK);
        await settle();

        expect(renderer.pickGeometryAsync.mock.calls).toEqual([[0.5, 0.25, 'vertex']]);
        expect(renderer.pickPartAsync).not.toHaveBeenCalled();
        expect(listener).not.toHaveBeenCalled();
    });
});
