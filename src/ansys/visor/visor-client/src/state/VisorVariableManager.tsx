import { FieldAssociation } from './appstate/vtkInfo/VisorVtkDataArray.tsx';
import type VisorVariableState from './appstate/VisorVariableState.tsx';

/**
 * Describes a selectable component of a variable.
 *
 * @remarks
 * The magnitude component uses an ID of `-1`. Individual array components
 * begin at `0`.
 */
export type VisorVariableComponentMetadata = Readonly<{
    /** Numeric identifier used to select the component. */
    id: number;

    /** Human-readable component label, such as `"Magnitude"`, `"X"`, or `"Y"`. */
    name: string;
}>;

/**
 * Describes a variable derived from one or more compatible VTK data arrays.
 *
 * @remarks
 * Variable objects are immutable, although their custom ranges can be changed
 * through {@link VisorVariableInfo.setCustomRange}.
 */
export type VisorVariableInfo = Readonly<{
    /**
     * Unique variable identifier.
     *
     * @remarks
     * The identifier has the format
     * `"<type>::<name>::<number-of-components>"`.
     */
    id: string;

    /** Data-array association type, can be either 'POINT' or 'CELL'. */
    type: FieldAssociation;

    /** Name of the underlying data array. */
    name: string;

    /** Human-readable shape name, such as `"Scalar"` or `"Vector3"`. */
    shape: string;

    /** Display name containing the association type, array name, and shape. */
    fullName: string;

    /** Number of components in the underlying data array. */
    numComponents: number;

    /** Components that can be selected when displaying the variable. */
    componentOptions: VisorVariableComponentMetadata[];

    /**
     * Gets the default and custom ranges for a component.
     *
     * @param component - Component index. Use `-1` for magnitude, `0` for the
     * first array component, or `null`/`undefined` when no component is selected.
     * @returns Cloned default and custom ranges, or `null` when the component is
     * missing or outside the supported range.
     */
    getRangeInfo: (component: number | null | undefined) => null | {
        /** Delivered default range of the component. */
        defaultRange: number[];

        /** User-configurable range for the selected component. */
        customRange: number[];
    };

    /**
     * Updates the custom range for a component.
     *
     * @param component - Component index. Use `-1` for magnitude.
     * @param min - New minimum value.
     * @param max - New maximum value.
     *
     * @remarks
     * No change is made when the component index is outside the supported range.
     */
    setCustomRange: (component: number, min: number, max: number) => void;
}>;

/**
 * A collection of variables associated with a group of data arrays.
 */
export type VisorVariableCollection = Readonly<{
    /** Variables in collection order. */
    array: VisorVariableInfo[];

    /**
     * Finds a variable by its unique identifier.
     *
     * @param id - Variable identifier, or `null` when no variable is selected.
     * @returns The matching variable, or `null` when no match exists.
     */
    getVariable: (id: string | null) => VisorVariableInfo | null;
}>;

/**
 * Holds the delivered variable records and projects them as variables.
 *
 * @remarks
 * {@link VisorVariableManager.setRecords} replaces the held records on every
 * delivery.  Call {@link VisorVariableManager.finishAddingDataArrayMetadata}
 * once before reading the global collection.
 */
export type VisorVariableManager = Readonly<{
    /**
     * Opens the global collection for reading.
     *
     * @throws Error if this method has already been called.
     */
    finishAddingDataArrayMetadata: () => void;

    /**
     * Replaces the held variable records with a delivered set.
     *
     * @param records - Every variable record in the delivery, each complete.
     *
     * @throws Error if any record is missing a field, carries fewer ranges than
     * components, or has an unsupported component count.  The held set is then
     * left unchanged.
     */
    setRecords: (records: VisorVariableState[]) => void;

    /**
     * Gets a live collection of the held variables whose records list a part.
     *
     * @param partId - Scene-graph id of the part.
     */
    getPartVariableCollection: (partId: number) => VisorVariableCollection;

    /**
     * Live collection of every held variable record.
     *
     * @throws Error if
     * {@link VisorVariableManager.finishAddingDataArrayMetadata} has not yet
     * been called.
     */
    globalVariableCollection: VisorVariableCollection;
}>;

