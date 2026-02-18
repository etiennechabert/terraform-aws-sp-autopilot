"""
Email notification module for Scheduler Lambda.

Provides email formatting and sending functionality for both scheduled
purchase notifications and dry run analysis results.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_sns.client import SNSClient

from shared import local_mode


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _format_coverage_block(coverage: dict[str, float] | None, config: dict[str, Any]) -> list[str]:
    if coverage is None:
        return []
    return [
        "Current Coverage:",
        f"  Compute SP:  {coverage.get('compute', 0):.2f}%",
        f"  Database SP: {coverage.get('database', 0):.2f}%",
        f"  SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
        "",
        f"Target Coverage: {config.get('coverage_target_percent', 90):.2f}%",
        "",
    ]


def _format_plans_block(purchase_plans: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    total_annual_cost = 0.0

    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get("sp_type", "unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term = plan.get("term", "unknown")
        payment_option = plan.get("payment_option", "ALL_UPFRONT")

        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        lines.extend(
            [
                f"{i}. {sp_type.upper()} Savings Plan",
                f"   Added Commitment: ${hourly_commitment:.4f}/hour",
                f"   Term: {term}",
                f"   Payment Option: {payment_option}",
                f"   Estimated Annual Cost: ${annual_cost:,.2f}",
                "",
            ]
        )

    lines.extend(
        [
            "-" * 50,
            f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
            "",
        ]
    )
    return lines


def _format_unknown_services_warning(
    unknown_services: list[str] | None,
) -> list[str]:
    if not unknown_services:
        return []
    lines = [
        "⚠️  WARNING: UNKNOWN SERVICES DETECTED",
        "=" * 50,
        "",
        f"Found {len(unknown_services)} service(s) with Savings Plans coverage",
        "that are NOT in our service constants:",
        "",
    ]
    for svc in sorted(unknown_services):
        lines.append(f"  - {svc}")
    lines.extend(
        [
            "",
            "Your analysis completed but may have INCOMPLETE coverage data.",
            "This likely means AWS added new services that support Savings Plans.",
            "",
            "ACTION REQUIRED:",
            "1. Open issue: https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues/new",
            "2. Title: New AWS services support Savings Plans",
            "3. Copy-paste:",
            "",
            f"   AWS added {len(unknown_services)} new service(s):",
        ]
    )
    for svc in sorted(unknown_services):
        lines.append(f"   - {svc}")
    lines.extend(
        [
            "",
            "   Please update lambda/shared/spending_analyzer.py",
            "",
            "=" * 50,
            "",
        ]
    )
    return lines


def _format_and_send(
    sns_client: SNSClient,
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
    unknown_services: list[str] | None,
    *,
    header_lines: list[str],
    plans_heading: str,
    footer_lines: list[str],
    subject: str,
    log_label: str,
) -> None:
    email_lines = [
        *header_lines,
        *_format_coverage_block(coverage, config),
        plans_heading,
        "-" * 50,
        *_format_plans_block(purchase_plans),
        *_format_unknown_services_warning(unknown_services),
        *footer_lines,
    ]

    message = "\n".join(email_lines)

    if local_mode.is_local_mode():
        logger.info(f"LOCAL MODE: Skipping SNS publish. {log_label} email content:")
        logger.info("=" * 60)
        logger.info(message)
        logger.info("=" * 60)
        return

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject=subject,
            Message=message,
        )
        logger.info(f"{log_label} email sent successfully to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send {log_label.lower()} email: {e!s}")
        raise


def send_scheduled_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
    unknown_services: list[str] | None = None,
) -> None:
    logger.info("Sending scheduled purchases email")
    _format_and_send(
        sns_client,
        config,
        purchase_plans,
        coverage,
        unknown_services,
        header_lines=[
            "Savings Plans Scheduled for Purchase",
            "=" * 50,
            "",
            f"Total Plans Queued: {len(purchase_plans)}",
            "",
        ],
        plans_heading="Scheduled Purchase Plans:",
        footer_lines=[
            "CANCELLATION INSTRUCTIONS:",
            "To cancel these purchases before they execute:",
            "1. Purge the SQS queue to remove all pending purchase intents",
            f"2. Queue URL: {config.get('queue_url', 'N/A')}",
            "3. AWS CLI command:",
            f"   aws sqs purge-queue --queue-url {config.get('queue_url', 'QUEUE_URL')}",
            "",
            "These purchases will be executed by the Purchaser Lambda.",
            "Monitor CloudWatch Logs and SNS notifications for execution results.",
        ],
        subject="Savings Plans Scheduled for Purchase",
        log_label="Scheduled",
    )


def send_dry_run_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
    unknown_services: list[str] | None = None,
) -> None:
    logger.info("Sending dry run email")
    _format_and_send(
        sns_client,
        config,
        purchase_plans,
        coverage,
        unknown_services,
        header_lines=[
            "***** DRY RUN MODE ***** Savings Plans Analysis",
            "=" * 50,
            "",
            "*** NO PURCHASES WERE SCHEDULED ***",
            "",
            f"Total Plans Analyzed: {len(purchase_plans)}",
            "",
        ],
        plans_heading="Purchase Plans (WOULD BE SCHEDULED if dry_run=false):",
        footer_lines=[
            "TO ENABLE ACTUAL PURCHASES:",
            "1. Set the DRY_RUN environment variable to 'false'",
            "2. Update the Lambda configuration:",
            "   aws lambda update-function-configuration \\",
            "     --function-name <scheduler-lambda-name> \\",
            "     --environment Variables={DRY_RUN=false,...}",
            "",
            "3. Or via Terraform:",
            "   Set dry_run = false in your terraform.tfvars",
            "",
            "Once disabled, the Scheduler will queue purchase intents to SQS,",
            "and the Purchaser Lambda will execute the actual purchases.",
        ],
        subject="[DRY RUN] Savings Plans Analysis - No Purchases Scheduled",
        log_label="Dry run",
    )
