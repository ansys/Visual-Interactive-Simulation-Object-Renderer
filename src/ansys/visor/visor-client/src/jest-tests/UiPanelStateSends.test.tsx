import { render, fireEvent, act } from '@testing-library/react';
import { VisorFrontend } from '../VisorFrontend';
import { Panel_TopLeft } from '../components/ui-panels/Panel_TopLeft';
import { Panel_TopRight } from '../components/ui-panels/Panel_TopRight';
import { CreateVisorSceneGraph, VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import type { IRenderer } from '../renderer/IRenderer';
import type VisorVtkSceneNode from '../state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import type { Panel_TopLeft_Util } from '../components/ui-panels/Panel_TopLeft_Util.tsx';
import type { Panel_TopRight_Util } from '../components/ui-panels/Panel_TopRight_Util.tsx';

/**
 * The client half of server-owned UI panel state: the four `VisorFrontend`
 * send methods, and the per-panel mount gate that keeps a freshly mounted
 * panel silent.
 *
 * Two subjects, and they fail differently.
 *
 *   1. Each send method puts its own trigger name and the value it was given
 *      on the wire. A name mismatched by one character between the two stacks
 *      routes nowhere on the server, logs nothing and fails nothing, so the
 *      name strings are pinned here as hand-written literals -- as is every
 *      expected payload.
 *
 *   2. Every rebuild remounts every panel, and each mount runs
 *      `expandButton.click()` (both panels, twice in the top-right) and
 *      `propertyTabElem.onclick(null!)`. Those writes run *before* the util is
 *      registered. Were the gate open there, every refresh and every rebuild
 *      would report the client's mount defaults over the record the server
 *      just delivered, and a save in that window would record them -- correct
 *      under every other test, and wrong in the running application only.
 *      Tests 5 and 6 pin the gate closed at mount for each panel separately,
 *      because the two gate differently: the top-left gate is purely
 *      synchronous, the top-right gate spans two awaits.
 *
 * Tests 5 and 6 cannot see a gate that never opens -- a panel that reports
 * nothing at mount and nothing afterwards passes both. Test 7 is that pin,
 * on the top-right panel, whose gate is the one behind the awaits.
 *
 * Test 8 is a third subject and not a send at all: the top-right panel
 * initializes its properties panel from the tree view's current selection,
 * rather than from an empty list. A selection delivered before the panel
 * mounts reaches the rows and the mesh through `TreeViewUtil.synchronize()`,
 * which runs no selection-change listener, so an empty-list initialization
 * leaves the properties panel blank until the user clicks a part.
 *
 * jsdom has no `ResizeObserver` and jest here runs with no `setupFiles`
 * (`jest.config.cjs`), so the stub below is this module's own.
 */

class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;

/** Hand-written literals. Every expected payload below is built from these. */
const TOP_LEFT_PANEL_COLLAPSED = true;
const TOP_RIGHT_PANEL_COLLAPSED = true;
const TOP_RIGHT_LEGEND_COLLAPSED = false;
const TOP_RIGHT_TAB_INDEX = 1;

/**
 * The minimum root scene-graph node `CreateVisorSceneGraph` accepts, which
 * `VisorFrontend`'s constructor builds the live graph from. Same shape
 * `AppStateProjectionLoad.test.ts` uses, and no parts: nothing here reads one.
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

/**
 * Every renderer member `VisorFrontend`'s constructor reaches. The sends are
 * the subject; these are here so construction completes.
 */
function makeRendererDouble() {
    return {
        attachSceneGraph: jest.fn(),
        domElement: document.createElement('div'),
        addCameraSettledListener: jest.fn(() => jest.fn()),
        addViewerClickedListener: jest.fn(() => jest.fn()),
    };
}

/**
 * A real `VisorFrontend` over a sender double. Real, not a double: the trigger
 * name strings these tests pin are in the frontend's own source, and a double
 * would restate them instead of reading them.
 */
function makeFrontend(): {
    frontend: VisorFrontend;
    triggerSender: jest.Mock<Promise<unknown>, [string, unknown]>;
} {
    const triggerSender = jest.fn(async () => undefined) as unknown as jest.Mock<
        Promise<unknown>,
        [string, unknown]
    >;
    const frontend = new VisorFrontend(
        makeRendererDouble() as unknown as IRenderer,
        makeSceneGraphNode() as unknown as VisorVtkSceneNode,
        triggerSender
    );
    return { frontend, triggerSender };
}

/** The four sends, as jest mocks, for the two panels to call. */
function makeSendDoubles() {
    return {
        sendPanelTopLeftPanelCollapsedAsync: jest.fn(async () => undefined),
        sendPanelTopRightPanelCollapsedAsync: jest.fn(async () => undefined),
        sendPanelTopRightLegendCollapsedAsync: jest.fn(async () => undefined),
        sendPanelTopRightTabIndexAsync: jest.fn(async () => undefined),
    };
}

/**
 * A real scene graph, which `Panel_TopLeft` hands to its `TreeView`.
 *
 * The renderer is optional and defaults to absent, which is what the two
 * mount-gate tests want: they never reach a node method. A test whose selection
 * is non-empty does reach one -- the properties panel clears the colour
 * variable on a part with no data arrays -- and supplies the double below.
 */
function makeSceneGraph(renderer?: IRenderer): VisorSceneNodeExtended {
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
                    id: 1,
                    dataArrays: [],
                    name: 'some-polydata-file.vtp',
                    isGroupNode: false,
                    isActorNode: true,
                    nodeType: 'vtkUnstructuredGrid',
                    diffuseColor: [1, 1, 1],
                    bounds: [],
                    children: [],
                },
            ],
        },
        undefined,
        renderer
    );
}

