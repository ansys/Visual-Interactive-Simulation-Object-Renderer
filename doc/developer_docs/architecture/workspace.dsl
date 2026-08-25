workspace "Visor" "VISOR (Visual Interactive Simulation Object Renderer) 3D Visualization Web Components for Solutions Applications" {
	!identifiers hierarchical
	!impliedRelationships false

	model {
		properties {
			"structurizr.groupSeparator" "/"
		}
		end_user = person "End User" "A person who is using a Solution" ""
		group "Ansys Corporate Client" {

			visor = softwareSystem "Visor" "3D Viewer for Solutions Applications" "" {
				visor_dash = container "VISOR 3D Viewer Dash UI component" "VISOR 3D Viewer Dash wrapper with Python bindings for the VISOR web client library and client api" "Dash, Python, Typescript, React, VTK WASM JS viewer library" "" {
					visor_dash_ui = component "VISOR Viewer web client library" "React TypeScript library of the VISOR client UI" "React,Typescript,Javascript" "#React,#Typescript,#JS"
					visor_dash_api = component "VISOR Dash UI Component API" "Provides an API through the React interface available through the Dash component in order to allow for client side callbacks triggering specific functionality from the Dash application" "Dash,React,TypeScript" "#Dash,#JS,#Typescript,#React"
					visor_client_api = component "VISOR client UI API" "Implements an API which interfaces and implements actions on the web UI, trame vtk module library and/or the scene component." "React,TypeScript" "#React,#TypeScript"
					visor_js_library  = component "VISOR JS library" "VISOR JS library implementing the visor client" "JavaScript,TypeScript,React" "#JavaScript,#TypeScript,#React"
				}
				group "VISOR Client" {
					visor_client = container "VISOR JS client" "VISOR client implementing the viewer functionality on the frontend using Trame VTK.WASM module library." "Typescript,JavaScript,React,MJS,Trame,WASM,VTK.WASM" ""{
						visor_scene_component =  component "VISOR Viewer Scene Graph component" "VISOR 3D Viewer scene graph component for visualization of the model topology" "VTK, Typescript, React" "#Typescript,#React,#VTK"
						visor_ui_elements = component "VISOR UI Elements" "VISOR UI elements for the VISOR viewer" "React,Typescript" "#React,#Typescript"
						visor_trame_functionality_api  = component "VISOR Trame application sync and state manager" "VISOR API for interfacing with the VISOR defined Trame application on the server" "TypeScript,Trame,React" ""
					}
					trame_vtk_local_container = container "Trame VTK.WASM library" {
						trame_wslink_connection = component "Trame WSLINK connection and WASM loader" "Trame WSLINK connection to the server and WASM loader" "Python, WebSocket, wslink" "#Python,#WebSocket,#wslink"
						trame_wasm_handler = component "Trame Object Manager" "VTK Object manager for serializaton/deserialization of VTK C++ classes for VTK pipeline objects shared between the client and the Trame server" "VTK.WASM,JS,MJS" "#VTK,#WASM,#JS,#MJS"
					}
				}

				visor_server = container "VISOR server" "VISOR server supporting 3D rendering of models from Ansys flagship products" "" "" {
					trame_server = component "Trame Server" "Trame server component supporting single session using a web socket connection" "Python, WebSocket, wslink" "#Python,#WebSocket,#wslink"
					visor_http_api = component "VISOR Server Orchestration HTTP API" "Provides an HTTP API for controlling the lifecycle of the starting, stopping or updating the Trame server and the websocket connection." "OpenAPI,FastAPI" "#openapi,#fastapi"
					visor_server_component = component "VISOR Server Component" "VISOR server component creating a Trame server for a single session for this VISOR application" "Python, WebSocket, wslink" "#Python,#WebSocket,#wslink"
				}

				visor_app = container "VISOR Application Component" "VISOR Application controlling the choice of rendering engine, a VISOR Server instance and providing the Python API to the application" "Python" ""{
					visor_api = component "VISOR API" "VISOR API for controlling the lifecycle of the starting, stopping or updating the Trame server and the websocket connection." "OpenAPI, FastAPI" "#openapi,#fastapi"
					trame_application = component "Trame application" "Trame application based on Trame vtk_local application utilizing VTK.WASM and a VTK Object Manager for client-server synchronization" "technology" "tags"
					vtk_pipeline = component "VTK Pipeline and shared objects with the client side" "VTK pipeline setup for visualization on the server side which is synchronized with the VTK rendering on the client side" "VTK" "#VTK"
					scene_graph  = component "Scene graph" "Scene graph for supporting visualization of object hierarchies and scene attributes between the client and the server side" "Python, VTK" "#Python,#VTK"
					visor_logmonitor = component "VISOR Logger and Monitor of the application, servers and services" "VISOR logger and monitor is the part of the VISOR application which implements the OpenTelemetry standards for VISOR" "Python,OpenTelemetry" "#Python,#OpenTelemetry"
				}
				visor_server.visor_http_api -> visor_app.visor_api "Provides an HTTP API for controlling the lifecycle of the starting, stopping or updating the Trame server and the websocket connection." "" "#openapi"
				visor_app -> visor_server.visor_http_api "Provides an HTTP API for controlling the lifecycle of the starting, stopping or updating the Trame server and the websocket connection." "" "#openapi"

				visor_dash.visor_dash_ui -> visor.visor_dash.visor_js_library "Triggers functionality from the Dash client to the VISOR client" "" "#React,#Typescript,#JavaScript"
				visor_app.trame_application -> visor_app.vtk_pipeline "Sets up the VTK pipeline for the server side and synchronizes with the client side"
				visor_app.trame_application -> visor_app.scene_graph "Sets up the scene graph for the server side"
				visor.visor_app.visor_logmonitor -> visor.visor_app.trame_application "Monitors the application and server"
				visor.visor_app.visor_api -> visor.visor_app.trame_application "Manages the Trame application client and server side, along with the VTK pipeline, scene management and input management."
				visor_app.scene_graph -> visor_client.visor_scene_component "Updates view and sends events to UI elements"
				visor.visor_dash.visor_client_api -> visor.visor_client.visor_trame_functionality_api "Triggers functionality from the Dash client to the VISOR client library which is either a web UI functionality, or a Trame VTK.WASM functionality synchronized with the server and/or functionality on the scene component"
				visor.visor_dash.visor_dash_api -> visor.visor_client.visor_scene_component "Triggers visualization updates"
				visor.visor_dash.visor_dash_api -> visor.visor_client.visor_trame_functionality_api "Triggers functionality from the Dash client to the VISOR client library utilizing Trame VTK.WASM functionality on the client or server side."
				visor_server.visor_server_component -> visor_server.trame_server "Lifecycle management of the Trame server"
				visor_server.trame_server -> trame_vtk_local_container.trame_wasm_handler "Sends scene updates"
				visor.visor_client.visor_trame_functionality_api -> visor_server.trame_server "Trigger VTK updates"
				visor.trame_vtk_local_container.trame_wasm_handler -> visor_server.trame_server "Triggers VTK updates"
				visor.trame_vtk_local_container.trame_wslink_connection -> visor_server.trame_server "Connects to running wslink session to setup a websocket connection."
				visor_server.visor_http_api -> visor_server.visor_server_component "Controls server start, stop and state updates as well as monitoring tasks."


				end_user -> visor.visor_dash.visor_dash_ui "Triggers 3D model view updates" "" ""
				end_user -> visor.visor_dash.visor_dash_api "Triggers 3D model view updates" "" ""
				visor.visor_client -> end_user "Visualization of 3D model data" "" ""
				visor.visor_client -> end_user "Updates 3D model view" "" ""
				visor.visor_client -> visor.visor_server "Requests model data"
				visor.visor_server -> visor.visor_client "Sends model data"
			}

			portal = softwareSystem "SAF Portal" "enables the user to create new project or select existing project then launch solution UI for project.  Does not have responsibility for implementation of any aspect of the solution business logic or the services consumed by the solution." "" {
				portal_server = container  "Portal Server" "implements a REST API that is consumed by the Portal UI.  The portal server consumes a small subset of the API provided by the GLOW API Server" "FastAPI" "#fastapi"
				ui = container "Portal User Interface" "provides a view of the projects in the projects directory.  enables the user to create or select a project then launch solution UI for the project" "React"
			}

			product_instance_manager = softwareSystem "Product Instance Manager" "enables the startup and termination of Ansys Flagship Products or other stateful processes" "" {
				url https://tfs.ansys.com:8443/tfs/ANSYS_Development/Extensibility/_git/Root?path=%2Fansys%2Finstancemanagement%2Flight
			}

			product = softwareSystem "Ansys Flagship Product" "A stateful process that is required to implement a GLOW transaction method (typically an Ansys Flagship product which contains a simulation solver designed to be a desktop application)" "#external"

			glow = softwareSystem "Guided Low Code Workflow (GLOW)" "framework for vertical applications orientated towards a guided workflow user experience"  {
				url https://github.com/ansys-internal/glow-engine
				dash_ui = container "Solution Dash UI" "A browser based client for the Dash server implemented in React Javascript that renders the UI defined by the Dash server" "React"

				group "API" {

					projects_directory = container "Projects Directory" "the file system directory containing project files"
					api = container "API Server" "Provides a REST API specific to a given solution, which is consumed by the solution UI server."
					projects_database = container "Projects Database" "stores instances of the solution schema"

				}

				dash = container "Dash Server" "a Flask server that services a React browser based UI defined using the Dash UI definition API" "Flask" "#Flask" {
					dash_flask_server = component "Dash Flask Server" "a Flask server that services a React browser based UI defined using the Dash UI definition API" "Flask" {
						url https://dash.plotly.com/
					}
					solution_ui = component "Solution UI" "a python package which defines how the solution is rendered via the Dash UI definition API" "Python" ""
					client_api = component "Client API" "a python package that provides a pythonic interface to a GLOW API server via REST" "Python"{
						url https://github.com/ansys-internal/glow-engine/tree/main/src/ansys/saf/glow/client
					}
					solution_definition_api = component "GLOW Solution definition API" "a python package that contains the set of python types required to define a GLOW solution" "Python" {
						url https://github.com/ansys-internal/glow-engine/tree/main/src/ansys/saf/glow/solution
					}
					solution = component "Solution definition" "the definition of a solution's schema and business logic" "Python" ""

					solution_ui -> dash_flask_server "invoke rendering providing UI structure and callbacks" "" "#import"
					solution_ui -> client_api "gets and sets data; and invokes methods via proxy objects" "" "#function"
					client_api -> solution "obtains schema and method set" "" "#import"
					solution -> solution_definition_api "obtains base types for solution definition" "" "#import"
					client_api -> glow.api "calls" "REST" "#REST"
				}

				method_process = container "Method Execution Process" "An OS process that implements a single call to a transaction method" "Python" "" {
					method_runner = component "Method Runner" "implements a single call to a transaction method" "Python" {
						url https://github.com/ansys-internal/glow-engine/blob/main/src/ansys/saf/glow/_executor/method_runner.py#L41
					}
					solution_definition_api = component "Solution definition API" "a python package that contains the set of python types required to define a GLOW solution" "Python"{
						url https://github.com/ansys-internal/glow-engine/tree/main/src/ansys/saf/glow/solution
					}
					solution = component "Solution definition" "the definition of a solution's schema and business logic" "Python" ""
					method_runner -> solution "executes method" "" "#function"
					solution -> solution_definition_api "obtains base types for solution definition" "" "#import"
				}


				method_file_space = container "Method file space" "the temporary directory used by a method execution process that exists just for the duration of the process." "file sdystem directory"
				product_instance_file_space = container "Product Instance file space" "the OS directory associated with a product instance" "file system directory" "#file"

				api -> method_process "starts & stops" "" "#process"
				method_process -> product "executes method code" "gRPC" "#gRPC"
				method_process -> product_instance_manager "queries product connection, requests product start & termination" "gRPC" "#gRPC"
				method_process -> api "calls" "REST" "#REST"
				method_process -> method_file_space "creates & deletes" "" "#file"
				method_process -> product_instance_file_space "creates & deletes" "" "#file"

				api -> product_instance_manager "requests product termination (on shutdown)" "gRPC" "#gRPC"
				api -> projects_database "gets, modifies & creates records in" "" "#file"
				api -> projects_directory "reads and writes project files" "" "#file"

				product_instance_manager -> product "starts & kills" "" "#process"
				product_instance_manager -> visor.visor_server "Starts, stops viewer" "" "#process"
				visor.visor_server -> method_file_space "reads model data" "" "#file"
				visor.visor_server -> product_instance_file_space "reads model data" "" "#file"
				product -> method_file_space "writes 3D model" "" "#file"
				product -> product_instance_file_space "writes 3D model" "" "#file"

				dash_ui -> dash "obtains code and state; signals user interface events" "REST" "#REST"
				dash -> api "Call" "REST" "#REST"
				dash_ui -> visor.visor_dash.visor_dash_ui "Signals user interface events" "" ""
				dash_ui -> visor.visor_dash.visor_dash_api "Triggers visual events and requests data from the VISOR 3D viewer" "" ""
				visor.visor_dash.visor_dash_api -> dash_ui "Sends data to the Dash UI and status responses based on user interaction"

				portal -> api "Call" "REST" "#REST"

				method_process -> api "uploads and downloads fields" "REST" "#REST"
				method_process -> method_file_space "creates and deletes" "" "#file"
				method_process -> product_instance_file_space "creates and deletes" "" "#file"

				api -> method_process "starts" "" "#process"

				end_user -> dash_ui "uses" "" "#user"


				end_user -> portal "uses" "" "#user"
				portal -> glow "launches UI for existing or new project"
				glow -> product_instance_manager "requests start and termination of product instances" "gRPC" "#gRPC"
				product_instance_manager -> visor "launches VISOR visualization" "" ""
				glow -> visor "launches VISOR visualization" "" ""
				portal -> glow.dash_ui "links to" "JavaScript Click Handler" "#link"
				glow -> product "calls" "gRPC" "#gRPC"
				product_writes_state = product -> glow.projects_directory "reads & writes product state" "" "#file"
				end_user -> visor  "Views and interacts with the 3D model"
			}
		}

		end_user_windows_pc_ = deploymentEnvironment "End User Windows Desktop PC" {
			deploymentNode "Python Interpreter" "the python interpreter that runs the GLOW solution" "Python" "" 1 {
				deploymentNode "Orchestrator" "the python module that starts and shutsdown the GLOW solution" "Python" "" 1 {
					api_ = containerInstance glow.api "" {
					}
					dash_ = containerInstance glow.dash "" {
					}
					method_process_ = containerInstance glow.method_process "" {
					}
					portal_server_ = containerInstance portal.portal_server "" {
					}
					product_instance_manager_ = softwareSystemInstance product_instance_manager "" {
					}
				}
				deploymentNode "pywebview" "a python and browser based engine for rendering web UIs as desktop application windows" "Python" "" 1 {
					dash_ui_ = containerInstance glow.dash_ui "" {
					}
					portal_ui_ = containerInstance portal.ui "" {
					}
					visor_ui_ = containerInstance visor.visor_client "" ""
				}
			}
			deploymentNode "File System" "the file system of a single Windows Desktop PC" "Windows" 1 {
				deploymentNode "User Documents Directory" "the Documents directory of the end user" "Windows"  1 {
					projects_directory_ = containerInstance glow.projects_directory
					product_instance_file_space_ = containerInstance glow.product_instance_file_space
				}
				deploymentNode "APPDATA Directory" "the APPDATA directory of the end user" "Windows" 1 {
					projects_database_ = containerInstance glow.projects_database "
				}
			}
		}

	}

	views {
		theme https://raw.githubusercontent.com/RVR06/cornifer-contrib/main/themes/semantic/theme.json
		theme https://raw.githubusercontent.com/RVR06/cornifer-contrib/main/themes/heraldry/theme.json
		branding {
			logo https://raw.githubusercontent.com/RVR06/cornifer-contrib/main/assets/ansys.png
		}

		systemLandscape "SystemLandscape" "VISOR integrated in Solution Application using GLOW" {
			include *
			autolayout lr
		}

		systemContext visor "VisorSolutionApplicationContext" "VISOR Solution Application Context" {
			include *
			include glow
			include portal
			autolayout lr
		}

		container visor "VisorContainers" "VISOR Containers" {
			include end_user
			include visor.visor_client
			include visor.visor_server
		}

		systemContext visor "VisorSystemContext" "VISOR Context" {
			include *
			autolayout lr
		}


		component visor.visor_server "VisorServerComponents" "VISOR Server Components" {
			include *
			include visor.visor_server.visor_http_api
			include visor.visor_server.visor_server_component
			include visor.visor_server.trame_server
			autolayout lr
		}

		component visor.visor_dash "VisorDashComponents" "VISOR Dash UI Components" {
			include *
			include visor.visor_dash.visor_dash_ui
			include visor.visor_dash.visor_dash_api
			include visor.visor_dash.visor_client_api
			include visor.visor_dash.visor_js_library
			autolayout lr
		}

		component visor.visor_client "VisorClientComponents" "VISOR Client Component" {
			include *
			include visor.visor_client.visor_ui_elements
			include visor.visor_client.visor_scene_component
			include visor.visor_client.visor_trame_functionality_api
			include visor.trame_vtk_local_container.trame_wasm_handler
			include visor.trame_vtk_local_container.trame_wslink_connection
			autolayout lr
		}

		component visor.visor_app "VisorAppComponents" "VISOR Application Components" {
			include *
			include visor.visor_app.visor_api
			include visor.visor_app.trame_application
			include visor.visor_app.vtk_pipeline
			include visor.visor_app.scene_graph
			include visor.visor_app.visor_logmonitor
			autolayout lr
		}

		deployment * end_user_windows_pc_ "EndUserDeployment" "End User Deployment" {
			include *
			autolayout lr
		}
	}