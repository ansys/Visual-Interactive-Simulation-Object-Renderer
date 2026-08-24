import { StateInput } from './../VisorStateCommon.tsx';
import VisorVtkSceneNode from './VisorVtkSceneNode.tsx';
import { RendererAnnotation, parseRendererAnnotation } from '../../../renderer/RendererAnnotation';

/**
 * Contains VTK scene metadata and the root of the serialized scene graph.
 */
export default class VisorVtkInfo {
    /**
     * Creates VTK scene information from serialized state.
     *
     * @param json_or_object - A JSON string, plain state object, or other
     * supported state input containing the VTK metadata and scene graph.
     */
    constructor(json_or_object: StateInput<VisorVtkInfo> = null) {
        const obj =
            typeof json_or_object === `string` ? JSON.parse(json_or_object) : json_or_object;
        this.sceneGraph = new VisorVtkSceneNode(obj.sceneGraph);
        this.rendererAnnotation = parseRendererAnnotation(obj.rendererAnnotation);
    }

    /**
     * Root node of the VTK scene graph.
     */
    sceneGraph: VisorVtkSceneNode;

    /**
     * Renderer-specific handles. `null` if the renderer has no client-side
     * handles to hand the client. Consumed only by the matching IRenderer.
     */
    rendererAnnotation: RendererAnnotation | null;
}
