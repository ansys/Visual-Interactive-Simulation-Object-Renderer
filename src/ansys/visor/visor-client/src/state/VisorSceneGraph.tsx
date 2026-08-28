import VisorColor from '../utils/VisorColor.tsx';
import {
    getSpectrumManager,
    VisorSpectrumCollection,
    VisorSpectrumManager,
} from './VisorSpectrumManager.tsx';
import VisorVtkDataArray from './appstate/vtkInfo/VisorVtkDataArray.tsx';
import { IRenderer } from '../renderer/IRenderer';

export type VisorSceneNodeSimple = Readonly<{
    id: number;
    dataArrays: VisorVtkDataArray[];
    name: string;
    isActorNode: boolean;
    isGroupNode: boolean;
    nodeType: string;
    bounds: number[];
    diffuseColor: number[];
    children: VisorSceneNodeSimple[];
}>;

export type VisorSceneNodeExtended = Readonly<{
    id: number;
    rootNode: VisorSceneNodeExtended;
    name: string;
    isActorNode: boolean;
    isGroupNode: boolean;
    nodeType: string;
    bounds: number[];
    children: VisorSceneNodeExtended[];
    diffuseRgb: Readonly<number[]>;
    visible: boolean;
    selected: boolean;
    edgeVisibility: boolean;
    opacity: number;
    descendantsOrSelfArray: VisorSceneNodeExtended[];
    descendantsOrSelfDictionary: Record<string, VisorSceneNodeExtended>;
    descendantsOrSelfDictionaryByPartName: Record<string, VisorSceneNodeExtended>;
    descendantActorNodesOrSelfArray: VisorSceneNodeExtended[];
    descendantActorNodesOrSelfDictionary: Record<string, VisorSceneNodeExtended>;
    descendantActorNodesOrSelfDictionaryByPartName: Record<string, VisorSceneNodeExtended>;
    resetDiffuseColorAsync: () => Promise<void>;
    setDiffuseColorHexAsync: (hex: string) => Promise<void>;
    setDiffuseColorRgbAsync: (r: number, g: number, b: number) => Promise<void>;
    setVisibilityAsync: (visible: boolean) => Promise<void>;
    setSelectedAsync: (selected: boolean) => Promise<void>;
    setEdgeVisibilityAsync: (edgeVisibility: boolean) => Promise<void>;
    setOpacityAsync: (opacity: number) => Promise<void>;
    clearColorVariableAsync: () => Promise<void>;
    setColorVariableAsync: (id: string, component?: number | null) => Promise<void>;
    setScalarRangeAsync: (min: number, max: number) => Promise<void>;
    spectrumCollection: VisorSpectrumCollection;
    spectrumId: string | null;
    spectrumComponent: number;
    spectrumMin: number;
    spectrumMax: number;
    defaultDiffuseColorRgb: Readonly<number[]>;
    defaultDiffuseColorHex: string;
    customDiffuseColorRgb: Readonly<number[]>;
    customDiffuseColorHex: string;
}>;

/**
 * @desc If json is provided, this parses the json into an extended Visor scene node object.
 * @desc If an existing simple Visor scene node object is provided, this transforms
 * the simple scene node object into an extended scene node object.
 */
