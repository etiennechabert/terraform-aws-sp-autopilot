"""
Validates that Terraform lambda archives include all required local modules.

Parses lambda.tf to find which files are packaged into each lambda ZIP,
then uses AST to verify that every local module imported by packaged code
is itself included in the archive.
"""

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
LAMBDA_TF = REPO_ROOT / "lambda.tf"
LAMBDA_DIR = REPO_ROOT / "lambda"


def parse_archive_sources(tf_content: str) -> dict[str, dict[str, Path]]:
    """Extract {archive_name: {zip_filename: source_path}} from lambda.tf."""
    archives: dict[str, dict[str, Path]] = {}
    current_archive = None
    pending_content_path = None

    for line in tf_content.splitlines():
        archive_match = re.match(r'data "archive_file" "(\w+)"', line)
        if archive_match:
            current_archive = archive_match.group(1)
            archives[current_archive] = {}
            pending_content_path = None
            continue

        if not current_archive:
            continue

        content_match = re.match(r'\s*content\s*=\s*file\("\$\{path\.module\}/(.+)"\)', line)
        if content_match:
            pending_content_path = REPO_ROOT / content_match.group(1)
            continue

        filename_match = re.match(r'\s*filename\s*=\s*"(.+)"', line)
        if filename_match and pending_content_path:
            archives[current_archive][filename_match.group(1)] = pending_content_path
            pending_content_path = None

    return archives


def get_local_imports(python_source: str) -> set[str]:
    """Extract candidate local module filenames from import statements using AST.

    Returns possible filenames like 'sp_types.py' or 'shared/handler_utils.py'.
    Only includes imports that look like they could be local project modules.
    """
    try:
        tree = ast.parse(python_source)
    except SyntaxError:
        return set()

    candidates = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if node.module == "shared":
                for alias in node.names:
                    candidates.add(f"shared/{alias.name}.py")
            elif parts[0] == "shared":
                candidates.add(f"shared/{parts[1]}.py")
            elif len(parts) == 1:
                # Simple import like `from sp_types import X`
                candidates.add(f"{parts[0]}.py")

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "." not in alias.name:
                    candidates.add(f"{alias.name}.py")

    return candidates


def _find_in_lambda_dirs(filename: str) -> bool:
    """Check if a module file exists anywhere in the lambda source tree."""
    for subdir in ["scheduler", "reporter", "purchaser", "shared"]:
        if (LAMBDA_DIR / subdir / filename).exists():
            return True
    return False


LAMBDA_ARCHIVES = ["scheduler", "purchaser", "reporter"]


@pytest.fixture(scope="module")
def archives():
    return parse_archive_sources(LAMBDA_TF.read_text())


@pytest.mark.parametrize("archive_name", LAMBDA_ARCHIVES)
def test_archive_includes_all_local_dependencies(archives, archive_name):
    if archive_name not in archives:
        pytest.skip(f"No archive_file '{archive_name}' found in lambda.tf")

    archive = archives[archive_name]
    packaged_filenames = set(archive.keys())
    missing = set()

    for zip_filename, source_path in sorted(archive.items()):
        if not zip_filename.endswith(".py") or not source_path.exists():
            continue

        candidates = get_local_imports(source_path.read_text())
        for dep in candidates:
            if dep in packaged_filenames:
                continue
            if _find_in_lambda_dirs(dep):
                missing.add((zip_filename, dep))

    if missing:
        details = "\n".join(f"  {src} imports {dep}" for src, dep in sorted(missing))
        pytest.fail(f"archive_file.{archive_name} is missing local modules:\n{details}")
