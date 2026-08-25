import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { AggregateSpectrumInfo } from './AggregateSpectrumInfo.tsx';
import { tryParseFloat } from '../utils/JsHelpers';

/**
 * Event handlers emitted when aggregate spectrum selections change.
 */
class AggregateSelectionEvents {
    /**
     * Called when the selected spectrum changes.
     *
     * A value of `undefined` generally represents a mixed selection, while
     * `null` represents no selected spectrum.
     */
    onSpectrumChange!: ((spectrumInfo: AggregateSpectrumInfo | null | undefined) => void) | null;

    /**
     * Called when a component of the selected spectrum changes.
     *
     * A value of `undefined` generally represents a mixed selection, while
     * `null` represents no selected spectrum.
     */
    onSpectrumComponentChange!:
        ((spectrumInfo: AggregateSpectrumInfo | null | undefined) => void) | null;
}

/**
 * Represents the shared editable state of a collection of selected scene nodes.
 *
 * Properties contain a concrete value when all selected nodes share that
 * value. A value of `undefined` indicates that the selected nodes have
 * different values, while `null` indicates that the value is not set.
 *
 * Instances must be created with {@link AggregateSelectionInfo.getInstanceAsync}.
 */
export class AggregateSelectionInfo {
    /**
     * Prevents direct construction.
     *
     * Use {@link AggregateSelectionInfo.getInstanceAsync} instead.
     */
    private constructor() {}

    /**
     * Display name shared by the selected nodes.
     */
    #displayName: string | null | undefined = null;

    /**
     * Display opacity shared by the selected nodes.
     */
    #displayOpacity: number | null | undefined = null;

    /**
     * Spectrum identifier shared by the selected nodes.
     */
    #displaySpectrumId: string | null | undefined = null;

    /**
     * Custom diffuse color shared by the selected nodes, represented as a
     * hexadecimal color string.
     */
    #displayDiffuseColor: string | null | undefined = null;

    /**
     * Available spectra collected from all selected nodes, keyed by spectrum ID.
     */
    #spectrumOptions: Map<string, AggregateSpectrumInfo> = new Map();

    /**
     * Aggregate information for the currently selected spectrum.
     */
    #currentSpectrumInfo: AggregateSpectrumInfo | null | undefined = null;

