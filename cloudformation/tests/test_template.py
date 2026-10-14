"""What the stack creates, and what its Lambdas are configured with, per parameter set."""

import hashlib
import re
from pathlib import Path

import build
import pytest
from cfn_eval import Stack
from conftest import TEST_CODE_SOURCE_URL, TEST_VERSION


FUNCTIONS = {"Scheduler": "scheduler", "Purchaser": "purchaser", "Reporter": "reporter"}
PLAN_TYPES = [
    "disabled",
    "no_upfront_one_year",
    "partial_upfront_one_year",
    "all_upfront_one_year",
    "no_upfront_three_year",
    "partial_upfront_three_year",
    "all_upfront_three_year",
]
EMAIL = {"NotificationEmail": "finops@example.com"}


def env(stack: Stack, function: str) -> dict[str, str]:
    return stack.properties(f"{function}Function")["Environment"]["Variables"]


def terraform_term_and_payment(plan_type: str) -> tuple[str, str]:
    """main.tf's compute_term / compute_payment_option (sagemaker_* are the same)."""
    if plan_type == "disabled":
        return "THREE_YEAR", "ALL_UPFRONT"
    term = "THREE_YEAR" if "three_year" in plan_type else "ONE_YEAR"
    if "all_upfront" in plan_type:
        return term, "ALL_UPFRONT"
    if "partial_upfront" in plan_type:
        return term, "PARTIAL_UPFRONT"
    return term, "NO_UPFRONT"


# Rules


def test_defaults_need_a_notification_target(template):
    assert Stack(template).failing_rules() == ["AtLeastOneNotification"]
    assert Stack(template, **EMAIL).failing_rules() == []


@pytest.mark.parametrize(
    "target",
    [
        {"NotificationEmail": "a@example.com"},
        {"SlackWebhookUrl": "https://hooks.slack.com/x"},
        {"TeamsWebhookUrl": "https://x.webhook.office.com/y"},
    ],
)
def test_any_one_notification_target_is_enough(template, target):
    assert Stack(template, **target).failing_rules() == []


def test_at_least_one_savings_plans_type(template):
    stack = Stack(template, **EMAIL, ComputePlanType="disabled")
    assert stack.failing_rules() == ["AtLeastOneSavingsPlanType"]
    assert (
        Stack(
            template, **EMAIL, ComputePlanType="disabled", SageMakerPlanType="no_upfront_one_year"
        ).failing_rules()
        == []
    )


def test_static_target_needs_a_commitment(template):
    assert Stack(template, **EMAIL, TargetStrategy="static").failing_rules() == [
        "StaticTargetNeedsCommitment"
    ]
    assert (
        Stack(template, **EMAIL, TargetStrategy="static", StaticCommitment=0.5).failing_rules()
        == []
    )


def test_the_source_template_refuses_to_deploy(source_template):
    assert "PackagedTemplate" in Stack(source_template, **EMAIL).failing_rules()


# Which resources exist


def test_defaults_run_the_scheduler_and_reporter_but_not_the_purchaser(template):
    resources = Stack(template, **EMAIL).resources()
    for logical_id in (
        "SchedulerFunction",
        "SchedulerRule",
        "SchedulerErrorsAlarm",
        "ReporterFunction",
        "ReporterRule",
        "ReporterErrorsAlarm",
    ):
        assert logical_id in resources
    assert not [r for r in resources if r.startswith("Purchaser")]
    assert "EmailSubscription" in resources


def test_enabling_the_purchaser_creates_it_with_its_schedule_and_alarm(template):
    resources = Stack(template, **EMAIL, EnablePurchaser="true").resources()
    for logical_id in (
        "PurchaserLogGroup",
        "PurchaserRole",
        "PurchaserFunction",
        "PurchaserRule",
        "PurchaserEventBridgePermission",
        "PurchaserErrorsAlarm",
    ):
        assert logical_id in resources


def test_an_empty_schedule_keeps_the_function_but_drops_its_rule(template):
    resources = Stack(template, **EMAIL, SchedulerSchedule="").resources()
    assert "SchedulerFunction" in resources
    assert "SchedulerRule" not in resources
    assert "SchedulerEventBridgePermission" not in resources


