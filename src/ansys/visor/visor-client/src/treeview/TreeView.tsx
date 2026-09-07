import { useEffect } from 'react';
import { AwcIcons } from '../components/AwcIcons';
import { escapeHtml, getRootFontSize, randomId, randomInt } from '../utils/JsHelpers';

/**
 * Describes a node that can be rendered by {@link TreeView}.
 *
 * @template T The concrete recursive node type.
 */
export interface ITreeViewNode<T extends ITreeViewNode<T>> {
    /** Unique identifier used to index the corresponding tree row. */
    id: number;
    /** Human-readable label displayed in the tree. */
    name: string;
    /** Whether the node should currently be visible in the underlying scene. */
    visible: boolean;
    /** Whether the node is currently selected in the underlying scene. */
    selected: boolean;
    /** Whether the node acts as a group that may contain child rows. */
    isGroupNode: boolean;
    /** Child nodes rendered beneath this node. */
    children: T[];
}

/**
 * Properties accepted by {@link TreeView}.
 *
 * @template T The concrete tree-node type.
 */
interface TreeViewProps<T extends ITreeViewNode<T>> {
    /** Root node of the scene graph to render. No tree is created when omitted. */
    sceneGraph?: T;
    /** Called after the tree has been built and its utility API is ready. */
    onLoad?: (util: TreeViewUtil<T>) => void;
}

/**
 * Runtime state and DOM handles associated with one rendered tree row.
 *
 * The object itself is read-only, while several properties expose mutable DOM
 * elements and child arrays managed internally by the tree.
 *
 * @template T The concrete tree-node type.
 */
export type TreeViewRow<T extends ITreeViewNode<T>> = Readonly<{
    /** Source node represented by this row. */
    node: T;
    /** Outer element containing this row and its descendant row elements. */
    nodeElem: HTMLDivElement;
    /** Table element that renders the interactive row. */
    tableElem: HTMLTableElement;
    /** Parent row, or `null` for the root row. */
    parentUtil: TreeViewRow<T> | null;
    /** Returns whether `row` appears in this row's root-to-self lineage. */
    contains: (row: TreeViewRow<T>) => boolean;
    /** Cached lineage ordered from the root row through this row, inclusive. */
    lineage: TreeViewRow<T>[];
    /** Whether this row's child container is expanded. */
    expanded: boolean;
    /** Whether this row is currently marked visible. */
    visible: boolean;
    /** Whether this row is currently selected. */
    selected: boolean;
    /** Button used to expand a group row. */
    expandButton: HTMLButtonElement;
    /** Button used to collapse a group row. */
    collapseButton: HTMLButtonElement;
    /** Button used to mark the row visible. */
    showButton: HTMLButtonElement;
    /** Button used to mark the row hidden. */
    hideButton: HTMLButtonElement;
    /** Whether this row represents a group node. */
    isComposite: boolean;
    /** Zero-based depth of the row, with the root at depth `0`. */
    depth: number;
    /** Position in the tree's flattened pre-order row array. */
    index: number;
    /** Direct child rows. */
    children: TreeViewRow<T>[];
    /** Selects this row and optionally all descendants. */
    selectRow: (recursive?: boolean) => void;
    /** Deselects this row and optionally all descendants. */
    deselectRow: (recursive?: boolean) => void;
    /** Marks this row visible and updates its visibility control. */
    show: () => void;
    /** Marks this row hidden and updates its visibility control. */
    hide: () => void;
}>;

/**
 * Imperative utility API exposed after a {@link TreeView} has loaded.
 *
 * @template T The concrete tree-node type.
 */
