"""Run the API and UI using the documented GLOW CLI."""

from ansys.saf.glow.runtime import glow_main

from visor_saf_smoke import ui
from visor_saf_smoke.solution import definition

if __name__ == "__main__":
    glow_main(definition, ui)
