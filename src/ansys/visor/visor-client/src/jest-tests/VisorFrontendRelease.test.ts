import { VisorFrontend } from '../VisorFrontend';
import type { IRenderer } from '../renderer/IRenderer';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import { deliveredScene } from './deliveredSceneFixture.ts';

/**
 * `release()` removes the viewer-click listener the frontend registered on its
 * renderer.  The `VtkScene` behind a client renderer survives a rebuild, so a
 * replaced frontend that is never released keeps picking geometry on every
 * click.  A second release removes nothing further.
 *
 * The same listener runs the geometry pick outside part mode; a pick that
 * fails is logged.
 */

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
        children: [],
    };
}

/** The renderer members the constructor reaches; each click registration returns its own remover. */
function makeRendererDouble() {
    return {
        domElement: document.createElement('div'),
        addViewerClickedListener: jest.fn(() => jest.fn()),
    };
}

/** A frontend over the double, and the remover of the one listener its constructor registered. */
function makeFrontend() {
    const renderer = makeRendererDouble();
    const frontend = new VisorFrontend(
        renderer as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        deliveredScene(),
        jest.fn(async () => undefined)
    );
    const remover = renderer.addViewerClickedListener.mock.results[0].value as jest.Mock;
    return { frontend, remover };
}

describe('VisorFrontend.release', () => {
    test('release removes the viewer-click listener the constructor registered', () => {
        const { frontend, remover } = makeFrontend();

        frontend.release();

        expect(remover).toHaveBeenCalledTimes(1);
    });

    test('a second release removes nothing further', () => {
        const { frontend, remover } = makeFrontend();

        frontend.release();
        frontend.release();

        expect(remover).toHaveBeenCalledTimes(1);
    });
});

describe('VisorFrontend geometry pick', () => {
    test('a failed geometry pick is logged', async () => {
        const error = new Error('x');
        const renderer = {
            domElement: document.createElement('div'),
            addViewerClickedListener: jest.fn(() => jest.fn()),
            clearGeometryHighlight: jest.fn(),
            pickGeometryAsync: jest.fn(async () => {
                throw error;
            }),
        };
        const frontend = new VisorFrontend(
            renderer as unknown as IRenderer,
            makeSceneGraphNode() as unknown as VisorVtkSceneNode,
            deliveredScene(),
            jest.fn(async () => undefined)
        );
        const geometryListener = (renderer.addViewerClickedListener.mock.calls[0] as unknown[])[0] as (
            ...args: unknown[]
        ) => void;
        const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
        try {
            frontend.setSelectionMode('vertex');

            geometryListener(null, false, false, 0.5, 0.5);
            await new Promise((resolve) => setTimeout(resolve, 0));

            expect(consoleError).toHaveBeenCalledWith('[VISOR] geometry pick failed', error);
        } finally {
            consoleError.mockRestore();
        }
    });
});
