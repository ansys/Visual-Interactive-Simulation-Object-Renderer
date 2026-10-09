.. _known-limitations:

Known limitations
#################

In this release, you might encounter the following known limitations:

- You cannot use the cross-section widget's ``cut mesh`` button.
- When you select mesh parts colored by a variable, the selection color does not blend with the variable color.
- When you hide a mesh part, its parent appears as hidden in the tree view, even if other child parts are still visible.
- When you update the VTK dataset (the currently loaded file) with ``/update``, the frontend UI does not reset automatically.
  Reload the page to resync the UI with the current geometry state.
- When you right-click objects in the render window, the part details popup does not appear.
- When you hide parts, the bounding box outline does not resize automatically.

The first two limitations come from the underlying VTK library (version 9.5.0) and should be addressed in
future VTK releases. The remaining limitations are expected to be addressed in future VISOR releases.
