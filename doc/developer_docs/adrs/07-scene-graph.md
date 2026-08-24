# ADR 07: Scene Graph

## Status

Proposed

## Context

The VISOR viewer must be aware of and preserve any object hierarchies that exist in files that are loaded. This is because the viewer must have the ability to perform actions on a single object, a custom-selected group of objects, or all descendants in a specific object's hierarchy. Examples of such actions include show, hide, select, and deselect.

In VTK parlance, a file can represent a `vtkDataSet` or `vtkCompositeDataSet`. A `vtkDataSet` is a single polygon mesh or unstructured grid, whereas a `vtkCompositeDataSet` is a _hierarchy_ of polygon meshes or unstructured grids.

Common subclasses of `vtkDataSet` are the `vtkPolyData` and `vtkUnstructuredGrid` types. The file extensions that typically contain these types are the following:

- **.vtp** - `vtkPolyData`
- **.vtu** - `vtkUnstructuredGrid`

Common subclasses of `vtkCompositeDataSet` are the `vtkMultiBlockDataSet` and `vtkMultiPieceDataSet` types. The file extensions that typically contain these types are the following (as you can see, the .vtm extension is used for both composite dataset types):

- **.vtm** - `vtkMultiBlockDataSet` and `vtkMultiPieceDataSet`

Because of these peculiarities among VTK datasets, VISOR requires a scene graph for management of the object hierarchies that may be present in the datasets. A scene graph is a hierarchical data structure commonly used in computer graphics and visualization to organize and manage the various objects that make up a graphical scene. It represents the spatial arrangement and relationships between objects, as well as their properties, transformations, and interactions. The scene graph allows for efficient rendering, interaction, and manipulation of complex scenes in 3D environments.

As mentioned earlier, the VTK object types that contain hierarchies are the `vtkMultiBlockDataSet` and `vtkMultiPieceDataSet` types, which are subclasses of `vtkCompositeDataSet`.

Although technically the `vtkPolyData` and `vtkUnstructuredGrid` types do not contain hierarchies, VISOR still treats them as being hierarchical objects, only with no children. This concept of "everything is a hierarchy" is beneficial to development, as it allows developers to normalize all scene graph methods and routines, without having to excessively make exceptions for "non-hierarchical" objects in code.

At a high level, the following is an example of a scene graph in VISOR after loading a file named _many_blocks.vtm_:

```text
● root (root)
└── ● many_blocks.vtm (vtkMultiBlockDataSet)
    ├── ● Group A (vtkMultiBlockDataSet)
    │   ├── ● untitled (vtkPolyData)
    │   ├── ● untitled (vtkPolyData)
    └── ● Group B (vtkMultiPieceDataSet)
        ├── ● untitled (vtkPolyData)
        ├── ● untitled (vtkPolyData)
        ├── ● untitled (vtkUnstructuredGrid)
        ├── ● untitled (vtkUnstructuredGrid)
        └── ● untitled (vtkUnstructuredGrid)
```

As you can see, the _many_blocks.vtm_ node is a child of the _root_ node. The _root_ node is always the top-level node, and not the file node. This design decision gives us the opportunity to load multiple files into the scene, if future requirements were to demand so.

Each node in the scene graph represents a single dataset. The dataset the node represents, however, can be "composite" or "non-composite". Composite datasets are `vtkMultiBlockDataSet` and `vtkMultiPieceDataSet`. Non-composite datasets are `vtkPolyData` and `vtkUnstructuredGrid`.

A composite node is just a group of other nodes, and cannot be rendered in VTK _by itself_. A composite node must contain non-composite children in order to be "rendered".

## Implementation

The simplest way of building a scene graph from a VTK file is to design a `SceneGraphNode` class whereby its constructor takes a VTK dataset and loops through each one of its immediate child datasets. A new `SceneGraphNode` object is created for each of these child datasets by passing the child dataset to the child node. The child node's constructor then loops through each of its own child datasets and creates nodes for them as well, and for the grandchildren, and so on, until the hierarchy is completely "walked".

As mentioned earlier, the dataset that is provided to a node's constructor will either be a composite `vtkCompositeDataSet` or non-composite `vtkDataSet`. Therefore, the node's constructor must have the ability to determine the type of dataset it was provided, so that it can set its respective class properties accordingly. These properties include `.NodeType` and `.Actor`, which are different depending on what kind of dataset the node represents. For example, a `vtkPolyData` node will have "vtkPolyData" as the `.NodeType`, and a non-null `.Actor`. Alternatively, a `vtkMultiBlockDataSet` will have "vtkMultiBlockDataSet" as the `.NodeType`, but have a null `.Actor`.