/**
 * The renderer members a selected part's own methods reach while the
 * properties panel initializes. Nothing here is asserted on: the subject is
 * what the panel shows, and these exist so the node's calls complete.
 */
function makeNodeRendererDouble(): IRenderer {
    return {
        clearColorVariableAsync: jest.fn(async () => undefined),
        sendClearPartColorVariableAsync: jest.fn(async () => undefined),
    } as unknown as IRenderer;
}

/**
 * A `VisorFrontend` stand-in carrying only what `Panel_TopLeft`'s effect
 * reaches, plus a promise that settles when the panel hands over its util --
 * which is the moment the gate is expected to open.
 */
function makeTopLeftFrontendDouble() {
    const sends = makeSendDoubles();
    let registered: (util: Panel_TopLeft_Util) => void = () => {};
    const utilRegistered = new Promise<Panel_TopLeft_Util>((resolve) => {
        registered = resolve;
    });
    const visorState = {
        ...sends,
        sceneGraph: makeSceneGraph(),
        render: jest.fn(async () => undefined),
        setTreeViewUtil: jest.fn(),
        setPanelTopLeftUtil: jest.fn((util: Panel_TopLeft_Util) => registered(util)),
    };
    return { visorState, sends, utilRegistered };
}

/**
 * The same for `Panel_TopRight`, whose effect additionally awaits the tree-view
 * util and runs a selection pass before it registers.
 *
 * `selectedNodes` is what the tree view util holds when the panel's effect
 * reaches it. It defaults to empty -- the state a tree with nothing selected is
 * in -- so the two mount-gate tests below are unaffected by its presence.
 */
function makeTopRightFrontendDouble(selectedNodes: VisorSceneNodeExtended[] = []) {
    const sends = makeSendDoubles();
    let registered: (util: Panel_TopRight_Util) => void = () => {};
    const utilRegistered = new Promise<Panel_TopRight_Util>((resolve) => {
        registered = resolve;
    });
    const treeViewUtil = {
        addSelectionChangeListener: jest.fn(() => jest.fn()),
        rows: [],
        rowUtilsMap: new Map(),
        selectedNodes,
        updateSelectedNodesArray: jest.fn(),
    };
    const visorState = {
        ...sends,
        treeViewUtilPromise: Promise.resolve(treeViewUtil),
        addViewerClickedListener: jest.fn(() => jest.fn()),
        addSelectionModeChangedListener: jest.fn(() => jest.fn()),
        getSelectionMode: jest.fn(() => 'part' as const),
        render: jest.fn(async () => undefined),
        setSpectrumRangeAsync: jest.fn(async () => undefined),
        setPanelTopRightUtil: jest.fn((util: Panel_TopRight_Util) => registered(util)),
    };
    return { visorState, sends, utilRegistered };
}

describe('VisorFrontend UI panel send surface', () => {
    test('sendPanelTopLeftPanelCollapsedAsync sends set_panel_top_left_panel_collapsed with the value it was given', async () => {
        const { frontend, triggerSender } = makeFrontend();

        await frontend.sendPanelTopLeftPanelCollapsedAsync(TOP_LEFT_PANEL_COLLAPSED);

        expect(triggerSender).toHaveBeenCalledTimes(1);
        expect(triggerSender).toHaveBeenCalledWith('set_panel_top_left_panel_collapsed', {
            collapsed: true,
        });
    });

    test('sendPanelTopRightPanelCollapsedAsync sends set_panel_top_right_panel_collapsed with the value it was given', async () => {
        const { frontend, triggerSender } = makeFrontend();

        await frontend.sendPanelTopRightPanelCollapsedAsync(TOP_RIGHT_PANEL_COLLAPSED);

        expect(triggerSender).toHaveBeenCalledTimes(1);
        expect(triggerSender).toHaveBeenCalledWith('set_panel_top_right_panel_collapsed', {
            collapsed: true,
        });
    });

    test('sendPanelTopRightLegendCollapsedAsync sends set_panel_top_right_legend_collapsed with the value it was given', async () => {
        const { frontend, triggerSender } = makeFrontend();

        await frontend.sendPanelTopRightLegendCollapsedAsync(TOP_RIGHT_LEGEND_COLLAPSED);

        expect(triggerSender).toHaveBeenCalledTimes(1);
        expect(triggerSender).toHaveBeenCalledWith('set_panel_top_right_legend_collapsed', {
            collapsed: false,
        });
    });

    test('sendPanelTopRightTabIndexAsync sends set_panel_top_right_tab_index with the value it was given', async () => {
        const { frontend, triggerSender } = makeFrontend();

        await frontend.sendPanelTopRightTabIndexAsync(TOP_RIGHT_TAB_INDEX);

        expect(triggerSender).toHaveBeenCalledTimes(1);
        expect(triggerSender).toHaveBeenCalledWith('set_panel_top_right_tab_index', {
            tabIndex: 1,
        });
    });
});

