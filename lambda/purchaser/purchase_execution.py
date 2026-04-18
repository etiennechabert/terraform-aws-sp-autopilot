"""Purchase execution + summary email for the Purchaser Lambda."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError
from validation import validate_purchase_intent

from shared.queue_adapter import QueueAdapter


if TYPE_CHECKING:
    from mypy_boto3_savingsplans.client import SavingsPlansClient
    from mypy_boto3_sns.client import SNSClient


logger = logging.getLogger(__name__)


def process_purchase_messages(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate, execute, and delete each queued intent; return per-status buckets."""
    logger.info(f"Processing {len(messages)} purchase messages")

    results: dict[str, Any] = {
        "successful": [],
        "skipped": [],
        "failed": [],
        "successful_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }

    for message in messages:
        try:
            purchase_intent = json.loads(message["Body"])

            try:
                validate_purchase_intent(purchase_intent)
            except ValueError as e:
                logger.error(f"Message validation failed: {e!s}")
                results["failed"].append(
                    {"intent": purchase_intent, "error": f"Validation error: {e!s}"}
                )
                results["failed_count"] += 1
                continue  # Leave in queue for retry.

            sp_id = execute_purchase(clients["savingsplans"], config, purchase_intent)
            logger.info(f"Purchase successful: {sp_id}")
            results["successful"].append({"intent": purchase_intent, "sp_id": sp_id})
            results["successful_count"] += 1

            QueueAdapter(sqs_client=clients["sqs"], queue_url=config["queue_url"]).delete_message(
                message["ReceiptHandle"]
            )

        except ClientError as e:
            logger.error(f"Failed to process purchase: {e!s}")
            results["failed"].append(
                {
                    "intent": purchase_intent if "purchase_intent" in locals() else {},
                    "error": str(e),
                }
            )
            results["failed_count"] += 1

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e!s}")
            results["failed"].append({"error": str(e)})
            results["failed_count"] += 1

    logger.info(
        f"Processing complete - Successful: {results['successful_count']}, "
        f"Skipped: {results['skipped_count']}, Failed: {results['failed_count']}"
    )
    return results


def execute_purchase(
    savingsplans_client: SavingsPlansClient,
    config: dict[str, Any],
    purchase_intent: dict[str, Any],
) -> str:
    """Call CreateSavingsPlan and return the new savingsPlanId."""
    client_token = purchase_intent.get("client_token")
    offering = purchase_intent.get("offering", {})
    offering_id = (
        offering.get("id") if isinstance(offering, dict) else purchase_intent.get("offering_id")
    )
    commitment = purchase_intent.get("commitment")
    upfront_amount = purchase_intent.get("upfront_amount")

    logger.info(f"Executing purchase: {client_token}")
    logger.info(f"Offering: {offering}, Commitment: ${commitment}/hr")

    tags = {
        "ManagedBy": "terraform-aws-sp-autopilot",
        "PurchaseDate": datetime.now(UTC).isoformat(),
        "ClientToken": client_token,
    }
    tags.update(config["tags"])

    create_params: dict[str, Any] = {
        "savingsPlanOfferingId": offering_id,
        "commitment": commitment,
        "clientToken": client_token,
        "tags": tags,
    }
    if upfront_amount is not None and float(upfront_amount) > 0:
        create_params["upfrontPaymentAmount"] = upfront_amount
        logger.info(f"Including upfront payment: ${upfront_amount}")

    logger.info(f"Calling CreateSavingsPlan API with offering={offering}")
    try:
        response = savingsplans_client.create_savings_plan(**create_params)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"CreateSavingsPlan failed - Code: {error_code}, Message: {error_message}")
        raise

    sp_id = response.get("savingsPlanId")
    logger.info(f"Purchase executed successfully: {sp_id}")
    return sp_id


