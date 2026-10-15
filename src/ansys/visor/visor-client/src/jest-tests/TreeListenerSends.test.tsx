import { render, fireEvent, act } from '@testing-library/react';
import { VisorFrontend } from '../VisorFrontend';
import { Panel_TopLeft } from '../components/ui-panels/Panel_TopLeft';
import { TreeViewUtil } from '../treeview/TreeView';
import { CreateVisorSceneGraph, VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type { IRenderer } from '../renderer/IRenderer';
import { deliveredPart, deliveredScene } from './deliveredSceneFixture.ts';

/**
 * The sends a tree interaction makes through `Panel_TopLeft`'s visibility and
 * selection listeners: each part whose value changes sends once, and a part
 * whose value does not change sends nothing.
 *
 * The scene is a root holding a group (parts 1 and 2) and part 3 outside it.
 * Each listener is fire-and-forget and ends with `visorState.render()`, so
 * every test awaits that call rather than a count of microtasks.
 */

const GROUP_ID = 10;
const PART_1_ID = 1;
const PART_2_ID = 2;
const PART_3_ID = 3;

/** The renderer members a part's visibility and selection methods reach. */
function makeRendererDouble() {
    return {
        setVisibilityAsync: jest.fn(async () => undefined),
        sendPartVisibilityAsync: jest.fn(async () => undefined),
        setSelectedAsync: jest.fn(async () => undefined),
        sendPartSelectedAsync: jest.fn(async () => undefined),
    };
}

function makeSceneGraph(
    renderer: IRenderer,
    part1Overrides: Record<string, unknown> = {}
): VisorSceneNodeExtended {
    const part = (id: number, name: string) => ({
        id,
        dataArrays: [],
        name,
        isGroupNode: false,
        isActorNode: true,
        nodeType: 'vtkPolyData',
        diffuseColor: [1, 1, 1],
        bounds: [],
        children: [],
    });
    return CreateVisorSceneGraph(
        {
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
                    id: GROUP_ID,
                    dataArrays: [],
                    name: 'group',
                    isGroupNode: true,
                    isActorNode: false,
                    nodeType: 'vtkMultiBlockDataSet',
                    diffuseColor: [1, 1, 1],
                    bounds: [],
                    children: [part(PART_1_ID, 'part 1'), part(PART_2_ID, 'part 2')],
                },
                part(PART_3_ID, 'part 3'),
            ],
        },
        deliveredScene(
            deliveredPart(PART_1_ID, part1Overrides),
            deliveredPart(PART_2_ID),
            deliveredPart(PART_3_ID)
        ),
        undefined,
        renderer
    );
}

/**
 * Mounts `Panel_TopLeft` over a stand-in frontend and returns the tree util,
 * the renderer double, and a function returning a promise for the next
 * `render()` call.
 */
async function mountPanel(part1Overrides: Record<string, unknown> = {}) {
    const renderer = makeRendererDouble();
    let treeViewUtil: TreeViewUtil<VisorSceneNodeExtended> = null!;
    let rendered: () => void = () => {};
    const visorState = {
        sceneGraph: makeSceneGraph(renderer as unknown as IRenderer, part1Overrides),
        render: jest.fn(async () => rendered()),
        setTreeViewUtil: jest.fn((u: TreeViewUtil<VisorSceneNodeExtended>) => {
            treeViewUtil = u;
        }),
        setPanelTopLeftUtil: jest.fn(),
        sendPanelTopLeftPanelCollapsedAsync: jest.fn(async () => undefined),
    };
    await act(async () => {
        render(<Panel_TopLeft visorState={visorState as unknown as VisorFrontend} onLoad={() => {}} />);
    });
    const nextRender = () =>
        new Promise<void>((resolve) => {
            rendered = resolve;
        });
    return { renderer, treeViewUtil, nextRender };
}

describe('tree visibility listener', () => {
    test('hiding one part in a multi-part tree sends its visibility once', async () => {
        const { renderer, treeViewUtil, nextRender } = await mountPanel();
        const done = nextRender();

        fireEvent.click(treeViewUtil.rowUtilsMap.get(PART_2_ID)!.hideButton);
        await done;

        expect(renderer.sendPartVisibilityAsync.mock.calls).toEqual([[2, false]]);
    });

    test('hiding a group row sends once per visible part in the group and none outside it', async () => {
        const { renderer, treeViewUtil, nextRender } = await mountPanel();
        const done = nextRender();

        fireEvent.click(treeViewUtil.rowUtilsMap.get(GROUP_ID)!.hideButton);
        await done;

        expect(renderer.sendPartVisibilityAsync.mock.calls).toEqual([
            [1, false],
            [2, false],
        ]);
    });
});

describe('tree selection listener', () => {
    test('adding a part to the selection sends its selection once', async () => {
        const { renderer, treeViewUtil, nextRender } = await mountPanel({ selected: true });
        const done = nextRender();

        fireEvent.click(treeViewUtil.rowUtilsMap.get(PART_3_ID)!.tableElem, { ctrlKey: true });
        await done;

        expect(renderer.sendPartSelectedAsync.mock.calls).toEqual([[3, true]]);
    });
});

