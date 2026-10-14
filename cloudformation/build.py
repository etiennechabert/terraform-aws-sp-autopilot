"""Package the CloudFormation template and its Lambda code for a release.

Writes the three Lambda packages, with the same files as the Terraform module's
archives (lambda.tf), and sp-autopilot.yaml with its placeholders filled in: the
release, where the stack downloads the packages from, and their SHA-256s, which the
stack checks before using them. Standard library only, so the release workflow runs
it without installing anything.

    python3 cloudformation/build.py --version v1.3.0 --output-dir dist/cloudformation
"""

import argparse
import hashlib
import io
import os
import re
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LAMBDA_DIR = REPO_ROOT / "lambda"
TEMPLATE = REPO_ROOT / "cloudformation" / "sp-autopilot.yaml"
TEMPLATE_NAME = "sp-autopilot.yaml"
FUNCTIONS = ("scheduler", "purchaser", "reporter")
SHARED_DIRS = ("shared", "shared/target_strategies", "shared/split_strategies")
DEFAULT_REPOSITORY = "etiennechabert/terraform-aws-sp-autopilot"
# Both are written verbatim into the YAML, so they are held to characters that keep it valid.
VERSION_PATTERN = re.compile(r"v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?")
CODE_SOURCE_URL_PATTERN = re.compile(r"https://[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+(?<!/)")
# Fixed timestamps and modes, so the same sources always give the same packages.
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)
ZIP_FILE_MODE = 0o644


def package_name(function: str) -> str:
    return f"sp-autopilot-{function}.zip"


def package_files(function: str) -> dict[str, Path]:
    """{name in the zip: source file}, as lambda.tf's archive_file for that function."""
    files = {path.name: path for path in (LAMBDA_DIR / function).glob("*.py")}
    for shared_dir in SHARED_DIRS:
        for path in (LAMBDA_DIR / shared_dir).glob("*.py"):
            files[f"{shared_dir}/{path.name}"] = path
    return dict(sorted(files.items()))


def build_zip(files: dict[str, Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ZIP_FILE_MODE << 16
            archive.writestr(info, files[name].read_bytes())
    return buffer.getvalue()


def stamp(template: str, values: dict[str, str]) -> str:
    """Replace each @@NAME@@ with its value, and refuse to leave any behind."""
    for name, value in values.items():
        placeholder = f"@@{name}@@"
        if placeholder not in template:
            raise ValueError(f"the template has no {placeholder} placeholder")
        template = template.replace(placeholder, value)
    leftover = re.findall(r"@@[A-Z0-9_]+@@", template)
    if leftover:
        raise ValueError(f"placeholders left unfilled: {', '.join(sorted(set(leftover)))}")
    return template


def default_code_source_url(version: str, repository: str) -> str:
    return f"https://github.com/{repository}/releases/download/{version}"


def build(version: str, code_source_url: str, output_dir: Path) -> dict[str, str]:
    """Write the packages, the template and SHA256SUMS; return {file name: sha256}."""
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"not a release version: {version!r}")
    if not CODE_SOURCE_URL_PATTERN.fullmatch(code_source_url):
        raise ValueError(
            f"the code source URL must be https://, without spaces, quotes or a trailing /: {code_source_url!r}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for function in FUNCTIONS:
        body = build_zip(package_files(function))
        (output_dir / package_name(function)).write_bytes(body)
        checksums[package_name(function)] = hashlib.sha256(body).hexdigest()

    template = stamp(
        TEMPLATE.read_text(encoding="utf-8"),
        {
            "VERSION": version,
            "CODE_SOURCE_URL": code_source_url,
            "SCHEDULER_SHA256": checksums[package_name("scheduler")],
            "PURCHASER_SHA256": checksums[package_name("purchaser")],
            "REPORTER_SHA256": checksums[package_name("reporter")],
            "PACKAGED": "yes",
        },
    )
    # Bytes, not text: text mode would translate newlines on Windows after hashing.
    template_bytes = template.encode("utf-8")
    (output_dir / TEMPLATE_NAME).write_bytes(template_bytes)
    checksums[TEMPLATE_NAME] = hashlib.sha256(template_bytes).hexdigest()

    sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    (output_dir / "SHA256SUMS").write_bytes(sums.encode("utf-8"))
    return checksums


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", required=True, help="Release tag, e.g. v1.3.0")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="owner/name whose GitHub release hosts the packages",
    )
    parser.add_argument(
        "--code-source-url",
        help="Where the stack downloads the packages from (default: the GitHub release's assets)",
    )
    args = parser.parse_args(argv)

    url = args.code_source_url or default_code_source_url(args.version, args.repository)
    try:
        checksums = build(args.version, url, args.output_dir)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for name, digest in sorted(checksums.items()):
        print(f"{digest}  {args.output_dir / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
