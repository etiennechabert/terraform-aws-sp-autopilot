"""cloudformation/build.py: the packages and the template a release ships."""

import hashlib
import importlib.util
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import build
import pytest
from conftest import REPO_ROOT, TEST_VERSION


def terraform_archives() -> dict[str, dict[str, Path]]:
    """{function: {name in zip: source}} as lambda.tf packages them, read by the packaging test."""
    path = REPO_ROOT / "lambda" / "tests" / "test_lambda_packaging.py"
    spec = importlib.util.spec_from_file_location("lambda_packaging", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_archive_sources((REPO_ROOT / "lambda.tf").read_text(encoding="utf-8"))


@pytest.mark.parametrize("function", build.FUNCTIONS)
def test_packages_hold_the_same_files_as_terraform_s_archives(function, packaged_dir):
    expected = terraform_archives()[function]
    assert build.package_files(function) == expected
    with zipfile.ZipFile(packaged_dir / build.package_name(function)) as archive:
        assert sorted(archive.namelist()) == sorted(expected)
        for name, source in expected.items():
            assert archive.read(name) == source.read_bytes()


@pytest.mark.parametrize("function", build.FUNCTIONS)
def test_packaged_handler_imports_on_its_own(function, packaged_dir, tmp_path):
    with zipfile.ZipFile(packaged_dir / build.package_name(function)) as archive:
        archive.extractall(tmp_path)
    # Only the package's own files and site-packages (boto3, as in the Lambda runtime).
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | {
        "AWS_DEFAULT_REGION": "eu-west-1"
    }
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path[0] = {str(tmp_path)!r}; import handler"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_packages_are_reproducible(tmp_path):
    first = build.build(TEST_VERSION, "https://example.com/a", tmp_path / "first")
    second = build.build(TEST_VERSION, "https://example.com/a", tmp_path / "second")
    assert first == second


def test_sha256sums_lists_every_file(packaged_dir):
    lines = (packaged_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = dict(reversed(line.split("  ")) for line in lines)
    assert set(listed) == {p.name for p in packaged_dir.iterdir()} - {"SHA256SUMS"}
    for name, digest in listed.items():
        assert hashlib.sha256((packaged_dir / name).read_bytes()).hexdigest() == digest


def test_template_placeholders_are_all_filled(packaged_dir):
    text = (packaged_dir / build.TEMPLATE_NAME).read_text(encoding="utf-8")
    assert "@@" not in text
    assert build.TEMPLATE.read_text(encoding="utf-8").count("@@") > 0


def test_stamp_refuses_missing_and_leftover_placeholders():
    with pytest.raises(ValueError, match="no @@B@@ placeholder"):
        build.stamp("@@A@@", {"A": "1", "B": "2"})
    with pytest.raises(ValueError, match="left unfilled: @@B@@"):
        build.stamp("@@A@@ @@B@@", {"A": "1"})


@pytest.mark.parametrize("version", ["1.3", "latest", "v1.3.0;rm", "v1.3.0\n", "v1.3.0 extra"])
def test_build_refuses_a_version_that_isnt_a_release(version, tmp_path):
    with pytest.raises(ValueError, match="not a release version"):
        build.build(version, "https://example.com", tmp_path)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://example.com/",
        'https://example.com/a"b',
        "https://example.com/a b",
        "https://example.com/a\n",
    ],
)
def test_build_refuses_a_code_source_url_that_isnt_plain_https(url, tmp_path):
    with pytest.raises(ValueError, match="https"):
        build.build(TEST_VERSION, url, tmp_path)


def test_main_defaults_to_the_github_release_assets(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert build.main(["--version", "v1.3.0", "--output-dir", str(tmp_path)]) == 0
    text = (tmp_path / build.TEMPLATE_NAME).read_text(encoding="utf-8")
    assert (
        "https://github.com/etiennechabert/terraform-aws-sp-autopilot/releases/download/v1.3.0"
        in text
    )
    assert build.TEMPLATE_NAME in capsys.readouterr().out


def test_main_reports_errors_without_a_traceback(tmp_path, capsys):
    assert build.main(["--version", "nope", "--output-dir", str(tmp_path)]) == 1
    assert "not a release version" in capsys.readouterr().err
