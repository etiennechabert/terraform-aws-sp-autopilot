"""Shared fixtures: the template as source and as a release packages it."""

import sys
from pathlib import Path

import pytest


CLOUDFORMATION_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CLOUDFORMATION_DIR.parent
sys.path.insert(0, str(CLOUDFORMATION_DIR))

import build  # noqa: E402
import cfn_eval  # noqa: E402


TEST_VERSION = "v9.8.7"
TEST_CODE_SOURCE_URL = "https://example.com/releases/v9.8.7"


@pytest.fixture(scope="session")
def packaged_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("packaged")
    build.build(TEST_VERSION, TEST_CODE_SOURCE_URL, output_dir)
    return output_dir


@pytest.fixture(scope="session")
def template(packaged_dir: Path) -> dict:
    """The template as a release ships it."""
    return cfn_eval.load((packaged_dir / build.TEMPLATE_NAME).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def source_template() -> dict:
    """The repository's template, placeholders and all."""
    return cfn_eval.load(build.TEMPLATE.read_text(encoding="utf-8"))
