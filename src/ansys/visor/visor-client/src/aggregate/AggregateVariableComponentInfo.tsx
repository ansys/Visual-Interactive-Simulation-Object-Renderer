import { VisorSceneNodeExtended } from '../state/VisorSceneGraph.tsx';
import { VisorVariableComponentMetadata } from '../state/VisorVariableManager.tsx';
import { AggregateVariableInfo } from './AggregateVariableInfo.tsx';
import { tryParseFloat } from '../utils/JsHelpers';

/**
 * Metadata describing a variable component within an aggregate variable.
 */
type VariableComponentMetadata = VisorVariableComponentMetadata & {};

/**
 * Event callbacks emitted when the component's displayed variable range changes.
 */
class AggregateVariableComponentInfoEvents {
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
 * Represents the aggregate display-range state for one variable component
 * across a collection of scene nodes.
 *
 * A range value has the following meanings:
 *
 * - `number`: all selected nodes share that value.
 * - `null`: the shared range endpoint has not been explicitly set.
 * - `undefined`: the selected nodes have different values, or range
 *   information is unavailable for at least one node.
 *
 * Instances must be created with {@link AggregateVariableComponentInfo.getInstanceAsync}.
 */
export class AggregateVariableComponentInfo {
    /**
     * Prevents direct construction.
     *
     * Use {@link AggregateVariableComponentInfo.getInstanceAsync} to create
     * and initialize an instance.
     */
    private constructor() {}

    /** Aggregate variable associated with this component. */
    #variableInfo!: AggregateVariableInfo;

    /** Metadata describing this variable component. */
    #componentMetadata!: VariableComponentMetadata;

    /** Shared default minimum across the selected scene nodes. */
    #displayVariableDefaultMin: number | null | undefined = null;

    /** Shared default maximum across the selected scene nodes. */
    #displayVariableDefaultMax: number | null | undefined = null;

    /** Shared custom minimum across the selected scene nodes. */
    #displayVariableMin: number | null | undefined = null;

    /** Shared custom maximum across the selected scene nodes. */
    #displayVariableMax: number | null | undefined = null;

    /** Event callbacks for changes to the custom display range. */
    #events: AggregateVariableComponentInfoEvents = {
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
     * @param actorNodes - Scene nodes whose variable ranges will be aggregated.
     * @param variableInfo - Aggregate variable containing the component.
     * @param componentMetadata - Metadata identifying the variable component.
     * @returns A fully initialized aggregate component information instance.
     */
    static async getInstanceAsync(
        actorNodes: VisorSceneNodeExtended[],
        variableInfo: AggregateVariableInfo,
        componentMetadata: VariableComponentMetadata
    ): Promise<AggregateVariableComponentInfo> {
        const obj = new AggregateVariableComponentInfo();
        obj.#variableInfo = variableInfo;
        obj.#componentMetadata = componentMetadata;

        for (let i = 0; i < actorNodes.length; i++) {
            const node = actorNodes[i];
            const thisVariable = node.variableCollection.getVariable(variableInfo.id);
            const rangeInfo = thisVariable?.getRangeInfo(componentMetadata.id);

            if (rangeInfo == null) {
                obj.#displayVariableDefaultMin = undefined;
                obj.#displayVariableDefaultMax = undefined;
                obj.#displayVariableMin = undefined;
                obj.#displayVariableMax = undefined;
                break;
            }

            const { defaultRange, customRange } = rangeInfo;
            const thisVariableDefaultMin: number | null = defaultRange[0];
            const thisVariableDefaultMax: number | null = defaultRange[1];
            const thisVariableMin: number | null = customRange[0];
            const thisVariableMax: number | null = customRange[1];

            if (i === 0) {
                obj.#displayVariableDefaultMin = thisVariableDefaultMin;
                obj.#displayVariableDefaultMax = thisVariableDefaultMax;
                obj.#displayVariableMin = thisVariableMin;
                obj.#displayVariableMax = thisVariableMax;
            } else {
                obj.#displayVariableDefaultMin !== thisVariableDefaultMin &&
                    (obj.#displayVariableDefaultMin = undefined);

                obj.#displayVariableDefaultMax !== thisVariableDefaultMax &&
                    (obj.#displayVariableDefaultMax = undefined);

                obj.#displayVariableMin !== thisVariableMin &&
                    (obj.#displayVariableMin = undefined);

                obj.#displayVariableMax !== thisVariableMax &&
                    (obj.#displayVariableMax = undefined);
            }
        }

        return obj;
    }

    /**
     * Gets the variable component identifier.
     */
    get id(): VariableComponentMetadata['id'] {
        return this.#componentMetadata.id;
    }

    /**
     * Gets the metadata associated with this variable component.
     */
    get metadata(): VariableComponentMetadata {
        return this.#componentMetadata;
    }

    /**
     * Gets the aggregate variable associated with this component.
     */
    get variableInfo(): AggregateVariableInfo {
        return this.#variableInfo;
    }

    /**
     * Gets the shared default minimum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displayVariableDefaultMin(): number | null | undefined {
        return this.#displayVariableDefaultMin;
    }

    /**
     * Gets the shared default maximum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displayVariableDefaultMax(): number | null | undefined {
        return this.#displayVariableDefaultMax;
    }

    /**
     * Gets the current custom minimum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displayVariableMin(): number | null | undefined {
        return this.#displayVariableMin;
    }

    /**
     * Gets the current custom maximum value.
     *
     * @returns The shared value, `null` when unset, or `undefined` when the
     * selected nodes do not agree or range information is unavailable.
     */
    get displayVariableMax(): number | null | undefined {
        return this.#displayVariableMax;
    }

    /**
     * Gets the event callbacks for display-range changes.
     */
    get events(): AggregateVariableComponentInfoEvents {
        return this.#events;
    }

    /**
     * Parses and sets the custom minimum display value.
     *
     * The registered {@link AggregateVariableComponentInfoEvents.onMinChange}
     * callback is invoked after the value is updated.
     *
     * @param min - A numeric value, numeric string, `null`, or `undefined`.
     * @returns `true` when the parsed value is neither `null` nor `undefined`;
     * otherwise `false`.
     */
    setDisplayVariableMin = (min: number | string | null | undefined): boolean => {
        this.#displayVariableMin = tryParseFloat(min);

        if (this.#events.onMinChange != null) {
            this.#events.onMinChange(this.#displayVariableMin);
        }

        return this.#displayVariableMin != null;
    };

    /**
     * Parses and sets the custom maximum display value.
     *
     * The registered {@link AggregateVariableComponentInfoEvents.onMaxChange}
     * callback is invoked after the value is updated.
     *
     * @param max - A numeric value, numeric string, `null`, or `undefined`.
     * @returns `true` when the parsed value is neither `null` nor `undefined`;
     * otherwise `false`.
     */
    setDisplayVariableMax = (max: number | string | null | undefined): boolean => {
        this.#displayVariableMax = tryParseFloat(max);

        if (this.#events.onMaxChange != null) {
            this.#events.onMaxChange(this.#displayVariableMax);
        }

        return this.#displayVariableMax != null;
    };
}
