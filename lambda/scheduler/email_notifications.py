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

from shared import local_mode, notifications


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_scheduled_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
    unknown_services: list[str] | None = None,
) -> None:
    """
    Send email notification for scheduled purchases.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        purchase_plans: List of planned purchases
        coverage: Current coverage (None for follow_aws strategy)
        unknown_services: List of unknown services found (optional)
    """
    logger.info("Sending scheduled purchases email")

    # Format email body
    email_lines = [
        "Savings Plans Scheduled for Purchase",
        "=" * 50,
        "",
        f"Total Plans Queued: {len(purchase_plans)}",
        "",
    ]

    # Add coverage info if available (fixed/dichotomy strategies)
    if coverage is not None:
        email_lines.extend(
            [
                "Current Coverage:",
                f"  Compute SP:  {coverage.get('compute', 0):.2f}%",
                f"  Database SP: {coverage.get('database', 0):.2f}%",
                f"  SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
                "",
                f"Target Coverage: {config.get('coverage_target_percent', 90):.2f}%",
                "",
            ]
        )

    email_lines.extend(
        [
            "Scheduled Purchase Plans:",
            "-" * 50,
        ]
    )

    # Add details for each purchase plan
    total_annual_cost = 0.0

    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get("sp_type", "unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term = plan.get("term", "unknown")
        payment_option = plan.get("payment_option", "ALL_UPFRONT")

        # Calculate estimated annual cost (hourly * 24 * 365)
        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        email_lines.extend(
            [
                f"{i}. {sp_type.upper()} Savings Plan",
                f"   Hourly Commitment: ${hourly_commitment:.4f}/hour",
                f"   Term: {term}",
                f"   Payment Option: {payment_option}",
                f"   Estimated Annual Cost: ${annual_cost:,.2f}",
                "",
            ]
        )

    email_lines.extend(
        [
            "-" * 50,
            f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
            "",
        ]
    )

    # Add warning if unknown services detected
    if unknown_services:
        email_lines.extend(
            [
                "⚠️  WARNING: UNKNOWN SERVICES DETECTED",
                "=" * 50,
                "",
                f"Found {len(unknown_services)} service(s) with Savings Plans coverage",
                "that are NOT in our service constants:",
                "",
            ]
        )
        for svc in sorted(unknown_services):
            email_lines.append(f"  - {svc}")
        email_lines.extend(
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
            email_lines.append(f"   - {svc}")
        email_lines.extend(
            [
                "",
                "   Please update lambda/shared/spending_analyzer.py",
                "",
                "=" * 50,
                "",
            ]
        )

    email_lines.extend(
        [
            "CANCELLATION INSTRUCTIONS:",
            "To cancel these purchases before they execute:",
            "1. Purge the SQS queue to remove all pending purchase intents",
            f"2. Queue URL: {config.get('queue_url', 'N/A')}",
            "3. AWS CLI command:",
            f"   aws sqs purge-queue --queue-url {config.get('queue_url', 'QUEUE_URL')}",
            "",
            "These purchases will be executed by the Purchaser Lambda.",
            "Monitor CloudWatch Logs and SNS notifications for execution results.",
        ]
    )

    message = "\n".join(email_lines)

    # Skip SNS publishing in local mode
    if local_mode.is_local_mode():
        logger.info("LOCAL MODE: Skipping SNS publish. Email content:")
        logger.info("=" * 60)
        logger.info(message)
        logger.info("=" * 60)
        return

    # Publish to SNS
    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="Savings Plans Scheduled for Purchase",
            Message=message,
        )
        logger.info(f"Email sent successfully to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send email: {e!s}")
        raise

    # Send Slack notification with interactive buttons (non-fatal if it fails)
    try:
        slack_webhook_url = config.get("slack_webhook_url")
        if slack_webhook_url:
            # Format Slack message body
            slack_body_lines = [
                f"*Total Plans Queued:* {len(purchase_plans)}",
                "",
            ]

            # Add coverage info if available
            if coverage is not None:
                slack_body_lines.extend(
                    [
                        "*Current Coverage:*",
                        f"• Compute SP: {coverage.get('compute', 0):.2f}%",
                        f"• Database SP: {coverage.get('database', 0):.2f}%",
                        f"• SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
                        "",
                        f"*Target Coverage:* {config.get('coverage_target_percent', 90):.2f}%",
                        "",
                    ]
                )

            # Add purchase plan summary
            slack_body_lines.append("*Scheduled Purchase Plans:*")
            for i, plan in enumerate(purchase_plans, 1):
                sp_type = plan.get("sp_type", "unknown")
                hourly_commitment = plan.get("hourly_commitment", 0.0)
                term = plan.get("term", "unknown")
                payment_option = plan.get("payment_option", "ALL_UPFRONT")
                annual_cost = hourly_commitment * 8760

                slack_body_lines.extend(
                    [
                        f"{i}. *{sp_type.upper()}* Savings Plan",
                        f"   • Hourly: ${hourly_commitment:.4f}/hour",
                        f"   • Term: {term}",
                        f"   • Payment: {payment_option}",
                        f"   • Annual Cost: ${annual_cost:,.2f}",
                        "",
                    ]
                )

            # Create Approve/Reject buttons for each purchase plan
            actions = []
            for i, plan in enumerate(purchase_plans):
                client_token = plan.get("client_token", f"unknown_{i}")
                sp_type = plan.get("sp_type", "unknown")

                # Add Approve button
                actions.append(
                    {
                        "text": f"✅ Approve {sp_type.upper()} #{i+1}",
                        "action_id": "approve_purchase",
                        "value": client_token,
                        "style": "primary",
                    }
                )

                # Add Reject button
                actions.append(
                    {
                        "text": f"❌ Reject {sp_type.upper()} #{i+1}",
                        "action_id": "reject_purchase",
                        "value": client_token,
                        "style": "danger",
                    }
                )

            # Format and send Slack message with interactive buttons
            slack_message = notifications.format_slack_message_with_actions(
                subject="Savings Plans Scheduled for Purchase",
                body_lines=slack_body_lines,
                actions=actions,
                severity="warning",
            )

            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Slack notification with interactive buttons sent successfully")
            else:
                logger.warning("Slack notification failed (non-fatal)")
    except Exception as e:
        logger.warning(f"Slack notification error (non-fatal): {e!s}")


def send_dry_run_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
    unknown_services: list[str] | None = None,
) -> None:
    """
    Send email notification for dry run analysis.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        purchase_plans: List of what would be purchased
        coverage: Current coverage (None for follow_aws strategy)
        unknown_services: List of unknown services found (optional)
    """
    logger.info("Sending dry run email")

    # Format email body
    email_lines = [
        "***** DRY RUN MODE ***** Savings Plans Analysis",
        "=" * 50,
        "",
        "*** NO PURCHASES WERE SCHEDULED ***",
        "",
        f"Total Plans Analyzed: {len(purchase_plans)}",
        "",
    ]

    # Add coverage info if available (fixed/dichotomy strategies)
    if coverage is not None:
        email_lines.extend(
            [
                "Current Coverage:",
                f"  Compute SP:  {coverage.get('compute', 0):.2f}%",
                f"  Database SP: {coverage.get('database', 0):.2f}%",
                f"  SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
                "",
                f"Target Coverage: {config.get('coverage_target_percent', 90):.2f}%",
                "",
            ]
        )

    email_lines.extend(
        [
            "Purchase Plans (WOULD BE SCHEDULED if dry_run=false):",
            "-" * 50,
        ]
    )

    # Add details for each purchase plan
    total_annual_cost = 0.0

    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get("sp_type", "unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term = plan.get("term", "unknown")
        payment_option = plan.get("payment_option", "ALL_UPFRONT")

        # Calculate estimated annual cost (hourly * 24 * 365)
        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        email_lines.extend(
            [
                f"{i}. {sp_type.upper()} Savings Plan",
                f"   Hourly Commitment: ${hourly_commitment:.4f}/hour",
                f"   Term: {term}",
                f"   Payment Option: {payment_option}",
                f"   Estimated Annual Cost: ${annual_cost:,.2f}",
                "",
            ]
        )

    email_lines.extend(
        [
            "-" * 50,
            f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
            "",
        ]
    )

    # Add warning if unknown services detected
    if unknown_services:
        email_lines.extend(
            [
                "⚠️  WARNING: UNKNOWN SERVICES DETECTED",
                "=" * 50,
                "",
                f"Found {len(unknown_services)} service(s) with Savings Plans coverage",
                "that are NOT in our service constants:",
                "",
            ]
        )
        for svc in sorted(unknown_services):
            email_lines.append(f"  - {svc}")
        email_lines.extend(
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
            email_lines.append(f"   - {svc}")
        email_lines.extend(
            [
                "",
                "   Please update lambda/shared/spending_analyzer.py",
                "",
                "=" * 50,
                "",
            ]
        )

    email_lines.extend(
        [
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
        ]
    )

    message = "\n".join(email_lines)

    # Skip SNS publishing in local mode
    if local_mode.is_local_mode():
        logger.info("LOCAL MODE: Skipping SNS publish. Dry run email content:")
        logger.info("=" * 60)
        logger.info(message)
        logger.info("=" * 60)
        return

    # Publish to SNS
    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="[DRY RUN] Savings Plans Analysis - No Purchases Scheduled",
            Message=message,
        )
        logger.info(f"Dry run email sent successfully to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send dry run email: {e!s}")
        raise
