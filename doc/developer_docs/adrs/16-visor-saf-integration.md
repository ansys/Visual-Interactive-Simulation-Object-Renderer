## VISOR SAF Integration

## Decision
Team approved

## Context

VISOR is aiming to be the Solutions' Applications 3D viewer and as such the primary platform that VISOR is going to be used is through Solutions Applications Framework (SAF). The tenets of the VISOR project can be found [here](https://github.com/ansys/visor/blob/3fdbf4413c63d1c7c2b2ef62792a638f8d6f2b85/doc/developer_docs/adrs/01-visor-tenets.md). Solutions Applications are required to be able to target desktop, on-premise deployment and cloud deployment through integration with SAF, REP and CISL/Cloud Burst platforms. VISOR as a Solutions Applications viewer is scoped to be aiming to the requirements of the Solutions Applications and ACE stakeholders rather than being a standalone application and as such it needs to comply with the requirements the Solutions Applications group, the Architecture Hub and the ACE stakeholders are providing. VISOR is not responsible for Authentication or Authorization of users, or directly deployments or running a service but its responsible for making sure that all the requirements set will be able to be implemented in VISOR through its architecture.

VISOR is targeting desktop, on-prem and cloud deployments. In terms of MVP, VISOR is targeting desktop deployment and it will iteratively target on-prem and cloud deployments as a component of the Solutions Applications Framework and not as a standalone service.

VISOR REST service is necessary for Solutions Applications to be able to connect to a running instance of VISOR from independent steps where VISOR is not a subsystem of GLOW. The VISOR service is managed by the SAF Product Instance Manager for its lifecycle and the Product Instance Configuration is expected to be able to be deployed along with SAF on the different deployment targets of the Solutions Applications Framework.

### Desktop

#### Requirements

SAF is requiring that a server running for a session to be running using a [PIM (Product Instance Manager) configuration](https://saf.glow.docs.solutions.ansys.com/version/dev/user_guide/using_ansys_products/product_instance_management/index.html). The PIM configuration requires the following:
* An HTTP service with the following endpoints:
```\```: GET root
```\initialize```: POST initialization
```\start```: POST start
```\stop```: POST stop
```\health```: GET health endpoint

* There is session management for the service
* PIM implementation of VISOR exposes the rest of the VISOR APIs through a VisorClient
* Stopping the service and it should clean up and remove any temporary directories that were created for the service to be running.
* A VISOR manager is included in [SAF Product Manager](https://github.com/ansys-internal/saf-product-manager/blob/main/src/ansys/saf/product_manager/theia/_theia_manager.py)
* A ``SAFVisorClient`` exposes APIs beyond the interface of the generic SAF Product Manager. As of 1.x version of VISOR it supports ``update`` functionality.
* SAF supported releases of VISOR are included in the SAF Product Configuration package: [saf-product-configuration](https://github.com/ansys-internal/saf-product-configuration/blob/main/src/ansys/saf/product_configuration/theia.py)
* There is an end-to-end test in [SAF Product Manager](https://github.com/ansys-internal/saf-product-manager/blob/main/tests/e2e/test_theia.py) which also tests the ``visordash`` API with the VISOR server configuration for Desktop.

(*) Note: There is a bug in terms of the PIM Desktop configuration which doesn't allow VM rendering due to using localhost and local ports without API gateway. Issue tracking for these: [glow-engine#622](https://github.com/ansys-internal/glow-engine/issues/622), [saf-product-manager#34](https://github.com/ansys-internal/saf-product-manager/issues/34)


### Deployment on-premise and cloud

VISOR is going to be using HPS for orchestrating on-premise and cloud deployment. VISOR is currently using Trame, which is a client-server architecture for a single session which sets up a web-socket connection based on the public session url of the web socket connection.

In order for VISOR to support multiple users or sessions it needs to be containerized and deployed through the HPS which will be creating new instances to scale VISOR based on the users or sessions which are necessary for smoothly running the on-premise deployment.

#### VISOR client-side rendering
Based on the current technology components of VISOR described [here](https://github.com/ansys/visor/blob/3fdbf4413c63d1c7c2b2ef62792a638f8d6f2b85/doc/developer_docs/adrs/02-visor-technology-components.md) it is using Trame VTK.WASM which is a client based rendering technology on the browser using VTK, Web assembly and OpenGL2.x and when its available WebGPU. This means that performance of VISOR is going to be impacted by network connectivity even though there is a websocket connecting directly to the client, it will still have the relative impact as there are models and data transferred to to the client.

*Additional requirements:*
* Kubernetes-based containerized version of VISOR
* VISOR running in the same cluster where data for rendering are stored and processed (avoid waiting for loading big data files to a different machine and duplicating those data)
* There is an API Gateway which provides the route to the Trame server instance with a url which is able to be served to the ``visordash`` client running on the browser of the user. Issue tracked here: [glow engine #34](https://github.com/ansys-internal/saf-product-manager/issues/34)


#### VISOR server-side rendering

VISOR will support server-side rendering with the same architecture and the only difference in terms of deployment is the requirement for running ParaView on the server. The ``visordash`` component will be using the same websocket connection client so it will require the publicly available websocket url for the Trame server (visualization server).

*Additional requirements:*
* Kubernetes-based containerized version of VISOR
* VISOR running in the same cluster where data for rendering are stored and processed (avoid waiting for loading big data files to a different machine and duplicating those data)
* There is an API Gateway which provides the route to the Trame server instance with a url which is able to be served to the ``visordash`` client running on the browser of the user. Issue tracked here: [glow engine #34](https://github.com/ansys-internal/saf-product-manager/issues/34)
* ParaView included in the containerized version of VISOR
* GPU is heavily recommended (as the assumption is that large/complex models are passing through the VTK pipeline)


### Notes

* For the first internal release the stop endpoint is not following OpenTelemetry requirements, it will only report if the VISOR server is healthy. At this point this covers the Trame server but not wslink running or the websocket connection health.

* A revision of the error codes and the health endpoint to cover OpenTelemetry requirements will be done at a later stage ahead of a full delivery of VISOR.

*29th of July 2025:*
As of now, an STC is not able to have a Product Instance Manager and Configuration included in GLOW. Only flagships have their configuration supported by the GLOW team. However, the [Product Instance Configuration repo](https://github.com/ansys-internal/saf-product-configuration) is the only that gets deployed along with SAF and has the testing support for PIM. The same goes for the [Product Instance Manager repo](https://github.com/ansys-internal/glow-engine/tree/main/src/ansys/saf/glow/solution/geometry). This repo contains testing which ensures that changes of the PIM configuration do not break the Product Instance Manager.


*23rd of December 2025:*
- The first release of VISOR is available and PIM light packages have the mechanisms to support VISOR for Desktop deployment (not containerized and without routing capabilities for external VPC connections)
- On-Premise and Cloud deployments are not yet implemented. The proposal is to use HPS as the orchestrator for VISOR since VISOR is using Trame server which implements a stateful, session based VTK rendering pipeline.
- VISOR is not currently providing a kubernetes based container. It only provides a Docker containerized version.