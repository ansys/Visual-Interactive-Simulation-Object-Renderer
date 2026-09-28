import VisorVtkDataArray, { FieldAssociation } from './appstate/vtkInfo/VisorVtkDataArray.tsx';

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
        /** Aggregate range calculated from all matching data arrays. */
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
 * A collection of spectra associated with a group of data arrays.
 */
export type VisorVariableCollection = Readonly<{
    /** Spectra in collection order. */
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
 * Coordinates variable metadata across multiple groups of VTK data arrays.
 *
 * @remarks
 * Call {@link VisorVariableManager.addDataArrayMetadata} for every relevant
 * group of arrays, then call
 * {@link VisorVariableManager.finishAddingDataArrayMetadata} once. The global
 * collection is unavailable until finalization is complete.
 */
export type VisorVariableManager = Readonly<{
    /**
     * Adds metadata for a group of VTK data arrays.
     *
     * @param dataArrays - Data arrays from which variable metadata is derived.
     * @returns A collection containing one variable for each supplied data array.
     *
     * @remarks
     * Arrays with the same type, name, and component count share a global
     * variable. Their default ranges are expanded to include all observed values.
     */
    addDataArrayMetadata: (dataArrays: VisorVtkDataArray[]) => VisorVariableCollection;

    /**
     * Finalizes the global variable collection.
     *
     * @throws Error if this method has already been called.
     */
    finishAddingDataArrayMetadata: () => void;

    /**
     * Finalized collection of all globally registered spectra.
     *
     * @throws Error if
     * {@link VisorVariableManager.finishAddingDataArrayMetadata} has not yet
     * been called.
     */
    globalVariableCollection: VisorVariableCollection;
}>;

/**
 * Creates a variable manager for aggregating metadata from VTK data arrays.
 *
 * @returns A new variable manager with no registered spectra.
 */
export function getVariableManager(): VisorVariableManager {
    /** Tracks variable IDs and their assigned lookup positions. */
    const variableIdLookup: Map<string, number> = new Map();

    /** Stores each globally unique variable by its ID. */
    const globalVariableMap: Map<string, VisorVariableInfo> = new Map();

    /** Stores aggregate default ranges for each variable. */
    const globalDefaultRanges: Map<string, number[][]> = new Map();

    /** Stores user-configurable ranges for each variable. */
    const globalCustomRanges: Map<string, number[][]> = new Map();

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

    /** Finalized global collection, or `null` until registration is complete. */
    let globalVariableCollection: VisorVariableCollection | null = null;

    return Object.freeze({
        addDataArrayMetadata,

        /**
         * Finalizes the global collection after all data-array metadata has been added.
         *
         * @throws Error if the global collection has already been finalized.
         */
        finishAddingDataArrayMetadata() {
            if (globalVariableCollection != null) {
                throw new Error(`finishAddingDataArrayMetadata() has already been called`);
            }

            const array = [];
            for (const item of globalVariableMap.values()) {
                array.push(item);
            }

            globalVariableCollection = Object.freeze({
                array,

                /**
                 * Finds a globally registered variable.
                 *
                 * @param id - Variable identifier, or `null`.
                 * @returns The matching variable, or `null` when none exists.
                 */
                getVariable(id: string | null) {
                    return id != null ? (globalVariableMap.get(id) ?? null) : null;
                },
            });
        },

        /**
         * Gets the finalized global variable collection.
         *
         * @throws Error if metadata registration has not yet been finalized.
         */
        get globalVariableCollection() {
            if (globalVariableCollection == null) {
                throw new Error(`finishAddingDataArrayMetadata() has not been called yet`);
            }

            return globalVariableCollection;
        },
    });

    /**
     * Creates or updates variable information for a data array.
     *
     * @param dataArray - Source data array metadata.
     * @returns The newly created variable, or the existing compatible variable.
     *
     * @remarks
     * When a compatible variable already exists, its default ranges are expanded
     * to include the new array's ranges. Its custom ranges are then reset to the
     * updated defaults.
     *
     * @throws Error if the data array has an unsupported component count.
     */
    function tryAddVariableInfo(dataArray: VisorVtkDataArray): VisorVariableInfo {
        const { type, name, numComponents, magnitudeRange, ranges } = dataArray;

        // Use a human-readable ID like 'point::displacement::3'
        const id = `${type}::${name}::${numComponents}`;

        if (globalVariableMap.has(id)) {
            // Update the existing ranges for this variable
            // with each subsequent new set of ranges.
            const defaultRanges = globalDefaultRanges.get(id)!;
            const customRanges = globalCustomRanges.get(id)!;

            magnitudeRange[0] < defaultRanges[0][0] && (defaultRanges[0][0] = magnitudeRange[0]);
            magnitudeRange[1] > defaultRanges[0][1] && (defaultRanges[0][1] = magnitudeRange[1]);

            ranges.forEach((range, i) => {
                range[0] < defaultRanges[i + 1][0] && (defaultRanges[i + 1][0] = range[0]);
                range[1] > defaultRanges[i + 1][1] && (defaultRanges[i + 1][1] = range[1]);
            });

            customRanges.forEach((range, i) => {
                range[0] = defaultRanges[i][0];
                range[1] = defaultRanges[i][1];
            });

            return globalVariableMap.get(id)!;
        }

        const labelInfo = labelInfoMap.get(numComponents);
        if (labelInfo == null) {
            const msg = `No label info was found for this data array. Do we support label info`;
            throw new Error(`${msg} for data arrays with ${numComponents} component(s)?`);
        }

        const componentOptions: VisorVariableComponentMetadata[] = [];
        for (let i = 0; i < labelInfo.componentLabels.length; i++) {
            componentOptions.push({
                id: i - 1,
                name: labelInfo.componentLabels[i],
            });
        }

        const [defaultRanges, customRanges] = (() => {
            const arr: number[][] = [];
            const arrClone: number[][] = [];

            arr.push([magnitudeRange[0], magnitudeRange[1]]);
            arrClone.push([magnitudeRange[0], magnitudeRange[1]]);

            for (let i = 0; i < numComponents; i++) {
                arr.push([ranges[i][0], ranges[i][1]]);
                arrClone.push([ranges[i][0], ranges[i][1]]);
            }

            return [arr, arrClone];
        })();

        globalDefaultRanges.set(id, defaultRanges);
        globalCustomRanges.set(id, customRanges);

        const info: VisorVariableInfo = Object.freeze({
            id,
            type,
            name,
            shape: labelInfo.shape,
            fullName: `${type} - ${name} (${labelInfo.shape})`,
            numComponents,
            componentOptions,

            /**
             * Gets cloned range information for a component.
             *
             * @param component - Component index, with `-1` representing magnitude.
             * @returns Range information, or `null` for an invalid component.
             */
            getRangeInfo: (component) => {
                if (component == null) {
                    return null;
                }

                const i = component + 1; // Add 1 because "magnitude" occupies index 0.

                return i >= 0 && i < customRanges.length
                    ? {
                          // Clone the arrays so they cannot be directly modified by the user.
                          defaultRange: [...defaultRanges[i]],
                          customRange: [...customRanges[i]],
                      }
                    : null;
            },

            /**
             * Changes the custom range for a component.
             *
             * @param component - Component index, with `-1` representing magnitude.
             * @param min - New minimum range value.
             * @param max - New maximum range value.
             */
            setCustomRange: (component, min, max) => {
                const i = component + 1; // Add 1 because "magnitude" occupies index 0.

                if (i >= 0 && i < customRanges.length) {
                    customRanges[i][0] = min;
                    customRanges[i][1] = max;
                }
            },
        });

        globalVariableMap.set(id, info);
        return info;
    }

    /**
     * Registers a group of data arrays and creates its local variable collection.
     *
     * @param dataArrays - Data arrays to register.
     * @returns An immutable collection containing spectra for the supplied arrays.
     */
    function addDataArrayMetadata(dataArrays: VisorVtkDataArray[]): VisorVariableCollection {
        const array: VisorVariableInfo[] = [];
        const map: Map<string, VisorVariableInfo> = new Map();

        for (let i = 0; i < dataArrays.length; i++) {
            const info = tryAddVariableInfo(dataArrays[i]);
            array.push(info);
            map.set(info.id, info);
        }

        Object.freeze(array);

        return Object.freeze({
            array,

            /**
             * Finds a variable within this local collection.
             *
             * @param id - Variable identifier, or `null`.
             * @returns The matching variable, or `null` when none exists.
             */
            getVariable(id: string | null) {
                return id != null ? (map.get(id) ?? null) : null;
            },
        });
    }
}
