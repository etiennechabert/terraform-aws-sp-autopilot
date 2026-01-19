"""
Test that Lambda handlers don't have runtime imports of mypy type stub packages.

This test ensures that type stubs (mypy_boto3_*) are only used for type checking
and not imported at runtime, which would cause Lambda import failures.
"""

import re
from pathlib import Path


def test_no_runtime_mypy_imports():
    """
    Test that all Lambda Python files use TYPE_CHECKING guards for mypy_boto3 imports.

    This prevents Lambda runtime errors like:
    "Unable to import module 'handler': No module named 'mypy_boto3_ce'"
    """
    # Find all Python files in Lambda directories
    lambda_dir = Path(__file__).parent.parent.parent
    python_files = []

    for subdir in ["scheduler", "purchaser", "reporter", "shared"]:
        subdir_path = lambda_dir / subdir
        if subdir_path.exists():
            python_files.extend(subdir_path.glob("**/*.py"))

    # Pattern to find mypy_boto3 imports that are NOT guarded by TYPE_CHECKING
    # This regex looks for lines like:
    #   from mypy_boto3_ce.client import CostExplorerClient
    # But NOT when they appear inside:
    #   if TYPE_CHECKING:
    #       from mypy_boto3_ce.client import CostExplorerClient
    mypy_import_pattern = re.compile(r"^\s*from\s+mypy_boto3")

    issues = []

    for file_path in python_files:
        # Skip test files
        if "test" in file_path.parts:
            continue

        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        # Check if file has any mypy imports
        has_mypy_imports = any(mypy_import_pattern.match(line) for line in lines)

        if has_mypy_imports:
            # Verify the file uses TYPE_CHECKING
            has_type_checking_import = "TYPE_CHECKING" in content
            has_type_checking_block = "if TYPE_CHECKING:" in content

            if not (has_type_checking_import and has_type_checking_block):
                # Find the problematic import lines
                problematic_lines = []
                for i, line in enumerate(lines, 1):
                    if mypy_import_pattern.match(line):
                        problematic_lines.append(f"  Line {i}: {line.strip()}")

                issues.append(
                    f"{file_path.relative_to(lambda_dir)}:\n"
                    + "\n".join(problematic_lines)
                    + "\n  Missing TYPE_CHECKING guard!"
                )

    if issues:
        error_msg = (
            "Found mypy_boto3 imports without TYPE_CHECKING guards:\n\n"
            + "\n\n".join(issues)
            + "\n\nAll mypy_boto3 imports must be guarded with:\n"
            + "  from typing import TYPE_CHECKING\n"
            + "  if TYPE_CHECKING:\n"
            + "      from mypy_boto3_... import ..."
        )
        raise AssertionError(error_msg)


def test_type_checking_guard_pattern():
    """
    Verify that TYPE_CHECKING guards follow the correct pattern.

    This test ensures files that use TYPE_CHECKING:
    1. Import TYPE_CHECKING from typing
    2. Use 'if TYPE_CHECKING:' block for mypy imports
    """
    lambda_dir = Path(__file__).parent.parent.parent
    python_files = []

    for subdir in ["scheduler", "purchaser", "reporter", "shared"]:
        subdir_path = lambda_dir / subdir
        if subdir_path.exists():
            python_files.extend(subdir_path.glob("**/*.py"))

    issues = []

    for file_path in python_files:
        # Skip test files
        if "test" in file_path.parts:
            continue

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # If file uses TYPE_CHECKING, verify it's imported
        if "if TYPE_CHECKING:" in content:
            # Check if TYPE_CHECKING is imported from typing
            has_import = re.search(
                r"from\s+typing\s+import\s+.*\bTYPE_CHECKING\b", content
            )

            if not has_import:
                issues.append(
                    f"{file_path.relative_to(lambda_dir)}: "
                    "Uses 'if TYPE_CHECKING:' but doesn't import TYPE_CHECKING from typing"
                )

    if issues:
        error_msg = "Found TYPE_CHECKING usage issues:\n" + "\n".join(issues)
        raise AssertionError(error_msg)
