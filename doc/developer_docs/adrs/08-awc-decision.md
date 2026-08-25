# ADR 08: AWC adoption

## Status

Team agreement

## Context

In the initial implementation of VISOR, the Ansys Web Components (AWCs) were used to create the front end features. This has been done with the following goals in mind:
- make the look and feel of VISOR common with the rest of Ansys products. This is especially important considering that VISOR is a Shared Technology Component, to be embedded inside other Ansys frameworks;
- reduce technical debt moving forward. Once the AWCs are used in VISOR, changes in the Ansys guidelines for the UI / UX would result in a simple component update, without having to have the team re-write all the UI elements;
- Outsource the UI work to another team. As the VISOR team is small, we'd like to outsource as many components as possible.

The team therefore started the project using AWCs for the front end.

## Issues with AWCs adoption

We list a number of issues the team has encountered when using the AWCs.

- Lack of support for new Dash versions<br>
AWCs currently fully support previous version of Dash (2.6 released in August 2022), and VISOR requires newer versions of Dash (>2.16, but preferably 3.0.1) due to the usage of JacaSacript Modules in the Trame Client, which is used in the VISOR client. This is a crucial technology choice which requires WebAssembly files and JS Modules (mjs) files. This means that the VISOR integration inside of SAF can not be done with UI elements if they are developed using AWCs.

- Non React-native: size and performance<br>
AWCs are available both in Angular and React. Upon further investigation, though, it appears that the React components are not native, but are obtained via a translation of the native Angular components. This creates performance and memory issues. The React AWCs tend to be very big in size and when VISOR needs to bundle all of its components and wrap them for its own bundle but even further the custom Dash component, the end result is excessively big in size and creates complications for the bundling of the VISOR client React component. The VISOR client already has to bundle in Dash the WebAssembly and JS Module files and adding excessive additional load to our bundle is creating issues that are ending up in loading times. At this point in time we have not bundled the AWCs in our dash component due to the fact that we would need to invest time to optimize and drive down the size of our bundle for it to be in acceptable sizes.

- Lack or personalization and optimization options<br>
AWCs appear to be designed to be used 'as is' in a Solution Application. But this is not VISOR's user case. VISOR currently is only focusing on MVP functionalities but going forward there are more UI elements that are going to be needing further customization, such as elements related to time variant domains and animation capabilities, which aren't commonly required in other tools. The customization levels are going to be even more prevalent as the project expands and the UI elements we are going to be loading on screen are going to be needing high optimization so that they don't take up the memory budget we require for loading meshes. Without the alignment of high performance React native elements it will not be possible for VISOR long term to be able to use them. In the memory budget we have on the browser we are required to optimize for providing as much as possible of that budget to the graphics engine and the browser to load complicated and the biggest meshes possible so we are bound to drive down the cost of UI elements as much as possible in the long term. The more elements we use this is going to become an even bigger issue and since this is a very specialized visualization application the consistency is actually compared to other Ansys applications which also have their own specialized elements.

- Low prioritization of missing features and bugs<br>
Some pretty basic features for VISOR's use case seem to be missing from AWC components. As the AWC team focuses mainly on the Angular version, little prioritization is given to our requests. For example, see the issues raised:<br>https://github.com/ansys-internal/ansys-web-components/issues/2156<br>The bugs associated with the issue have been filed 3 weeks after the initial report and given low or medium priority. The lack of responsiveness creates a dependency that is hard to accept and justify. These discussionss with the AWC team show that the requirements that VISOR provides are not necessarily aligned with the scope of AWCs. We require AWC which are fully customizable by other teams and able to be integrated in React applications, not necessarily used 'as is' in a Solution Application.

- Rejection of features<br>
Some features we've requested to the AWC team have been rejected, even through we feel they're basic requests that VISOR can not stay without. For example, see item 1. in this discussion:<br>https://github.com/ansys-internal/ansys-web-components/issues/2156<br>The request to have a tree (for the part list) that adapts in size with the length of the part names is rejected. We therefore are left with a very large UI component that occupies almost 1/2 of the rendering window even if the text of the part list is small. Similarly, a request to control the padding of the strings is rejected, leaving us with UI components way too large.

## Decision

Given the issues listed in this ADR, the team has decided to abandon the AWCs for VISOR's front end and will be looking at having its own specialized elements. We remain open to discussion in the future if the project's requirement were to re-align with AWCs target. We also remain open to the possibility of alternative ways to achieve consistency with other Ansys products such as Theme libraries and shared CSS resources, as well as guidelines which allow for common look and feel even through the elements are implemented using different technologies.