def test_disabling_a_function_drops_everything_it_owns(template):
    resources = Stack(template, **EMAIL, EnableScheduler="false").resources()
    assert not [r for r in resources if r.startswith("Scheduler")]
    assert "PurchaseIntentsQueuePolicy" not in resources


def test_alarm_switches(template):
    resources = Stack(
        template, **EMAIL, EnablePurchaser="true", LambdaErrorAlarms="false", DlqAlarm="false"
    ).resources()
    assert not [r for r in resources if r.endswith("Alarm")]


def test_outputs_exist_only_for_running_functions(template):
    stack = Stack(template, **EMAIL)
    outputs = {
        name
        for name, out in template["Outputs"].items()
        if "Condition" not in out or stack.condition(out["Condition"])
    }
    assert "SchedulerRoleArn" in outputs
    assert "PurchaserRoleArn" not in outputs


# Lambda configuration


@pytest.mark.parametrize("plan_type", PLAN_TYPES)
def test_compute_plan_type_sets_term_and_payment_like_terraform(template, plan_type):
    stack = Stack(
        template, **EMAIL, ComputePlanType=plan_type, SageMakerPlanType="no_upfront_one_year"
    )
    term, payment = terraform_term_and_payment(plan_type)
    for function in ("Scheduler", "Reporter"):
        variables = env(stack, function)
        assert (variables["COMPUTE_SP_TERM"], variables["COMPUTE_SP_PAYMENT_OPTION"]) == (
            term,
            payment,
        )
        assert variables["ENABLE_COMPUTE_SP"] == ("false" if plan_type == "disabled" else "true")


@pytest.mark.parametrize("plan_type", PLAN_TYPES)
def test_sagemaker_plan_type_sets_term_and_payment_like_terraform(template, plan_type):
    stack = Stack(template, **EMAIL, SageMakerPlanType=plan_type)
    term, payment = terraform_term_and_payment(plan_type)
    for function in ("Scheduler", "Reporter"):
        variables = env(stack, function)
        assert (variables["SAGEMAKER_SP_TERM"], variables["SAGEMAKER_SP_PAYMENT_OPTION"]) == (
            term,
            payment,
        )
        assert variables["ENABLE_SAGEMAKER_SP"] == ("false" if plan_type == "disabled" else "true")


@pytest.mark.parametrize("plan_type", ["disabled", "no_upfront_one_year"])
def test_database_payment_option_is_always_no_upfront(template, plan_type):
    stack = Stack(template, **EMAIL, DatabasePlanType=plan_type, EnablePurchaser="true")
    for function in ("Scheduler", "Reporter"):
        assert env(stack, function)["DATABASE_SP_PAYMENT_OPTION"] == "NO_UPFRONT"
    for function in FUNCTIONS:
        assert env(stack, function)["ENABLE_DATABASE_SP"] == (
            "false" if plan_type == "disabled" else "true"
        )


