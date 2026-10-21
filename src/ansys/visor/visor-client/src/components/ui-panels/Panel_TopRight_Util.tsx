export class Panel_TopRight_Util {
    constructor(
        applyPanelCollapsed: (collapsed: boolean) => void,
        applyLegendCollapsed: (collapsed: boolean) => void,
        applyTabIndex: (index: number) => void,
        getIsPanelCollapsed: () => boolean,
        getIsLegendCollapsed: () => boolean,
        getTabIndex: () => number,
        refreshSelectionAsync: () => Promise<void>
    ) {
        this.#applyPanelCollapsed = applyPanelCollapsed;
        this.#applyLegendCollapsed = applyLegendCollapsed;
        this.#applyTabIndex = applyTabIndex;
        this.#getIsPanelCollapsed = getIsPanelCollapsed;
        this.#getIsLegendCollapsed = getIsLegendCollapsed;
        this.#getTabIndex = getTabIndex;
        this.refreshSelectionAsync = refreshSelectionAsync;
    }

    readonly #applyPanelCollapsed: (collapsed: boolean) => void;
    readonly #applyLegendCollapsed: (collapsed: boolean) => void;
    readonly #applyTabIndex: (index: number) => void;
    readonly #getIsPanelCollapsed: () => boolean;
    readonly #getIsLegendCollapsed: () => boolean;
    readonly #getTabIndex: () => number;

    /** Collapse or expand the panel; send nothing. */
    applyPanelCollapsed(collapsed: boolean): void {
        this.#applyPanelCollapsed(collapsed);
    }

    /** Collapse or expand the legend overlay; send nothing. */
    applyLegendCollapsed(collapsed: boolean): void {
        this.#applyLegendCollapsed(collapsed);
    }

    /** Select the tab; send nothing.  Other indices do nothing, as today. */
    applyTabIndex(index: number): void {
        this.#applyTabIndex(index);
    }

    get isPanelCollapsed() {
        return this.#getIsPanelCollapsed();
    }

    get isLegendCollapsed() {
        return this.#getIsLegendCollapsed();
    }

    get tabIndex() {
        return this.#getTabIndex();
    }

    /** Re-reads the current selection into the properties and legend panels. */
    readonly refreshSelectionAsync: () => Promise<void>;
}
