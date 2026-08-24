import asyncio
from os import path

from ansys.visor.viewer import Visor
from ansys.visor.viewer.core.metadata import Metadata


async def start_update_stop(visualizer: Visor, input_file: str, update_file: str, metadata: Metadata):
        await visualizer._start_async(input_file, metadata)
        await asyncio.sleep(5)
        visualizer.update(update_file, Metadata(name="test_model_2", unit="m"))
        await asyncio.sleep(5)
        await visualizer._stop_async()

if __name__ == "__main__":
    input_file = path.join(path.dirname(__file__), "../..", "tests", "files", "plate.vtp")
    update_file = path.join(path.dirname(__file__), "../..", "tests", "files", "mesh.vtu")
    metadata = Metadata(name="test_model", unit="m")

    visualizer = Visor(url="http://localhost:8081", standalone=True)

    asyncio.run(start_update_stop(visualizer, input_file, update_file, metadata))
