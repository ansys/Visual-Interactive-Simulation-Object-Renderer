import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { VisorSpectrumComponentMetadata } from '../state/VisorSpectrumManager.tsx';
import { AggregateSpectrumInfo } from './AggregateSpectrumInfo.tsx';
import { tryParseFloat } from '../utils/JsHelpers';

/**
 * Metadata describing a spectrum component within an aggregate spectrum.
 */
type SpectrumComponentMetadata = VisorSpectrumComponentMetadata & {};

/**
 * Event callbacks emitted when the component's displayed spectrum range changes.
 */
class AggregateSpectrumComponentInfoEvents {
    /**
     * Called when the displayed minimum value changes.
     *
     * `undefined` may indicate that selected actors have different minimum
     * values or that range information is unavailable.
     */
    onMinChange!: ((min: number | null | undefined) => void) | null;

    /**
     * Called when the displayed maximum value changes.
     *
     * `undefined` may indicate that selected actors have different maximum
     * values or that range information is unavailable.
     */
    onMaxChange!: ((max: number | null | undefined) => void) | null;
}

/**
 * Represents the aggregate display-range state for one spectrum component
 * across a collection of scene nodes.
 *
 * A range value has the following meanings:
 *
 * - `number`: all selected nodes share that value.
 * - `null`: the shared range endpoint has not been explicitly set.
 * - `undefined`: the selected nodes have different values, or range
 *   information is unavailable for at least one node.
 *
 * Instances must be created with {@link AggregateSpectrumComponentInfo.getInstanceAsync}.
 */
export class AggregateSpectrumComponentInfo {
    /**
     * Prevents direct construction.
     *
     * Use {@link AggregateSpectrumComponentInfo.getInstanceAsync} to create
     * and initialize an instance.
     */
    private constructor() {}

    /** Aggregate spectrum associated with this component. */
    #spectrumInfo!: AggregateSpectrumInfo;

    /** Metadata describing this spectrum component. */
    #componentMetadata!: SpectrumComponentMetadata;

    /** Shared default minimum across the selected scene nodes. */
    #displaySpectrumDefaultMin: number | null | undefined = null;

    /** Shared default maximum across the selected scene nodes. */
    #displaySpectrumDefaultMax: number | null | undefined = null;

    /** Shared custom minimum across the selected scene nodes. */
    #displaySpectrumMin: number | null | undefined = null;

    /** Shared custom maximum across the selected scene nodes. */
    #displaySpectrumMax: number | null | undefined = null;

