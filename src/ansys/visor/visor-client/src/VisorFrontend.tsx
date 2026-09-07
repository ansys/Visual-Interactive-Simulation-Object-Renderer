import { getSpectrumManager, VisorSpectrumCollection } from './state/VisorSpectrumManager.tsx';
import { CreateVisorSceneGraph, VisorSceneNodeExtended } from './state/VisorSceneGraph.tsx';
import { getPromiseResolver } from './utils/JsHelpers';
import VisorAppState from './state/appstate/VisorAppState.tsx';
import VisorDatasetState from './state/appstate/VisorDatasetState.tsx';
import VisorPartState from './state/appstate/VisorPartState.tsx';
import VisorSpectrumState from './state/appstate/VisorSpectrumState.tsx';
import { TreeViewUtil } from './treeview/TreeView.tsx';
import { StateInput } from './state/appstate/VisorStateCommon.tsx';
import VisorVtkSceneNode from './state/appstate/vtkInfo/VisorVtkSceneNode.tsx';
import { IRenderer, VisorCameraState } from './renderer/IRenderer';
import { Panel_TopRight_Util } from './components/ui-panels/Panel_TopRight_Util.tsx';
import { Panel_TopLeft_Util } from './components/ui-panels/Panel_TopLeft_Util.tsx';
import { OrientationWidget } from './widgets/orientationWidget.ts';
import { UiScaffoldUtil } from './components/UiScaffold.tsx';

export type { VisorCameraState } from './renderer/IRenderer';

