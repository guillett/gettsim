from pathlib import Path

# Obtain the root directory of the package. Do not import gettsim which creates a
# circular import.
ROOT_DIR = Path(__file__).parent

GEP_1_CHARACTER_LIMIT = 17

INTERNAL_FUNCTION_FILES = [
    "soz_vers",
    "benefits",
    "taxes",
    "renten_anspruch_dag.py",
    "demographic_vars.py",
]