/**
 * One held variable record, with its ranges in slot order: slot 0 is the
 * magnitude and slot `i + 1` is component `i`.
 */
class HeldVariableRecord {
    private constructor(
        private readonly partIds: ReadonlySet<number>,
        private readonly defaultRanges: number[][],
        private readonly customRanges: number[][]
    ) {}

    /**
     * Copies a delivered record into slot order.
     *
     * @throws Error if the record is missing a field or carries fewer ranges
     * than components.
     */
    static fromState(state: VisorVariableState): HeldVariableRecord {
        const id = state.id;
        const numComponents = state.numComponents;
        const missing = (field: string) =>
            new Error(`Variable record '${id}' is missing '${field}'`);

        if (id === '') {
            throw missing('id');
        } else if (state.arrayName === '') {
            throw missing('arrayName');
        } else if (state.type === undefined) {
            throw missing('type');
        } else if (!(numComponents > 0)) {
            throw missing('numComponents');
        } else if (state.partIds === undefined) {
            throw missing('partIds');
        }

        const defaultMagnitudeRange = state.defaultMagnitudeRange;
        const defaultRanges = state.defaultRanges;
        const magnitudeRange = state.magnitudeRange;
        if (defaultMagnitudeRange === undefined) {
            throw missing('defaultMagnitudeRange');
        } else if (defaultRanges === undefined) {
            throw missing('defaultRanges');
        } else if (magnitudeRange === undefined) {
            throw missing('magnitudeRange');
        }

        const toSlots = (
            field: string,
            magnitude: number[],
            perComponent: (number[] | undefined)[]
        ): number[][] => {
            const slots: number[][] = [[magnitude[0], magnitude[1]]];
            for (let i = 0; i < numComponents; i++) {
                const range = perComponent[i];
                if (range === undefined) {
                    throw new Error(
                        `Variable record '${id}' has no entry ${i} in '${field}' for ${numComponents} component(s)`
                    );
                }
                slots.push([range[0], range[1]]);
            }
            return slots;
        };

        return new HeldVariableRecord(
            new Set(state.partIds),
            toSlots('defaultRanges', defaultMagnitudeRange, defaultRanges),
            toSlots('ranges', magnitudeRange, state.ranges)
        );
    }

    /** Whether the record lists the part. */
    includesPart(partId: number): boolean {
        return this.partIds.has(partId);
    }

    /** Cloned default and custom range of a component, `-1` being the magnitude. */
    getRangeInfo(
        component: number | null | undefined
    ): null | { defaultRange: number[]; customRange: number[] } {
        if (component == null) {
            return null;
        }
        const slot = component + 1;
        return slot >= 0 && slot < this.customRanges.length
            ? {
                  defaultRange: [...this.defaultRanges[slot]],
                  customRange: [...this.customRanges[slot]],
              }
            : null;
    }

    /** Writes the custom range of a component, `-1` being the magnitude; ignores any other id. */
    setCustomRange(component: number, min: number, max: number): void {
        const slot = component + 1;
        if (slot >= 0 && slot < this.customRanges.length) {
            this.customRanges[slot][0] = min;
            this.customRanges[slot][1] = max;
        }
    }
}

/**
 * Creates a variable manager holding delivered variable records.
 *
 * @returns A new variable manager with no held records.
 */