# main.tf's strategy locals for the README's strategy combinations, and for split
# parameters set for a split that isn't chosen (ignored, as Terraform ignores them).
STRATEGIES = [
    (
        {},
        {
            "TARGET_STRATEGY_TYPE": "dynamic",
            "DYNAMIC_RISK_LEVEL": "prudent",
            "PRUDENT_PERCENTAGE": 85,
            "STATIC_COMMITMENT": 0,
            "SPLIT_STRATEGY_TYPE": "gap_split",
            "FIXED_STEP_PERCENT": 10,
            "MAX_PURCHASE_PERCENT": 100,
            "MIN_PURCHASE_PERCENT": "",
            "GAP_SPLIT_DIVIDER": 2,
        },
    ),
    (
        {
            "DynamicRiskLevel": "min_hourly",
            "GapSplitDivider": 3,
            "GapSplitMinPurchasePercent": "5",
            "GapSplitMaxPurchasePercent": "50",
        },
        {
            "TARGET_STRATEGY_TYPE": "dynamic",
            "DYNAMIC_RISK_LEVEL": "min_hourly",
            "PRUDENT_PERCENTAGE": 85,
            "STATIC_COMMITMENT": 0,
            "SPLIT_STRATEGY_TYPE": "gap_split",
            "FIXED_STEP_PERCENT": 10,
            "MAX_PURCHASE_PERCENT": 50,
            "MIN_PURCHASE_PERCENT": 5,
            "GAP_SPLIT_DIVIDER": 3,
        },
    ),
    (
        {
            "TargetStrategy": "static",
            "StaticCommitment": 0.5,
            "SplitStrategy": "fixed_step",
            "FixedStepPercent": 25,
            "GapSplitMaxPurchasePercent": "50",
        },
        {
            "TARGET_STRATEGY_TYPE": "static",
            "DYNAMIC_RISK_LEVEL": "",
            "PRUDENT_PERCENTAGE": 85,
            "STATIC_COMMITMENT": 0.5,
            "SPLIT_STRATEGY_TYPE": "fixed_step",
            "FIXED_STEP_PERCENT": 25,
            "MAX_PURCHASE_PERCENT": 25,
            "MIN_PURCHASE_PERCENT": "",
            "GAP_SPLIT_DIVIDER": 2,
        },
    ),
    (
        {
            "TargetStrategy": "aws",
            "SplitStrategy": "one_shot",
            "PrudentPercentage": 60,
            "GapSplitMinPurchasePercent": "5",
        },
        {
            "TARGET_STRATEGY_TYPE": "aws",
            "DYNAMIC_RISK_LEVEL": "",
            "PRUDENT_PERCENTAGE": 85,
            "STATIC_COMMITMENT": 0,
            "SPLIT_STRATEGY_TYPE": "one_shot",
            "FIXED_STEP_PERCENT": 10,
            "MAX_PURCHASE_PERCENT": 100,
            "MIN_PURCHASE_PERCENT": "",
            "GAP_SPLIT_DIVIDER": 2,
        },
    ),
]


@pytest.mark.parametrize(("parameters", "expected"), STRATEGIES)
def test_strategy_settings_reach_the_scheduler_and_reporter_like_terraform(
    template, parameters, expected
):
    stack = Stack(template, **EMAIL, **parameters)
    for function in ("Scheduler", "Reporter"):
        variables = env(stack, function)
        for name, value in expected.items():
            if isinstance(value, str):
                assert variables[name] == value, name
            else:
                assert float(variables[name]) == pytest.approx(value), name


@pytest.mark.parametrize(
    "parameters",
    [
        {
            "ComputePlanType": "partial_upfront_three_year",
            "SageMakerPlanType": "partial_upfront_one_year",
            "DatabasePlanType": "no_upfront_one_year",
        },
        {
            "SpikeGuardEnabled": "false",
            "SpikeGuardLongLookbackDays": 60,
            "SpikeGuardShortLookbackDays": 7,
            "SpikeGuardThresholdPercent": 35,
        },
        *(parameters for parameters, _ in STRATEGIES),
    ],
)
def test_settings_shared_by_the_functions_are_identical(template, parameters):
    stack = Stack(template, **EMAIL, **parameters, EnablePurchaser="true")
    scheduler, purchaser, reporter = (env(stack, f) for f in FUNCTIONS)
    for name in set(scheduler) & set(reporter):
        if name != "MANAGEMENT_ACCOUNT_ROLE_ARN":
            assert scheduler[name] == reporter[name], name
    for name in set(purchaser) & set(scheduler):
        if name != "MANAGEMENT_ACCOUNT_ROLE_ARN":
            assert purchaser[name] == scheduler[name], name


def test_management_account_roles(template):
    reader = "arn:aws:iam::111122223333:role/SPReadOnlyRole"
    buyer = "arn:aws:iam::111122223333:role/SPPurchaserRole"
    stack = Stack(
        template,
        **EMAIL,
        EnablePurchaser="true",
        ManagementReadOnlyRoleArn=reader,
        ManagementPurchaseRoleArn=buyer,
    )
    expected = {"Scheduler": reader, "Purchaser": buyer, "Reporter": reader}
    for function, role_arn in expected.items():
        assert env(stack, function)["MANAGEMENT_ACCOUNT_ROLE_ARN"] == role_arn
        policies = {p["PolicyName"]: p for p in stack.properties(f"{function}Role")["Policies"]}
        assert policies["assume-role"]["PolicyDocument"]["Statement"] == [
            {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn}
        ]

    single_account = Stack(template, **EMAIL, EnablePurchaser="true")
    for function in FUNCTIONS:
        names = [p["PolicyName"] for p in single_account.properties(f"{function}Role")["Policies"]]
        assert "assume-role" not in names


