import { getVariableManager, VisorVariableCollection } from './state/VisorVariableManager.tsx';
import { CreateVisorSceneGraph, VisorSceneNodeExtended } from './state/VisorSceneGraph.tsx';
import { getPromiseResolver } from './utils/JsHelpers';
import VisorAppState from './state/appstate/VisorAppState.tsx';
import VisorDatasetState from './state/appstate/VisorDatasetState.tsx';
import VisorPartState from './state/appstate/VisorPartState.tsx';
import VisorSceneState from './state/appstate/VisorSceneState.tsx';
import { TreeViewUtil } from './treeview/TreeView.tsx';
import { StateInput } from './state/appstate/VisorStateCommon.tsx';
import VisorVtkSceneNode from './state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import { IRenderer, VisorCameraState } from './renderer/IRenderer';
import type { TrameTriggerSender } from './renderer/IRenderer';
import { Panel_TopRight_Util } from './components/ui-panels/Panel_TopRight_Util.tsx';
import { Panel_TopLeft_Util } from './components/ui-panels/Panel_TopLeft_Util.tsx';
import { FullscreenWidget } from './widgets/fullscreenWidget.ts';
import { UiScaffoldUtil } from './components/UiScaffold.tsx';

export type { VisorCameraState } from './renderer/IRenderer';

