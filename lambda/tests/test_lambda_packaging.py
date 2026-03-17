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
    """Extract {archive_name: {zip_filename: source_path}} from lambda.tf.

    Handles three terraform patterns:
    - dynamic source with for_each = fileset(...) and filename = source.value
    - dynamic source with for_each = toset([...]) and filename = source.value
    - dynamic source with filename = "prefix/${source.value}"
    """
    archives: dict[str, dict[str, Path]] = {}
    current_archive = None

    in_dynamic = False
    for_each_values: list[str] | None = None
    content_dir: str | None = None
    filename_template: str | None = None
    collecting_toset = False
    toset_items: list[str] = []

    for line in tf_content.splitlines():
        stripped = line.strip()

        archive_match = re.match(r'data "archive_file" "(\w+)"', stripped)
        if archive_match:
            current_archive = archive_match.group(1)
            archives[current_archive] = {}
            continue

        if not current_archive:
            continue

        if stripped.startswith('dynamic "source"'):
            in_dynamic = True
            for_each_values = None
            content_dir = None
            filename_template = None
            collecting_toset = False
            toset_items = []
            continue

        if not in_dynamic:
            continue

        # for_each = fileset("${path.module}/dir", "pattern")
        m = re.match(r'for_each\s*=\s*fileset\("\$\{path\.module\}/(.+?)",\s*"(.+?)"\)', stripped)
        if m:
            fs_dir = REPO_ROOT / m.group(1)
            for_each_values = sorted(p.name for p in fs_dir.glob(m.group(2)))
            continue

        # for_each = toset([...]) - may span multiple lines
        if re.match(r"for_each\s*=\s*toset\(\[", stripped):
            collecting_toset = True
            toset_items = re.findall(r'"([^"]+)"', stripped)
            if "]" in stripped:
                collecting_toset = False
                for_each_values = list(toset_items)
            continue

        if collecting_toset:
            toset_items.extend(re.findall(r'"([^"]+)"', stripped))
            if "]" in stripped:
                collecting_toset = False
                for_each_values = list(toset_items)
            continue

        # content = file("${path.module}/.../${source.value}")
        m = re.match(
            r"content\s*=\s*file\(\"\$\{path\.module\}/(.+?)\$\{source\.value\}\"\)", stripped
        )
        if m:
            content_dir = m.group(1)
            continue

        # filename = "prefix/${source.value}" (quoted, with interpolation)
        m = re.match(r'filename\s*=\s*"(.+\$\{source\.value\}.*)"', stripped)
        if m:
            filename_template = m.group(1)
        # filename = source.value (no quotes)
        elif re.match(r"filename\s*=\s*source\.value", stripped):
            filename_template = "${source.value}"

        # Resolve once all three pieces are known
        if (
            in_dynamic
            and for_each_values is not None
            and content_dir is not None
            and filename_template is not None
        ):
            for value in for_each_values:
                source_path = REPO_ROOT / (content_dir + value)
                zip_fn = filename_template.replace("${source.value}", value)
                archives[current_archive][zip_fn] = source_path
            in_dynamic = False

    return archives


def get_local_imports(python_source: str) -> set[str]:
    """Extract candidate local module filenames from import statements using AST."""
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
            elif parts[0] in ("target_strategies", "split_strategies"):
                if len(parts) > 1:
                    candidates.add(f"{parts[0]}/{parts[1]}.py")
                else:
                    for alias in node.names:
                        candidates.add(f"{parts[0]}/{alias.name}.py")
                candidates.add(f"{parts[0]}/__init__.py")
            elif len(parts) == 1:
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
    """Verify every local import in the archive is satisfied by another file in the archive."""
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


@pytest.mark.parametrize("archive_name", LAMBDA_ARCHIVES)
def test_archive_resolves_all_files(archives, archive_name):
    """Verify every file referenced in the archive actually exists on disk."""
    if archive_name not in archives:
        pytest.skip(f"No archive_file '{archive_name}' found in lambda.tf")

    archive = archives[archive_name]
    missing = [str(path) for path in archive.values() if not path.exists()]

    if missing:
        pytest.fail(
            f"archive_file.{archive_name} references non-existent files:\n"
            + "\n".join(f"  {p}" for p in missing)
        )