def test_webhooks_reach_the_purchaser_and_reporter_only(template):
    stack = Stack(
        template,
        SlackWebhookUrl="https://hooks.slack.com/x",
        TeamsWebhookUrl="https://t.example.com/y",
        EnablePurchaser="true",
    )
    for function in ("Purchaser", "Reporter"):
        assert env(stack, function)["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/x"
        assert env(stack, function)["TEAMS_WEBHOOK_URL"] == "https://t.example.com/y"
    assert "SLACK_WEBHOOK_URL" not in env(stack, "Scheduler")
    assert "EmailSubscription" not in stack.resources()


# Encryption and logging


def test_default_encryption(template):
    stack = Stack(template, **EMAIL)
    assert stack.properties("NotificationsTopic")["KmsMasterKeyId"] == "alias/aws/sns"
    for queue in ("PurchaseIntentsQueue", "PurchaseIntentsDlq"):
        assert stack.properties(queue)["KmsMasterKeyId"] == "alias/aws/sqs"
    rule = stack.properties("ReportsBucket")["BucketEncryption"][
        "ServerSideEncryptionConfiguration"
    ][0]
    assert rule["ServerSideEncryptionByDefault"] == {"SSEAlgorithm": "AES256"}


def test_encryption_can_be_turned_off_or_moved_to_kms(template):
    key = "arn:aws:kms:eu-west-1:123456789012:key/abcd"
    stack = Stack(template, **EMAIL, SnsKmsKey="", SqsKmsKey="", ReportsKmsKeyArn=key)
    assert "KmsMasterKeyId" not in stack.properties("NotificationsTopic")
    assert "KmsMasterKeyId" not in stack.properties("PurchaseIntentsQueue")
    assert "KmsDataKeyReusePeriodSeconds" not in stack.properties("PurchaseIntentsQueue")
    rule = stack.properties("ReportsBucket")["BucketEncryption"][
        "ServerSideEncryptionConfiguration"
    ][0]
    assert rule["ServerSideEncryptionByDefault"] == {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": key,
    }


def test_access_logging(template):
    assert "LoggingConfiguration" not in Stack(template, **EMAIL).properties("ReportsBucket")
    stack = Stack(template, **EMAIL, S3AccessLogging="true", S3AccessLogsPrefix="logs/")
    assert stack.properties("ReportsBucket")["LoggingConfiguration"] == {
        "DestinationBucketName": "<ReportsLogsBucket>",
        "LogFilePrefix": "logs/",
    }
    allow = stack.properties("ReportsLogsBucketPolicy")["PolicyDocument"]["Statement"][0]
    assert allow["Principal"] == {"Service": "logging.s3.amazonaws.com"}
    # The policy names the reports bucket; that name must be the one the stack gives it.
    assert (
        allow["Condition"]["ArnLike"]["aws:SourceArn"]
        == f"arn:aws:s3:::{stack.properties('ReportsBucket')['BucketName']}"
    )


# Lambda code


def test_functions_run_the_code_the_stack_copied(template):
    stack = Stack(template, **EMAIL, EnablePurchaser="true")
    for function in FUNCTIONS:
        code = stack.properties(f"{function}Function")["Code"]
        assert code == {"S3Bucket": "<LambdaCodeBucket>", "S3Key": f"<LambdaCode.{function}>"}


def test_the_stack_copies_this_release_packages(template, packaged_dir: Path):
    packages = Stack(template, **EMAIL).properties("LambdaCode")["Packages"]
    assert set(packages) == set(FUNCTIONS)
    for function, name in FUNCTIONS.items():
        zip_name = build.package_name(name)
        assert packages[function]["Url"] == f"{TEST_CODE_SOURCE_URL}/{zip_name}"
        assert (
            packages[function]["Sha256"]
            == hashlib.sha256((packaged_dir / zip_name).read_bytes()).hexdigest()
        )
    assert template["Mappings"]["Release"]["Package"]["Version"] == TEST_VERSION
    assert TEST_VERSION in template["Description"]


def test_every_lambda_runs_on_the_same_runtime(template):
    runtimes = {
        r["Properties"]["Runtime"]
        for r in template["Resources"].values()
        if r["Type"] == "AWS::Lambda::Function"
    }
    assert len(runtimes) == 1


# Security


def test_buckets_are_private_encrypted_and_https_only(template):
    stack = Stack(template, **EMAIL, S3AccessLogging="true")
    resources = stack.resources()
    buckets = [logical_id for logical_id, r in resources.items() if r["Type"] == "AWS::S3::Bucket"]
    assert sorted(buckets) == ["LambdaCodeBucket", "ReportsBucket", "ReportsLogsBucket"]
    for bucket in buckets:
        properties = stack.properties(bucket)
        assert set(properties["PublicAccessBlockConfiguration"].values()) == {True}
        assert "BucketEncryption" in properties
        policies = [
            stack.properties(p)
            for p, r in resources.items()
            if r["Type"] == "AWS::S3::BucketPolicy"
            and stack.properties(p)["Bucket"] == f"<{bucket}>"
        ]
        statements = [s for policy in policies for s in policy["PolicyDocument"]["Statement"]]
        assert {"Bool": {"aws:SecureTransport": "false"}} in [
            s.get("Condition") for s in statements if s["Effect"] == "Deny"
        ]


def test_iam_never_grants_wildcard_actions_and_scopes_what_it_can(template):
    stack = Stack(
        template,
        **EMAIL,
        EnablePurchaser="true",
        ManagementReadOnlyRoleArn="arn:aws:iam::111122223333:role/R",
        ManagementPurchaseRoleArn="arn:aws:iam::111122223333:role/P",
    )
    for logical_id, resource in stack.resources().items():
        if resource["Type"] != "AWS::IAM::Role":
            continue
        for policy in stack.properties(logical_id)["Policies"]:
            for statement in policy["PolicyDocument"]["Statement"]:
                actions = (
                    statement["Action"]
                    if isinstance(statement["Action"], list)
                    else [statement["Action"]]
                )
                assert not [a for a in actions if a == "*" or a.endswith(":*")], (
                    logical_id,
                    actions,
                )
                if statement["Resource"] == "*":
                    # Cost Explorer and Savings Plans actions take no resource ARNs.
                    assert {a.split(":")[0] for a in actions} <= {"ce", "savingsplans"}, (
                        logical_id,
                        actions,
                    )


def test_the_code_copier_can_only_write_to_the_code_bucket(template):
    policies = Stack(template, **EMAIL).properties("CodeCopierRole")["Policies"]
    s3_statements = [
        s
        for p in policies
        for s in p["PolicyDocument"]["Statement"]
        if any(a.startswith("s3:") for a in s["Action"])
    ]
    assert s3_statements == [
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:DeleteObject"],
            "Resource": "<LambdaCodeBucket.Arn>/*",
        }
    ]


