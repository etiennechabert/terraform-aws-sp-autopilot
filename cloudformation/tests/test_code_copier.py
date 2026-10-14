"""The inline function that copies the Lambda packages into the stack's code bucket.

Runs the code exactly as the template carries it, with S3 and HTTP faked.
"""

import hashlib
import json
import sys
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

import build
import pytest
from cfn_eval import Stack


PACKAGES = {
    "Scheduler": b"scheduler zip",
    "Purchaser": b"purchaser zip",
    "Reporter": b"reporter zip",
}
RESPONSE_URL = "https://cloudformation-custom-resource-response.example.com/signed"


class FakeS3:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.deleted: list[tuple[str, str]] = []
        self.fail_deletes = False
        self.failing_puts = 0

    def put_object(self, Bucket, Key, Body):  # noqa: N803 - boto3's names
        if self.failing_puts:
            self.failing_puts -= 1
            raise RuntimeError("AccessDenied")
        self.objects[(Bucket, Key)] = Body

    def delete_object(self, Bucket, Key):  # noqa: N803 - boto3's names
        if self.fail_deletes:
            raise RuntimeError("NoSuchBucket")
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)


class FakeResponse:
    def __init__(self, body: bytes = b""):
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Web:
    """Serves package bodies by URL and records the responses sent to CloudFormation."""

    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.fetched: list[str] = []
        self.responses: list[dict] = []
        self.failing: dict[str, int] = {}

    def urlopen(self, target, timeout=None):
        if isinstance(target, urllib.request.Request):
            assert target.full_url == RESPONSE_URL
            assert target.get_method() == "PUT"
            assert target.get_header("Content-type") == ""
            self.responses.append(json.loads(target.data))
            return FakeResponse()
        self.fetched.append(target)
        if self.failing.get(target):
            self.failing[target] -= 1
            raise urllib.error.URLError("connection reset")
        return FakeResponse(self.files[target])

    @property
    def response(self) -> dict:
        assert len(self.responses) == 1
        return self.responses[0]


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


@pytest.fixture(autouse=True)
def sleeps(monkeypatch) -> list[float]:
    """The copier's retry delays, recorded instead of slept."""
    delays: list[float] = []
    monkeypatch.setattr(time, "sleep", delays.append)
    return delays


@pytest.fixture
def copier(template, s3, monkeypatch):
    """The function's module, loaded from the template with a fake boto3."""
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda *_: s3
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    module = types.ModuleType("index")
    code = template["Resources"]["CodeCopierFunction"]["Properties"]["Code"]["ZipFile"]
    # Runs the code the template ships, as Lambda would.
    exec(compile(code, "index.py", "exec"), module.__dict__)
    return module


def serve(monkeypatch, files: dict[str, bytes]) -> Web:
    web = Web(files)
    monkeypatch.setattr(urllib.request, "urlopen", web.urlopen)
    return web


def packages(bodies: dict[str, bytes] = PACKAGES, base: str = "https://example.com/v1") -> dict:
    return {
        name: {"Url": f"{base}/{name.lower()}.zip", "Sha256": hashlib.sha256(body).hexdigest()}
        for name, body in bodies.items()
    }


def event(request_type: str, props: dict, physical_id: str | None = None) -> dict:
    request = {
        "RequestType": request_type,
        "ResponseURL": RESPONSE_URL,
        "StackId": "arn:aws:cloudformation:eu-west-1:123456789012:stack/sp-autopilot/abc",
        "RequestId": "request-1",
        "LogicalResourceId": "LambdaCode",
        "ResourceType": "Custom::LambdaCode",
        # CloudFormation passes every property, ServiceToken and ServiceTimeout included.
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:eu-west-1:123456789012:function:copier",
            "ServiceTimeout": "600",
            **props,
        },
    }
    if physical_id is not None:
        request["PhysicalResourceId"] = physical_id
    return request


CONTEXT = types.SimpleNamespace(log_stream_name="2026/10/14/[$LATEST]abc")


def files_for(props: dict, bodies: dict[str, bytes] = PACKAGES) -> dict[str, bytes]:
    return {props["Packages"][name]["Url"]: body for name, body in bodies.items()}


def test_create_copies_every_package_under_checksum_named_keys(copier, s3, monkeypatch):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    web = serve(monkeypatch, files_for(props))

    copier.handler(event("Create", props), CONTEXT)

    response = web.response
    assert response["Status"] == "SUCCESS"
    release = response["PhysicalResourceId"]
    assert response["Data"] == {name: f"{release}/{name.lower()}.zip" for name in PACKAGES}
    assert s3.objects == {
        ("code-bucket", f"{release}/{name.lower()}.zip"): body for name, body in PACKAGES.items()
    }
    for key in ("StackId", "RequestId", "LogicalResourceId"):
        assert response[key] == event("Create", props)[key]


def test_a_tampered_package_fails_the_create_and_writes_nothing(copier, s3, monkeypatch):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    files = files_for(props)
    files[props["Packages"]["Reporter"]["Url"]] = b"something else"
    web = serve(monkeypatch, files)

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "FAILED"
    assert "reporter.zip has SHA-256" in web.response["Reason"]
    assert s3.objects == {}


