"""The stack and the Terraform module must deploy the same thing.

These read the module's .tf files, so a change on one side that isn't made on the
other fails here: IAM actions, Lambda environment variable names, defaults,
resource names, runtime and log retention.
"""

import re

import pytest
from cfn_eval import Stack
from conftest import REPO_ROOT


FUNCTIONS = ("scheduler", "purchaser", "reporter")
EVERYTHING_ON = {
    "NotificationEmail": "finops@example.com",
    "EnablePurchaser": "true",
    "ManagementReadOnlyRoleArn": "arn:aws:iam::111122223333:role/SPReadOnlyRole",
    "ManagementPurchaseRoleArn": "arn:aws:iam::111122223333:role/SPPurchaserRole",
    "SlackWebhookUrl": "https://hooks.slack.com/x",
    "TeamsWebhookUrl": "https://t.example.com/y",
}
# Where the stack deliberately differs from the module's defaults.
INTENDED_DEFAULT_DIFFERENCES = {
    # Purchases are irreversible: a one-click stack starts at the README's
    # Recommended Rollout step 2 (scheduler and reporter, no purchases).
    "EnablePurchaser": ("false", "true"),
}


def read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def blocks(text: str, kind: str) -> dict[str, str]:
    """{name: body} of each top-level `<kind> "<type>" "<name>" {` or `<kind> "<name>" {` block."""
    found = {}
    for match in re.finditer(
        rf'^{kind} (?:"[\w-]+" )?"([\w-]+)" \{{\n(.*?)^\}}', text, re.MULTILINE | re.DOTALL
    ):
        found[match.group(1)] = match.group(2)
    return found


def hcl_map_keys(text: str, local_name: str) -> set[str]:
    body = re.search(rf"^  {local_name} = \{{\n(.*?)^  \}}", text, re.MULTILINE | re.DOTALL).group(
        1
    )
    return set(re.findall(r"^\s+([A-Z_]+)\s+=", body, re.MULTILINE))


@pytest.fixture(scope="module")
def stack(template):
    return Stack(template, **EVERYTHING_ON)


# IAM


def terraform_policies() -> dict[str, dict[str, list[str]]]:
    """{function: {policy name: actions}} from iam.tf."""
    policies: dict[str, dict[str, list[str]]] = {f: {} for f in FUNCTIONS}
    for body in blocks(read("iam.tf"), "resource").values():
        role = re.search(r"role\s+=\s+aws_iam_role\.(\w+)\[0\]\.id", body)
        if role is None:
            continue
        name = re.search(r'^  name\s+=\s+"([\w-]+)"', body, re.MULTILINE).group(1)
        policies[role.group(1)][name] = sorted(re.findall(r'"([a-z0-9-]+:[A-Za-z*]+)"', body))
    return policies


def test_terraform_policies_were_found():
    assert all(len(p) >= 5 for p in terraform_policies().values())


@pytest.mark.parametrize("function", FUNCTIONS)
def test_execution_roles_grant_the_same_actions_as_terraform(stack, function):
    cfn = {}
    for policy in stack.properties(f"{function.title()}Role")["Policies"]:
        actions = []
        for statement in policy["PolicyDocument"]["Statement"]:
            actions += (
                statement["Action"]
                if isinstance(statement["Action"], list)
                else [statement["Action"]]
            )
        cfn[policy["PolicyName"]] = sorted(actions)
    assert cfn == terraform_policies()[function]


def test_queue_policy_matches_terraform(stack):
    terraform = blocks(read("sqs.tf"), "resource")["purchase_intents"]
    assert re.search(r"AWS = aws_iam_role\.scheduler\[0\]\.arn", terraform)
    statement = stack.properties("PurchaseIntentsQueuePolicy")["PolicyDocument"]["Statement"]
    assert statement == [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "<SchedulerRole.Arn>"},
            "Action": "sqs:SendMessage",
            "Resource": "<PurchaseIntentsQueue.Arn>",
        }
    ]


# Lambda environment


