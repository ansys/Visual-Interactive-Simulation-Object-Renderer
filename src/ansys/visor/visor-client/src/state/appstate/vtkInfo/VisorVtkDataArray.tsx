import { ensureArray, ensureNumber, ensureString, StateInput } from './../VisorStateCommon.tsx';

/**
 * Define types for VTK data array types: can be 'POINT' or 'CELL'
 */
const FIELD_ASSOCIATIONS = ['POINT', 'CELL'] as const;

/**
 * Define union type for VTK data array based on list in FIELD_ASSOCIATIONS.
 */
export type FieldAssociation = (typeof FIELD_ASSOCIATIONS)[number];

/**
 * Validator determining whether a string is a valid FieldAssociation
 */
const isFieldAssociation = (v: string): v is FieldAssociation =>
    (FIELD_ASSOCIATIONS as readonly string[]).includes(v);

/**
 * Describes a data array associated with a VTK dataset.
 *
 * A data array identifies its scalar or vector type, component count,
 * component ranges, and overall magnitude range.
 */
export default class VisorVtkDataArray {
    /**
     * Creates a VTK data-array description from serialized state.
     *
     * @param json_or_object - A JSON string, plain state object, or other
     * supported state input containing the data-array properties.
     */
    constructor(json_or_object: StateInput<VisorVtkDataArray> = null) {
        const obj =
            typeof json_or_object === `string` ? JSON.parse(json_or_object) : json_or_object;
        ensureNumber(obj.indexForType, `indexForType`);
        ensureString(obj.type, `type`);
        ensureString(obj.name, `name`);
        ensureNumber(obj.numComponents, `numComponents`);
        ensureArray(obj.magnitudeRange, `magnitudeRange`);
        ensureArray(obj.ranges, `ranges`);
        this.indexForType = obj.indexForType;
        if (!isFieldAssociation(obj.type))
            throw new Error(
                `type must be one of ${FIELD_ASSOCIATIONS.join(', ')}, received ${JSON.stringify(obj.type)}`
            );
        this.type = obj.type;
        this.name = obj.name;
        this.numComponents = obj.numComponents;
        this.magnitudeRange = obj.magnitudeRange;
        this.ranges = obj.ranges;
    }

    /**
     * Position of this array among arrays of the same type.
     */
    indexForType: number;

    /**
     * VTK data-array type or classification.
     */
    type: FieldAssociation;

    /**
     * Display name of the data array.
     */
    name: string;

    /**
     * Number of components stored for each tuple in the data array.
     */
    numComponents: number;

    /**
     * Minimum and maximum magnitude values for the data array.
     */
    magnitudeRange: number[];

    /**
     * Minimum and maximum values for each component.
     */
    ranges: number[][];
}
