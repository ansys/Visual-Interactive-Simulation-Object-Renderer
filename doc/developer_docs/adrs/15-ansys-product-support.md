# VISOR Format Support of  Flagship Simulation Products

## Status
Team and Stakeholder Αpproved


## Decision
VISOR depends on legacy Ansys flagships to provide VTK format support and on PyAnsys APIs to enable those flagships to be used within Solutions Applications. These workflows improve maintainability and adoption by leveraging PyAnsys, which offers a specialized 3D viewer for examples and lowers the effort required for community users to access needed functionality. Each flagship product is responsible for converting its internal data to the common format. That format is aligned with SimAI requirements and maintained by the flagship teams, ensuring it stays optimized and in sync with the 3D viewer as products evolve.

## Context
Our requirements for legacy Ansys product support were based on the requirements for legacy Ansys products namely, Discovery, SpaceClaim, Fluent, Mechanical, AEDT suite and EnSight. Our prioritized requirements are for Fluent, GeometryService, but all legacy Ansys flagship products are included in the VISOR roadmap as well as Electronics Simulation Products. VISOR is a component which will be available within the Solution Architecture Framework and it is in VISOR's scope to be able to visualize the models and the data produced in those products. It is out of scope for VISOR to be doing transformations of the Ansys product formats to its internal representation. VISOR is using a scene graph described in the [08-scene-graph ADR](https://github.com/ansys-internal/theia/blob/c5ec3e366c8dbe385b5de520ddff10da7eaf6f78/docs/adrs/07-scene-graph.md). This scene description graph supports VTK format.

