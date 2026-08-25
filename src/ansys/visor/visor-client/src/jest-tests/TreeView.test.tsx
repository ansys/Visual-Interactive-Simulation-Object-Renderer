import { render, fireEvent } from '@testing-library/react';
import { TreeView, TreeViewUtil } from '../treeview/TreeView';
import {
    CreateVisorSceneGraph,
    VisorSceneNodeExtended,
    VisorSceneNodeSimple,
} from '../state/VisorSceneGraph.tsx';

describe('TreeView', () => {
    it('renders without a scene graph', () => {
        render(<TreeView />);
    });
    it('renders with a simple scene graph', () => {
        render(<TreeView sceneGraph={getSmallSceneGraph()} />);
    });
    it('renders with a complex scene graph', () => {
        render(<TreeView sceneGraph={getLargeSceneGraph()} />);
    });
    test('component util is not null for a simple scene graph', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getSmallSceneGraph()} onLoad={(u) => (util = u)} />);
        expect(util).toBeTruthy();
    });
    test('component util contains the correct node count for a simple scene graph', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getSmallSceneGraph()} onLoad={(u) => (util = u)} />);
        expect(util.nodeCount).toBe(2);
    });
    test('component util is not null for a complex scene graph', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        expect(util).toBeTruthy();
    });
    test('component util contains the correct node count for a complex scene graph', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        expect(util.nodeCount).toBe(8);
    });
    test('root node row is the first element in the rows array', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        expect(util.rows[0].node.nodeType).toBe('root');
    });
    test('root node row expand button works', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        const rootRow = util.rows[0];
        fireEvent.click(rootRow.expandButton);
        expect(rootRow.expanded).toBe(true);
    });
    test('root node row collapse button works', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        const rootRow = util.rows[0];
        fireEvent.click(rootRow.collapseButton);
        expect(rootRow.expanded).toBe(false);
    });
    test('root node row show button works', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        const rootRow = util.rows[0];
        fireEvent.click(rootRow.showButton);
        expect(rootRow.visible).toBe(true);
    });
    test('root node row hide button works', () => {
        let util: TreeViewUtil<VisorSceneNodeExtended> = null!;
        render(<TreeView sceneGraph={getLargeSceneGraph()} onLoad={(u) => (util = u)} />);
        const rootRow = util.rows[0];
        fireEvent.click(rootRow.hideButton);
        expect(rootRow.visible).toBe(false);
    });
});

function getSmallSceneGraph(): VisorSceneNodeExtended {
    return CreateVisorSceneGraph({
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
    });
}

function getLargeSceneGraph(): VisorSceneNodeExtended {
    return CreateVisorSceneGraph(getSceneNodeSimple());

    function getSceneNodeSimple(): VisorSceneNodeSimple {
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
                    id: 1,
                    dataArrays: [],
                    name: 'some-multiblock-file.vtm',
                    isGroupNode: true,
                    isActorNode: false,
                    nodeType: 'vtkMultiBlockDataSet',
                    diffuseColor: [1, 1, 1],
                    bounds: [],
                    children: [
                        {
                            id: 2,
                            dataArrays: [],
                            name: 'PolyData Container',
                            isGroupNode: true,
                            isActorNode: false,
                            nodeType: 'vtkMultiBlockDataSet',
                            diffuseColor: [1, 1, 1],
                            bounds: [],
                            children: [
                                {
                                    id: 3,
                                    dataArrays: [],
                                    name: 'mesh A',
                                    isGroupNode: false,
                                    isActorNode: true,
                                    nodeType: 'vtkPolyData',
                                    diffuseColor: [1, 1, 1],
                                    bounds: [],
                                    children: [],
                                },
                                {
                                    id: 4,
                                    dataArrays: [],
                                    name: 'mesh B',
                                    isGroupNode: false,
                                    isActorNode: true,
                                    nodeType: 'vtkPolyData',
                                    diffuseColor: [1, 1, 1],
                                    bounds: [],
                                    children: [],
                                },
                            ],
                        },
                        {
                            id: 5,
                            dataArrays: [],
                            name: 'mesh C',
                            isGroupNode: false,
                            isActorNode: true,
                            nodeType: 'vtkUnstructuredGrid',
                            diffuseColor: [1, 1, 1],
                            bounds: [],
                            children: [],
                        },
                        {
                            id: 6,
                            dataArrays: [],
                            name: 'mesh D',
                            isGroupNode: false,
                            isActorNode: true,
                            nodeType: 'vtkUnstructuredGrid',
                            diffuseColor: [1, 1, 1],
                            bounds: [],
                            children: [],
                        },
                        {
                            id: 7,
                            dataArrays: [],
                            name: 'mesh E',
                            isGroupNode: false,
                            isActorNode: true,
                            nodeType: 'vtkUnstructuredGrid',
                            diffuseColor: [1, 1, 1],
                            bounds: [],
                            children: [],
                        },
                    ],
                },
            ],
        };
    }
}
