import {
    ensureArray,
    ensureBoolean,
    ensureNumber,
    ensureString,
    StateInput,
} from './../VisorStateCommon.tsx';
import VisorVtkDataArray from './VisorVtkDataArray.tsx';

/**
 * Represents a node in a hierarchical VTK scene graph.
 *
 * A node may represent an actor, a logical group, or another supported scene
 * element. Child nodes and associated data arrays are recursively converted
 * into their corresponding class instances.
 */
export default class VisorVtkSceneNode {
    /**
     * Creates a scene-graph node from serialized state.
     *
     * @param json_or_object - A JSON string, plain state object, or other
     * supported state input containing the node properties.
     */
    constructor(json_or_object: StateInput<VisorVtkSceneNode> = null) {
        const obj =
            typeof json_or_object === `string` ? JSON.parse(json_or_object) : json_or_object;
        ensureNumber(obj.id, `id`);
        ensureArray(obj.dataArrays, `dataArrays`);
        ensureString(obj.name, `name`);
        ensureBoolean(obj.isActorNode, `isActorNode`);
        ensureBoolean(obj.isGroupNode, `isGroupNode`);
        ensureString(obj.nodeType, `nodeType`);
        ensureArray(obj.bounds, `bounds`);
        ensureArray(obj.diffuseColor, `diffuseColor`);
        ensureArray(obj.children, `children`);
        this.id = obj.id;
        this.name = obj.name;
        this.isActorNode = obj.isActorNode;
        this.isGroupNode = obj.isGroupNode;
        this.nodeType = obj.nodeType;

        // obj.bounds should be a plain number array.
        // I'm not going to number-type check each bounds
        // array element as that could be quite slow on a
        // large scene graph. - BHB 2026-01-28
        this.bounds = obj.bounds;
        this.diffuseColor = obj.diffuseColor;

        this.children = new Array(obj.children.length);
        for (let i = 0; i < obj.children.length; i++) {
            this.children[i] = new VisorVtkSceneNode(obj.children[i]);
        }

        this.dataArrays = new Array(obj.dataArrays.length);
        for (let i = 0; i < obj.dataArrays.length; i++) {
            this.dataArrays[i] = new VisorVtkDataArray(obj.dataArrays[i]);
        }
    }

    /**
     * Application-level identifier for this scene node.
     */
    id: number;

    /**
     * Data arrays available on the dataset represented by this node.
     */
    dataArrays: VisorVtkDataArray[];

    /**
     * Display name of the scene node.
     */
    name: string;

    /**
     * Indicates whether this node represents a VTK actor.
     */
    isActorNode: boolean;

    /**
     * Indicates whether this node is a logical grouping node.
     */
    isGroupNode: boolean;

    /**
     * String identifier describing the node's scene-graph type.
     */
    nodeType: string;

    /**
     * Axis-aligned bounds of the node, typically represented as
     * `[xMin, xMax, yMin, yMax, zMin, zMax]`.
     */
    bounds: number[];

    /**
     * Diffuse RGB color associated with the node.
     */
    diffuseColor: number[];

    /**
     * Direct descendants of this scene-graph node.
     */
    children: VisorVtkSceneNode[];
}
