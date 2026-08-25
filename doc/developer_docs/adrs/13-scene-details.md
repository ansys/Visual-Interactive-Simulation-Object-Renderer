# ADR 13: Complete VisorSceneDetails Schema

## Context

In order for VISOR to properly load the visualizer in a browser, VISOR's Python backend needs to send some data to the VTK-WASM frontend. This is to ensure the object tree, drop-down options, and various labels and such are populated with the correct information.

In this ADR, we decide on a schema that the frontend will use to send data from the Python backend to the frontend. Specifically, this is the JSON structure that the data will have. The top-level container is called the `VisorSceneDetails`. Children of the `VisorSceneDetails` are the `VisorAppState` and `VtkInfo`.

## Structure

```text
VisorSceneDetails
│
├─ appState : VisorAppState
│   │
│   ├─ ui : VisorUiState
│   │   │
│   │   ├─ darkTheme : boolean | undefined
│   │   ├─ panelTopLeftPanelCollapsed : boolean | undefined
│   │   ├─ panelTopRightPanelCollapsed : boolean | undefined
│   │   ├─ panelTopRightLegendCollapsed : boolean | undefined
│   │   └─ panelTopRightTabIndex : number | undefined
│   │
│   └─ scene : VisorSceneState
│       │
│       ├─ unit : string | undefined
│       ├─ orthographicEnabled: boolean | undefined
│       ├─ crossSectionEnabled: boolean | undefined
│       ├─ edgesEnabled: boolean | undefined
│       ├─ boundingBoxEnabled: boolean | undefined
│       │
│       ├─ camera: VisorCameraState
│       │   ├─ position: number[] | undefined
│       │   ├─ focalPoint: number[] | undefined
│       │   ├─ viewUp: number[] | undefined
│       │   ├─ clippingRange: number[] | undefined
│       │   ├─ parallelProjection: boolean | undefined
│       │   ├─ viewAngle: number | undefined
│       │   └─ parallelScale: number | undefined
│       │
│       ├─ crossSection: VisorCrossSectionState
│       │   ├─ origin: number[] | undefined
│       │   └─ normal: number[] | undefined
│       │
│       ├─ datasetStates : Record<string, VisorDatasetState>
│       │   │
│       │   └─ [datasetId] : VisorDatasetState
│       │       ├─ id   : string
│       │       └─ partStates : Record<string, VisorPartState>
│       │           │
│       │           └─ [partId] : VisorPartState
│       │               ├─ id                : string
│       │               ├─ opacity           : number | undefined
│       │               ├─ visible           : boolean | undefined
│       │               ├─ diffuseRgb        : number[] | undefined
│       │               ├─ selected          : boolean | undefined
│       │               ├─ spectrumId        : number | null | undefined
│       │               └─ spectrumComponent : number | undefined
│       │
│       └─ spectrumStates : Record<string, VisorSpectrumState>
│           │
│           └─ [spectrumId] : VisorSpectrumState
│               ├─ id               : string
│               ├─ magnitudeRange   : [number, number] | undefined
│               └─ ranges           : Array<[number, number] | undefined>
│
└─ vtkInfo : VtkInfo
    │
    ├─ orientationWidgetWasmId               : number
    ├─ crossSectionPlaneWasmId               : number
    ├─ crossSectionPlaneWidgetWasmId         : number
    ├─ crossSectionPlaneRepresentationWasmId : number
    ├─ boundingBoxBoxAlgorithmWasmId         : number
    ├─ boundingBoxOutlineWasmActorId         : number
    ├─ boundingBoxAxesWasmActorId            : number
    │
    └─ sceneGraph : RootNode
        ├─ id               : number
        ├─ wasmActorId      : number
        ├─ wasmPropertyId   : number
        ├─ wasmMapperId     : number
        ├─ dataArrays       : Array<any>
        ├─ name             : string
        ├─ isGroupNode      : true
        ├─ isActorNode      : false
        ├─ nodeType         : "root"
        ├─ diffuseColor     : [number, number, number]
        ├─ bounds           : number[]
        │
        └─ children : Array<DatasetNode>
            │
            └─ DatasetNode (vtkMultiBlockDataSet)
                ├─ id               : number
                ├─ wasmActorId      : number
                ├─ wasmPropertyId   : number
                ├─ wasmMapperId     : number
                ├─ dataArrays       : Array<any>
                ├─ name             : string
                ├─ isGroupNode      : true
                ├─ isActorNode      : false
                ├─ nodeType         : "vtkMultiBlockDataSet"
                ├─ diffuseColor     : [number, number, number]
                ├─ bounds           : number[]
                │
                └─ children : Array<PartNode>
                    │
                    └─ PartNode (vtkPolyData)
                        ├─ id               : number
                        ├─ wasmActorId      : number
                        ├─ wasmPropertyId   : number
                        ├─ wasmMapperId     : number
                        ├─ dataArrays       : Array<any>
                        ├─ name             : string
                        ├─ isGroupNode      : false
                        ├─ isActorNode      : true
                        ├─ nodeType         : "vtkPolyData"
                        ├─ diffuseColor     : [number, number, number]
                        ├─ bounds           : number[]
                        └─ children         : []

```