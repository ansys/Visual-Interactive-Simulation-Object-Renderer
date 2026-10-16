import { TreeViewUtil } from '../../treeview/TreeView.tsx';
import { VisorSceneNodeExtended } from '../../state/VisorSceneGraph.tsx';

export class Panel_TopLeft_Util {
    constructor(
        treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>,
        applyPanelCollapsed: (collapsed: boolean) => void,
        getIsPanelCollapsed: () => boolean
    ) {
        this.treeViewUtil = treeViewUtil;
        this.#applyPanelCollapsed = applyPanelCollapsed;
        this.#getIsPanelCollapsed = getIsPanelCollapsed;
    }

    readonly treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>;
    readonly #applyPanelCollapsed: (collapsed: boolean) => void;
    readonly #getIsPanelCollapsed: () => boolean;

    /** Collapse or expand the panel; send nothing. */
    applyPanelCollapsed(collapsed: boolean): void {
        this.#applyPanelCollapsed(collapsed);
    }

    get isPanelCollapsed() {
        return this.#getIsPanelCollapsed();
    }
}
