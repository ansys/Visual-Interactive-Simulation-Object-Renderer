import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { VisorSpectrumInfo } from '../state/VisorSpectrumManager.tsx';
import { AggregateSpectrumComponentInfo } from './AggregateSpectrumComponentInfo.tsx';
import { AggregateSelectionInfo } from './AggregateSelectionInfo.tsx';

/**
 * Represents aggregate spectrum information for a collection of selected scene
 * nodes.
 *
 * The class resolves the available spectrum components and determines whether
 * the selected nodes share a common component to display.
 *
 * Instances must be created with {@link AggregateSpectrumInfo.getInstanceAsync}.
 */
export class AggregateSpectrumInfo {
    /**
     * Creates an uninitialized aggregate spectrum information object.
     *
     * @private
     */
    private constructor() {}

    /** Metadata for the spectrum represented by this instance. */
    #spectrumInfo!: VisorSpectrumInfo;

    /** Selection state associated with this spectrum. */
    #selectionInfo!: AggregateSelectionInfo;

    /**
     * The component ID currently displayed by all selected nodes.
     *
     * - A number indicates that all nodes share the same component.
     * - `null` indicates that no component is selected.
     * - `undefined` indicates that the selected nodes have different components.
     */
    #displayComponentId: number | null | undefined = null;

    /**
     * Information for the currently displayed component.
     *
     * This follows the same nullability semantics as
     * {@link AggregateSpectrumInfo.displayComponentId}.
     */
    #currentComponentInfo: AggregateSpectrumComponentInfo | null | undefined = null;

    /**
     * Available component information, indexed by the component ID converted to
     * a string.
     */
    #componentOptions: Map<string, AggregateSpectrumComponentInfo> = new Map();

    /**
     * Creates and initializes aggregate spectrum information for a collection
     * of scene nodes.
     *
     * Component metadata is resolved asynchronously. The selected nodes are then
     * inspected to determine whether they share a common spectrum component.
     *
     * When a node's configured component is unavailable for the spectrum, the
     * first component option is used as its fallback.
     *
     * @param actorNodes - Scene nodes included in the aggregate selection.
     * @param selectionInfo - Selection state that owns this spectrum information.
     * @param spectrumInfo - Metadata describing the spectrum and its components.
     * @returns A fully initialized aggregate spectrum information instance.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[],
        selectionInfo: AggregateSelectionInfo,
        spectrumInfo: VisorSpectrumInfo
    ): Promise<AggregateSpectrumInfo> {
        const obj = new AggregateSpectrumInfo();
        obj.#selectionInfo = selectionInfo;
        obj.#spectrumInfo = spectrumInfo;

        for (const componentMetadata of spectrumInfo.componentOptions) {
            const val = await AggregateSpectrumComponentInfo.getInstanceAsync(
                actorNodes,
                obj,
                componentMetadata
            );
            obj.#componentOptions.set(componentMetadata.id.toString(), val);
        }

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const spectrum = node.spectrumCollection.getSpectrum(spectrumInfo.id);
            let thisComponentId: number | null = node.spectrumComponent;

            if (spectrum != null) {
                if (spectrum.getRangeInfo(node.spectrumComponent) == null) {
                    // Default to the first component option.
                    thisComponentId = spectrum.componentOptions[0].id;
                }
            }

            if (i === 0) {
                obj.#displayComponentId = thisComponentId;
            } else {
                obj.#displayComponentId !== thisComponentId &&
                    (obj.#displayComponentId = undefined);
            }
        }

        if (obj.#displayComponentId != null) {
            obj.#currentComponentInfo = obj.#componentOptions.get(
                obj.#displayComponentId.toString()
            );

            if (obj.#currentComponentInfo == null) {
                console.warn(`invalid componentId: '${obj.#displayComponentId}'`);
            }
        } else {
            obj.#currentComponentInfo = obj.#displayComponentId;
        }

        return obj;
    }

    /**
     * Gets the spectrum's unique identifier.
     *
     * @returns The spectrum identifier.
     */
    get id(): VisorSpectrumInfo['id'] {
        return this.#spectrumInfo.id;
    }

    /**
     * Gets the underlying spectrum metadata.
     *
     * @returns The spectrum metadata associated with this instance.
     */
    get metadata(): VisorSpectrumInfo {
        return this.#spectrumInfo;
    }

    /**
     * Gets the component ID currently shared by the selected nodes.
     *
     * @returns The shared component ID, `null` when no component is selected, or
     * `undefined` when the selected nodes use different components.
     */
    get displayComponentId(): number | null | undefined {
        return this.#displayComponentId;
    }

    /**
     * Gets all available spectrum components.
     *
     * The map is keyed by each component ID converted to a string.
     *
     * @returns A map of component IDs to component information.
     */
    get componentOptions(): Map<string, AggregateSpectrumComponentInfo> {
        return this.#componentOptions;
    }

    /**
     * Gets information about the currently displayed component.
     *
     * @returns The current component information, `null` when no valid component
     * is selected, or `undefined` when the selected nodes do not share a common
     * component.
     */
    get currentComponentInfo(): AggregateSpectrumComponentInfo | null | undefined {
        return this.#currentComponentInfo;
    }

    /**
     * Changes the component displayed for the current spectrum.
     *
     * The spectrum must be the current spectrum in the associated selection.
     * After the value is updated, the selection's spectrum-component-change
     * callback is invoked when one is registered.
     *
     * @param id - The component ID to display. Numeric and string IDs are
     * normalized to strings for lookup. Passing `null` or `undefined` clears or
     * marks the component state accordingly.
     * @returns Information for the selected component, `null` when the ID does
     * not match an available component, or `undefined` when explicitly passed.
     * @throws {Error} When there is no current spectrum.
     * @throws {Error} When this instance is not the current spectrum.
     */
    setDisplayComponentId = (
        id: number | string | null | undefined
    ): AggregateSpectrumComponentInfo | null | undefined => {
        if (this.#selectionInfo.currentSpectrumInfo == null) {
            throw new Error('component should not be changed when the current spectrum is null');
        } else if (this.#selectionInfo.currentSpectrumInfo !== this) {
            throw new Error('component should not be changed on a spectrum that is not current');
        }

        if (id != null) {
            this.#currentComponentInfo = this.#componentOptions.get(id.toString()) ?? null;
            this.#displayComponentId = this.#currentComponentInfo?.id ?? null;
        } else {
            this.#currentComponentInfo = id;
            this.#displayComponentId = id;
        }

        const events = this.#selectionInfo.events;

        if (events.onSpectrumComponentChange != null) {
            events.onSpectrumComponentChange(this.#selectionInfo.currentSpectrumInfo);
        }

        return this.#currentComponentInfo;
    };
}