The following is rudimentary example of a `SceneGraphNode` class, with eager loading of each `vtkActor`:

```python
from vtkmodules.vtkCommonDataModel import (
    vtkMultiBlockDataSet,
    vtkMultiPieceDataSet,
    vtkUnstructuredGrid,
    vtkPolyData,
)
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkCommonExecutionModel import vtkPolyDataAlgorithm
import os
import re
from vtkmodules.vtkIOXML import (
    vtkXMLMultiBlockDataReader,
    vtkXMLUnstructuredGridReader,
    vtkXMLPolyDataReader,
)
from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataSet


class SceneGraphNode:
    def __init__(self, dataset: vtkDataSet | vtkCompositeDataSet):
        node_type: str
        actor: vtkActor | None = None
        children: list[SceneGraphNode] = []
        if isinstance(dataset, vtkMultiBlockDataSet):
            node_type = "vtkMultiBlockDataSet"
            for i in range(dataset.GetNumberOfBlocks()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
        elif isinstance(dataset, vtkMultiPieceDataSet):
            node_type = "vtkMultiPieceDataSet"
            for i in range(dataset.GetNumberOfPieces()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
        elif isinstance(dataset, vtkUnstructuredGrid):
            node_type = "vtkUnstructuredGrid"
            algorithm: vtkPolyDataAlgorithm = vtkGeometryFilter()
            algorithm.SetInputData(dataset)
            algorithm.Update(None)
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(algorithm.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
        elif isinstance(dataset, vtkPolyData):
            node_type = "vtkPolyData"
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(dataset)
            actor = vtkActor()
            actor.SetMapper(mapper)
        else:
            raise RuntimeError(f"dataset type not yet supported: {type(dataset)}")
        self.__NodeType: str = node_type
        self.__Actor: vtkActor | None = actor
        self.__Children: list[SceneGraphNode] = children

    @property
    def NodeType(self):
        return self.__NodeType

    @property
    def Actor(self):
        return self.__Actor

    @property
    def Children(self):
        return self.__Children


def file_to_dataset(file_path: str) -> vtkDataSet | vtkCompositeDataSet:
    """"""
    # make file_path lowercase so extension testing is case-insensitive
    filename: str = os.path.basename(file_path).lower()
    extension: str = os.path.splitext(filename)[1][1:]
    dataset: vtkDataSet | vtkCompositeDataSet
    if extension == "vtu":
        """"""
        reader: vtkXMLUnstructuredGridReader = vtkXMLUnstructuredGridReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtp":
        """"""
        reader: vtkXMLPolyDataReader = vtkXMLPolyDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtm":
        """"""
        reader: vtkXMLMultiBlockDataReader = vtkXMLMultiBlockDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    else:
        """"""
        raise RuntimeError(f"Unsupported file: {file_path}")
    return dataset


def main():
    dataset = file_to_dataset("c:/path/to/file.vtm")
    root_node = SceneGraphNode(dataset)
```

There are interesting things to note with this example. First of all, notice that if the node represents a `vtkUnstructuredGrid` or `vtkPolyData`, its `.Children` property will be empty. Secondly, notice that if the node represents a `vtkMultiBlockDataSet` or `vtkMultiPieceDataSet`, its `.Actor` property will be `None`. This follows the design principle mentioned earlier whereby composite datasets cannot be rendered on their own (because they have no actor), in addition to non-composite objects still being treated as hierarchical, just with 0 children.