export const CreateVisorSceneGraph = (() => {
    return (
        string_or_object: string | VisorSceneNodeSimple,
        spectrumManager?: VisorSpectrumManager,
        renderer?: IRenderer
    ) => {
        let simpleState: VisorSceneNodeSimple;
        if (typeof string_or_object === 'string') {
            simpleState = JSON.parse(string_or_object);
        } else {
            simpleState = string_or_object;
        }
        const localSpectrumManager = spectrumManager == null;
        spectrumManager ??= getSpectrumManager();
        const rootNode = extendSimpleNode(simpleState, spectrumManager, null, null, renderer);
        localSpectrumManager && spectrumManager.finishAddingDataArrayMetadata();
        return rootNode;
    };

    function extendSimpleNode(
        simpleNode: VisorSceneNodeSimple,
        spectrumManager: VisorSpectrumManager,
        rootNodeSimple?: VisorSceneNodeSimple | null,
        rootNodeExtended?: VisorSceneNodeExtended | null,
        renderer?: IRenderer
    ): VisorSceneNodeExtended {
        rootNodeSimple ??= simpleNode;
        if (spectrumManager == null) {
            throw new Error(`spectrumManager cannot be null`);
        } else if (rootNodeSimple.nodeType !== 'root') {
            throw new Error(`rootNodeSimple.nodeType must be 'root'`);
        }
        let _visible: boolean = true;
        let _selected: boolean = false;
        let _edgeVisibility: boolean = false;
        let _opacity: number = 1;
        let _spectrumId: string | null = null;
        let _spectrumComponent: number = -1;
        let _spectrumMin: number = -1;
        let _spectrumMax: number = -1;
        const defaultDiffuseColor = new VisorColor();
        const customDiffuseColor = new VisorColor();
        if (simpleNode.isActorNode) {
            defaultDiffuseColor.setRgb(
                simpleNode.diffuseColor[0],
                simpleNode.diffuseColor[1],
                simpleNode.diffuseColor[2],
                true
            );
            customDiffuseColor.setHex(defaultDiffuseColor.hex);
        }
        const nodeId = simpleNode.id;

        const spectrumCollection = spectrumManager.addDataArrayMetadata(simpleNode.dataArrays);

        const node: VisorSceneNodeExtended = {
            id: simpleNode.id,
            get rootNode() {
                return rootNodeExtended!; // this is set later
            },
            name: simpleNode.name,
            isActorNode: simpleNode.isActorNode,
            isGroupNode: simpleNode.isGroupNode,
            nodeType: simpleNode.nodeType,
            bounds: simpleNode.bounds,
            children: [], // this collection is populated later
            descendantsOrSelfArray: [], // this collection is populated later
            descendantsOrSelfDictionary: {}, // this collection is populated later
            descendantsOrSelfDictionaryByPartName: {}, // this collection is populated later
            descendantActorNodesOrSelfArray: [], // this collection is populated later
            descendantActorNodesOrSelfDictionary: {}, // this collection is populated later
            descendantActorNodesOrSelfDictionaryByPartName: {}, // this collection is populated later
            get diffuseRgb() {
                return customDiffuseColor.rgbNormalized;
            },
            get visible() {
                return _visible;
            },
            get selected() {
                return _selected;
            },
            get edgeVisibility() {
                return _edgeVisibility;
            },
            get opacity() {
                return _opacity;
            },
            spectrumCollection,
            async resetDiffuseColorAsync() {
                customDiffuseColor.setHex(defaultDiffuseColor.hex);
                await renderer!.resetDiffuseColorAsync(
                    nodeId,
                    customDiffuseColor.rgbNormalized,
                    _selected
                );
                // A reset is "no custom colour", sent as an explicit null --
                // not as the default colour's value, and not by omitting the
                // key. Absence is absence.
                await renderer!.sendPartDiffuseColorAsync(nodeId, null);
            },
            async setDiffuseColorHexAsync(hex) {
                customDiffuseColor.setHex(hex);
                const rgbNormalized = customDiffuseColor.rgbNormalized;
                await renderer!.setDiffuseColorRgbAsync(
                    nodeId,
                    rgbNormalized[0],
                    rgbNormalized[1],
                    rgbNormalized[2],
                    _selected
                );
                await renderer!.sendPartDiffuseColorAsync(nodeId, rgbNormalized);
            },
            async setDiffuseColorRgbAsync(r, g, b) {
                customDiffuseColor.setRgb(r, g, b);
                const rgbNormalized = customDiffuseColor.rgbNormalized;
                await renderer!.setDiffuseColorRgbAsync(
                    nodeId,
                    rgbNormalized[0],
                    rgbNormalized[1],
                    rgbNormalized[2],
                    _selected
                );
                await renderer!.sendPartDiffuseColorAsync(nodeId, rgbNormalized);
            },
            async clearColorVariableAsync() {
                _spectrumId = null;
                _spectrumComponent = -1;
                _spectrumMin = -1;
                _spectrumMax = -1;
                await renderer!.clearColorVariableAsync(nodeId);
                await renderer!.sendClearPartColorVariableAsync(nodeId);
            },
            async setColorVariableAsync(id, component) {
                if (_spectrumId === id && _spectrumComponent === component) {
                    return;
                } else if (component == null) {
                    return;
                }
                const spectrum = spectrumCollection.getSpectrum(id);
                if (spectrum == null) {
                    return;
                }
                const rangeInfo = spectrum.getRangeInfo(component);
                if (rangeInfo == null) {
                    return;
                }
                const min = rangeInfo.customRange[0];
                const max = rangeInfo.customRange[1];
                _spectrumId = id;
                _spectrumComponent = component;
                _spectrumMin = min;
                _spectrumMax = max;
                const descriptor = {
                    spectrumId: id,
                    spectrumType: spectrum.type,
                    spectrumName: spectrum.name,
                    component,
                    min,
                    max,
                };
                await renderer!.setColorVariableAsync(nodeId, descriptor);
                await renderer!.sendPartColorVariableAsync(nodeId, descriptor);
            },
            async setScalarRangeAsync(min, max) {
                await renderer!.setScalarRangeAsync(nodeId, min, max);
            },
            async setVisibilityAsync(visible) {
                if (_visible === visible) {
                    return;
                }
                _visible = visible;
                if (node.isGroupNode) {
                    const promises = [];
                    for (const n of node.descendantActorNodesOrSelfArray) {
                        promises.push(n.setVisibilityAsync(visible));
                    }
                    await Promise.all(promises);
                    return;
                }
                await renderer!.setVisibilityAsync(nodeId, visible);
                await renderer!.sendPartVisibilityAsync(nodeId, visible);
            },
            async setSelectedAsync(selected) {
                if (_selected === selected) {
                    return;
                }
                _selected = selected;
                if (node.isGroupNode) {
                    const promises = [];
                    for (const n of node.descendantActorNodesOrSelfArray) {
                        promises.push(n.setSelectedAsync(selected));
                    }
                    await Promise.all(promises);
                    return;
                }
                await renderer!.setSelectedAsync(
                    nodeId,
                    _selected,
                    customDiffuseColor.rgbNormalized
                );
                // The trigger carries no colour: the server reads the part's
                // stored colour from its own record.
                await renderer!.sendPartSelectedAsync(nodeId, _selected);
            },
            async setEdgeVisibilityAsync(edgeVisibility: boolean) {
                if (_edgeVisibility === edgeVisibility) {
                    return;
                }
                _edgeVisibility = edgeVisibility;
                if (node.isGroupNode) {
                    const promises = [];
                    for (const n of node.descendantActorNodesOrSelfArray) {
                        promises.push(n.setEdgeVisibilityAsync(edgeVisibility));
                    }
                    await Promise.all(promises);
                    return;
                }
                await renderer!.setEdgeVisibilityAsync(nodeId, edgeVisibility);
            },
            async setOpacityAsync(opacity: number) {
                if (_opacity === opacity) {
                    return;
                } else if (opacity < 0 || opacity > 1) {
                    throw new Error(`opacity must be a number between 0 and 1 (${opacity})`);
                }
                _opacity = opacity;
                if (node.isGroupNode) {
                    const promises = [];
                    for (const n of node.descendantActorNodesOrSelfArray) {
                        promises.push(n.setOpacityAsync(opacity));
                    }
                    await Promise.all(promises);
                    return;
                }
                await renderer!.setOpacityAsync(nodeId, opacity);
                await renderer!.sendPartOpacityAsync(nodeId, opacity);
            },
            get spectrumId() {
                return _spectrumId;
            },
            get spectrumComponent(): number {
                return _spectrumComponent;
            },
            get spectrumMin(): number {
                return _spectrumMin;
            },
            get spectrumMax(): number {
                return _spectrumMax;
            },
            get customDiffuseColorRgb() {
                return customDiffuseColor.rgb;
            },
            get customDiffuseColorHex() {
                return customDiffuseColor.hex;
            },
            get defaultDiffuseColorRgb() {
                return defaultDiffuseColor.rgb;
            },
            get defaultDiffuseColorHex() {
                return defaultDiffuseColor.hex;
            },
        };
        rootNodeExtended ??= node;
        if (rootNodeSimple.nodeType !== 'root') {
            throw new Error(`rootNodeSimple.nodeType must be 'root'`);
        }
        node.descendantsOrSelfArray.push(node);
        node.descendantsOrSelfDictionary[node.id] = node;
        node.descendantsOrSelfDictionaryByPartName[node.name] = node;
        if (node.isActorNode) {
            node.descendantActorNodesOrSelfArray.push(node);
            node.descendantActorNodesOrSelfDictionary[node.id] = node;
            node.descendantActorNodesOrSelfDictionaryByPartName[node.name] = node;
        }
        simpleNode.children.forEach((simpleChild) => {
            const extendedChild = extendSimpleNode(
                simpleChild,
                spectrumManager,
                rootNodeSimple,
                rootNodeExtended,
                renderer
            );
            node.children.push(extendedChild);
            node.descendantsOrSelfArray.push(...extendedChild.descendantsOrSelfArray);
            Object.assign(
                node.descendantsOrSelfDictionary,
                extendedChild.descendantsOrSelfDictionary
            );
            Object.assign(
                node.descendantsOrSelfDictionaryByPartName,
                extendedChild.descendantsOrSelfDictionaryByPartName
            );
            node.descendantActorNodesOrSelfArray.push(
                ...extendedChild.descendantActorNodesOrSelfArray
            );
            Object.assign(
                node.descendantActorNodesOrSelfDictionary,
                extendedChild.descendantActorNodesOrSelfDictionary
            );
            Object.assign(
                node.descendantActorNodesOrSelfDictionaryByPartName,
                extendedChild.descendantActorNodesOrSelfDictionaryByPartName
            );
        });
        Object.freeze(node.children);
        Object.freeze(node.descendantsOrSelfArray);
        Object.freeze(node.descendantsOrSelfDictionary);
        Object.freeze(node.descendantsOrSelfDictionaryByPartName);
        Object.freeze(node.descendantActorNodesOrSelfArray);
        Object.freeze(node.descendantActorNodesOrSelfDictionary);
        Object.freeze(node.descendantActorNodesOrSelfDictionaryByPartName);
        return Object.freeze(node);
    }
})();