export class VisorFrontend {
    constructor(renderer: IRenderer, sceneGraphNode: VisorVtkSceneNode) {
        const spectrumManager = getSpectrumManager();
        const sceneGraph = CreateVisorSceneGraph(sceneGraphNode, spectrumManager, renderer);
        spectrumManager.finishAddingDataArrayMetadata();
        renderer.attachSceneGraph(sceneGraph);

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

        // const orientationWidget = new OrientationWidget(vtkScene, vtkInfo.orientationWidgetWasmId);

        let themeDarkCss: string | null | undefined = null;
        let themeLightCss: string | null | undefined = null;
        let themeStyleElem: HTMLStyleElement | null | undefined = null;

        // Respect base path prefix set by the Dash component (for reverse-proxy deployments).
        const bp: string = ((window as any).__visorArgs?.basePath ?? '').replace(/\/$/, '');

        const self = this;
        this.globalSpectrumCollection = spectrumManager.globalSpectrumCollection;
        this.#unit = '';
        this.darkMode = darkMode;
        this.render = async () => {
            await renderer.renderAsync();
        };
        this.resizeAsync = async () => {
            await renderer.resizeAsync();
            // await orientationWidget.resizeAsync();
        };
        this.domElement = renderer.domElement;
        this.getCameraStateAsync = () => renderer.getCameraStateAsync();
        this.defaultActorColor = [];
        this.setSpectrumRangeAsync = async (spectrumId, component, min, max) => {
            const spectrum = spectrumManager.globalSpectrumCollection.getSpectrum(spectrumId);
            if (spectrum == null) {
                return;
            }
            spectrum.setCustomRange(component, min, max);
            for (const actorNode of sceneGraph.descendantActorNodesOrSelfArray) {
                if (
                    actorNode.spectrumId === spectrumId &&
                    actorNode.spectrumComponent == component
                ) {
                    await actorNode.setScalarRangeAsync(min, max);
                }
            }
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
            // Clear the client-side highlight overlay whenever mode changes
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
            // Draw client-side highlight overlay (no server sync needed)
            renderer.setGeometryHighlightAsync(result).catch(() => {});
            for (const cb of geometryPickedListeners.values()) cb(result);
            return result;
        };

        // Extended viewer click listener that also triggers geometry picking
        renderer.addViewerClickedListener((_nodeId, _ctrlKey, _shiftKey, normX, normY) => {
            if (selectionMode !== 'part') {
                this.pickGeometryAsync(normX, normY).catch(() => {});
            }
        });
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
        this.toggleFullScreenAsync = () => renderer.toggleFullScreenAsync();
        this.setEdgeVisibilityAsync = (visible) => renderer.setEdgeVisibilityGlobalAsync(visible);
        this.setCrossSectionVisibilityAsync = (visible) =>
            renderer.setCrossSectionVisibilityAsync(visible);
        this.updateCrossSectionBoundsAsync = () => renderer.updateCrossSectionBoundsAsync();
        this.setBoundingBoxVisibilityAsync = (visible) =>
            renderer.setBoundingBoxVisibilityAsync(visible);
        this.updateBoundingBoxBoundsAsync = () => renderer.updateBoundingBoxBoundsAsync();
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
                    partState.setSpectrumId(partNode.spectrumId);
                    partState.setSpectrumComponent(partNode.spectrumComponent);
                    datasetState.copyPart(partState);
                }
                sceneState.copyDataset(datasetState);
            }
            const spectrumInfos = spectrumManager.globalSpectrumCollection;
            for (const spectrumInfo of spectrumInfos.array) {
                const spectrumState = new VisorSpectrumState();
                spectrumState.setId(spectrumInfo.id.toString());
                spectrumState.setArrayName(spectrumInfo.name);
                spectrumState.setType(spectrumInfo.type);
                spectrumState.setNumComponents(spectrumInfo.numComponents);
                const magnitudeRange = spectrumInfo.getRangeInfo(-1);
                if (magnitudeRange == null) {
                    throw new Error(`range at component ${-1} not found`);
                }
                spectrumState.setMagnitudeRange(magnitudeRange.customRange);
                const ranges: number[][] = [];
                for (let i = 0; i < spectrumInfo.numComponents; i++) {
                    const range = spectrumInfo.getRangeInfo(i);
                    if (range == null) {
                        throw new Error(`range at component ${i} not found`);
                    }
                    ranges.push(range.customRange);
                }
                spectrumState.setRanges(ranges);
                sceneState.copySpectrum(spectrumState);
            }
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
                    if (uiState.panelTopLeftPanelCollapsed) {
                        panelTopLeft.collapsePanel();
                    } else {
                        panelTopLeft.expandPanel();
                    }
                }
            })();
            void (async () => {
                const panelTopRight = await panelTopRightUtilPromise;
                if (uiState.panelTopRightPanelCollapsed !== undefined) {
                    if (uiState.panelTopRightPanelCollapsed) {
                        panelTopRight.collapsePanel();
                    } else {
                        panelTopRight.expandPanel();
                    }
                }
                if (uiState.panelTopRightLegendCollapsed !== undefined) {
                    if (uiState.panelTopRightLegendCollapsed) {
                        panelTopRight.collapseLegend();
                    } else {
                        panelTopRight.expandLegend();
                    }
                }
                if (uiState.panelTopRightTabIndex !== undefined) {
                    panelTopRight.selectTab(uiState.panelTopRightTabIndex);
                }
            })();
            const promises: Promise<void>[] = [];
            const sceneState = appState.scene;
            if (sceneState.unit !== undefined) {
                const unit = (this.#unit = sceneState.unit);
                void (async () => {
                    const uiScaffold = await uiScaffoldUtilPromise;
                    uiScaffold.setUnit(unit);
                })();
            }
            if (sceneState.orthographicEnabled !== undefined) {
                const promise = renderer.setOrthographicModeAsync(sceneState.orthographicEnabled);
                promises.push(promise);
            }
            if (sceneState.crossSectionEnabled !== undefined) {
                const promise = renderer.setCrossSectionVisibilityAsync(
                    sceneState.crossSectionEnabled
                );
                promises.push(promise);
            }
            if (sceneState.edgesEnabled !== undefined) {
                const promise = renderer.setEdgeVisibilityGlobalAsync(sceneState.edgesEnabled);
                promises.push(promise);
            }
            if (sceneState.boundingBoxEnabled !== undefined) {
                const promise = renderer.setBoundingBoxVisibilityAsync(
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
                const promise = renderer.setCameraParallelProjectionAsync(
                    cameraState.parallelProjection
                );
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
                        let partPromise: Promise<void> = Promise.resolve();
                        if (part_state.diffuseRgb !== undefined) {
                            const [r, g, b] = part_state.diffuseRgb;
                            partPromise = partPromise.then(() =>
                                partNode.setDiffuseColorRgbAsync(r, g, b)
                            );
                        }
                        // `selected` is applied to the node, like every other
                        // part field, so the node owns the value and both the
                        // renderer and the tree read it from there. `=== true`
                        // holds the current semantics: a part state carrying
                        // null (never touched) deselects, and the node always
                        // receives a boolean.
                        partPromise = partPromise.then(() =>
                            partNode.setSelectedAsync(part_state.selected === true)
                        );
                        promises.push(partPromise);
                        if (part_state.opacity !== undefined) {
                            const promise = node.setOpacityAsync(part_state.opacity);
                            promises.push(promise);
                        }
                        if (part_state.visible !== undefined) {
                            const promise = node.setVisibilityAsync(part_state.visible);
                            promises.push(promise);
                        }
                        if (
                            part_state.spectrumId !== undefined &&
                            part_state.spectrumComponent !== undefined
                        ) {
                            let promise;
                            if (part_state.spectrumId !== null) {
                                promise = node.setColorVariableAsync(
                                    part_state.spectrumId,
                                    part_state.spectrumComponent
                                );
                            } else {
                                promise = node.clearColorVariableAsync();
                            }
                            promises.push(promise);
                        }
                    }
                }
            }
            // wait for all the parts to be updated before updating the spectrum ranges
            await Promise.all(promises);
            promises.length = 0;
            for (const spectrum_state of sceneState.getSpectrumStates()) {
                const idStr = spectrum_state.id;
                if (spectrum_state.magnitudeRange !== undefined) {
                    const range = spectrum_state.magnitudeRange;
                    const promise = self.setSpectrumRangeAsync(idStr, -1, range[0], range[1]);
                    promises.push(promise);
                }
                for (let i = 0; i < spectrum_state.ranges.length; i++) {
                    const range = spectrum_state.ranges[i];
                    if (range !== undefined) {
                        const promise = self.setSpectrumRangeAsync(idStr, i, range[0], range[1]);
                        promises.push(promise);
                    }
                }
            }
            await Promise.all(promises);
            if (updateUI) {
                await panelTopRightUtilPromise;
                const treeViewUtil: TreeViewUtil<VisorSceneNodeExtended> =
                    await treeViewUtilPromise;
                // Selection and visibility are both applied to the nodes
                // above; the tree derives its rows from them here.
                treeViewUtil.synchronize();
            }
            await renderer.resizeAsync();
        };
        Object.freeze(this);
    }

    get unit() {
        return this.#unit;
    }

    #unit: string;
    darkMode: boolean;
    render: () => Promise<void>;
    resizeAsync: () => Promise<void>;
    sceneGraph: VisorSceneNodeExtended;
    domElement: HTMLDivElement;
    setTreeViewUtil: (treeViewUtil: TreeViewUtil<VisorSceneNodeExtended>) => void;
    setPanelTopLeftUtil: (panelTopRightUtil: Panel_TopLeft_Util) => void;
    setPanelTopRightUtil: (panelTopRightUtil: Panel_TopRight_Util) => void;
    setUiScaffoldUtil: (uiScaffoldUtil: UiScaffoldUtil) => void;
    treeViewUtilPromise: Promise<TreeViewUtil<VisorSceneNodeExtended>>;
    panelTopLeftUtilPromise: Promise<Panel_TopLeft_Util>;
    panelTopRightUtilPromise: Promise<Panel_TopRight_Util>;
    uiScaffoldUtilPromise: Promise<UiScaffoldUtil>;
    getCameraStateAsync: () => Promise<VisorCameraState>;
    toggleFullScreenAsync: () => Promise<void>;
    addCameraChangedListener: (callback: (cameraState: VisorCameraState) => void) => () => void;
    globalSpectrumCollection: VisorSpectrumCollection;
    setSpectrumRangeAsync: (
        spectrumId: string,
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
    updateCrossSectionBoundsAsync: () => Promise<void>;
    setBoundingBoxVisibilityAsync: (visible?: boolean) => Promise<void>;
    setEdgeVisibilityAsync: (visible?: boolean | undefined) => Promise<void>;
    updateBoundingBoxBoundsAsync: () => Promise<void>;
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
