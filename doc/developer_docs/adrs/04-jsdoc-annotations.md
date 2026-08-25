# ADR 04: JSDoc Annotations

## Status
Proposed

## Context
The VISOR web visualization project, in support of VTK.wasm, makes use of JavaScript to establish WebSocket connections and thereby communicate with its server-side component. By nature, JavaScript is dynamically typed, which  means IDE code hinting features (e.g. Intellisense in VSCode) will often be unable to determine if written JavaScript is valid. This means that developers working in the VISOR project who rely on this feature for Python and TypeScript will be unable to do so when writing JavaScript. VISOR does have a React frontend which makes use of TypeScript (a statically typed language), although the decision to maintain "vanilla" JavaScript for the viewer WebSocket communications allows for quicker field testing and debugging, as it allows developers to skip a compilation step.

## Decision
Ensure a reasonable amount of JSDoc annotations exist alongside JavaScript functions, classes, and other items to enable code hinting features in IDEs for developers adding to or modifying VISOR JavaScript. The JSDoc type definition names (i.e. "typedef" names) will be of the form "Visor_[type name]". For example: Visor_Vector3, Visor_WebSocketConnection, Visor_StateManager, etc.

#### JSDoc on JavaScript Functions

There are a multitude of ways JavaScript functions in VISOR may be annotated with JSDoc. Because functions in JavaScript can be standard declarations or expressions, corresponding JSDoc comments alongside functions may vary:

```javascript
// example 1

/**@type{function(arr:any[]):number}*/
const getArrayLength = arr => {
  return arr.length;
};
////////////////////////////////////////////////////////
// example 2

/**@type{(arr:any[])=>number}*/
const getArrayLength = arr => {
  return arr.length;
};
////////////////////////////////////////////////////////
// example 3

/**
 * @param {any[]} arr
 * @return number
 */
function getArrayLength(arr) {
  return arr.length;
}
```

#### JSDoc on JavaScript Objects

Like JavaScript functions, there are several ways JavaScript objects in VISOR may be annotated with JSDoc. Unlike with functions however, JSDoc comments on objects may be slightly less straightforward:

```javascript
// example 1

/**
 * @typedef {Object} Visor_Vector3
 * @property {number} x - The x component.
 * @property {number} y - The y component.
 * @property {number} z - The z component.
 */

/**@type{Visor_Vector3}*/
let myVariable = null;
////////////////////////////////////////////////////////
// example 2

/**
 * @typedef {{x:number,y:number,z:number}} Visor_Vector3
 */

/**@type{Visor_Vector3}*/
let myVariable = null;
////////////////////////////////////////////////////////
// example 3 - note the use of the "@lends" tag

/**
 * @typedef {Object} Visor_Vector3
 */

let myVariable =/**@lends VISOR_Vector3#*/{
    /**@type{number}*/
    x: 0,
    /**@type{number}*/
    y: 1,
    /**@type{number}*/
    z: 0
};
```