def terraform_environment_names() -> dict[str, set[str]]:
    main = read("main.tf")
    shared = {
        "common_lambda_env": hcl_map_keys(main, "common_lambda_env"),
        "strategy_lambda_env": hcl_map_keys(main, "strategy_lambda_env"),
    }
    names = {}
    for function, body in blocks(read("lambda.tf"), "resource").items():
        if function not in FUNCTIONS:
            continue
        environment = re.search(r"environment \{(.*?)\n  \}", body, re.DOTALL).group(1)
        keys = set(re.findall(r"^\s+([A-Z_]+)\s+=", environment, re.MULTILINE))
        for local_name, local_keys in shared.items():
            if f"local.{local_name}" in environment:
                keys |= local_keys
        names[function] = keys
    return names


@pytest.mark.parametrize("function", FUNCTIONS)
def test_functions_get_the_same_environment_variables_as_terraform(stack, function):
    cfn = set(stack.properties(f"{function.title()}Function")["Environment"]["Variables"])
    assert cfn == terraform_environment_names()[function]


def test_purchased_plans_get_terraform_s_tags(stack):
    # main.tf's common_tags with no extra tags; the purchaser tags every plan it buys with them.
    assert re.search(
        r'ManagedBy = "terraform-aws-sp-autopilot"\s+Module\s+= "savings-plans-automation"',
        read("main.tf"),
    )
    variables = stack.properties("PurchaserFunction")["Environment"]["Variables"]
    assert (
        variables["TAGS"]
        == '{"ManagedBy":"terraform-aws-sp-autopilot","Module":"savings-plans-automation"}'
    )


@pytest.mark.parametrize("function", FUNCTIONS)
def test_functions_use_terraform_s_runtime_and_handler(stack, function):
    terraform = blocks(read("lambda.tf"), "resource")[function]
    properties = stack.properties(f"{function.title()}Function")
    assert properties["Runtime"] == re.search(r'runtime = "(.+)"', terraform).group(1)
    assert properties["Handler"] == re.search(r'handler = "(.+)"', terraform).group(1)


def test_code_copier_uses_the_same_runtime(stack):
    assert (
        stack.properties("CodeCopierFunction")["Runtime"]
        == stack.properties("SchedulerFunction")["Runtime"]
    )


@pytest.mark.parametrize("function", FUNCTIONS)
def test_log_retention_matches_terraform(stack, function):
    terraform = blocks(read("cloudwatch.tf"), "resource")[function]
    retention = int(re.search(r"retention_in_days = (\d+)", terraform).group(1))
    assert stack.properties(f"{function.title()}LogGroup")["RetentionInDays"] == retention


# Defaults

# (stack parameter, module variable, attribute of that variable). An attribute of
# None reads the variable's own default.
DEFAULTS = [
    ("NamePrefix", "name_prefix", None),
    ("RenewalWindowDays", "purchase_strategy", "renewal_window_days"),
    ("PurchaseCooldownDays", "purchase_strategy", "purchase_cooldown_days"),
    ("MinCommitmentPerPlan", "purchase_strategy", "min_commitment_per_plan"),
    ("PrudentPercentage", "purchase_strategy", "prudent_percentage"),
    ("SpikeGuardEnabled", "purchase_strategy", "enabled"),
    ("SpikeGuardLongLookbackDays", "purchase_strategy", "long_lookback_days"),
    ("SpikeGuardShortLookbackDays", "purchase_strategy", "short_lookback_days"),
    ("SpikeGuardThresholdPercent", "purchase_strategy", "threshold_percent"),
    ("SchedulerSchedule", "cron_schedules", "scheduler"),
    ("PurchaserSchedule", "cron_schedules", "purchaser"),
    ("ReporterSchedule", "cron_schedules", "reporter"),
    ("ReportFormat", "reporting", "format"),
    ("EmailReports", "reporting", "email_reports"),
    ("IncludeDebugData", "reporting", "include_debug_data"),
    ("ReportsTransitionIaDays", "reporting", "transition_ia_days"),
    ("ReportsTransitionGlacierDays", "reporting", "transition_glacier_days"),
    ("ReportsExpirationDays", "reporting", "expiration_days"),
    ("ReportsNoncurrentExpirationDays", "reporting", "noncurrent_expiration_days"),
    ("S3AccessLogging", "s3_access_logging", "enabled"),
    ("S3AccessLogsPrefix", "s3_access_logging", "target_prefix"),
    ("S3AccessLogsExpirationDays", "s3_access_logging", "expiration_days"),
    ("DlqAlarm", "monitoring", "dlq_alarm"),
    ("LambdaErrorThreshold", "monitoring", "error_threshold"),
    ("LowUtilizationThreshold", "monitoring", "low_utilization_threshold"),
    ("LambdaErrorAlarms", "lambda_config", "error_alarm"),
    ("LambdaMemorySize", "lambda_config", "memory_mb"),
    ("LambdaTimeout", "lambda_config", "timeout"),
    ("EnableScheduler", "lambda_config", "enabled"),
    ("EnablePurchaser", "lambda_config", "enabled"),
    ("EnableReporter", "lambda_config", "enabled"),
    ("SnsKmsKey", "encryption", "sns_kms_key"),
    ("SqsKmsKey", "encryption", "sqs_kms_key"),
]