describe('the panel mount gate', () => {
    test('Panel_TopLeft sends nothing while mounting', async () => {
        const { visorState, sends, utilRegistered } = makeTopLeftFrontendDouble();

        await act(async () => {
            render(
                <Panel_TopLeft
                    visorState={visorState as unknown as VisorFrontend}
                    onLoad={() => {}}
                />
            );
        });
        await utilRegistered;

        // The mount click has run and the util has been handed over, so the
        // gate is open now -- and nothing was reported on the way there.
        expect(visorState.setPanelTopLeftUtil).toHaveBeenCalledTimes(1);
        expect(sends.sendPanelTopLeftPanelCollapsedAsync).not.toHaveBeenCalled();
    });

    test('Panel_TopRight sends nothing while mounting', async () => {
        const { visorState, sends, utilRegistered } = makeTopRightFrontendDouble();

        await act(async () => {
            render(
                <Panel_TopRight
                    visorState={visorState as unknown as VisorFrontend}
                    onLoad={() => {}}
                />
            );
        });
        await utilRegistered;

        // Three mount writes here, not one: both blocks' expand clicks and the
        // tab call, all before the registration this has now awaited.
        expect(visorState.setPanelTopRightUtil).toHaveBeenCalledTimes(1);
        expect(sends.sendPanelTopRightPanelCollapsedAsync).not.toHaveBeenCalled();
        expect(sends.sendPanelTopRightLegendCollapsedAsync).not.toHaveBeenCalled();
        expect(sends.sendPanelTopRightTabIndexAsync).not.toHaveBeenCalled();
    });

    test('a click on a Panel_TopRight control after its util is registered sends exactly once', async () => {
        const { visorState, sends, utilRegistered } = makeTopRightFrontendDouble();
        const { container } = render(
            <Panel_TopRight visorState={visorState as unknown as VisorFrontend} onLoad={() => {}} />
        );
        await act(async () => {
            await utilRegistered;
        });

        // The panel's collapse button, located by structure: the ids in this
        // component are `randomId()`-generated, and the collapse-button cell is
        // the only `td.shrink.padding-all` in it. The legend's own collapse
        // button lives in a plain `td.shrink` inside the legend overlay.
        const collapseButton = container.querySelector(
            'td.shrink.padding-all > button'
        ) as HTMLButtonElement;
        expect(collapseButton).not.toBeNull();

        fireEvent.click(collapseButton);

        expect(sends.sendPanelTopRightPanelCollapsedAsync).toHaveBeenCalledTimes(1);
        expect(sends.sendPanelTopRightPanelCollapsedAsync).toHaveBeenCalledWith(true);
    });
});

describe('the properties panel at mount', () => {
    test("Panel_TopRight shows the tree view's current selection at mount", async () => {
        // The selection is already on the tree view util before the panel
        // mounts, which is what a refresh or a rebuild leaves behind: the rows
        // and the mesh carry it, and `synchronize()` puts it in this array
        // without running any selection-change listener. Nothing in this test
        // clicks anything, and nothing fires a selection event -- the handler
        // the panel registers with `addSelectionChangeListener` is captured by
        // the double and never invoked here.
        const sceneGraph = makeSceneGraph(makeNodeRendererDouble());
        const part = sceneGraph.children[0];
        const { visorState, utilRegistered } = makeTopRightFrontendDouble([part]);

        let container: HTMLElement = null!;
        await act(async () => {
            container = render(
                <Panel_TopRight
                    visorState={visorState as unknown as VisorFrontend}
                    onLoad={() => {}}
                />
            ).container;
        });
        await utilRegistered;

        // The name field, located by structure: the ids in this component are
        // `randomId()`-generated, and this is the component's only read-only
        // text input. It lives inside the property panel's body, which the
        // no-selection branch hides.
        const nameInput = container.querySelector(
            'input[type="text"][readonly]'
        ) as HTMLInputElement;
        expect(nameInput).not.toBeNull();
        expect(nameInput.value).toBe('some-polydata-file.vtp');
    });
});
