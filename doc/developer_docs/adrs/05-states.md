# ADR 05: Definition of States and User Cases

## Status
Verified and Accepted by PM and ACE stakeholders

## Context
The VISOR project shall allow for saving and restoring of states, in order to provide a smooth experience to the end user. The scope of this ADR is to define what a state is, what information it should contain, and how the restore operation should work in different deployments.

## User case scenarios
There are three scenarios in which save and restore states will be implemented.
1. VISOR is implemented as part of a larger application. The user exits the session. When they re-enter the application, VISOR will restore the state. This will work for all deployment types (desktop, on prem and cloud).
2. The application sends to VISOR a new model to dynamically upload (streaming scenario).
3. VISOR is deployed in an on-prem or cloud application, with multiple users having access to the same project. In this scenario, VISOR should always restore the latest state for each session, regardless of which user was the last one to run VISOR.

The consequence of the three user case scenarios outlined above is that the VISOR state files will be saved per session, and no information about which user saved the state file needs to be stored / used in the restore operation.

**Note:** In scenario 3., there will be users with different permissions on the session - edit / read-only. In the context of the VISOR project, this is irrelevant as VISOR does not allow for modification of the model / simulation workflow itself, but only visualization. Therefore, any user who is allows to launch VISOR and load the model should be allowed to save and restore states.

## State definition
The following information needs to be stored in a state:
1. Camera settings (look at point, look from point, rotation, zooming factor)
2. Part visibility
3. Cross section settings (on/off. Orientation and position of the cross section plane)
4. Mesh visualization (on/off)
5. Parts color by variable (on a per-part basis)
6. Legend visualization settings (hide / show, position of the legend)
7. Legend min / max
8. Legend palette
No information about the current status of the UI should be stored

## State restore
Here we describe the expectation when restoring a state.
All the settings defined in a state should restore automatically. The UI will reset to the default UI status when you load a model for the first time.
In user case scenario 2, there is the possibility that the new model contains a different topology (part list) or a different list of variables. Here the expected behavior:
1. Missing parts: the new model has missing parts compared to the one stored in the state. Drop the information on the extra parts. This is not needed and should not be used in any way. Do not store it moving forward.
2. Extra parts: the new model has new parts compared to the one stored in the state. Visualize them with the default settings: visible and colored by a constant.

**Note:** part matching is done based on the part name

3. Missing variables: the new model has missing variables compared to the ones stored in the state. Drop the information on the extra variables. This is not needed and should not be used in any way. Do not store it moving forward.
4. Extra variables: the new models has new variables compared to the ones stored in the state. They will appear in the list of available variables to color a part by (when appropriate), but their settings should be the default ones.