    /**
     * Event handlers associated with this aggregate selection.
     */
    #events: AggregateSelectionEvents = {
        onSpectrumChange: null,
        onSpectrumComponentChange: null,
    };

    /**
     * Creates aggregate selection information for a collection of scene nodes.
     *
     * The resulting display properties contain a shared value when every node
     * has the same value. Properties are set to `undefined` when the nodes have
     * differing values.
     *
     * Spectrum options from all supplied nodes are also collected and converted
     * into {@link AggregateSpectrumInfo} instances.
     *
     * @param actorNodes - Scene nodes included in the aggregate selection.
     * @returns A promise resolving to the initialized aggregate selection.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[]
    ): Promise<AggregateSelectionInfo> {
        const obj = new AggregateSelectionInfo();

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const thisName: string | null = node.name;
            const thisOpacity: number | null = node.opacity;
            const thisSpectrumId: string | null = node.spectrumId;
            const thisDiffuseColor: string | null = node.customDiffuseColorHex;

            for (const spectrumInfo of node.spectrumCollection.array) {
                const idStr = spectrumInfo.id.toString();

                if (!obj.#spectrumOptions.has(idStr)) {
                    const val = await AggregateSpectrumInfo.getInstanceAsync(
                        actorNodes,
                        obj,
                        spectrumInfo
                    );
                    obj.#spectrumOptions.set(idStr, val);
                }
            }

            if (i === 0) {
                obj.#displayName = thisName;
                obj.#displayOpacity = thisOpacity;
                obj.#displaySpectrumId = thisSpectrumId;
                obj.#displayDiffuseColor = thisDiffuseColor;
            } else {
                obj.#displayName !== thisName && (obj.#displayName = undefined);

                obj.#displayOpacity !== thisOpacity && (obj.#displayOpacity = undefined);

                obj.#displaySpectrumId !== thisSpectrumId && (obj.#displaySpectrumId = undefined);

                obj.#displayDiffuseColor !== thisDiffuseColor &&
                    (obj.#displayDiffuseColor = undefined);
            }
        }

        if (obj.#displaySpectrumId != null) {
            obj.#currentSpectrumInfo = obj.#spectrumOptions.get(obj.#displaySpectrumId.toString());

            if (obj.#currentSpectrumInfo == null) {
                console.warn(`invalid spectrumId: '${obj.#displaySpectrumId}'`);
            }
        } else {
            obj.#currentSpectrumInfo = obj.#displaySpectrumId;
        }

        return obj;
    }

    /**
     * Gets the display name shared by the selected nodes.
     *
     * @returns The shared name, `null` when unset, or `undefined` when mixed.
     */
    get displayName(): string | null | undefined {
        return this.#displayName;
    }

    /**
     * Gets the display opacity shared by the selected nodes.
     *
     * @returns The shared opacity, `null` when unset, or `undefined` when mixed.
     */
    get displayOpacity(): number | null | undefined {
        return this.#displayOpacity;
    }

    /**
     * Gets the custom diffuse color shared by the selected nodes.
     *
     * @returns The shared hexadecimal color, `null` when unset, or `undefined`
     * when mixed.
     */
    get displayDiffuseColor(): string | null | undefined {
        return this.#displayDiffuseColor;
    }

    /**
     * Gets the spectrum identifier shared by the selected nodes.
     *
     * @returns The shared spectrum ID, `null` when unset, or `undefined` when
     * mixed.
     */
    get displaySpectrumId(): string | null | undefined {
        return this.#displaySpectrumId;
    }

    /**
     * Gets information about the currently selected spectrum.
     *
     * @returns The current spectrum information, `null` when no valid spectrum
     * is selected, or `undefined` when the selection is mixed.
     */
    get currentSpectrumInfo(): AggregateSpectrumInfo | null | undefined {
        return this.#currentSpectrumInfo;
    }

    /**
     * Gets all available aggregate spectrum options.
     *
     * @returns A map of spectrum IDs to aggregate spectrum information.
     */
    get spectrumOptions(): ReadonlyMap<string, AggregateSpectrumInfo> {
        return this.#spectrumOptions;
    }

    /**
     * Gets the event handlers for this aggregate selection.
     *
     * @returns The aggregate selection event handlers.
     */
    get events(): AggregateSelectionEvents {
        return this.#events;
    }

    /**
     * Updates the aggregate display name.
     *
     * @param name - The new display name. Use `null` to clear the name or
     * `undefined` to represent a mixed selection.
     */
    setDisplayName = (name: string | null | undefined): void => {
        this.#displayName = name;
    };

    /**
     * Updates the aggregate display opacity.
     *
     * String values are parsed as floating-point numbers by
     * {@link tryParseFloat}.
     *
     * @param opacity - The new numeric opacity, a parseable string, `null`, or
     * `undefined`.
     */
    setDisplayOpacity = (opacity: number | string | null | undefined): void => {
        this.#displayOpacity = tryParseFloat(opacity);
    };

    /**
     * Selects a spectrum by its numeric or string identifier.
     *
     * When the identifier is not present in {@link spectrumOptions}, the
     * current spectrum and display spectrum ID are set to `null`. Passing
     * `null` or `undefined` preserves that value and clears or marks the
     * selection as mixed, respectively.
     *
     * The `onSpectrumChange` handler is invoked after the selection is updated.
     *
     * @param id - The spectrum identifier to select, `null` to clear the
     * selection, or `undefined` to represent a mixed selection.
     * @returns Information about the selected spectrum, `null` when no matching
     * spectrum exists, or `undefined` for a mixed selection.
     */
    setDisplaySpectrumId = (
        id: number | string | null | undefined
    ): AggregateSpectrumInfo | null | undefined => {
        if (id != null) {
            this.#currentSpectrumInfo = this.#spectrumOptions.get(id.toString()) ?? null;

            this.#displaySpectrumId = this.#currentSpectrumInfo?.id ?? null;
        } else {
            this.#currentSpectrumInfo = id;
            this.#displaySpectrumId = id;
        }

        if (this.#events.onSpectrumChange != null) {
            this.#events.onSpectrumChange(this.#currentSpectrumInfo);
        }

        return this.#currentSpectrumInfo;
    };
}