# Parameters


def test_longest_name_prefix_keeps_every_name_within_aws_limits(template):
    prefix = "a" * template["Parameters"]["NamePrefix"]["MaxLength"]
    stack = Stack(
        template, **EMAIL, NamePrefix=prefix, EnablePurchaser="true", S3AccessLogging="true"
    )
    limits = {
        "BucketName": 63,
        "FunctionName": 64,
        "RoleName": 64,
        "QueueName": 80,
        "TopicName": 256,
        "AlarmName": 255,
        "Name": 64,
    }
    for logical_id in stack.resources():
        properties = stack.properties(logical_id)
        for key, limit in limits.items():
            if key in properties and isinstance(properties[key], str):
                assert len(properties[key]) <= limit, (logical_id, key, properties[key])


def test_every_parameter_is_in_exactly_one_console_group(template):
    groups = template["Metadata"]["AWS::CloudFormation::Interface"]["ParameterGroups"]
    grouped = [name for group in groups for name in group["Parameters"]]
    assert sorted(grouped) == sorted(template["Parameters"])


def test_parameter_defaults_satisfy_their_own_constraints(template):
    for name, spec in template["Parameters"].items():
        default = spec.get("Default")
        if default is None:
            continue
        if "AllowedPattern" in spec:
            assert re.fullmatch(spec["AllowedPattern"], str(default)), name
        if "MinValue" in spec:
            assert float(default) >= spec["MinValue"], name
        if "MaxValue" in spec:
            assert float(default) <= spec["MaxValue"], name
        if "MaxLength" in spec:
            assert len(str(default)) <= spec["MaxLength"], name