export type TreeViewUtil<T extends ITreeViewNode<T>> = Readonly<{
    /** Total number of rows in the flattened tree. */
    nodeCount: number;
    /** Flattened pre-order collection of all row utilities. */
    rows: TreeViewRow<T>[];
    /** Lookup table from node ID to its row utility. */
    rowUtilsMap: Map<number, TreeViewRow<T>>;
    /**
     * Registers a selection-change listener.
     *
     * @param handler Callback receiving the current selected-node array.
     * @returns A function that unregisters the listener.
     */
    addSelectionChangeListener: (handler: (selectedNodes: T[]) => void) => () => void;
    /**
     * Registers a visibility-change listener.
     *
     * @param handler Callback receiving the current visible-node array.
     * @returns A function that unregisters the listener.
     */
    addVisibilityChangeListener: (handler: (visibleNodes: T[]) => void) => () => void;
    /**
     * Rebuilds the selected-node array and reconciles group selection state.
     *
     * @param startingUtil Optional subtree root used for group-state reconciliation.
     */
    updateSelectedNodesArray: (startingUtil?: TreeViewRow<T> | null) => void;
    /** Mutable array containing the currently selected source nodes. */
    selectedNodes: T[];
    /** Mutable array containing the currently visible source nodes. */
    visibleNodes: T[];
    /**
     * Replaces the current selection with rows matching the supplied node IDs.
     *
     * @param selectedNodeIds Node IDs to select.
     * @param runEventListeners Whether to notify registered listeners; defaults to `true`.
     */
    setSelection: (selectedNodeIds: number[], runEventListeners?: boolean) => void;
    /** Synchronizes row visibility from each source node's `visible` property. */
    synchronize: () => void;
}>;

/**
 * Renders an imperative, searchable tree view for a recursive scene graph.
 *
 * Selection supports standard click, Ctrl-click, and Shift-click behavior.
 * Visibility controls can affect either one row, all selected rows, or a group
 * row and all of its descendants.
 *
 * @template T The concrete tree-node type.
 * @param props Tree configuration and optional load callback.
 * @returns The container element populated by the effect after mounting.
 */
