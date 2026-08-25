import { TreeViewUtil } from '../../treeview/TreeView.tsx';
import { VisorSceneNodeExtended } from '../../state/VisorSceneGraph.tsx';

export class Panel_TopLeft_Util {
    constructor(
        treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>,
        expandPanel: () => void,
        collapsePanel: () => void,
        getIsPanelCollapsed: () => boolean
    ) {
        this.treeViewUtil = treeViewUtil;
        this.expandPanel = expandPanel;
        this.collapsePanel = collapsePanel;
        this.#getIsPanelCollapsed = getIsPanelCollapsed;
    }

    readonly treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>;
    readonly expandPanel: () => void;
    readonly collapsePanel: () => void;
    readonly #getIsPanelCollapsed: () => boolean;

    get isPanelCollapsed() {
        return this.#getIsPanelCollapsed();
    }
}
