import pathlib
from os.path import join

from ansys.visor.viewer import Visor
from ansys.visor.viewer.core.metadata import Metadata


def start_poc_session():
    abs_dir = pathlib.Path(__file__).parent.resolve()
    assets_directory = join(abs_dir, "../assets")
    file_path = join(assets_directory, "reactor.vtm")
    visualizer: Visor = Visor(standalone=True)
    visualizer.start(input=file_path, metadata= Metadata(name="reactor", unit = "m"))

def main():
    start_poc_session()


if __name__ == "__main__":
    main()
