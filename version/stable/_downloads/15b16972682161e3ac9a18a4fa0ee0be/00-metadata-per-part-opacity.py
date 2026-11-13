"""
.. _ref_per_part_opacity:

Set per-part opacity for multiblock dataset
===========================================

Create a small VTK multiblock dataset, with unique names for each part (leaf block).

Create a Metadata object to set custom opacity for each part of the dataset.

Pass the dataset and metadata to VISOR.start() to visualize the dataset with the specified per-part opacity.

.. image:: /_static/visor_multiblock_opacity.png
   :alt: VISOR multiblock with per-part opacity
   :width: 600px
   :align: center

"""


from vtk import vtkCompositeDataSet, vtkSphereSource
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet

from ansys.visor.viewer import Metadata, Visor


def make_simple_block(source_id: int) -> vtkSphereSource:
    """Create a small sphere with a slightly different radius/center per block."""
    sphere = vtkSphereSource()
    sphere.SetRadius(1.0)
    sphere.SetCenter(source_id * 3.0, 0.0, 0.0)
    sphere.SetThetaResolution(16)
    sphere.SetPhiResolution(16)
    sphere.Update()
    return sphere.GetOutput()

def make_multiblock() -> vtkMultiBlockDataSet:
    """Create a multiblock dataset with 3 blocks."""

    part_names = ["Part1", "Part2", "Part3"]

    multiblock = vtkMultiBlockDataSet()

    for i, name in enumerate(part_names):
        block = make_simple_block(i)
        multiblock.SetBlock(i, block)
        # Assign a unique name to this block
        multiblock.GetMetaData(i).Set(vtkCompositeDataSet.NAME(), name)

    return multiblock


################################################################################
# Create the multiblock and metadata
################################################################################
multiblock_data = make_multiblock()

# Create a metadata dictionary specifying the opacity for each part
metadata = Metadata(
    name="multiblock_example",
    unit="m",
    state={
        "parts":
            {
                "Part1": {"opacity": 0.2},
                "Part2": {"opacity": 0.5},
                "Part3": {"opacity": 0.8},
            }
    }
)

################################################################################
# Instantiate the viewer and start it with the data and metadata we just created
################################################################################
visualizer = Visor()
visualizer.start(input=multiblock_data, metadata=metadata)