export function getVariableManager(): VisorVariableManager {
    /** Tracks variable IDs and their assigned lookup positions. */
    const variableIdLookup: Map<string, number> = new Map();

    /** Maps supported component counts to shape and component-label metadata. */
    const labelInfoMap: Map<
        number,
        {
            /** Human-readable shape name. */
            shape: string;

            /**
             * Component labels in display order.
             *
             * @remarks
             * The first label represents magnitude. Remaining labels correspond to
             * the underlying array components.
             */
            componentLabels: string[];
        }
    > = new Map();

    labelInfoMap.set(1, {
        shape: 'Scalar',
        componentLabels: ['Magnitude'],
    });

    labelInfoMap.set(2, {
        shape: 'Vector2',
        componentLabels: ['Magnitude', 'X', 'Y'],
    });

    labelInfoMap.set(3, {
        shape: 'Vector3',
        componentLabels: ['Magnitude', 'X', 'Y', 'Z'],
    });

    labelInfoMap.set(4, {
        shape: 'Vector4',
        componentLabels: ['Magnitude', 'X', 'Y', 'Z', 'W'],
    });

    labelInfoMap.set(9, {
        shape: 'Vector4',
        componentLabels: ['Magnitude', 'XX', 'XY', 'XZ', 'YX', 'YY', 'YZ', 'ZX', 'ZY', 'ZZ'],
    });

    /** Held records by id, each with the variable object that reads it, in delivery order. */
    let heldRecords: Map<string, { record: HeldVariableRecord; info: VisorVariableInfo }> =
        new Map();

    /** Whether the global collection may be read. */
    let finished = false;

    /** The one global collection: a live view over the held records. */
    const globalVariableCollection: VisorVariableCollection = Object.freeze({
        get array() {
            return [...heldRecords.values()].map((entry) => entry.info);
        },

        /**
         * Finds a held variable.
         *
         * @param id - Variable identifier, or `null`.
         * @returns The matching variable, or `null` when none is held.
         */
        getVariable(id: string | null) {
            return id != null ? (heldRecords.get(id)?.info ?? null) : null;
        },
    });

    return Object.freeze({
        /**
         * Opens the global collection for reading.
         *
         * @throws Error if the global collection has already been opened.
         */
        finishAddingDataArrayMetadata() {
            if (finished) {
                throw new Error(`finishAddingDataArrayMetadata() has already been called`);
            }
            finished = true;
        },

        setRecords(records: VisorVariableState[]) {
            const next: Map<string, { record: HeldVariableRecord; info: VisorVariableInfo }> =
                new Map();
            for (const state of records) {
                const record = HeldVariableRecord.fromState(state);
                const existing = heldRecords.get(state.id)?.info;
                const info =
                    existing != null &&
                    existing.name === state.arrayName &&
                    existing.type === state.type &&
                    existing.numComponents === state.numComponents
                        ? existing
                        : createRecordVariableInfo(state);
                next.set(state.id, { record, info });
            }
            heldRecords = next;
        },

        getPartVariableCollection(partId: number): VisorVariableCollection {
            return Object.freeze({
                get array() {
                    return [...heldRecords.values()]
                        .filter((entry) => entry.record.includesPart(partId))
                        .map((entry) => entry.info);
                },

                /**
                 * Finds a held variable whose record lists this part.
                 *
                 * @param id - Variable identifier, or `null`.
                 * @returns The matching variable, or `null` when none is held for the part.
                 */
                getVariable(id: string | null) {
                    const entry = id != null ? heldRecords.get(id) : undefined;
                    return entry != null && entry.record.includesPart(partId) ? entry.info : null;
                },
            });
        },

        /**
         * Gets the global variable collection.
         *
         * @throws Error if the collection has not yet been opened.
         */
        get globalVariableCollection() {
            if (!finished) {
                throw new Error(`finishAddingDataArrayMetadata() has not been called yet`);
            }

            return globalVariableCollection;
        },
    });

    /**
     * Creates the variable object for a held record.  Its ranges are read from,
     * and written to, whichever record is held under its id at the time.
     *
     * @throws Error if the record has an unsupported component count.
     */
    function createRecordVariableInfo(state: VisorVariableState): VisorVariableInfo {
        const id = state.id;
        const type = state.type!;
        const name = state.arrayName;
        const numComponents = state.numComponents;
        const labelInfo = labelInfoMap.get(numComponents);
        if (labelInfo == null) {
            const msg = `No label info was found for variable record '${id}'. Do we support label info`;
            throw new Error(`${msg} for variables with ${numComponents} component(s)?`);
        }

        const componentOptions: VisorVariableComponentMetadata[] = labelInfo.componentLabels.map(
            (label, i) => ({ id: i - 1, name: label })
        );

        return Object.freeze({
            id,
            type,
            name,
            shape: labelInfo.shape,
            fullName: `${type} - ${name} (${labelInfo.shape})`,
            numComponents,
            componentOptions,
            getRangeInfo: (component: number | null | undefined) =>
                heldRecords.get(id)?.record.getRangeInfo(component) ?? null,
            setCustomRange: (component: number, min: number, max: number) => {
                heldRecords.get(id)?.record.setCustomRange(component, min, max);
            },
        });
    }
}
