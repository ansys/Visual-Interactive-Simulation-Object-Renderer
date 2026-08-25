# VISOR - (Visual Interactive Simulation Object Renderer) Solutions Applications 3D Visualization Components Tenets

## Decision

VISOR (Visual Interactive Simulation Object Renderer, from here on "VISOR") is a framework providing Solutions Applications the necessary visualization components in order to be able to support the diversity of requirements for 3D visualization needs of Solution Applications while being able to follow the following tenets in terms terms non-functional requirements:
   * Seamless integration and architecture compatibility with SAF
   * Seamless integration with Ansys Dynamic Reporting
   * Ease of use and integratability delivered through PyAnsys initiatives (pyansys-visualization-tools)
   * Scalability in terms of supporting more complicated 3D models, multiple users
   * Deploymentability without sacrificing functionality, performance and maintainability requirements for desktop, on-prem and cloud architectures. The deployment processes should adhere to KPIs such as Deployment Frequency, Lead Time for Changes, Change Failure Rate, Deployment Duration, Automated Test Coverage, Resource Utilization, User Impact, Deployment Success Rate. In order to achieve the previous, containerizing and deploying the solution is part of our process and the KPIs towards that include Image Build Time, Image Size, Image PUll Time, Image Vulnerabilities, Image Layers, Image Age, Image Reuse, Image Compatibility, Resource Utilization, Compliance, Automated Test Coverage.
   * Performance in terms of web component KPIs as as well as service side KPIs.
   * Maintainability and alignment with best practises and development processes of CASEBU STCs. One of the processes followed is to have our documentation based on the relevant CASEBU ADRs in terms of architecture and developer documentation and examples of using this component.

## Context

VISOR is a new STC which is aiming to provide Solution Applications a set of 3D visualization components which can support all the different aspects of functional and non-functional requirements. As this is targeting solutions applications instead of a specific product and is created as part of the Enablement Platform AIEP development framework there are specific tenets that make sense to be agreed upon now that its being started so that they can remain and evolve along with the project.


## Options

1. ✔️ Framework that follows an architecture design which can scale in terms of adding different frameworks and providing customized components for the different integrations and functional and non-functional requirements as they are being created
1. ❌ New 3D Viewer Rendering Components
1. ❌ Specific 3D Viewer / 3D Viewer Framework (Trame, Ceetron Hoops, AVZ)

## Consequences

1. ✔️ It depends on technologies provided by other internal or external teams and provides all the integration interfaces, APIs and tools targeting CASEBU STCs and products which are included in Solution Applications. The rationale for choosing this option is that:
    - the functional requirements can be provided by existing and under development 3D visualization technologies
    - the non-functional requirements are not provided by any existing or under development 3D visualization technology
    - solutions applications have extremely diverse needs and a matrix of deployment options and there is a lot of effort that needs engineering expertise to make the integration robust, secure, scalable and easy to integrate by ACE groups.
    - even though it leads to adding complexity to the components as they need to provide flexibility for rendering choices and deployment options, its the unique value that this project can provide which external technologies cannot do, as they cannot work this closely with products and ACE groups.
    - it does lead to depending on different rendering technologies not necessarily owned by the same team or group and can be external companies, but its chosen due to time frame and resourcing constraints
1. ❌ New 3D Viewer Rendering Components
    - It's not recommended even though there is expertise in that area which we can utilize due to time-frame and resourcing constraints
    - It is also an issue of separating concerns and being able to put resources on providing components which ACE groups developing Solutions can integrate and be productive so that a continuous pain point is addressed
    - Even if the same group develops new rendering technologies to address problems that cannot be solved from other groups that doesn't mean they cannot be integrated with this framework when they are read and provide an easier path for migration to new graphics technologies for Solutions Applications rather than a straight on integration.
1. ❌ Specific 3D Viewer / 3D Viewer Framework (Trame, Ceetron Hoops, AVZ)
    - This is the fastest and less complicated route for first delivery but its not future proof
    - It leads to vendor-locking
    - None of the existing technologies can currently deliver the full list of functional and non-functional requirements so its inevitable that we are going to keep going forward and keep evolving our visualization tools to meet the growing needs of the Solutions group.

## Advice

Complete advice process recorded [here](https://github.com/ansys-internal/aap/discussions/43).