It is worth mentioning that there are limitations in this rudimentary `SceneGraphNode` example. For example, there is no way to update each node's pipeline at runtime from outside the class (i.e., you cannot add extra algorithms to the VTK pipeline before the initial dataset is handed over to a `vtkMapper`). Secondly, there is no convenient way to access all of a node's descendants (i.e. there is only a `.Children` array, which is just a node's immediate children, and does not include grandchildren, great-grandchildren, and so on). These limitations and solutions are discussed in the next two sections.

## Runtime VTK Algorithm Pipeline Modding

In order to improve the scalability of the `SceneGraphNode` class, each node's pipeline should be changeable from outside the class. In the rudimentary `SceneGraphNode` code example shown earlier, each node's base dataset is directly converted to a `vtkActor`. In other words, there is no ability to inject "middleware" to the pipeline before the dataset is sent to the `vtkActor`.

We can change this by introducing the ability to provide a function parameter to each node, whereby the function is given a `vtkAlgorithm`, and returns a `vtkAlgorithm`. The updated code for this is as follows (see the method `.UpdateDescendantOrSelfActors()`):

```python
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from typing import Callable
from vtkmodules.vtkCommonDataModel import (
    vtkMultiBlockDataSet,
    vtkMultiPieceDataSet,
    vtkUnstructuredGrid,
    vtkPolyData,
)
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkCommonExecutionModel import vtkPolyDataAlgorithm
import os
import re
from vtkmodules.vtkIOXML import (
    vtkXMLMultiBlockDataReader,
    vtkXMLUnstructuredGridReader,
    vtkXMLPolyDataReader,
)
from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataSet
from vtkmodules.vtkFiltersModeling import vtkLoopSubdivisionFilter


class SceneGraphNode:
    def __init__(self, dataset: vtkDataSet | vtkCompositeDataSet):
        node_type: str
        base_algorithm: vtkPolyDataAlgorithm | None = None
        actor: vtkActor | None = None
        children: list[SceneGraphNode] = []
        if isinstance(dataset, vtkMultiBlockDataSet):
            node_type = "vtkMultiBlockDataSet"
            for i in range(dataset.GetNumberOfBlocks()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
        elif isinstance(dataset, vtkMultiPieceDataSet):
            node_type = "vtkMultiPieceDataSet"
            for i in range(dataset.GetNumberOfPieces()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
        elif isinstance(dataset, vtkUnstructuredGrid):
            node_type = "vtkUnstructuredGrid"
            base_algorithm = vtkGeometryFilter()
            base_algorithm.SetInputData(dataset)
            base_algorithm.Update(None)
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(base_algorithm.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
        elif isinstance(dataset, vtkPolyData):
            node_type = "vtkPolyData"
            base_algorithm = vtkAppendPolyData()
            base_algorithm.SetInputData(dataset)
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(dataset)
            actor = vtkActor()
            actor.SetMapper(mapper)
        else:
            raise RuntimeError(f"dataset type not yet supported: {type(dataset)}")
        self.__NodeType: str = node_type
        self.__BaseAlgorithm: vtkPolyDataAlgorithm | None = base_algorithm
        self.__Actor: vtkActor | None = actor
        self.__Children: list[SceneGraphNode] = children

    @property
    def NodeType(self):
        return self.__NodeType

    @property
    def Actor(self):
        return self.__Actor

    @property
    def Children(self):
        return self.__Children

    def UpdateDescendantOrSelfActors(
        self, algorithm_filter: Callable[[vtkPolyDataAlgorithm], vtkPolyDataAlgorithm]
    ):
        if self.__BaseAlgorithm is None:
            # if base algorithm is not present, then this is a composite node
            # therefore loop through all the children with the algorithm filter
            for node in self.__Children:
                node.UpdateDescendantOrSelfActors(algorithm_filter)
        else:
            # if base algorithm is present, then this is an actual mesh node
            # therefore update the mapper with the new algorithm (and thus
            # the actor)
            mapper = self.__Actor.GetMapper()
            if isinstance(mapper, vtkPolyDataMapper):
                algorithm = algorithm_filter(self.__BaseAlgorithm)
                mapper.SetInputConnection(algorithm.GetOutputPort())
            else:
                raise RuntimeError(
                    f"mapper is not vtkPolyDataMapper. actual type: {type(mapper)}"
                )


def file_to_dataset(file_path: str) -> vtkDataSet | vtkCompositeDataSet:
    """"""
    # make file_path lowercase so extension testing is case-insensitive
    filename: str = os.path.basename(file_path).lower()
    extension: str = os.path.splitext(filename)[1][1:]
    dataset: vtkDataSet | vtkCompositeDataSet
    if extension == "vtu":
        """"""
        reader: vtkXMLUnstructuredGridReader = vtkXMLUnstructuredGridReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtp":
        """"""
        reader: vtkXMLPolyDataReader = vtkXMLPolyDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtm":
        """"""
        reader: vtkXMLMultiBlockDataReader = vtkXMLMultiBlockDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    else:
        """"""
        raise RuntimeError(f"Unsupported file: {file_path}")
    return dataset


def main():
    dataset = file_to_dataset("c:/path/to/file.vtm")
    root_node = SceneGraphNode(dataset)

    def algorithm_filter(algorithm: vtkPolyDataAlgorithm):
        subdivide: vtkPolyDataAlgorithm = vtkLoopSubdivisionFilter()
        subdivide.SetInputConnection(algorithm.GetOutputPort())
        return subdivide

    root_node.UpdateDescendantOrSelfActors(algorithm_filter)
```

Notice the addition of `base_algorithm = vtkAppendPolyData()` to the `vtkPolyData` match case in the node constructor. This algorithm serves as a "pass-through" filter to allow us to use our `vtkPolyData` object as an algorithm.

Lastly, notice the `algorithm_filter` function passed to the `.UpdateDescendantOrSelfActors()` method. This function argument will be applied to every descendant node under the root node (since we called the method on the root node).

## Iterate All Node Descendants (not just immediate children)

At this point, iterating through the immediate children of a node is straightforward:

```python
scene_root = SceneGraphNode(dataset)
for node in scene_root.Children:
    print(f"node type: {node.NodeType}")
```

However, iterating through ALL descendants of a node requires a function definition to be called recursively:

```python
def recursive_func(node: SceneGraphNode):
    print(f"node type: {node.NodeType}")
    for node in node.Children:
        recursive_func(node)


scene_root = SceneGraphNode(dataset)
recursive_func(scene_root)
```

Alternatively, we could attach a special array and dictionary to each node to make each node's descendants much easier to iterate. See the following code for this functionality:

```python
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from typing import Callable
from vtkmodules.vtkCommonDataModel import (
    vtkMultiBlockDataSet,
    vtkMultiPieceDataSet,
    vtkUnstructuredGrid,
    vtkPolyData,
)
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkCommonExecutionModel import vtkPolyDataAlgorithm
import os
import re
from vtkmodules.vtkIOXML import (
    vtkXMLMultiBlockDataReader,
    vtkXMLUnstructuredGridReader,
    vtkXMLPolyDataReader,
)
from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataSet
from vtkmodules.vtkFiltersModeling import vtkLoopSubdivisionFilter
import random


class SceneGraphNode:
    def __init__(self, dataset: vtkDataSet | vtkCompositeDataSet):
        node_type: str
        base_algorithm: vtkPolyDataAlgorithm | None = None
        actor: vtkActor | None = None
        children: list[SceneGraphNode] = []
        # in case this node gets serialized to JSON and used in JavaScript,
        # limit the maximum value to 9007199254740991, since this is
        # JavaScript's maximum safe integer
        javascript_safe_id: int = random.randint(1000000000000000, 9007199254740991)
        descendantNodesOrSelfDictionary: dict[int, SceneGraphNode] = {
            javascript_safe_id: self
        }
        descendantNodesOrSelfArray: list[SceneGraphNode] = [self]
        self.__DescendantNodesOrSelfDictionary: dict[
            int, SceneGraphNode
        ] = descendantNodesOrSelfDictionary
        self.__DescendantNodesOrSelfArray: list[
            SceneGraphNode
        ] = descendantNodesOrSelfArray
        if isinstance(dataset, vtkMultiBlockDataSet):
            node_type = "vtkMultiBlockDataSet"
            for i in range(dataset.GetNumberOfBlocks()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
                descendantNodesOrSelfDictionary.update(
                    item.DescendantNodesOrSelfDictionary
                )
                descendantNodesOrSelfArray.extend(item.DescendantNodesOrSelfArray)
        elif isinstance(dataset, vtkMultiPieceDataSet):
            node_type = "vtkMultiPieceDataSet"
            for i in range(dataset.GetNumberOfPieces()):
                child = dataset.GetBlock(i)
                item = SceneGraphNode(child)
                children.append(item)
                descendantNodesOrSelfDictionary.update(
                    item.DescendantNodesOrSelfDictionary
                )
                descendantNodesOrSelfArray.extend(item.DescendantNodesOrSelfArray)
        elif isinstance(dataset, vtkUnstructuredGrid):
            node_type = "vtkUnstructuredGrid"
            base_algorithm = vtkGeometryFilter()
            base_algorithm.SetInputData(dataset)
            base_algorithm.Update(None)
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(base_algorithm.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
        elif isinstance(dataset, vtkPolyData):
            node_type = "vtkPolyData"
            base_algorithm = vtkAppendPolyData()
            base_algorithm.SetInputData(dataset)
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(dataset)
            actor = vtkActor()
            actor.SetMapper(mapper)
        else:
            raise RuntimeError(f"dataset type not yet supported: {type(dataset)}")
        self.__NodeType: str = node_type
        self.__BaseAlgorithm: vtkPolyDataAlgorithm | None = base_algorithm
        self.__Actor: vtkActor | None = actor
        self.__Children: list[SceneGraphNode] = children

    @property
    def DescendantNodesOrSelfDictionary(self):
        return self.__DescendantNodesOrSelfDictionary

    @property
    def DescendantNodesOrSelfArray(self):
        return self.__DescendantNodesOrSelfArray

    @property
    def NodeType(self):
        return self.__NodeType

    @property
    def Actor(self):
        return self.__Actor

    @property
    def Children(self):
        return self.__Children

    def UpdateDescendantOrSelfActors(
        self, algorithm_filter: Callable[[vtkPolyDataAlgorithm], vtkPolyDataAlgorithm]
    ):
        if self.__BaseAlgorithm is None:
            # if base algorithm is not present, then this is a composite node
            # therefore loop through all the children with the algorithm filter
            for node in self.__Children:
                node.UpdateDescendantOrSelfActors(algorithm_filter)
        else:
            # if base algorithm is present, then this is an actual mesh node
            # therefore update the mapper with the new algorithm (and thus
            # the actor)
            mapper = self.__Actor.GetMapper()
            if isinstance(mapper, vtkPolyDataMapper):
                algorithm = algorithm_filter(self.__BaseAlgorithm)
                mapper.SetInputConnection(algorithm.GetOutputPort())
            else:
                raise RuntimeError(
                    f"mapper is not vtkPolyDataMapper. actual type: {type(mapper)}"
                )


def file_to_dataset(file_path: str) -> vtkDataSet | vtkCompositeDataSet:
    """"""
    # make file_path lowercase so extension testing is case-insensitive
    filename: str = os.path.basename(file_path).lower()
    extension: str = os.path.splitext(filename)[1][1:]
    dataset: vtkDataSet | vtkCompositeDataSet
    if extension == "vtu":
        """"""
        reader: vtkXMLUnstructuredGridReader = vtkXMLUnstructuredGridReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtp":
        """"""
        reader: vtkXMLPolyDataReader = vtkXMLPolyDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    elif extension == "vtm":
        """"""
        reader: vtkXMLMultiBlockDataReader = vtkXMLMultiBlockDataReader()
        reader.SetFileName(file_path)
        reader.Update()
        dataset = reader.GetOutput()
    else:
        """"""
        raise RuntimeError(f"Unsupported file: {file_path}")
    return dataset


def main():
    dataset = file_to_dataset("c:/path/to/file.vtm")
    root_node = SceneGraphNode(dataset)

    def algorithm_filter(algorithm: vtkPolyDataAlgorithm):
        subdivide: vtkPolyDataAlgorithm = vtkLoopSubdivisionFilter()
        subdivide.SetInputConnection(algorithm.GetOutputPort())
        return subdivide

    root_node.UpdateDescendantOrSelfActors(algorithm_filter)
```

The property `DescendantNodesOrSelfDictionary` is a dictionary that contains all descendant nodes of a node PLUS the node it was called from. The key is a random integer, and the value is the descendant node.

Notice that the name of the properties `DescendantNodesOrSelfDictionary` and `DescendantNodesOrSelfArray` include the phrase "OrSelf". This is because the content of these collections depends on whether the node they are accessed from is a composite or non-composite node. If it is a composite node, the dictionary and array contain all descendant nodes of the node the property was accessed from PLUS the node the properties were accessed from. If the node the property was accessed from is a non-composite node, then the collections contain ONLY the node that the property was accessed from.

We can now shorten our iteration code to the following:

```python
scene_root = SceneGraphNode(dataset)
for node in scene_root.DescendantNodesOrSelfArray:
    print(f"node type: {node.NodeType}")
```

The code above will iterate through all descendants of the scene root, BUT the first element in the collection will be the scene root itself. The same goes for the dictionary as well.