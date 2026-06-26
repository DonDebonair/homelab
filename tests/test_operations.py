"""Data-driven tests for the custom Proxmox PVE operations.

Each directory under ``operations/`` is named after the dotted import path of an
operation (``<module>.<operation>`` below ``BASE_IMPORT_PATH``) and contains one
JSON case file per test. See ``pyinfra-testing`` for the case-file format.
"""

from pathlib import Path

from pyinfra_testing.operations import make_operation_tests

BASE_IMPORT_PATH = "operations"
TESTS_BASE = Path(__file__).parent / "operations"

for op_path in sorted(
    d.name for d in TESTS_BASE.iterdir() if d.is_dir() and not d.name.startswith("_")
):
    locals()[op_path] = make_operation_tests(BASE_IMPORT_PATH, op_path, TESTS_BASE / op_path)
