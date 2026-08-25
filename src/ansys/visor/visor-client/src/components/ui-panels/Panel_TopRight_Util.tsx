export class Panel_TopRight_Util {
    constructor(
        expandPanel: () => void,
        collapsePanel: () => void,
        expandLegend: () => void,
        collapseLegend: () => void,
        getIsPanelCollapsed: () => boolean,
        getIsLegendCollapsed: () => boolean,
        selectTab: (tabIndex: number) => void,
        getTabIndex: () => number
    ) {
        this.expandPanel = expandPanel;
        this.collapsePanel = collapsePanel;
        this.expandLegend = expandLegend;
        this.collapseLegend = collapseLegend;
        this.#getIsPanelCollapsed = getIsPanelCollapsed;
        this.#getIsLegendCollapsed = getIsLegendCollapsed;
        this.selectTab = selectTab;
        this.#getTabIndex = getTabIndex;
    }

    readonly collapsePanel: () => void;
    readonly expandPanel: () => void;
    readonly collapseLegend: () => void;
    readonly expandLegend: () => void;
    readonly #getIsPanelCollapsed: () => boolean;
    readonly #getIsLegendCollapsed: () => boolean;

    get isPanelCollapsed() {
        return this.#getIsPanelCollapsed();
    }

    get isLegendCollapsed() {
        return this.#getIsLegendCollapsed();
    }

    readonly selectTab: (tabIndex: number) => void;
    readonly #getTabIndex: () => number;

    get tabIndex() {
        return this.#getTabIndex();
    }
}