VISOR supports VTK-based formats (including VTKHDF), which is the requirement for supporting 3D data along with the mixed OpenUSD and VTK formats from the [architecture board decision #29](https://github.com/ansys-internal/architecture-decision-records/blob/main/content/docs/adrs/0029-visualization-formats.md). Based on that decision, all legacy Ansys products need to support the mixed OpenUSD and VTK format, and for VTK they should be providing VTKHDF. This decision is based on achieving a common visualization format which covers the current needs and the upcoming view regarding OpenUSD format. Considerations for the legacy Ansys common data model may impact some of the decisions here but those discussions will need to make sure to include the requirements and constraints of the VISOR 3D viewer.

## VISOR currently supports VTK

VISOR directly supports VTK-based formats.

_*Advantages*_:

1. :heavy_check_mark: VISOR viewer as a visualization tool focuses on the visualization capabilities and technology stack which covers its functional and non-functional requirements as a visualization tool.
2. :heavy_check_mark: Avoids overlap with DPF and PyAnsys initiatives which are creating bindings from their formats to open formats such as VTK.
3. :heavy_check_mark: Existing tools such as DPF and PyAnsys bindings can be used to create workflows from Ansys flagship products to VTK format and with the usage of VTKHDF all the information should be encoded to the file format. Only additional information would be necessary for VISOR internal state management.
4. :heavy_check_mark: VISOR is required to enable high-performance workflows, but it is the responsibility of all the different components in the Solutions Application Visualization Workflow to cover the performance requirements of those. This is the reason VISOR is not adding these tools behind any of its APIs.
5. :heavy_check_mark: The developers creating a Solution Application are able to use PyAnsys products to also have post-processing capabilities that a viewer cannot have in its scope.
6. :heavy_check_mark: VISOR's release package and containers contain the minimum dependencies required for VISOR's functional capabilities in order to be aligned with the deployment KPIs of an Shared Technology Component.
7. :heavy_check_mark: VISOR doesn't need to spend development and testing resources for an all-formats-to-one-format.
8. :heavy_check_mark: The usage of open formats for rendering pipelines and formats allows VISOR to have less legacy Ansys proprietary and protected content in terms of visualization which can enable open sourcing part or the whole of the viewer and as such enabling a seamless integration with the PyAnsys initiative and greater adoption. The alignment with the PyAnsys initiative also drives the ability to have maintained and up-to-date APIs since legacy Ansys flagships and the PyAnsys community has put investment on that side which will be continuing in the foreseeable future.

_*Disadvantages*_:

1. :x: VISOR is not a single visualization component covering the visualization workflow. The Solution Application Developers need to be able to setup that workflow using PyAnsys APIs or DPF to create a workflow in a Solution.
2. :x: VISOR's input format is not supported by all legacy Ansys Simulation Flagships so the products themselves need to provide that optimized conversion to VTK format. The AVZ workflow has been offering transformations from all Ansys Flagship Simulation Products to its proprietary Ansys Visualization Format (AVZ). In this model, we switch to using VTK, which is an open standard and in that way the proprietary format is only limited to the products and whenever they do updates of their format they will also make sure to maintain their VTK export.


### Visualization workflows for Solution Applications

VISOR is relying on legacy Ansys flagships to provide VTK format support as well as PyAnsys APIs to support flagships in order to be able to be used in Solutions Applications. These workflows allow better maintainability and adoption as PyAnsys has a specialized 3D viewer for examples and showcasing specific products capabilities which is also able to provide less effort for the community users in order to get functionality they are requiring. The flagship products will own the part of converting their internal format to the common format but that format is aligning with SimAI requirements and its also able to be optimized and maintained by them so there is no lag between their updates and the version actually used in the 3D viewer.



### Consequences

* Deprecation of libraries that were providing code for transforming Discovery and Fluent format to VTK. More specifically the following libraries are being *deprecated*: [visor-geometry-support](https://github.com/ansys-internal/theia-geometry/tree/main/examples) and [visor-fluent-support](https://github.com/ansys-internal/theia-fluent-support). These were created in order to provide proof of concepts and evaluations for VISOR usage but they were never aimed to go to production.
* VISOR will own any specialized formatting it needs which is more specialized than what the generic product support provides.
* PyAnsys initiative pyansys-visualization-tools and any relevant initiatives and PyAnsys APIs for specific products like PyGeometry need to have prioritization in terms of VISOR's technical stakeholders.
* PyAnsys APIs for specific products would benefit from supporting VISOR and having some less performant APIs like we have for PyGeometry until there is full support from products.
* DPF and pyDPF is able to support VISOR as it is and based on the fact that it supports VTKHDF and hierarchical data (assemblies) it can provide more performant bindings if they from their side implement the relevant transformations.

### Examples and testing

The [Reference Solution](https://github.com/ansys-internal/airfoil-explorer) created by the Task Force PI&E which targets the Control Plane Blueprint for desktop, on-prem and cloud-native targets is using VISOR for 3D visualization for geometry models created by the GeometryService through PyGeometry APIs. This solution application is also going to be used for testing the integration of these components to provide more long-term support.


## Notes

### 4/7/2026

After the [architecture board decision #29](https://github.com/ansys-internal/architecture-decision-records/blob/main/content/docs/adrs/0029-visualization-formats.md) for the common graphics format, a lot of the context of the specific formats for each product is actually obsolete from this discussion as they are required to support the VTK format. The information that was previously outlined can be found here:

|No | Product| File Extension/ Format |  Priority |
----|--------|------------------------|-----------|
| 1 | Fluent |.cas.h5, .dat.h5, msh(.h5), | MVP  |
| 2 | SpaceClaim | .scdoc(x) | MVP |
| 3 | Discovery | .dsco | MVP |
| 4 | AEDT | .aedt, .case | High |
| 5 | Mechanical | .cdb, .rst, .rth, .rstp, .rmg | High |
| 6 | Ansys Viewer (AVZ) | .avz | Medium |
| 7 | CFX | .res, .dat, .def | Low |
| 8 | HFSS | .obj, .aedtplt | Low |
| 9 | SIWave | .anf, ODB++, EDB, IPC-2581, DXF, GDSII, .snp | Low|
|10 | Maxwell | .ies, .ldt | Low |
| 11 | EnSight | .case, .encas | Low |

(*) Note: This prioritization is based on our VISOR board and not on the document which is not currently being updated in terms of priorities but the requirements in terms of formats are still up to date as of 7/31/2025.



## Options and recommended usage per format

### Fluent

Fluent formats are the following: .cas.h5, .dat.h5, msh(.h5). There are currently the following options for using VISOR in a Solutions with these formats.

#### VISORFluentSupport


```python
converter = VisorFluentSupport()

file, metadata = converter.to_vtk_file(
    case_file=str(pathlib.Path.joinpath(dir, "input.cas.h5")),
    data_file=str(pathlib.Path.joinpath(dir, "input.dat.h5")),
    file_path=str(pathlib.Path.joinpath(dir, "output")),
)

visualization = Visor(input=file, metadata=metadata, standalone=True)
visualization.start()
file, metadata = converter.to_vtk_file(
    case_file=str(pathlib.Path.joinpath(dir, "input.cas.h5")),
    data_file=str(pathlib.Path.joinpath(dir, "input.dat.h5")),
    file_path=str(pathlib.Path.joinpath(dir, "output")),
)
visualization.update(input=file, metadata=metadata)

visualization.stop()
```


#### DPF/DataBridge

VISOR will be able to accept files in its Pythonic APIs using DPF APIs as it has been done for DataBridge. If DPF is able to convert to single VtkDataset along with the existing capabilities of DPF to provide a metadata object then the in-memory API can also be used.



### Ansys Geometry Format (SpaceClaim/Discovery/Geometry Service)

Geometry format from Ansys products Discovery (SpaceClaim) and the Geometry Service support PyVista bindings in their PyAnsys bindings. Using those bindings we can convert to VTK formats and metadata objects and files which are compatible with VISOR. The Solutions Applications Visualization Workflow can use the Geometry Service directly or helper libraries to be able to convert to VTK format. Such a helper library is VisorGeometrySupport
in the following example:

```python
converter = VisorGeometrySupport()
(model, metadata) = converter.to_vtk_file(
    resolve_path("reactor.scdocx"), resolve_path("reactor")
)
visualizer = Visor(input=model, metadata=metadata, standalone=True)
visualizer.start()
```

### Ansys Discovery Physics

Ansys Discovery supports exporting VTK format for geometry and physics but its not currently connected to the Python bindings. This
needs to be a feature request for adding the Python bindings.

### Ansys Mechanical formats

A conversion mechanism based on DPF can be used in order to be able to convert these formats to VTK files or datasets and to the metadata object.
This can be done currently and if necessary for ease of use helper libraries could be created as part of the Solutions Applications.

### EnSight

EnSight is able to export to VTK format compatible with VISOR and is able to be integrated with VISOR viewer.

### AVZ

Conversions from AVZ to VTK can be supported if that is actually proritized from the business cases.

### Electronics formats

In order to support formats: .aedt, .case,  .res, .dat, .def, obj, .aedtplt, .anf, ODB++, EDB, IPC-2581, DXF, GDSII, .snp, .ies, .ldt we would need to leverage DPF and PyAnsys bindings which are offered from PyAEDT. This work hasn't been prioritized but the basis of capabilities currently exists
from PYAEDT.







