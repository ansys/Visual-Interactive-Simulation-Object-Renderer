import { ensureNumber, ensureString } from '../state/appstate/VisorStateCommon.tsx';

/**
 * Wasm object-manager ids for one renderable part node. Mirrors
 * `WasmNodeHandles` in `ansys.visor.viewer.models.runtime.vtk.renderer_annotation`.
 */
export type WasmNodeHandles = Readonly<{
    actorId: number;
    propertyId: number;
    mapperId: number;
}>;

/**
 * Wasm object-manager ids for the renderer's singleton widgets. Mirrors
 * `WasmWidgetHandles` in `ansys.visor.viewer.models.runtime.vtk.renderer_annotation`.
 * Static after renderer initialisation; independent of scene contents.
 */
export type WasmWidgetHandles = Readonly<{
    orientationWidgetId: number;
    crossSectionPlaneId: number;
    crossSectionPlaneWidgetId: number;
    crossSectionPlaneRepresentationId: number;
    boundingBoxAlgorithmId: number;
    boundingBoxOutlineActorId: number;
    boundingBoxAxesActorId: number;
}>;

/**
 * Annotation produced by the wasm (`VisorLocalRenderer`) renderer. Mirrors
 * `WasmRendererAnnotation` on the Python side.
 *
 * `RendererAnnotation` is currently just this one type. It is written as its
 * own alias, rather than folded directly into `RendererAnnotation`, so that a
 * future second renderer kind can be added as a real discriminated union
 * without touching this type's shape.
 */
export type WasmRendererAnnotation = Readonly<{
    rendererKind: 'wasm';
    /** Keyed by String(nodeId). Only part nodes appear. */
    nodes: Readonly<Record<string, WasmNodeHandles>>;
    widgets: WasmWidgetHandles;
}>;

/**
 * Every renderer's annotation. Today there is exactly one renderer kind that
 * produces a non-null annotation on the wire (`'wasm'`); a renderer with no
 * client-side handles is represented by absence (`null`).
 */
export type RendererAnnotation = WasmRendererAnnotation;

function parseWasmNodeHandles(obj: any, path: string): WasmNodeHandles {
    ensureNumber(obj.actorId, `${path}.actorId`);
    ensureNumber(obj.propertyId, `${path}.propertyId`);
    ensureNumber(obj.mapperId, `${path}.mapperId`);
    return {
        actorId: obj.actorId,
        propertyId: obj.propertyId,
        mapperId: obj.mapperId,
    };
}

function parseWasmWidgetHandles(obj: any): WasmWidgetHandles {
    ensureNumber(obj.orientationWidgetId, `rendererAnnotation.widgets.orientationWidgetId`);
    ensureNumber(obj.crossSectionPlaneId, `rendererAnnotation.widgets.crossSectionPlaneId`);
    ensureNumber(
        obj.crossSectionPlaneWidgetId,
        `rendererAnnotation.widgets.crossSectionPlaneWidgetId`
    );
    ensureNumber(
        obj.crossSectionPlaneRepresentationId,
        `rendererAnnotation.widgets.crossSectionPlaneRepresentationId`
    );
    ensureNumber(obj.boundingBoxAlgorithmId, `rendererAnnotation.widgets.boundingBoxAlgorithmId`);
    ensureNumber(
        obj.boundingBoxOutlineActorId,
        `rendererAnnotation.widgets.boundingBoxOutlineActorId`
    );
    ensureNumber(obj.boundingBoxAxesActorId, `rendererAnnotation.widgets.boundingBoxAxesActorId`);
    return {
        orientationWidgetId: obj.orientationWidgetId,
        crossSectionPlaneId: obj.crossSectionPlaneId,
        crossSectionPlaneWidgetId: obj.crossSectionPlaneWidgetId,
        crossSectionPlaneRepresentationId: obj.crossSectionPlaneRepresentationId,
        boundingBoxAlgorithmId: obj.boundingBoxAlgorithmId,
        boundingBoxOutlineActorId: obj.boundingBoxOutlineActorId,
        boundingBoxAxesActorId: obj.boundingBoxAxesActorId,
    };
}

function parseWasmRendererAnnotation(obj: any): WasmRendererAnnotation {
    if (typeof obj.nodes !== 'object' || obj.nodes === null) {
        throw new TypeError(`rendererAnnotation.nodes must be an object`);
    }
    if (typeof obj.widgets !== 'object' || obj.widgets === null) {
        throw new TypeError(`rendererAnnotation.widgets must be an object`);
    }
    const nodes: Record<string, WasmNodeHandles> = {};
    for (const nodeId of Object.keys(obj.nodes)) {
        nodes[nodeId] = parseWasmNodeHandles(
            obj.nodes[nodeId],
            `rendererAnnotation.nodes[${nodeId}]`
        );
    }
    const widgets = parseWasmWidgetHandles(obj.widgets);
    return { rendererKind: 'wasm', nodes, widgets };
}

/**
 * Parse and narrow at the payload boundary.
 *
 * `null`/`undefined` parse to `null`: a renderer with no client-side handles
 * is represented by absence.
 *
 * Throws on any other `rendererKind`.
 */
export function parseRendererAnnotation(obj: any): RendererAnnotation | null {
    if (obj == null) {
        return null;
    }
    ensureString(obj.rendererKind, `rendererAnnotation.rendererKind`);
    if (obj.rendererKind === 'wasm') {
        return parseWasmRendererAnnotation(obj);
    }
    throw new TypeError(`Unrecognized rendererAnnotation.rendererKind: '${obj.rendererKind}'`);
}

/** Narrow to the wasm annotation, or throw if the annotation is absent. */
export function requireWasmAnnotation(a: RendererAnnotation | null): WasmRendererAnnotation {
    if (a == null) {
        throw new TypeError(`Expected a wasm renderer annotation, but the annotation is absent`);
    }
    return a;
}
