"""Wire-format builder for scene-graph state."""

from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphNode


class SceneGraphStateBuilder:
    """Compose a :class:`SceneGraphNodeInfo` tree from the scene graph.

    Reads structure and metadata only, from the scene-graph nodes. Carries
    no renderer handles; those are stamped separately by the caller from the
    renderer's annotation.
    """

    def __init__(self, scene_graph: VisorSceneGraphNode):
        self._scene_graph = scene_graph

    def build(self) -> SceneGraphNodeInfo:
        """Return the assembled ``SceneGraphNodeInfo`` for the whole graph."""
        return self._build_node(self._scene_graph)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_node(self, node: VisorSceneGraphNode) -> SceneGraphNodeInfo:
        info = node.state
        if node.is_group_node:
            # Recurse so leaves further down the tree are reachable too.
            info.children = [self._build_node(c) for c in node.children]
        return info