    /** Event callbacks for changes to the custom display range. */
    #events: AggregateSpectrumComponentInfoEvents = {
        onMinChange: null,
        onMaxChange: null,
    };

    /**
     * Creates aggregate component information for the supplied scene nodes.
     *
     * Range endpoints are retained when every node has the same value.
     * An endpoint is set to `undefined` when values differ between nodes or
     * when a node does not contain range information for this component.
     *
     * @param actorNodes - Scene nodes whose spectrum ranges will be aggregated.
     * @param spectrumInfo - Aggregate spectrum containing the component.
     * @param componentMetadata - Metadata identifying the spectrum component.
     * @returns A fully initialized aggregate component information instance.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[],
        spectrumInfo: AggregateSpectrumInfo,
        componentMetadata: SpectrumComponentMetadata
    ): Promise<AggregateSpectrumComponentInfo> {
        const obj = new AggregateSpectrumComponentInfo();
        obj.#spectrumInfo = spectrumInfo;
        obj.#componentMetadata = componentMetadata;

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const thisSpectrum = node.spectrumCollection.getSpectrum(spectrumInfo.id);
            const rangeInfo = thisSpectrum?.getRangeInfo(componentMetadata.id);

            if (rangeInfo == null) {
                obj.#displaySpectrumDefaultMin = undefined;
                obj.#displaySpectrumDefaultMax = undefined;
                obj.#displaySpectrumMin = undefined;
                obj.#displaySpectrumMax = undefined;
                break;
            }

            const { defaultRange, customRange } = rangeInfo;
            const thisSpectrumDefaultMin: number | null = defaultRange[0];
            const thisSpectrumDefaultMax: number | null = defaultRange[1];
            const thisSpectrumMin: number | null = customRange[0];
            const thisSpectrumMax: number | null = customRange[1];

            if (i === 0) {
                obj.#displaySpectrumDefaultMin = thisSpectrumDefaultMin;
                obj.#displaySpectrumDefaultMax = thisSpectrumDefaultMax;
                obj.#displaySpectrumMin = thisSpectrumMin;
                obj.#displaySpectrumMax = thisSpectrumMax;
            } else {
                obj.#displaySpectrumDefaultMin !== thisSpectrumDefaultMin &&
                    (obj.#displaySpectrumDefaultMin = undefined);

                obj.#displaySpectrumDefaultMax !== thisSpectrumDefaultMax &&
                    (obj.#displaySpectrumDefaultMax = undefined);

                obj.#displaySpectrumMin !== thisSpectrumMin &&
                    (obj.#displaySpectrumMin = undefined);

                obj.#displaySpectrumMax !== thisSpectrumMax &&
                    (obj.#displaySpectrumMax = undefined);
            }
        }

        return obj;
    }

    /**
     * Gets the spectrum component identifier.
     */
    get id(): SpectrumComponentMetadata['id'] {
        return this.#componentMetadata.id;
    }

    /**
     * Gets the metadata associated with this spectrum component.
     */
    get metadata(): SpectrumComponentMetadata {
        return this.#componentMetadata;
    }

    /**
     * Gets the aggregate spectrum associated with this component.
     */
    get spectrumInfo(): AggregateSpectrumInfo {
        return this.#spectrumInfo;
    }

    /**
     * Gets the shared default minimum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displaySpectrumDefaultMin(): number | null | undefined {
        return this.#displaySpectrumDefaultMin;
    }

    /**
     * Gets the shared default maximum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displaySpectrumDefaultMax(): number | null | undefined {
        return this.#displaySpectrumDefaultMax;
    }

    /**
     * Gets the current custom minimum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displaySpectrumMin(): number | null | undefined {
        return this.#displaySpectrumMin;
    }

    /**
     * Gets the current custom maximum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displaySpectrumMax(): number | null | undefined {
        return this.#displaySpectrumMax;
    }

    /**
     * Gets the event callbacks for display-range changes.
     */
    get events(): AggregateSpectrumComponentInfoEvents {
        return this.#events;
    }

    /**
     * Parses and sets the custom minimum display value.
     *
     * The registered {@link AggregateSpectrumComponentInfoEvents.onMinChange}
     * callback is invoked after the value is updated.
     *
     * @param min - A numeric value, numeric string, `null`, or `undefined`.
     * @returns `true` when the parsed value is neither `null` nor `undefined`;
     * otherwise `false`.
     */
    setDisplaySpectrumMin = (min: number | string | null | undefined): boolean => {
        this.#displaySpectrumMin = tryParseFloat(min);

        if (this.#events.onMinChange != null) {
            this.#events.onMinChange(this.#displaySpectrumMin);
        }

        return this.#displaySpectrumMin != null;
    };

    /**
     * Parses and sets the custom maximum display value.
     *
     * The registered {@link AggregateSpectrumComponentInfoEvents.onMaxChange}
     * callback is invoked after the value is updated.
     *
     * @param max - A numeric value, numeric string, `null`, or `undefined`.
     * @returns `true` when the parsed value is neither `null` nor `undefined`;
     * otherwise `false`.
     */
    setDisplaySpectrumMax = (max: number | string | null | undefined): boolean => {
        this.#displaySpectrumMax = tryParseFloat(max);

        if (this.#events.onMaxChange != null) {
            this.#events.onMaxChange(this.#displaySpectrumMax);
        }

        return this.#displaySpectrumMax != null;
    };
}