def terraform_defaults(variable: str, attribute: str | None) -> set[str]:
    """Every default given to that attribute in the variable's block, as strings."""
    body = blocks(read("variables.tf"), "variable")[variable]
    if attribute is None:
        return set(re.findall(r'^  default\s+=\s+"?([^"\n]+?)"?$', body, re.MULTILINE))
    optional = re.findall(rf"\b{attribute}\s+=\s+optional\(\w+, \"?([^\")]+)\"?\)", body)
    # cron_schedules sets its defaults in the variable's default block instead.
    literal = re.findall(
        rf'^\s+{attribute}\s+=\s+"([^"]+)"', body.split("default = {", 1)[-1], re.MULTILINE
    )
    return set(optional) | (set(literal) if "default = {" in body else set())


@pytest.mark.parametrize(("parameter", "variable", "attribute"), DEFAULTS)
def test_defaults_match_terraform(template, parameter, variable, attribute):
    default = template["Parameters"][parameter]["Default"]
    default = ("true" if default else "false") if isinstance(default, bool) else str(default)
    terraform = terraform_defaults(variable, attribute)
    if parameter in INTENDED_DEFAULT_DIFFERENCES:
        ours, theirs = INTENDED_DEFAULT_DIFFERENCES[parameter]
        assert (default, terraform) == (ours, {theirs})
    elif attribute == "expiration_days" and variable == "reporting":
        # reporting.s3_lifecycle's expiration_days, not noncurrent_expiration_days.
        assert default in terraform
    else:
        assert terraform == {default}, (parameter, terraform)


# Names


NAMED_PROPERTIES = (
    "TopicName",
    "QueueName",
    "BucketName",
    "FunctionName",
    "RoleName",
    "AlarmName",
    "LogGroupName",
    "Name",
)


def test_resources_have_terraform_s_names(template):
    terraform = set()
    for name in (
        "sns.tf",
        "sqs.tf",
        "s3.tf",
        "lambda.tf",
        "iam.tf",
        "cloudwatch.tf",
        "eventbridge.tf",
    ):
        for prefix, suffix in re.findall(
            r'^\s+(?:name|function_name|bucket|alarm_name)\s+=\s+"([^"$]*)\$\{local\.module_name\}([^"]*)"',
            read(name),
            re.MULTILINE,
        ):
            terraform.add(
                prefix
                + "{prefix}"
                + suffix.replace("${data.aws_caller_identity.current.account_id}", "123456789012")
            )

    stack = Stack(template, **EVERYTHING_ON, S3AccessLogging="true", NamePrefix="pfx")
    cfn = set()
    for logical_id in stack.resources():
        properties = stack.properties(logical_id)
        for key in NAMED_PROPERTIES:
            if isinstance(properties.get(key), str) and "pfx" in properties[key]:
                cfn.add(properties[key].replace("pfx", "{prefix}"))

    assert len(terraform) >= 15  # a function, its role and its rule share one name
    assert cfn - terraform == {"{prefix}-code-copier", "/aws/lambda/{prefix}-code-copier"}
    assert terraform - cfn == set()
