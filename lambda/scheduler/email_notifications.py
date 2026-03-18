"""
Email notification module for Scheduler Lambda.

Provides email formatting and sending functionality for scheduled
purchase notifications.
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


def _format_plans_block(
    purchase_plans: list[dict[str, Any]],
    coverage: dict[str, float] | None,
) -> list[str]:
    lines: list[str] = []
    total_annual_cost = 0.0

    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get("sp_type", "unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term = plan.get("term", "unknown")
        payment_option = plan.get("payment_option", "ALL_UPFRONT")
        savings_pct = plan.get("estimated_savings_percentage", 0.0)

        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        target = plan.get("details", {}).get("coverage", {}).get("target")
        current_cov = coverage.get(sp_type, 0) if coverage else 0

        purchase_pct = plan.get("purchase_percent", 0.0)

        plan_lines = [f"{i}. {sp_type.upper()} Savings Plan"]
        if target is not None:
            plan_lines.append(f"   Target Coverage:       {target:.2f}%")
        plan_lines.append(f"   Current Coverage:      {current_cov:.2f}%")
        plan_lines.append(f"   Added Coverage:        {purchase_pct:.2f}%")
        plan_lines.append(f"   Added Commitment:      ${hourly_commitment:.5f}/hour")
        plan_lines.append(f"   Term:                  {term}")
        plan_lines.append(f"   Payment Option:        {payment_option}")
        plan_lines.append(f"   Estimated Annual Cost: ${annual_cost:,.2f}")
        if savings_pct > 0:
            od_equivalent = hourly_commitment / (1 - savings_pct / 100)
            annual_savings = (od_equivalent - hourly_commitment) * 8760
            plan_lines.append(
                f"   Estimated Savings:     ${annual_savings:,.2f}/year ({savings_pct:.1f}% discount)"
            )
        plan_lines.append("")
        lines.extend(plan_lines)

    lines.extend(
        [
            "-" * 50,
            f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
            "",
        ]
    )
    return lines


def _format_strategy_warnings(
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
) -> list[str]:
    """Format warnings about the selected target and split strategies."""
    lines: list[str] = []
    lines.extend(_format_target_strategy_warning(config, purchase_plans))
    lines.extend(_format_split_strategy_warning(config))
    return lines


def _format_target_strategy_warning(
    config: dict[str, Any],
    purchase_plans: list[dict[str, Any]],
) -> list[str]:
    """Format warning about the target strategy."""
    target = config.get("target_strategy_type")

    if target == "static":
        return _format_static_target_warning(purchase_plans)
    if target == "aws":
        return _format_aws_target_warning()
    return []


def _format_static_target_warning(
    purchase_plans: list[dict[str, Any]],
) -> list[str]:
    warnings = []
    for plan in purchase_plans:
        for w in plan.get("static_warnings", []):
            if w not in warnings:
                warnings.append(w)

    lines = [
        "⚠️  TARGET STRATEGY: STATIC — OVER-COMMITMENT RISK",
        "=" * 50,
        "",
        "The static strategy uses a fixed $/h target that does NOT adapt",
        "to your actual usage. If your workloads change, you may be paying",
        "for unused commitment with no way to cancel.",
        "",
    ]

    for w in warnings:
        sp = w["sp_type"].upper()
        if w["level"] == "critical":
            lines.append(
                f"  🔴 {sp}: Target ${w['target']:.4f}/h EXCEEDS actual spend "
                f"${w['avg_hourly']:.4f}/h ({w['ratio']:.1f}x over-committed)"
            )
        else:
            lines.append(
                f"  🟡 {sp}: Target ${w['target']:.4f}/h is near actual spend "
                f"${w['avg_hourly']:.4f}/h — at risk if usage drops"
            )

    if warnings:
        lines.append("")

    lines.extend(
        [
            "RECOMMENDATION: Switch to the 'dynamic' strategy which automatically",
            "derives targets from actual usage patterns and adjusts as workloads change.",
            '  target_strategy_type = "dynamic"',
            "",
            "=" * 50,
            "",
        ]
    )
    return lines


def _format_aws_target_warning() -> list[str]:
    return [
        "NOTE — TARGET STRATEGY: AWS RECOMMENDATIONS",
        "=" * 50,
        "",
        "AWS Cost Explorer recommendations tend to use conservative discount",
        "assumptions, which can lead to higher commitment amounts than needed.",
        "The actual discount you receive is often better than what AWS estimates,",
        "meaning you may end up over-committed.",
        "",
        "RECOMMENDATION: Consider the 'dynamic' strategy which derives targets",
        "from your actual usage and observed discount rates, giving you more",
        "accurate commitment sizing.",
        '  target_strategy_type = "dynamic"',
        "",
        "=" * 50,
        "",
    ]


def _format_split_strategy_warning(config: dict[str, Any]) -> list[str]:
    """Format warning about the split strategy."""
    split = config.get("split_strategy_type")

    if split != "one_shot":
        return []

    return [
        "NOTE — SPLIT STRATEGY: ONE SHOT",
        "=" * 50,
        "",
        "The one_shot split is the fastest way to reach your target — it purchases",
        "the entire gap in a single cycle. However, this means a full commitment",
        "with no opportunity to observe and adjust if usage changes.",
        "",
        "RECOMMENDATION: Consider gap_split which distributes purchases evenly",
        "over time. It covers 50% of the gap on the first cycle, 75% after two",
        "cycles, and converges smoothly toward the target — balancing speed with",
        "the ability to adapt to changing workloads.",
        '  split_strategy_type = "gap_split"',
        "",
        "=" * 50,
        "",
    ]


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
            "   Please add them to the appropriate constant in lambda/shared/spending_analyzer.py:",
            "   - COMPUTE_SP_SERVICES (EC2, Lambda, Fargate)",
            "   - DATABASE_SP_SERVICES (RDS, DynamoDB, ElastiCache, etc.)",
            "   - SAGEMAKER_SP_SERVICES (SageMaker)",
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
        *_format_strategy_warnings(config, purchase_plans),
        *header_lines,
        plans_heading,
        "-" * 50,
        *_format_plans_block(purchase_plans, coverage),
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
            f"2. Queue URL: {config['queue_url']}",
            "3. AWS CLI command:",
            f"   aws sqs purge-queue --queue-url {config['queue_url']}",
            "",
            "These purchases will be executed by the Purchaser Lambda.",
            "Monitor CloudWatch Logs and SNS notifications for execution results.",
        ],
        subject="Savings Plans Scheduled for Purchase",
        log_label="Scheduled",
    )


def send_spike_guard_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked_plans: list[dict[str, Any]],
    guard_results: dict[str, dict[str, Any]],
) -> None:
    """Send notification that purchases were blocked due to usage spike."""
    logger.info("Sending spike guard email")

    flagged_types = {p.get("sp_type") for p in blocked_plans}
    lines = [
        "⚠️  USAGE SPIKE DETECTED — Purchases Blocked",
        "=" * 50,
        "",
        f"{len(blocked_plans)} purchase plan(s) were blocked because recent usage is abnormally high.",
        "This prevents over-committing to Savings Plans based on temporary spikes",
        "(e.g. Black Friday, seasonal peaks, one-off migrations).",
        "",
        "Spike Details:",
        "-" * 50,
    ]

    for sp_type in sorted(flagged_types):
        result = guard_results.get(sp_type, {})
        lines.extend(
            [
                f"  {sp_type.upper()} Savings Plan:",
                f"    Long-term avg: ${result.get('long_term_avg', 0):.4f}/hour",
                f"    Short-term avg: ${result.get('short_term_avg', 0):.4f}/hour",
                f"    Spike: +{result.get('change_percent', 0):.1f}%",
                "",
            ]
        )

    lines.extend(
        [
            "Blocked Purchase Plans:",
            "-" * 50,
        ]
    )

    for i, plan in enumerate(blocked_plans, 1):
        lines.extend(
            [
                f"  {i}. {plan.get('sp_type', 'unknown').upper()} — "
                f"${plan.get('hourly_commitment', 0):.5f}/hour",
            ]
        )

    lines.extend(
        [
            "",
            "These purchases were NOT scheduled. Non-flagged SP types (if any) proceeded normally.",
            "",
            "To adjust sensitivity, modify spike_guard settings in your Terraform configuration:",
            "  purchase_strategy.spike_guard.threshold_percent (currently "
            f"{config['spike_guard_threshold_percent']}%)",
            "  purchase_strategy.spike_guard.enabled = false  (to disable entirely)",
        ]
    )

    message = "\n".join(lines)

    if local_mode.is_local_mode():
        logger.info("LOCAL MODE: Skipping SNS publish. Usage guard email content:")
        logger.info("=" * 60)
        logger.info(message)
        logger.info("=" * 60)
        return

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked (Usage Spike Detected)",
            Message=message,
        )
        logger.info(f"Usage guard email sent to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send spike guard email: {e!s}")
        raise


def send_cooldown_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked_plans: list[dict[str, Any]],
    cooldown_types: set[str],
) -> None:
    """Send notification that purchases were blocked due to purchase cooldown."""
    logger.info("Sending cooldown email")
    cooldown_days = config["purchase_cooldown_days"]

    lines = [
        "⏳  PURCHASE COOLDOWN — Purchases Blocked",
        "=" * 50,
        "",
        f"{len(blocked_plans)} purchase plan(s) were blocked because a Savings Plan",
        f"of the same type was purchased within the last {cooldown_days} days.",
        "This prevents double-purchasing while Cost Explorer data settles (24-48h lag).",
        "",
        f"SP Types in Cooldown: {', '.join(sorted(t.upper() for t in cooldown_types))}",
        "",
        "Blocked Purchase Plans:",
        "-" * 50,
    ]

    for i, plan in enumerate(blocked_plans, 1):
        lines.append(
            f"  {i}. {plan.get('sp_type', 'unknown').upper()} — "
            f"${plan.get('hourly_commitment', 0):.5f}/hour"
        )

    lines.extend(
        [
            "",
            "These purchases were NOT scheduled. Non-cooldown SP types (if any) proceeded normally.",
            "",
            "To adjust cooldown duration, modify purchase_cooldown_days in your Terraform configuration.",
        ]
    )

    message = "\n".join(lines)

    if local_mode.is_local_mode():
        logger.info("LOCAL MODE: Skipping SNS publish. Cooldown email content:")
        logger.info("=" * 60)
        logger.info(message)
        logger.info("=" * 60)
        return

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked (Cooldown)",
            Message=message,
        )
        logger.info(f"Cooldown email sent to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send cooldown email: {e!s}")
        raise