def test_a_tampered_package_is_not_downloaded_again(copier, s3, monkeypatch, sleeps):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    files = files_for(props)
    files[props["Packages"]["Scheduler"]["Url"]] = b"something else"
    web = serve(monkeypatch, files)

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "FAILED"
    assert web.fetched == [props["Packages"]["Scheduler"]["Url"]]
    assert sleeps == []


def test_writes_are_retried_while_the_new_role_propagates(copier, s3, monkeypatch, sleeps):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    web = serve(monkeypatch, files_for(props))
    s3.failing_puts = 2

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "SUCCESS"
    assert len(s3.objects) == len(PACKAGES)
    assert sleeps == [5, 15]


def test_downloads_are_retried_after_a_network_error(copier, s3, monkeypatch, sleeps):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    web = serve(monkeypatch, files_for(props))
    web.failing[props["Packages"]["Purchaser"]["Url"]] = 1

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "SUCCESS"
    assert sleeps == [5]


def test_retries_give_up_after_three_attempts(copier, s3, monkeypatch, sleeps):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    web = serve(monkeypatch, files_for(props))
    s3.failing_puts = 3

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "FAILED"
    assert "AccessDenied" in web.response["Reason"]
    assert sleeps == [5, 15]


def test_only_https_sources_are_fetched(copier, s3, monkeypatch):
    props = {"Bucket": "code-bucket", "Packages": packages(base="http://example.com/v1")}
    web = serve(monkeypatch, {})

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "FAILED"
    assert "isn't https" in web.response["Reason"]
    assert web.fetched == []


def test_unpackaged_template_fails_clearly(copier, s3, monkeypatch):
    props = {"Bucket": "code-bucket", "Packages": packages(base="@@CODE_SOURCE_URL@@")}
    web = serve(monkeypatch, {})

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "FAILED"


def test_a_new_release_gets_new_keys_and_the_same_release_the_same_ones(copier, s3, monkeypatch):
    first = {"Bucket": "code-bucket", "Packages": packages()}
    changed = dict(PACKAGES, Purchaser=b"purchaser zip v2")
    second = {"Bucket": "code-bucket", "Packages": packages(changed, base="https://example.com/v2")}
    moved = {"Bucket": "code-bucket", "Packages": packages(base="https://mirror.example.com/v1")}
    web = serve(monkeypatch, files_for(first) | files_for(second, changed) | files_for(moved))

    copier.handler(event("Create", first), CONTEXT)
    copier.handler(event("Update", second, web.responses[0]["PhysicalResourceId"]), CONTEXT)
    copier.handler(event("Update", moved, web.responses[0]["PhysicalResourceId"]), CONTEXT)

    ids = [r["PhysicalResourceId"] for r in web.responses]
    # Every key changes with any package, so cleaning up the old release never
    # deletes a key the new one uses. A new download URL alone changes nothing.
    assert ids[0] != ids[1]
    assert ids[0] == ids[2]
    assert not set(web.responses[0]["Data"].values()) & set(web.responses[1]["Data"].values())


def test_delete_removes_the_release_keys(copier, s3, monkeypatch):
    props = {"Bucket": "code-bucket", "Packages": packages()}
    web = serve(monkeypatch, files_for(props))
    copier.handler(event("Create", props), CONTEXT)
    release = web.responses[0]["PhysicalResourceId"]

    copier.handler(event("Delete", props, release), CONTEXT)

    assert (web.responses[1]["Status"], web.responses[1]["PhysicalResourceId"]) == (
        "SUCCESS",
        release,
    )
    assert s3.objects == {}
    assert sorted(s3.deleted) == sorted(
        ("code-bucket", f"{release}/{name.lower()}.zip") for name in PACKAGES
    )


def test_a_failing_delete_still_lets_the_stack_go(copier, s3, monkeypatch):
    s3.fail_deletes = True
    web = serve(monkeypatch, {})

    copier.handler(event("Delete", {"Bucket": "gone", "Packages": packages()}, "abc"), CONTEXT)

    assert web.response["Status"] == "SUCCESS"
    assert "NoSuchBucket" in web.response["Reason"]


def test_malformed_properties_still_get_an_answer(copier, s3, monkeypatch):
    web = serve(monkeypatch, {})

    copier.handler(event("Create", {"Bucket": "code-bucket"}), CONTEXT)

    assert web.response["Status"] == "FAILED"
    assert web.response["PhysicalResourceId"]


def test_the_stack_s_own_properties_copy_the_built_packages(
    template, copier, s3, monkeypatch, packaged_dir: Path
):
    props = Stack(template, NotificationEmail="a@example.com").properties("LambdaCode")
    props.pop("ServiceToken")
    props.pop("ServiceTimeout")
    files = {}
    for name in PACKAGES:
        url = props["Packages"][name]["Url"]
        files[url] = (packaged_dir / build.package_name(name.lower())).read_bytes()
    web = serve(monkeypatch, files)

    copier.handler(event("Create", props), CONTEXT)

    assert web.response["Status"] == "SUCCESS"
    # The functions read these attributes (LambdaCode.Scheduler and so on).
    assert set(web.response["Data"]) == set(PACKAGES)