export const TreeView = <T extends ITreeViewNode<T>>(props: TreeViewProps<T>) => {
    const { sceneGraph, onLoad = () => undefined } = props;
    const componentContainerElemId = randomId();
    useEffect(createTreeElem, []);
    return <div id={componentContainerElemId} className={'visor-tree-view nowrap'}></div>;

    /**
     * Builds the tree DOM, initializes row state, and exposes the utility API.
     *
     * @returns A React effect cleanup callback, or `undefined` when no graph exists.
     */
    function createTreeElem() {
        if (sceneGraph == null) {
            return;
        }
        const fontSize: number = getRootFontSize(14);
        const componentContainerElem = document.getElementById(
            componentContainerElemId
        ) as HTMLDivElement;
        const headerContainer = document.createElement('div');
        const treeContainer = document.createElement('div');
        componentContainerElem.appendChild(headerContainer);
        componentContainerElem.appendChild(treeContainer);
        const selectedNodes: T[] = [];
        const visibleNodes: T[] = [];
        const rowUtilsMap: Map<number, TreeViewRow<T>> = new Map();
        const rowUtilsArr: TreeViewRow<T>[] = [];
        const selectionChangeListeners: Record<string, (selectedNodes: T[]) => void> = {};
        const visibilityChangeListeners: Record<string, (visibleNodes: T[]) => void> = {};
        (() => {
            // placing these variable declarations inside an
            // IIFE so we don't pollute the outer scope
            const rootRow = createRowUtil(sceneGraph, 0, null);
            treeContainer.appendChild(rootRow.nodeElem);
            // Rows seed themselves from their node, but group rows are derived
            // from their descendants, so reconcile once the tree is built.
            updateVisibleNodesArray(null);
            updateSelectedNodesArray(null);
            const searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.placeholder = 'Search...';
            searchInput.oninput = (e) => {
                if (searchInput.value === '') {
                    rowUtilsArr.forEach((row) => {
                        row.tableElem.style.removeProperty('display');
                    });
                    return;
                }
                const lower = searchInput.value.toLowerCase();
                rowUtilsArr.forEach((row) => {
                    if (row.node.name.toLowerCase().includes(lower)) {
                        row.tableElem.style.removeProperty('display');
                    } else {
                        row.tableElem.style.display = 'none';
                    }
                });
            };
            const headerMarkup = getNodeMarkup(0);
            headerMarkup.nodeElem.style.marginBottom = '5px';
            headerMarkup.cells[1].appendChild(searchInput);
            headerContainer.appendChild(headerMarkup.nodeElem);
            // BHB 2025-06-19: per standup meeting on 2025-06-19 we are not
            // adding a "global" show/hide button for selected actors.
            // Showing/hiding all selected actors is done by clicking on the
            // show/hide button for any selected actor in the tree view.
            // addSelectedShowHideButton();

            /**
             * Adds the currently disabled global visibility control for selected rows.
             *
             * @remarks The caller is intentionally commented out per the dated note above.
             */
            function addSelectedShowHideButton() {
                const showButton = AwcIcons.getHideIcon(fontSize * 1.2, 3, true, [
                    'theme-hover-background-3',
                ]) as HTMLButtonElement;
                const hideButton = AwcIcons.getShowIcon(fontSize * 1.2, 3, true, [
                    'theme-hover-background-3',
                ]) as HTMLButtonElement;
                showButton.onclick = showSelected;
                hideButton.onclick = hideSelected;
                headerMarkup.cells[2].appendChild(showButton);
                headerMarkup.cells[2].appendChild(hideButton);
                showSelected(null);

                /**
                 * Marks all selected rows visible and emits a visibility-change event.
                 *
                 * @param e Optional originating mouse event.
                 */
                function showSelected(e: MouseEvent | null) {
                    showButton.remove();
                    headerMarkup.cells[2].appendChild(hideButton);
                    rowUtilsArr.forEach((u) => {
                        u.selected && u.show();
                    });
                    runVisibilityChangeListeners(visibleNodes);
                    e?.stopImmediatePropagation();
                }

                /**
                 * Marks all selected rows hidden and emits a visibility-change event.
                 *
                 * @param e Optional originating mouse event.
                 */
                function hideSelected(e: MouseEvent | null) {
                    hideButton.remove();
                    headerMarkup.cells[2].appendChild(showButton);
                    rowUtilsArr.forEach((u) => {
                        u.selected && u.hide();
                    });
                    runVisibilityChangeListeners(visibleNodes);
                    e?.stopImmediatePropagation();
                }
            }
        })();
        onLoad({
            nodeCount: rowUtilsArr.length,
            rows: rowUtilsArr,
            rowUtilsMap,
            addSelectionChangeListener: (handler) => {
                const key = randomInt();
                selectionChangeListeners[key] = handler;
                return () => delete selectionChangeListeners[key];
            },
            addVisibilityChangeListener: (handler) => {
                const key = randomInt();
                visibilityChangeListeners[key] = handler;
                return () => delete visibilityChangeListeners[key];
            },
            updateSelectedNodesArray,
            selectedNodes,
            visibleNodes,
            setSelection,
            synchronize,
        });
        return () => {
            // no useEffect() cleanup required
        };

        /**
         * Replaces the current selection using node IDs.
         *
         * @param selectedNodeIds IDs of rows to select.
         * @param runEventListeners Whether registered selection listeners should run.
         */
        function setSelection(selectedNodeIds: number[], runEventListeners: boolean = true) {
            rowUtilsArr.forEach((u) => u.deselectRow());
            for (const id of selectedNodeIds) {
                const rowUtil = rowUtilsMap.get(id);
                rowUtil != null && rowUtil.selectRow();
            }
            updateSelectedNodesArray(null);
            if (runEventListeners) {
                runSelectionChangeListeners(selectedNodes);
            }
        }

        /** Synchronizes every row's visibility and selection from its source node. */
        function synchronize() {
            rowUtilsArr.forEach((u) => {
                // The node owns the value; the row derives from it. `=== false`
                // and `=== true` keep a node that omits the field on the
                // previous defaults (visible, not selected).
                u.node.visible === false ? u.hide() : u.show();
                u.node.selected === true ? u.selectRow() : u.deselectRow();
            });
            updateVisibleNodesArray(null);
            updateSelectedNodesArray(null);
        }

        /**
         * Invokes all registered selection-change listeners.
         *
         * @param selectedNodes Current selected source nodes.
         */
        function runSelectionChangeListeners(selectedNodes: T[]) {
            Object.values(selectionChangeListeners).forEach((handler) => {
                handler(selectedNodes);
            });
        }

        /**
         * Invokes all registered visibility-change listeners.
         *
         * @param visibleNodes Current visible source nodes.
         */
        function runVisibilityChangeListeners(visibleNodes: T[]) {
            Object.values(visibilityChangeListeners).forEach((handler) => {
                handler(visibleNodes);
            });
        }

        /**
         * Creates the base DOM structure for a tree row or header row.
         *
         * @param depth Zero-based indentation depth.
         * @returns The outer element, table element, and first-row cells.
         */
        function getNodeMarkup(depth: number) {
            const nodeElem = document.createElement('div');
            let h = ``;
            h += `<table>`;
            h += `<tr>`;
            h += `<td class="shrink"></td>`;
            h += `<td></td>`;
            h += `<td class="shrink"></td>`;
            h += `</tr>`;
            h += `</table>`;
            nodeElem.innerHTML = h;
            const tableElem = nodeElem.getElementsByTagName('table')[0];
            tableElem.style.fontSize = `${fontSize}px`;
            tableElem.style.borderColor = 'transparent';
            tableElem.style.borderWidth = '2px 0';
            tableElem.style.userSelect = 'none';
            const cells = tableElem.rows[0].cells;
            cells[0].style.paddingLeft = `${fontSize * depth}px`;
            return {
                nodeElem,
                tableElem,
                cells,
            };
        }

        /**
         * Rebuilds `selectedNodes` and selects a group only when all descendants are selected.
         *
         * @param startingUtil Optional subtree root for group-state reconciliation.
         */
        function updateSelectedNodesArray(startingUtil?: TreeViewRow<T> | null) {
            selectedNodes.length = 0;
            startingUtil ??= rowUtilsArr[0];
            allDescendantsSelected(startingUtil);
            rowUtilsArr.forEach((u) => {
                u.selected && selectedNodes.push(u.node);
            });

            /**
             * Reconciles selection state for one row and its descendants.
             *
             * @param util Row whose subtree should be evaluated.
             * @returns `true` when the row or all of its descendants are selected.
             */
            function allDescendantsSelected(util: TreeViewRow<T>) {
                if (util.isComposite) {
                    let result = true;
                    for (const childUtil of util.children) {
                        if (!allDescendantsSelected(childUtil)) {
                            result = false;
                        }
                    }
                    if (!result) {
                        util.deselectRow();
                    } else {
                        util.selectRow();
                    }
                    return result;
                }
                return util.selected;
            }
        }

        /**
         * Rebuilds `visibleNodes` and derives group visibility from descendant visibility.
         *
         * @param startingUtil Optional subtree root for visibility reconciliation.
         */
        function updateVisibleNodesArray(startingUtil?: TreeViewRow<T> | null) {
            visibleNodes.length = 0;
            allDescendantsVisible(startingUtil ?? rowUtilsArr[0]);
            rowUtilsArr.forEach((u) => {
                u.visible && visibleNodes.push(u.node);
            });

            /**
             * Reconciles visibility state for one row and its descendants.
             *
             * @param util Row whose subtree should be evaluated.
             * @returns `true` when the row or at least one descendant is visible.
             */
            function allDescendantsVisible(util: TreeViewRow<T>) {
                if (util.isComposite) {
                    let result = false;
                    for (const childUtil of util.children) {
                        if (allDescendantsVisible(childUtil)) {
                            result = true;
                        }
                    }
                    if (!result) {
                        util.hide();
                    } else {
                        util.show();
                    }
                    return result;
                }
                return util.visible;
            }
        }

        /**
         * Recursively creates a rendered row and its runtime utility object.
         *
         * @param node Source node represented by the row.
         * @param depth Zero-based depth within the tree.
         * @param parentUtil Parent row utility, or `null` for the root.
         * @returns The initialized row utility.
         */
        function createRowUtil(node: T, depth: number, parentUtil: TreeViewRow<T> | null) {
            const { nodeElem, tableElem, cells } = getNodeMarkup(depth);
            cells[1].innerHTML = escapeHtml(node.name);
            const childrenDiv = document.createElement('div');
            nodeElem.appendChild(childrenDiv);
            tableElem.onclick = tableClick;
            let selected: boolean = false;
            let visible: boolean = false;
            const showButton = AwcIcons.getHideIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            const hideButton = AwcIcons.getShowIcon(fontSize * 1.2, 3, true, [
                'theme-hover-background-3',
            ]) as HTMLButtonElement;
            const getLineage: () => TreeViewRow<T>[] = (() => {
                const lineage: TreeViewRow<T>[] = [];
                return () => {
                    if (lineage.length === 0) {
                        let curUtil: TreeViewRow<T> | null = rowUtil;
                        while (curUtil != null) {
                            lineage.push(curUtil);
                            curUtil = curUtil.parentUtil;
                        }
                        lineage.reverse();
                        Object.freeze(lineage);
                    }
                    return lineage;
                };
            })();

            let expanded = false;
            let expandButton: HTMLButtonElement = null!;
            let collapseButton: HTMLButtonElement = null!;
            if (node.isGroupNode) {
                expandButton = AwcIcons.getArrowHeadRightIcon(fontSize * 1.2, 3, true, [
                    'theme-hover-background-3',
                ]) as HTMLButtonElement;
                collapseButton = AwcIcons.getArrowHeadDownIcon(fontSize * 1.2, 3, true, [
                    'theme-hover-background-3',
                ]) as HTMLButtonElement;
                expandButton.onclick = (e) => {
                    expand();
                    e.stopPropagation();
                };
                collapseButton.onclick = (e) => {
                    collapse();
                    e.stopPropagation();
                };
                expand();

                /** Expands the group row and reveals its child container. */
                function expand() {
                    expandButton!.remove();
                    cells[0].appendChild(collapseButton!);
                    childrenDiv.style.removeProperty('display');
                    expanded = true;
                }

                /** Collapses the group row and hides its child container. */
                function collapse() {
                    collapseButton!.remove();
                    cells[0].appendChild(expandButton!);
                    childrenDiv.style.display = 'none';
                    expanded = false;
                }
            } else {
                // cells[0].appendChild(AwcIcons.getNullIcon(0));
            }
            const rowUtil: TreeViewRow<T> = {
                node,
                nodeElem,
                tableElem,
                parentUtil,
                isComposite: node.isGroupNode,
                depth,
                index: rowUtilsArr.length,
                children: [],
                contains: (row) => {
                    return getLineage().includes(row);
                },
                get lineage() {
                    return getLineage();
                },
                get expanded() {
                    return expanded;
                },
                get visible() {
                    return visible;
                },
                get selected() {
                    return selected;
                },
                expandButton,
                collapseButton,
                showButton,
                hideButton,
                show() {
                    showButton.remove();
                    cells[2].appendChild(hideButton);
                    visible = true;
                },
                hide() {
                    hideButton.remove();
                    cells[2].appendChild(showButton);
                    visible = false;
                },
                selectRow: (recursive) => {
                    if (selected && !recursive) {
                        return;
                    }
                    tableElem.classList.add('theme-selected-background');
                    selected = true;
                    if (recursive === true) {
                        for (const child of rowUtil.children) {
                            child.selectRow(recursive);
                        }
                    }
                },
                deselectRow: (recursive) => {
                    if (!selected && !recursive) {
                        return;
                    }
                    tableElem.classList.remove('theme-selected-background');
                    selected = false;
                    if (recursive === true) {
                        for (const child of rowUtil.children) {
                            child.deselectRow(recursive);
                        }
                    }
                },
            };
            rowUtilsMap.set(node.id, rowUtil);
            showButton.onclick = (e) => {
                if (selected) {
                    rowUtilsArr.forEach((u) => {
                        u.selected && u.show();
                    });
                } else {
                    rowUtil.show();
                    if (rowUtil.isComposite) {
                        for (let i = rowUtil.index + 1; i < rowUtilsArr.length; i++) {
                            const u = rowUtilsArr[i];
                            if (u.depth <= rowUtil.depth) {
                                break;
                            }
                            u.show();
                        }
                    }
                }
                updateVisibleNodesArray(rowUtilsArr[0]);
                runVisibilityChangeListeners(visibleNodes);
                e.stopImmediatePropagation();
            };
            hideButton.onclick = (e) => {
                if (selected) {
                    rowUtilsArr.forEach((u) => {
                        u.selected && u.hide();
                    });
                } else {
                    rowUtil.hide();
                    if (rowUtil.isComposite) {
                        for (let i = rowUtil.index + 1; i < rowUtilsArr.length; i++) {
                            const u = rowUtilsArr[i];
                            if (u.depth <= rowUtil.depth) {
                                break;
                            }
                            u.hide();
                        }
                    }
                }
                updateVisibleNodesArray(rowUtilsArr[0]);
                runVisibilityChangeListeners(visibleNodes);
                e.stopImmediatePropagation();
            };
            // Seed the row from the node, which owns the value. Testing for
            // `=== false` / `=== true` rather than truthiness keeps a node that
            // omits the field on the previous defaults (visible, not selected).
            node.visible === false ? rowUtil.hide() : rowUtil.show();
            if (node.selected === true) {
                rowUtil.selectRow();
            }
            rowUtilsArr.push(rowUtil);
            cells[1].style.paddingLeft = `${fontSize / 4}px`;
            depth++;
            for (const childNode of node.children) {
                const childUtil = createRowUtil(childNode, depth, rowUtil);
                rowUtil.children.push(childUtil);
                childrenDiv.appendChild(childUtil.nodeElem);
            }
            return rowUtil;

            /**
             * Applies click, Ctrl-click, or Shift-click selection behavior for this row.
             *
             * @param e Mouse event raised by the row table.
             */
            function tableClick(e: MouseEvent) {
                if (e.ctrlKey && e.shiftKey) {
                    return;
                } else if (e.shiftKey) {
                    let startIndex = 0;
                    let endIndex = 0;
                    for (let i = rowUtil.index + 1; i < rowUtilsArr.length; i++) {
                        if (rowUtilsArr[i].selected) {
                            for (let c = i + 1; c < rowUtilsArr.length; c++) {
                                if (!rowUtilsArr[c].selected) {
                                    break;
                                }
                                i = c;
                            }
                            endIndex = i + 1;
                            break;
                        }
                    }
                    if (endIndex > 0) {
                        startIndex = rowUtil.index;
                    } else {
                        endIndex = rowUtil.index + 1;
                        for (let i = rowUtil.index - 1; i >= 0; i--) {
                            if (rowUtilsArr[i].selected) {
                                for (let c = i - 1; c >= 0; c--) {
                                    if (!rowUtilsArr[c].selected) {
                                        break;
                                    }
                                    i = c;
                                }
                                startIndex = i;
                                break;
                            }
                        }
                    }
                    for (let i = 0; i < startIndex; i++) {
                        rowUtilsArr[i].deselectRow();
                    }
                    for (let i = startIndex; i < endIndex; i++) {
                        const u = rowUtilsArr[i];
                        if (i === endIndex - 1 && u.isComposite) {
                            u.selectRow(true);
                            let newEndIndex = i + 1 + u.children.length;
                            for (let c = newEndIndex; c < rowUtilsArr.length; c++) {
                                if (rowUtilsArr[c].depth <= u.depth) {
                                    newEndIndex = c;
                                    break;
                                }
                            }
                            endIndex = newEndIndex;
                        } else {
                            u.selectRow();
                        }
                    }
                    for (let i = endIndex; i < rowUtilsArr.length; i++) {
                        rowUtilsArr[i].deselectRow();
                    }
                    updateSelectedNodesArray(null);
                    runSelectionChangeListeners(selectedNodes);
                    return;
                } else if (!e.ctrlKey) {
                    rowUtilsArr.forEach((u) => {
                        u.deselectRow();
                    });
                }
                if (selected) {
                    rowUtil.deselectRow(true);
                } else {
                    rowUtil.selectRow(true);
                }
                updateSelectedNodesArray(null);
                runSelectionChangeListeners(selectedNodes);
            }
        }
    }
};
