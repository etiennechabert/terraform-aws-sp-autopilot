"""What release.yml may do with the template and with the AWS role that hosts it.

publish-template is the only job with AWS credentials, and they can replace the
template every user's Launch Stack link opens, so its shape is pinned here.
"""

import re

import cfn_eval
import pytest
import yaml
from conftest import REPO_ROOT


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )


def run_scripts(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_release_job_packages_and_attaches_the_template(workflow):
    job = workflow["jobs"]["release"]
    assert "python3 cloudformation/build.py" in run_scripts(job)
    create = next(
        s for s in job["steps"] if s.get("uses", "").startswith("ncipollo/release-action@")
    )
    assert create["with"]["artifacts"] == "dist/cloudformation/*"
    assert create["with"]["artifactErrorsFailBuild"] is True
    assert create["with"]["draft"] is False  # draft assets aren't downloadable by stacks


def test_publish_template_holds_an_oidc_token_and_nothing_else(workflow):
    job = workflow["jobs"]["publish-template"]
    assert job["permissions"] == {"id-token": "write"}
    # The hosting role trusts this environment only (hosting/template-hosting.yaml).
    assert job["environment"] == "release"
    assert job["needs"] == "release"


def test_publish_template_runs_no_repository_code(workflow):
    job = workflow["jobs"]["publish-template"]
    assert [step.get("uses") for step in job["steps"]] == [None]
    assert not re.search(r"\b(python3?|pip|npm|npx|make|bash|sh)\b|\./", run_scripts(job))


def test_publish_template_uploads_the_released_template_only(workflow):
    script = run_scripts(workflow["jobs"]["publish-template"])
    assert "releases/download/${TAG}/sp-autopilot.yaml" in script
    assert "--duration-seconds 900" in script
    uploads = [line.strip() for line in script.splitlines() if "aws s3" in line]
    assert uploads == [
        'aws s3 cp sp-autopilot.yaml "s3://${TEMPLATE_BUCKET}/templates/${folder}/sp-autopilot.yaml" \\'
    ]


def test_publish_template_waits_for_all_three_variables(workflow):
    condition = workflow["jobs"]["publish-template"]["if"]
    for variable in ("TEMPLATE_BUCKET", "TEMPLATE_ROLE_ARN", "TEMPLATE_REGION"):
        assert f"vars.{variable} != ''" in condition


def test_hosting_role_trusts_the_release_environment_and_writes_templates_only():
    hosting = cfn_eval.load(
        (REPO_ROOT / "cloudformation" / "hosting" / "template-hosting.yaml").read_text(
            encoding="utf-8"
        )
    )
    role = hosting["Resources"]["ReleaseUploadRole"]["Properties"]
    (trust,) = role["AssumeRolePolicyDocument"]["Statement"]
    assert trust["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"] == {
        "Fn::Sub": "repo:${GitHubRepository}:environment:release"
    }
    (policy,) = role["Policies"]
    assert policy["PolicyDocument"]["Statement"] == [
        {
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": {"Fn::Sub": "${TemplatesBucket.Arn}/templates/*"},
        }
    ]