def send_summary_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    results: dict[str, Any],
    coverage: dict[str, float],
) -> None:
    """Publish an SNS summary of per-intent outcomes and post-run coverage."""
    logger.info("Sending summary email")
    execution_time = datetime.now(UTC).isoformat()

    total = results["successful_count"] + results["skipped_count"] + results["failed_count"]
    subject = (
        f"AWS Savings Plans Purchase Complete - "
        f"{results['successful_count']} Executed, "
        f"{results['skipped_count']} Skipped, "
        f"{results['failed_count']} Failed"
    )

    body_lines = [
        "AWS Savings Plans Purchaser - Execution Summary",
        "=" * 60,
        f"Execution Time: {execution_time}",
        f"Total Purchase Intents Processed: {total}",
        f"Successful Purchases: {results['successful_count']}",
        f"Skipped Purchases: {results['skipped_count']}",
        f"Failed Purchases: {results['failed_count']}",
        "",
        "Current Coverage After Execution:",
        f"  Compute Savings Plans: {coverage.get('compute', 0):.2f}%",
        f"  Database Savings Plans: {coverage.get('database', 0):.2f}%",
        f"  SageMaker Savings Plans: {coverage.get('sagemaker', 0):.2f}%",
        "",
    ]

    _append_successful_section(body_lines, results["successful"])
    _append_skipped_section(body_lines, results["skipped"])
    _append_failed_section(body_lines, results["failed"])

    body_lines.extend(
        [
            "-" * 60,
            "This is an automated message from AWS Savings Plans Automation.",
        ]
    )

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"], Subject=subject, Message="\n".join(body_lines)
        )
        logger.info("Summary email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send summary email: {e!s}")
        raise


def _term_string(term_seconds: int) -> str:
    term_years = term_seconds / (365.25 * 24 * 3600)
    return f"{term_years:.0f}-year" if term_years == int(term_years) else f"{term_years:.1f}-year"


def _sp_type_display(sp_type: str) -> str:
    return sp_type.replace("SavingsPlans", " SP")


def _append_successful_section(lines: list[str], successful: list[dict[str, Any]]) -> None:
    if not successful:
        lines.append("No successful purchases.")
        lines.append("")
        return

    lines.append("SUCCESSFUL PURCHASES:")
    lines.append("-" * 60)
    for i, purchase in enumerate(successful, 1):
        intent = purchase["intent"]
        sp_id = purchase["sp_id"]
        offering = intent.get("offering", {})
        offering_desc = offering.get("description", "") if isinstance(offering, dict) else ""

        lines.extend(
            [
                f"{i}. {_sp_type_display(intent['sp_type'])}",
                f"   Savings Plan ID: {sp_id}",
                f"   Commitment: ${intent['commitment']}/hour",
                f"   Term: {_term_string(intent['term_seconds'])}",
                f"   Payment Option: {intent['payment_option']}",
            ]
        )
        if offering_desc:
            lines.append(f"   Offering: {offering_desc}")
        if intent.get("upfront_amount") and float(intent["upfront_amount"]) > 0:
            lines.append(f"   Upfront Payment: ${float(intent['upfront_amount']):,.2f}")
        if intent.get("strategy"):
            lines.append(f"   Strategy: {intent['strategy']}")
        if intent.get("estimated_savings_percentage") is not None:
            lines.append(f"   Estimated Savings: {intent['estimated_savings_percentage']}%")

        cov = intent.get("details", {}).get("coverage", {})
        if cov.get("current") is not None and cov.get("added") is not None:
            projected = cov["current"] + cov["added"]
            lines.append(
                f"   Coverage: {cov['current']:.2f}% -> {projected:.2f}% (+{cov['added']:.2f}%)"
            )

        lines.append("")


def _append_skipped_section(lines: list[str], skipped: list[dict[str, Any]]) -> None:
    if not skipped:
        lines.append("No skipped purchases.")
        lines.append("")
        return

    lines.append("SKIPPED PURCHASES:")
    lines.append("-" * 60)
    for i, skip in enumerate(skipped, 1):
        intent = skip["intent"]
        lines.extend(
            [
                f"{i}. {_sp_type_display(intent['sp_type'])}",
                f"   Commitment: ${intent['commitment']}/hour",
                f"   Term: {_term_string(intent['term_seconds'])}",
                f"   Reason: {skip['reason']}",
                "",
            ]
        )


def _append_failed_section(lines: list[str], failed: list[dict[str, Any]]) -> None:
    if not failed:
        lines.append("No failed purchases.")
        lines.append("")
        return

    lines.append("FAILED PURCHASES:")
    lines.append("-" * 60)
    for i, failure in enumerate(failed, 1):
        error = failure.get("error", "Unknown error")
        intent = failure.get("intent", {})
        if intent:
            lines.extend(
                [
                    f"{i}. Error: {error}",
                    f"   SP Type: {intent.get('sp_type', 'Unknown')}",
                    f"   Commitment: ${intent.get('commitment', 'Unknown')}/hour",
                    "",
                ]
            )
        else:
            lines.extend([f"{i}. Error: {error}", ""])
