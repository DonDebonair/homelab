"""Data-driven tests for the custom Proxmox PVE facts.

Each directory under ``facts/`` is named after the dotted import path of a fact
(``<module>.<FactClass>`` below ``BASE_IMPORT_PATH``) and contains one JSON case
file per test. See ``pyinfra-testing`` for the case-file format.
"""

from pathlib import Path

from pyinfra_testing.facts import make_fact_tests

BASE_IMPORT_PATH = "facts"
TESTS_BASE = Path(__file__).parent / "facts"

for fact_path in sorted(
    d.name for d in TESTS_BASE.iterdir() if d.is_dir() and not d.name.startswith("_")
):
    locals()[fact_path] = make_fact_tests(BASE_IMPORT_PATH, fact_path, TESTS_BASE / fact_path)
