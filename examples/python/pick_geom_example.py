from ansys.visor.viewer import Visor
from ansys.visor.viewer.core.metadata import Metadata


def main():

    # input_file = "tests/files/sample_hex_cube.vtp"
    # input_file = "tests/files/cone_r0.5.vtp"
    input_file = "tests/files/tria_cube.vtp"
    print('Instantiating Visor')
    # Initialize the Visor viewer
    visor = Visor(url='http://0.0.0.0:8081',
                  standalone=True)

    # Start the viewer with the specified file path
    print(f'Starting Visor viewer with input file: {input_file}')
    visor.start(
        input=input_file,
        timeout=0,
        metadata=Metadata(unit='m', name='Test VTM Scene'),
        blocking=True
    )

if __name__ == "__main__":
    main()