export class VisorFrontend {
    constructor(
        renderer: IRenderer,
        sceneGraphNode: VisorVtkSceneNode,
        deliveredScene: VisorSceneState,
        triggerSender: TrameTriggerSender
    ) {
        const variableManager = getVariableManager();
        const sceneGraph = CreateVisorSceneGraph(
            sceneGraphNode,
            deliveredScene,
            variableManager,
            renderer
        );
        variableManager.finishAddingDataArrayMetadata();

        let treeViewUtilSet: boolean = false;
        let panelTopLeftUtilSet: boolean = false;
        let panelTopRightUtilSet: boolean = false;
        let uiScaffoldUtilSet: boolean = false;
        const { promise: treeViewUtilPromise, resolver: treeViewUtilResolve } =
            getPromiseResolver<TreeViewUtil<VisorSceneNodeExtended>>();
        const {
            isSet: isPanelTopLeftUtilSet,
            promise: panelTopLeftUtilPromise,
            resolver: panelTopLeftUtilResolve,
        } = getPromiseResolver<Panel_TopLeft_Util>();
        const {
            isSet: isPanelTopRightUtilSet,
            promise: panelTopRightUtilPromise,
            resolver: panelTopRightUtilResolve,
        } = getPromiseResolver<Panel_TopRight_Util>();
        const {
            isSet: isUiScaffoldUtilSet,
            promise: uiScaffoldUtilPromise,
            resolver: uiScaffoldUtilResolve,
        } = getPromiseResolver<UiScaffoldUtil>();
        let darkMode: boolean = true;

        // TODO: uncomment these lines when the dataset addition bug is fixed
        // const orientationWidget = vtkScene.getVtkObject(vtkInfo.orientationWidgetWasmId);
        // use "void" here to suppress the "no await" IDE warning
        // void orientationWidget.SetShouldResetCamera(false);

        let themeDarkCss: string | null | undefined = null;
        let themeLightCss: string | null | undefined = null;
        let themeStyleElem: HTMLStyleElement | null | undefined = null;

        // Respect base path prefix set by the Dash component (for reverse-proxy deployments).
        const bp: string = ((window as any).__visorArgs?.basePath ?? '').replace(/\/$/, '');

        this.globalVariableCollection = variableManager.globalVariableCollection;
        this.#unit = '';
        this.darkMode = darkMode;
        this.render = async () => {
            await renderer.renderAsync();
        };
        this.resizeAsync = async () => {
            await renderer.resizeAsync();
        };
        this.domElement = renderer.domElement;
        this.getCameraStateAsync = () => renderer.getCameraStateAsync();
        this.defaultActorColor = [];
        // Reports one variable slot's range; errors are logged, not rethrown,
        // since the client already applied the range locally.
        this.sendVariableRangeAsync = async (variableId, component, min, max) => {
            try {
                await triggerSender('set_variable_range', { variableId, component, min, max });
            } catch (err) {
                console.error(
                    `[VISOR] variable range trigger send failed: variableId='${variableId}' component=${component}`,
                    err
                );
            }
        };
        this.setVariableRangeAsync = async (variableId, component, min, max) => {
            const variable = variableManager.globalVariableCollection.getVariable(variableId);
            if (variable == null) {
                return;
            }
            variable.setCustomRange(component, min, max);
            for (const actorNode of sceneGraph.descendantActorNodesOrSelfArray) {
                if (
                    actorNode.variableId === variableId &&
                    actorNode.variableComponent == component
                ) {
                    await actorNode.setScalarRangeAsync(min, max);
                }
            }
            await this.sendVariableRangeAsync(variableId, component, min, max);
        };
        this.addCameraChangedListener = (callback) => {
            return renderer.addCameraChangedListener(callback);
        };
        this.addFrameRenderedListener = (callback) => {
            return renderer.addFrameRenderedListener((fps) => {
                callback(fps);
            });
        };
        this.addViewerClickedListener = (callback) => {
            return renderer.addViewerClickedListener(
                (nodeId, ctrlKey, shiftKey, _normX, _normY) => {
                    const node =
                        nodeId == null
                            ? null
                            : sceneGraph.descendantActorNodesOrSelfDictionary[nodeId];
                    callback(node ?? null, ctrlKey, shiftKey);
                }
            );
        };

        // Selection mode ─────────────────────────────────────────────────────
        type SelectionMode = 'part' | 'vertex' | 'edge' | 'face';
        let selectionMode: SelectionMode = 'part';
        const selectionModeChangedListeners = new Map<() => void, (mode: SelectionMode) => void>();
        const geometryPickedListeners = new Map<() => void, (result: any) => void>();

        this.getSelectionMode = () => selectionMode;
        this.setSelectionMode = (mode: SelectionMode) => {
            selectionMode = mode;
            // Clear the geometry highlight whenever mode changes
            renderer.clearGeometryHighlight();
            for (const cb of selectionModeChangedListeners.values()) cb(mode);
        };
        this.addSelectionModeChangedListener = (callback) => {
            const remover = () => selectionModeChangedListeners.delete(remover);
            selectionModeChangedListeners.set(remover, callback);
            return remover;
        };
        this.addGeometryPickedListener = (callback) => {
            const remover = () => geometryPickedListeners.delete(remover);
            geometryPickedListeners.set(remover, callback);
            return remover;
        };
        this.pickGeometryAsync = async (normX: number, normY: number) => {
            const mode = selectionMode;
            if (mode === 'part') return null;
            const result = await renderer.pickGeometryAsync(normX, normY, mode);
            // Highlight the picked feature; the renderer decides where it is drawn
            renderer.setGeometryHighlightAsync(result).catch(() => {});
            for (const cb of geometryPickedListeners.values()) cb(result);
            return result;
        };

        // Extended viewer click listener that also triggers geometry picking.
        // The remover is held because the `VtkScene` behind the renderer
        // survives a client rebuild: a listener left registered keeps picking
        // for a frontend that has been replaced.  `#private` because
        // `Object.freeze(this)` below makes a public field assigned after
        // construction throw.
        this.#viewerClickedRemover = renderer.addViewerClickedListener(
            (_nodeId, _ctrlKey, _shiftKey, normX, normY) => {
                if (selectionMode !== 'part') {
                    this.pickGeometryAsync(normX, normY).catch((err) =>
                        console.error('[VISOR] geometry pick failed', err)
                    );
                }
            }
        );
        this.release = () => {
            const remover = this.#viewerClickedRemover;
            // Cleared first, so a second call is a no-op.
            this.#viewerClickedRemover = null;
            remover?.();
        };
        this.sceneGraph = sceneGraph;
        this.treeViewUtilPromise = treeViewUtilPromise;
        this.panelTopLeftUtilPromise = panelTopLeftUtilPromise;
        this.panelTopRightUtilPromise = panelTopRightUtilPromise;
        this.uiScaffoldUtilPromise = uiScaffoldUtilPromise;
        this.setTreeViewUtil = (treeViewUtil) => {
            if (treeViewUtil == null) {
                throw new Error('treeViewUtil cannot be null');
            } else if (treeViewUtilSet) {
                throw new Error('treeViewUtil has already been set');
            }
            treeViewUtilSet = true;
            treeViewUtilResolve(treeViewUtil);
        };
        this.setPanelTopLeftUtil = (panelTopLeftUtil) => {
            if (panelTopLeftUtil == null) {
                throw new Error('panelTopLeftUtil cannot be null');
            } else if (panelTopLeftUtilSet) {
                throw new Error('panelTopLeftUtil has already been set');
            }
            panelTopLeftUtilSet = true;
            panelTopLeftUtilResolve(panelTopLeftUtil);
        };
        this.setPanelTopRightUtil = (panelTopRightUtil) => {
            if (panelTopRightUtil == null) {
                throw new Error('panelTopRightUtil cannot be null');
            } else if (panelTopRightUtilSet) {
                throw new Error('panelTopRightUtil has already been set');
            }
            panelTopRightUtilSet = true;
            panelTopRightUtilResolve(panelTopRightUtil);
        };
        this.setUiScaffoldUtil = (uiScaffoldUtil) => {
            if (uiScaffoldUtil == null) {
                throw new Error('uiScaffoldUtil cannot be null');
            } else if (uiScaffoldUtilSet) {
                throw new Error('uiScaffoldUtil has already been set');
            }
            uiScaffoldUtilSet = true;
            uiScaffoldUtilResolve(uiScaffoldUtil);
        };
        // Reports one panel field per call; errors are logged, not rethrown,
        // since the client already applied the change locally.
        const sendUiPanelTriggerAsync = async (
            triggerName: string,
            payload: Record<string, unknown>
        ): Promise<void> => {
            try {
                await triggerSender(triggerName, payload);
            } catch (err) {
                console.error(
                    `[VISOR] ui panel trigger send failed: trigger='${triggerName}'`,
                    err
                );
            }
        };
        this.sendPanelTopLeftPanelCollapsedAsync = (collapsed) =>
            sendUiPanelTriggerAsync('set_panel_top_left_panel_collapsed', { collapsed });
        this.sendPanelTopRightPanelCollapsedAsync = (collapsed) =>
            sendUiPanelTriggerAsync('set_panel_top_right_panel_collapsed', { collapsed });
        this.sendPanelTopRightLegendCollapsedAsync = (collapsed) =>
            sendUiPanelTriggerAsync('set_panel_top_right_legend_collapsed', { collapsed });
        this.sendPanelTopRightTabIndexAsync = (tabIndex) =>
            sendUiPanelTriggerAsync('set_panel_top_right_tab_index', { tabIndex });
        const fullscreenWidget = new FullscreenWidget();
        this.toggleFullScreenAsync = () => fullscreenWidget.setFullScreenAsync();
        this.setEdgeVisibilityGlobalAsync = (visible) =>
            renderer.setEdgeVisibilityGlobalAsync(visible);
        this.setCrossSectionVisibilityAsync = (visible) =>
            renderer.setCrossSectionVisibilityAsync(visible);
        this.setBoundingBoxVisibilityAsync = (visible) =>
            renderer.setBoundingBoxVisibilityAsync(visible);
        this.setOrthographicModeAsync = async () => {
            await renderer.setOrthographicModeAsync();
            const uiScaffold = await uiScaffoldUtilPromise;
            uiScaffold.setUnit(this.#unit);
        };
        this.getAppStateAsync = async (keyedByName) => {
            const appState = new VisorAppState();
            const uiState = appState.ui;
            uiState.setDarkTheme(darkMode);
            if (isPanelTopLeftUtilSet()) {
                const panelTopLeft = await panelTopLeftUtilPromise;
                uiState.setPanelTopLeftPanelCollapsed(panelTopLeft.isPanelCollapsed);
            }
            if (isPanelTopRightUtilSet()) {
                const panelTopRight = await panelTopRightUtilPromise;
                uiState.setPanelTopRightPanelCollapsed(panelTopRight.isPanelCollapsed);
                uiState.setPanelTopRightLegendCollapsed(panelTopRight.isLegendCollapsed);
                uiState.setPanelTopRightTabIndex(panelTopRight.tabIndex);
            }
            const sceneState = appState.scene;
            sceneState.setUnit(this.#unit);
            sceneState.setOrthographicEnabled(renderer.isOrthographicEnabled());
            sceneState.setCrossSectionEnabled(renderer.isCrossSectionVisible());
            sceneState.setEdgesEnabled(renderer.areEdgesVisibleGlobally());
            sceneState.setBoundingBoxEnabled(renderer.isBoundingBoxVisible());
            const currentCameraState = await renderer.getCameraStateAsync();
            sceneState.camera.setPosition(currentCameraState.position as number[]);
            sceneState.camera.setFocalPoint(currentCameraState.focalPoint as number[]);
            sceneState.camera.setViewUp(currentCameraState.viewUp as number[]);
            sceneState.camera.setClippingRange(currentCameraState.clippingRange as number[]);
            sceneState.camera.setParallelProjection(currentCameraState.parallelProjection);
            sceneState.camera.setViewAngle(currentCameraState.viewAngle);
            sceneState.camera.setParallelScale(currentCameraState.parallelScale);
            sceneState.crossSection.setOrigin(
                (await renderer.getCrossSectionOriginAsync()) as number[]
            );
            sceneState.crossSection.setNormal(
                (await renderer.getCrossSectionNormalAsync()) as number[]
            );
            for (const datasetNode of sceneGraph.children) {
                const datasetState = new VisorDatasetState();
                datasetState.setId(datasetNode.id.toString());
                datasetState.setKeyedByName(keyedByName);
                datasetState.setName(datasetNode.name);
                for (const partNode of datasetNode.descendantActorNodesOrSelfArray) {
                    const partState = new VisorPartState();
                    partState.setId(partNode.id.toString());
                    partState.setKeyedByName(keyedByName);
                    partState.setName(partNode.name);
                    partState.setVisible(partNode.visible);
                    partState.setDiffuseRgb(partNode.diffuseRgb);
                    partState.setOpacity(partNode.opacity);
                    partState.setSelected(partNode.selected);
                    partState.setVariableId(partNode.variableId);
                    partState.setVariableComponent(partNode.variableComponent);
                    datasetState.copyPart(partState);
                }
                sceneState.copyDataset(datasetState);
            }
            // No variable block: the server owns the variable records and
            // delivers them on every push.  Carrying a copy across a rebuild
            // would replace the delivered records with this one.
            return appState;
        };
        this.setAppStateAsync = async (state, updateUI) => {
            const appState = new VisorAppState(state);
            const uiState = appState.ui;
            if (uiState.darkTheme !== undefined) {
                darkMode = uiState.darkTheme;
                if (themeDarkCss == null) {
                    const response = await fetch(`${bp}/css/theme-dark.css`);
                    themeDarkCss = await response.text();
                }
                if (themeLightCss == null) {
                    const response = await fetch(`${bp}/css/theme-light.css`);
                    themeLightCss = await response.text();
                }
                // Ensure the theme style element exists
                // and is a child of the <head> element.
                if (themeStyleElem == null) {
                    const styleElemId = `__visorThemeStyle`;
                    themeStyleElem = document.getElementById(styleElemId) as HTMLStyleElement;
                    if (themeStyleElem == null) {
                        themeStyleElem = document.createElement('style');
                        themeStyleElem.id = styleElemId;
                    }
                }
                if (darkMode) {
                    themeStyleElem.innerHTML = themeDarkCss;
                } else {
                    themeStyleElem.innerHTML = themeLightCss;
                }
                if (themeStyleElem.parentNode !== document.head) {
                    document.head.appendChild(themeStyleElem);
                }
            }
            void (async () => {
                const panelTopLeft = await panelTopLeftUtilPromise;
                if (uiState.panelTopLeftPanelCollapsed !== undefined) {
                    panelTopLeft.applyPanelCollapsed(uiState.panelTopLeftPanelCollapsed);
                }
            })();
            void (async () => {
                const panelTopRight = await panelTopRightUtilPromise;
                if (uiState.panelTopRightPanelCollapsed !== undefined) {
                    panelTopRight.applyPanelCollapsed(uiState.panelTopRightPanelCollapsed);
                }
                if (uiState.panelTopRightLegendCollapsed !== undefined) {
                    panelTopRight.applyLegendCollapsed(uiState.panelTopRightLegendCollapsed);
                }
                if (uiState.panelTopRightTabIndex !== undefined) {
                    panelTopRight.applyTabIndex(uiState.panelTopRightTabIndex);
                }
            })();
            const promises: Promise<unknown>[] = [];
            const sceneState = appState.scene;
            if (sceneState.unit !== undefined) {
                const unit = (this.#unit = sceneState.unit);
                void (async () => {
                    const uiScaffold = await uiScaffoldUtilPromise;
                    uiScaffold.setUnit(unit);
                })();
            }
            // `sceneState.orthographicEnabled` is deliberately not read;
            // projection's sole writer is the camera write below. See
            // AppStateProjectionLoad.test.ts for why.
            if (sceneState.crossSectionEnabled !== undefined) {
                const promise = renderer.applyCrossSectionVisibilityAsync(
                    sceneState.crossSectionEnabled
                );
                promises.push(promise);
            }
            if (sceneState.edgesEnabled !== undefined) {
                const promise = renderer.applyEdgeVisibilityGlobalAsync(sceneState.edgesEnabled);
                promises.push(promise);
            }
            if (sceneState.boundingBoxEnabled !== undefined) {
                const promise = renderer.applyBoundingBoxVisibilityAsync(
                    sceneState.boundingBoxEnabled
                );
                promises.push(promise);
            }
            const cameraState = sceneState.camera;
            if (cameraState.position !== undefined) {
                const promise = renderer.setCameraPositionAsync(cameraState.position);
                promises.push(promise);
            }
            if (cameraState.focalPoint !== undefined) {
                const promise = renderer.setCameraFocalPointAsync(cameraState.focalPoint);
                promises.push(promise);
            }
            if (cameraState.viewUp !== undefined) {
                const promise = renderer.setCameraViewUpAsync(cameraState.viewUp);
                promises.push(promise);
            }
            if (cameraState.clippingRange !== undefined) {
                const promise = renderer.setCameraClippingRangeAsync(cameraState.clippingRange);
                promises.push(promise);
            }
            if (cameraState.parallelProjection !== undefined) {
                // Routed through applyOrthographicModeAsync, not setCameraParallelProjectionAsync: only
                // the former also sets the widget flag, so the latter would leave it stale for the next save.
                const promise = renderer.applyOrthographicModeAsync(cameraState.parallelProjection);
                promises.push(promise);
            }
            if (cameraState.viewAngle !== undefined) {
                const promise = renderer.setCameraViewAngleAsync(cameraState.viewAngle);
                promises.push(promise);
            }
            if (cameraState.parallelScale !== undefined) {
                const promise = renderer.setCameraParallelScaleAsync(cameraState.parallelScale);
                promises.push(promise);
            }
            const crossSectionState = sceneState.crossSection;
            if (crossSectionState.origin !== undefined) {
                const promise = renderer.setCrossSectionOriginAsync(crossSectionState.origin);
                promises.push(promise);
            }
            if (crossSectionState.normal !== undefined) {
                const promise = renderer.setCrossSectionNormalAsync(crossSectionState.normal);
                promises.push(promise);
            }
            // Held before the part loop: a part coloured below reads its
            // range from these records.  Guarded on presence, so a state with
            // no variable block leaves the held records alone, while an empty
            // block clears them.
            if (sceneState.hasVariableStates) {
                variableManager.setRecords(sceneState.getVariableStates());
            }
            for (const dataset_state of sceneState.getDatasetStates()) {
                for (const part_state of dataset_state.getPartStates()) {
                    let node;
                    if (part_state.keyedByName) {
                        node =
                            sceneGraph.descendantActorNodesOrSelfDictionaryByPartName[
                                part_state.id
                            ];
                    } else {
                        node = sceneGraph.descendantActorNodesOrSelfDictionary[part_state.id];
                    }
                    if (node != null) {
                        // Narrow once: `node` is a `let`, so the null check
                        // above does not survive into the callbacks below.
                        const partNode = node;
                        // The diffuse-colour path and the selection path both
                        // write this actor's ambient/diffuse properties with
                        // different values, so they must be sequenced for this
                        // node rather than raced as independent promises.
                        let partPromise: Promise<unknown> = Promise.resolve();
                        if (part_state.diffuseRgb !== undefined) {
                            const [r, g, b] = part_state.diffuseRgb;
                            partPromise = partPromise.then(() =>
                                partNode.applyDiffuseColorRgbAsync(r, g, b)
                            );
                        }
                        // `selected` is applied to the node, like every other
                        // part field, so the node owns the value and both the
                        // renderer and the tree read it from there.
                        if (part_state.selected !== undefined) {
                            const selected = part_state.selected;
                            partPromise = partPromise.then(() =>
                                partNode.applySelectedAsync(selected)
                            );
                        }
                        promises.push(partPromise);
                        if (part_state.opacity !== undefined) {
                            const promise = node.applyOpacityAsync(part_state.opacity);
                            promises.push(promise);
                        }
                        if (part_state.visible !== undefined) {
                            const promise = node.applyVisibilityAsync(part_state.visible);
                            promises.push(promise);
                        }
                        // A null reference clears the colouring; an absent one leaves it.
                        const colorVariable = part_state.colorVariable;
                        if (colorVariable !== undefined) {
                            promises.push(node.applyColorVariableAsync(colorVariable));
                        }
                    }
                }
            }
            // Every part is applied before the tree and the panel re-read them.
            await Promise.all(promises);
            if (updateUI) {
                await panelTopRightUtilPromise;
                const treeViewUtil: TreeViewUtil<VisorSceneNodeExtended> =
                    await treeViewUtilPromise;
                // Selection and visibility are both applied to the nodes
                // above; the tree derives its rows from them here.
                treeViewUtil.synchronize();
            }
            // After the tree has taken the delivered selection, so the panel
            // re-reads that selection's ranges from the records just held.
            // Skipped until the panel exists; its mount reads them itself.
            if (isPanelTopRightUtilSet()) {
                const panelTopRight = await panelTopRightUtilPromise;
                await panelTopRight.refreshSelectionAsync();
            }
            await renderer.resizeAsync();
        };
        Object.freeze(this);
    }

    get unit() {
        return this.#unit;
    }

    #unit: string;
    #viewerClickedRemover: (() => void) | null;
    darkMode: boolean;
    /** Remove every listener this frontend registered on its renderer; a second call does nothing. */
    release: () => void;
    render: () => Promise<void>;
    resizeAsync: () => Promise<void>;
    sceneGraph: VisorSceneNodeExtended;
    domElement: HTMLDivElement;
    setTreeViewUtil: (treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>) => void;
    setPanelTopLeftUtil: (panelTopRightUtil: Panel_TopLeft_Util) => void;
    setPanelTopRightUtil: (panelTopRightUtil: Panel_TopRight_Util) => void;
    setUiScaffoldUtil: (uiScaffoldUtil: UiScaffoldUtil) => void;
    sendPanelTopLeftPanelCollapsedAsync: (collapsed: boolean) => Promise<void>;
    sendPanelTopRightPanelCollapsedAsync: (collapsed: boolean) => Promise<void>;
    sendPanelTopRightLegendCollapsedAsync: (collapsed: boolean) => Promise<void>;
    sendPanelTopRightTabIndexAsync: (tabIndex: number) => Promise<void>;
    treeViewUtilPromise: Promise<TreeViewUtil<VisorSceneNodeExtended>>;
    panelTopLeftUtilPromise: Promise<Panel_TopLeft_Util>;
    panelTopRightUtilPromise: Promise<Panel_TopRight_Util>;
    uiScaffoldUtilPromise: Promise<UiScaffoldUtil>;
    getCameraStateAsync: () => Promise<VisorCameraState>;
    toggleFullScreenAsync: () => Promise<void>;
    addCameraChangedListener: (callback: (cameraState: VisorCameraState) => void) => () => void;
    globalVariableCollection: VisorVariableCollection;
    /** Reports one variable slot's range to the server, -1 being the magnitude; a failed send is logged, not rethrown. */
    sendVariableRangeAsync: (
        variableId: string,
        component: number,
        min: number,
        max: number
    ) => Promise<void>;
    /** Writes a variable slot's range to the held record, applies it to every part coloured by that slot, then reports it to the server. */
    setVariableRangeAsync: (
        variableId: string,
        component: number,
        min: number,
        max: number
    ) => Promise<void>;
    defaultActorColor: number[];
    addViewerClickedListener: (
        handler: (node: VisorSceneNodeExtended | null, ctrlKey: boolean, shiftKey: boolean) => void
    ) => () => void;
    addFrameRenderedListener: (handler: (fps: number) => void) => () => void;
    setCrossSectionVisibilityAsync: (visible?: boolean) => Promise<void>;
    setBoundingBoxVisibilityAsync: (visible?: boolean) => Promise<void>;
    /** Show, hide or toggle edges on every part. */
    setEdgeVisibilityGlobalAsync: (visible?: boolean | undefined) => Promise<void>;
    setOrthographicModeAsync: (enable?: boolean) => Promise<void>;
    getAppStateAsync: (keyedByName?: boolean) => Promise<VisorAppState>;
    setAppStateAsync: (state?: StateInput<VisorAppState>, updateUI?: boolean) => Promise<void>;
    // Selection mode
    getSelectionMode: () => 'part' | 'vertex' | 'edge' | 'face';
    setSelectionMode: (mode: 'part' | 'vertex' | 'edge' | 'face') => void;
    addSelectionModeChangedListener: (
        callback: (mode: 'part' | 'vertex' | 'edge' | 'face') => void
    ) => () => void;
    addGeometryPickedListener: (callback: (result: any) => void) => () => void;
    pickGeometryAsync: (normX: number, normY: number) => Promise<any>;
}
