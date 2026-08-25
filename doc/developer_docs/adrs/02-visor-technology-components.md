## VISOR technology components

### Status
Approved

### Decision
Based on the project tenets, the wide variety of projects to integrate with in our roadmap and our prioritized use cases and time frame, we are aiming at being technology agnostic on the API level for VISOR and provide ways to support different rendering and framework technologies on the backend. The technology we are aiming for our first release is going to be Trame framework targeting VTK WASM. We will continue researching other options and technologies as the project evolves.

### Context

VISOR is targeting to provide a 3D viewer web component and the services, tools and utilities to support the growing needs of Solutions Applications. The first release is aiming for Q4 2024/Q1 2025 based on continuous integration releases (QP2). The assessment in terms of options is done based on this time frame and the options that are not viable due to the timeframe we have can be evaluated for a different milestone in our roadmap.  The Minimum Viable Product (MVP) shortlist is tracked [here](https://ansys-my.sharepoint.com.mcas.ms/:x:/r/personal/marina_galvagni_ansys_com/_layouts/15/Doc.aspx?sourcedoc=%7B1D341238-D500-4E4B-A2A6-11DC492C2CFB%7D&file=MVP_shortlist.xlsx&action=default&mobileredirect=true) and covers all functional requirements. Key requirements non-functional are the following:

|No | Requirement |  Priority |
----|-------------|-----------|
| 1 | JS/React Client  | MVP |
| 2 | Python API (service side) | MVPt |
| 3 | Multiple user support | Long-term roadmap (to be decided) |
| 4 | Data streaming of updates  | Long-term roadmap (to be decided)|
| 5 | Integratable with Dynamic Reporting | MVP |
| 6 | Integratable and interoperable with SAF components | MVP |
| 7 | Deployment target: Desktop | MVP |
| 8 | Deployment target: On Premise | MVP |
| 9 | Deployment target : public/private cloud |  3- Low |
| 10 | Ease of use through Python scripts | MVP |
| 11 | Contributors documentation | MVP |
| 12 | Internal User documentation | MVP |
| 13 | Interoperable with pyansys-visualization-tools | Long-term roadmap (to be decided) |
| 14 | Multiple viewers (single) per session | MVP|
| 15 | Single user per session | MVP |
| 16 | Multiple users per session | Long-term roadmap (to be decided) |
| 17 | Multiple sessions | Long-term roadmap (to be decided) |
| 18 | Performance targets for pipeline for SAF, DPF, HPS for small/medium non-complex meshes| MVP |
| 19 | Performance targets for pipeline for SAF, DPF, HPS, ADR for small/medium non-complex meshes| MVP (To be decided)|
| 20 | Performance targets for pipeline for SAF, DPF, HPS, ADR for larger/ complex meshes| Long-term roadmap (to be decided) |

### Options

There are several options for this project where each of them has different advantages and challenges. The research done for each option and the rationale behind each of them is explained as:

1. [Trame](https://kitware.github.io/trame/) (VTK.js) :heavy_plus_sign: : This is a visualization framework that is already in production based on VTK.js and supported by Kitware. This is the mainline Trame framework already included in the official VTK releases.

    _Advantages_:

    * :heavy_plus_sign: _Released framework, so it is already available for integration and it is stable._
    * :heavy_plus_sign: _It has all the components we will require in order to get an estimation of delivering by the end of the year, given there is still risk in this estimation. We can get support from Kitware in terms of bugfixing for these_
    * :heavy_plus_sign: It provides server-side rendering capabilities for larger/more complicated models.
    * It is an open source project so we don't transfer cost to ACE or our customers for using this technology.
    * The GLTF 2.0 import/export.
    * VTK based visualization frameworks including Trame are being used or their visualization of choice by ACE groups, PyAnsys and some Ansys products, which can aid integratability and ease of use.

    _Disadvantages_:

    * :heavy_minus_sign: Performance is poor on the client side for medium models (~3m elements)
    * :heavy_minus_sign: It is going to be replaced by the new generation of WASM based rendering which has a different JS API and bindings on the client side
    * There are other frameworks that can potentially provide better performance long term due to using more optimal graphics formats
and better architecture in terms of streaming APIs and services for on-prem and cloud deployment targets.

    _Mitigation_:
    * We can have Kitware support on bugfixes and issues we have
    * We can use server-side rendering for more complex or larger models


2. [Trame  targeting VTK.WASM](https://github.com/Kitware/trame-vtklocal)  :heavy_check_mark: : This is the new generation for Trame which uses VTK.WASM for rendering and is also going to target WebGPU from the VTK side. This has been in development phase and only now is transitioning to productization with expected release in November.

   _Advantages_:

   * :heavy_plus_sign: It has all the components we will require in order to get an estimation of delivering at the end of the year or beginning of Q1 2025, given there is still risk in this estimation. We can get support from Kitware in terms of bugfixing for these and the engineering effort for creating and maintaining the customized viewer is the smallest of the alternatives.
   * It targets VTK.WASM on the client side which is able to provide the extra performance required for small and medium sized meshes.
   * :heavy_plus_sign: It has an object manager API which is able to serialize/deserialize objects and be used for easier integration of client side and server side rendering as well as being able to provide easier interoperability on the client side with different client side frameworks and components. Its much easier to utilize this API from a JS API and React component to integrate with SAF rather than the alternatives which would be to define the API and the multiple layers of bindings.
   * :heavy_plus_sign: It is going to be the main version of Trame on the next release of VTK.WASM and Trame frameworks.
   * :heavy_plus_sign: It needs less work on the client side to create our own client side viewer.
   * The new WebGPU releases on the VTK side will bring more performance on the client side so it will reduce the need for server side for medium or more complex models.
   * It is an open source project so we don't transfer cost to ACE or our customers for using this technology
   * VTK based visualization frameworks including Trame are being used or their visualization of choice by ACE groups, PyAnsys and some Ansys products, which can aid integratability and ease of use.
   *

   _Disadvantages_:

   * :heavy_minus_sign: It is expected to be released in November
   * It hasn't been stable so we will need more support from Kitware in order to be able to release in our timeframes and it's still going to be an issue if they don't make the stable release in November.
   * There are other frameworks that can potentially provide better performance long term due to using more optimal graphics formats and better architecture in terms of streaming APIs and services for on-prem and cloud deployment targets.

   _Mitigation_:
   * We can have Kitware support on bugfixes and issues we have

3. [Omniverse](https://www.nvidia.com/en-us/omniverse/) (OpenUSD) :heavy_multiplication_x: : NVIDIA Omniverse™ is a platform of APIs, SDKs, and services that enable developers to easily integrate Universal Scene Description (OpenUSD) and RTX rendering technologies into existing software tools and simulation workflows. There are multiple initiatives within Ansys that are integrating omniverse in their visualization workflows, which can be seen in this [slide deck](https://ansys-my.sharepoint.com/:p:/p/nicolas_dalmasso/EfBCg7P1hWRFmRQaFg1X8TABFuFUpk_imKN3IZsjayzD-g?e=966IyE) by Nicolas Dalmasso. This option hasn't been explored fully in terms of integrating the current version and then moving on to the next version of APIs and SDKs in terms of effort. There is a related task for more in-depth research though a [spike](https://github.com/ansys-internal/theia/issues/7).

    _Advantages_:

    * This platform has the latest rendering capabilities provided by NVIDIA
    * It is in partnership with Ansys and there are a lot of initiatives which are integrating Omniverse with existing tools, e.g. EnSight
    * It supports [Universal Scene Description (OpenUSD)](https://www.nvidia.com/en-us/omniverse/usd/) which is an open standard that Ansys is a collaborator
    * It has APIs and SDK Kits for developing viewers which can utilize the rendering capabilities of RTX technologies.
    * It will provide Streaming APIs covering the matrix of deployment targets Desktop, On-Prem and Cloud technologies

    _Disadvantages_:

    * It is now going through a large refactoring of their APIs which will lead to a much better performance and usability support and currently its in beta but not ready for release.
    * It requires engineering effort greater than other alternatives for supporting computational meshes and operations to provide a first version for a viewer.
    * It has a cost associated for using this platform as well as having the corresponding hardware in a desktop or on-prem configuration, which has to be agreed on for the Solution Applications and ACE if its going to be the default or a required option.

4. AVZ :heavy_multiplication_x: : This is the current viewer for Solutions Applications targeting desktop integration. The option would be to re-engineer AVZ in order to be able to support all the current functional requirements, target the new Khronos Standard GLTF 2.0 and also create a service that is able to support the On-Prem and cloud deployment targets.

    _Advantages_:
    * This is the current viewer which has experts within Ansys and could potentially deliver a next generation AVZ if the priorities were provided as such
    * It is already integrated with ADR and in the desktop version it is integrated with SAF.
    * It has proven that has the performance capabilities to be integraed in Ansys products (FLUENT).
    * It is integrated with a lot of Ansys products already so there is less effort required in building interfaces with Ansys flagship products.

    _Disadvantages_:
    * It needs engineering effort in order to be able to target the next generation of rendering technologies and standards required.
    * It doesn't have an efficient service for on premise and cloud deployment targets.
    * It is currently in flux in terms of roadmap, code ownership and codebase refactoring which needs to be resolved in order to be able to deliver our integration targets and ease of use.

5. WebGX  :heavy_multiplication_x: : This is the rendering framework developed by DBU which is targeting WebGPU. It is not researched in depth as it is currently in flux, but it could be a viable solution that we can re-evaluate.

    _Advantages_:
    * This is a framework developed for web component visualization capabilities within Ansys and has expertise in Ansys.
    * It is targeting WebGPU on the client side which has the potential to provide the performance requirements of VISOR.

    _Disadvantages_:
    * There is no maintained viewer component for VISOR
    * It is currently in flux in terms of roadmap

6. [Hoops](https://docs.techsoft3d.com/hps/latest/index.html) :heavy_multiplication_x: : It is an engineering 3D visualization SDK and it is going to provide the services and integration for our deployment targets at their next generation of software. It has not been fully evaluated as it is a vendor specific offering which has its own internal graphics format and it was not prioritized as high as other ones. We can organise time for looking into it more thoroughly but it hasn't currently been done in depth.

    _Advantages:_
    * It provides scientific SDK for JS client which aids the ease of development of the viewer and covering functional requirements (haven't researched whether all are covered with the associated performance requirements).
    * It is an established framework that we are using in Ansys products.

    _Disadvantages:_
    * It doesn't target an standard graphics format that we are contributing into
    * It has vendor requirements for using it
    * It is the next version which covers our non-functional requirements.


7. New viewer based on [Three.JS](https://threejs.org/) :heavy_multiplication_x:: This is the option of using a new custom Three.JS viewer with the use of visualization libraries to be researched and creating the service infrastructure and tools to support our functional and on-functional requirements. This option has not been researched yet, this is the corresponding [spike task](https://github.com/ansys-internal/theia/issues/18).

   _Advantages:_
    * Fully customized viewer for our needs
    * Expertise within the company

   _Disadvantages:_
    * Needs the more engineering effort in order to be able to deliver the functional requirements and the non-functional ones in terms of time and resourcing

### Consequences

These [tenets](https://github.com/ansys/visor/blob/main/doc/developer_docs/adrs/01-visor-tenets.md) allow the project to change direction without transferring effort to the groups integrated with VISOR or at least with minimal effort. This means that the option decided now it doesn't have to be the only option going forward but it is going to necessitate engineering effort to add more targets or transition the project to a new visualization SDK or platform. The view of the project is to be itself a platform for visualization components for the Solutions Group and handle the engineering complexity of those components and integrating them in VISOR rather than pushing it to the Solutions Applications. This is also a matter of choosing vendor or making it possible to have different initial, running cost and maintenance cost for the different approaches as the deployment targets and the cost evaluation differs.

The current target is to release in Q4 2024 a VISOR MVP version. The consequences per option are outlined in the following table:

| Option | Technology | Decision | Reason | Potential future target |
|---------|-----------|-----------|--------|-------------------------|
| 1 | Trame VTK.JS | No | Performance is not future looking, the architecture of our viewer is simpler and more effective with the next generation, it is a risk in terms of making the Q4 release based on the Trame VTK.WASM delivering in November officially.| No |
| 2 | Trame VTK.WASM | Yes | Performance is more future looking, architecture and engineering effort on the viewer is the shortest of all the options and we have funding for Kitware resources to help us with delivering| Yes |
|3 | Omniverse | No | It requires further investigation and the streaming APIs that we would want to target are not released yet, it also has a cost, deployment requirements and we need to make sure that Solutions Applications are all agreeing on that| Yes |
|4| AVZ (next gen) | No|  As we need to define the plan and roadmap for this next generation as it doesn't currently fulfill our requirements | Yes |
|5| WebGX | No | It needs further research | Yes|
|6| Hoops | No | It needs further research | Yes |
|7| New Three.js Viewer | No|  It needs further research | No |












