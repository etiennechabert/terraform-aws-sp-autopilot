"""
Purchaser Lambda - Executes Savings Plan purchases from queued intents.

This Lambda:
1. Checks SQS queue for purchase intents
2. Gets current coverage (excluding plans expiring within renewal_window_days)
3. Processes each message:
   - Validates message schema
   - Executes purchase via CreateSavingsPlan API
   - Deletes message on success
4. Sends aggregated email with results
5. Handles errors with immediate notification
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient
    from mypy_boto3_sns.client import SNSClient
    from mypy_boto3_sqs.client import SQSClient
from validation import validate_purchase_intent

from shared import constants, handler_utils
from shared.queue_adapter import QueueAdapter


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_configuration() -> dict[str, Any]:
    """Load configuration - backward compatible wrapper."""
    from config import load_configuration as config_load

    return config_load()


@handler_utils.lambda_handler_wrapper("Purchaser")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main handler for Purchaser Lambda.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        dict: Status and summary of purchases

    Raises:
        Exception: Raised on API errors (no silent failures)
    """
    try:
        # Load configuration from environment
        config = load_configuration()

        # Create error callback function
        def send_error_email(error_msg: str) -> None:
            """Send error notification using shared utility."""
            # Get SNS client directly (before full client initialization)
            sns = boto3.client("sns")
            handler_utils.send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=error_msg,
                lambda_name="Purchaser",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )

        # Initialize clients (with assume role if configured)
        clients = handler_utils.initialize_clients(
            config,
            session_name="sp-autopilot-purchaser",
            error_callback=send_error_email,
        )

        # Step 1: Check queue
        messages = receive_messages(clients["sqs"], config["queue_url"])

        # If queue is empty, exit silently (no email, no error)
        if not messages:
            logger.info("Queue is empty - exiting silently")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No purchases to process", "purchases_executed": 0}),
            }

        logger.info(f"Found {len(messages)} purchase intents in queue")

        # Step 1.5: Run purchasing spike guard
        if config["spike_guard_enabled"]:
            messages = _run_purchasing_spike_guard(clients, config, messages)
            if not messages:
                logger.info("All messages blocked by spike guard - exiting")
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "All purchases blocked by spike guard",
                            "purchases_executed": 0,
                        }
                    ),
                }

        # Step 1.6: Per-type purchase cooldown
        cooldown_days = config["purchase_cooldown_days"]
        if cooldown_days > 0:
            messages = _run_purchase_cooldown(clients, config, messages, cooldown_days)
            if not messages:
                logger.info("All messages blocked by purchase cooldown - exiting")
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "All purchases blocked by cooldown",
                            "purchases_executed": 0,
                        }
                    ),
                }

        # Step 2: Get current coverage
        coverage = get_current_coverage(clients, config)
        logger.info(
            f"Current coverage - Compute: {coverage.get('compute', 0)}%, Database: {coverage.get('database', 0)}%, SageMaker: {coverage.get('sagemaker', 0)}%"
        )

        # Step 3: Process each message
        results = process_purchase_messages(clients, config, messages, coverage)

        # Step 4: Send aggregated email
        send_summary_email(clients["sns"], config, results, coverage)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Purchaser completed successfully",
                    "purchases_executed": results["successful_count"],
                    "purchases_skipped": results["skipped_count"],
                }
            ),
        }

    except Exception as e:
        # Try to send error notification
        try:
            config = load_configuration()
            sns = boto3.client("sns")
            handler_utils.send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=str(e),
                lambda_name="Purchaser",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )
        except Exception as notification_error:
            logger.warning(f"Failed to send error notification: {notification_error}")
        raise  # Re-raise to ensure Lambda fails visibly


def receive_messages(
    sqs_client: SQSClient, queue_url: str, max_messages: int = 10
) -> list[dict[str, Any]]:
    """
    Receive messages from queue.
    Supports both AWS SQS and local filesystem modes.

    Args:
        sqs_client: Boto3 SQS client (not used in local mode)
        queue_url: SQS queue URL (not used in local mode)
        max_messages: Maximum number of messages to retrieve

    Returns:
        list: List of messages
    """
    logger.info(f"Receiving messages from queue: {queue_url}")

    try:
        queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)
        messages = queue_adapter.receive_messages(max_messages=max_messages)
        logger.info(f"Received {len(messages)} messages from queue")
        return messages

    except ClientError as e:
        logger.error(f"Failed to receive messages: {e!s}")
        raise


def get_current_coverage(clients: dict[str, Any], config: dict[str, Any]) -> dict[str, float]:
    """
    Calculate current Savings Plans coverage, excluding plans expiring soon.

    Args:
        clients: Dictionary of AWS clients
        config: Configuration dictionary

    Returns:
        dict: Coverage percentages by SP type
    """
    logger.info("Calculating current coverage")

    try:
        # Get date range for coverage query using configured lookback period
        # Cost Explorer has 24-48 hour data lag, so we query multiple days for stability
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = today
        start_time = end_time - timedelta(hours=config["lookback_hours"])

        # Get raw coverage from Cost Explorer
        raw_coverage = get_ce_coverage(clients["ce"], start_time, end_time, config)

        # Get existing Savings Plans
        expiring_plans = get_expiring_plans(clients["savingsplans"], config)

        # Adjust coverage to exclude expiring plans
        adjusted_coverage = adjust_coverage_for_expiring_plans(raw_coverage, expiring_plans)

        logger.info(
            f"Coverage calculated: Compute={adjusted_coverage['compute']:.2f}%, Database={adjusted_coverage['database']:.2f}%, SageMaker={adjusted_coverage['sagemaker']:.2f}%"
        )
        logger.info(f"Expiring plans excluded: {len(expiring_plans)} plans")

        return adjusted_coverage

    except ClientError as e:
        logger.error(f"Failed to calculate coverage: {e!s}")
        raise


def get_ce_coverage(
    ce_client: CostExplorerClient,
    start_time: datetime,
    end_time: datetime,
    _config: dict[str, Any],
) -> dict[str, Any]:
    """
    Get Savings Plans coverage from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client
        start_time: Start datetime for coverage period
        end_time: End datetime for coverage period
        config: Configuration dictionary

    Returns:
        dict: Raw coverage data by SP type
    """
    logger.info(f"Getting coverage from Cost Explorer for {start_time.date()} to {end_time.date()}")

    try:
        date_format = "%Y-%m-%dT%H:%M:%SZ"

        response = ce_client.get_savings_plans_coverage(
            TimePeriod={
                "Start": start_time.strftime(date_format),
                "End": end_time.strftime(date_format),
            },
            Granularity="HOURLY",
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Get most recent spend data for each service
        # When using GroupBy, AWS flattens the response: each item represents one service for one day
        # Iterate backwards to find the latest data point for each service
        service_latest_spend = {}

        for item in reversed(response.get("SavingsPlansCoverages", [])):
            service_name = item.get("Attributes", {}).get("SERVICE", "").lower()

            # Skip if we already found this service's latest data
            if service_name in service_latest_spend:
                continue

            coverage_data = item.get("Coverage", {})

            # When using GroupBy, AWS returns spend amounts, not percentages
            spend_covered = float(coverage_data.get("SpendCoveredBySavingsPlans", 0))
            on_demand_cost = float(coverage_data.get("OnDemandCost", 0))

            service_latest_spend[service_name] = {
                "covered": spend_covered,
                "on_demand": on_demand_cost,
            }

        # Aggregate spend amounts by SP type, then calculate coverage percentage
        sp_type_spend = {
            "compute": {"covered": 0.0, "on_demand": 0.0},
            "database": {"covered": 0.0, "on_demand": 0.0},
            "sagemaker": {"covered": 0.0, "on_demand": 0.0},
        }

        for service_name, spend in service_latest_spend.items():
            # Compute Savings Plans cover: EC2, Lambda, Fargate, ECS, EKS
            if any(
                svc in service_name
                for svc in [
                    "ec2",
                    "elastic compute cloud",
                    "lambda",
                    "fargate",
                    "elastic container service",
                ]
            ):
                sp_type_spend["compute"]["covered"] += spend["covered"]
                sp_type_spend["compute"]["on_demand"] += spend["on_demand"]
            # SageMaker Savings Plans cover: SageMaker
            elif "sagemaker" in service_name:
                sp_type_spend["sagemaker"]["covered"] += spend["covered"]
                sp_type_spend["sagemaker"]["on_demand"] += spend["on_demand"]
            # Database: RDS, DynamoDB, Database Migration Service
            elif any(
                svc in service_name
                for svc in [
                    "rds",
                    "relational database",
                    "dynamodb",
                    "database migration",
                ]
            ):
                sp_type_spend["database"]["covered"] += spend["covered"]
                sp_type_spend["database"]["on_demand"] += spend["on_demand"]

        # Calculate coverage percentages from aggregated spend
        coverage = {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        for sp_type, spend in sp_type_spend.items():
            total_spend = spend["covered"] + spend["on_demand"]
            if total_spend > 0:
                coverage[sp_type] = (spend["covered"] / total_spend) * 100

        logger.info(
            f"Raw coverage from CE: Compute={coverage['compute']:.2f}%, Database={coverage['database']:.2f}%, SageMaker={coverage['sagemaker']:.2f}%"
        )
        return coverage

    except ClientError as e:
        logger.error(f"Failed to get Cost Explorer coverage: {e!s}")
        raise


def get_expiring_plans(
    savingsplans_client: SavingsPlansClient, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Get list of Savings Plans expiring within renewal_window_days.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        config: Configuration dictionary

    Returns:
        list: List of expiring Savings Plans
    """
    renewal_window_days = config["renewal_window_days"]
    logger.info(f"Getting Savings Plans expiring within {renewal_window_days} days")

    try:
        # Get all active Savings Plans
        response = savingsplans_client.describe_savings_plans(states=["active"])

        # Calculate expiration threshold
        expiration_threshold = datetime.now(UTC) + timedelta(days=renewal_window_days)

        # Filter to plans expiring within the window
        expiring_plans = []
        for plan in response.get("savingsPlans", []):
            end_time = datetime.fromisoformat(plan["end"].replace("Z", "+00:00"))

            if end_time <= expiration_threshold:
                expiring_plans.append(
                    {
                        "savingsPlanId": plan["savingsPlanId"],
                        "savingsPlanType": plan["savingsPlanType"],
                        "commitment": float(plan["commitment"]),
                        "end": plan["end"],
                    }
                )

        logger.info(f"Found {len(expiring_plans)} plans expiring within {renewal_window_days} days")
        return expiring_plans

    except ClientError as e:
        logger.error(f"Failed to get Savings Plans: {e!s}")
        raise


def adjust_coverage_for_expiring_plans(
    raw_coverage: dict[str, float], expiring_plans: list[dict[str, Any]]
) -> dict[str, float]:
    """
    Adjust coverage by excluding expiring plans.

    Since expiring plans are still active but should be treated as if expired,
    we return 0% coverage if ANY plans are expiring. This forces recalculation
    of their coverage need.

    Args:
        raw_coverage: Raw coverage percentages from Cost Explorer
        expiring_plans: List of plans expiring within renewal window

    Returns:
        dict: Adjusted coverage percentages by type
    """
    adjusted_coverage = raw_coverage.copy()

    # Map plan types to coverage keys
    plan_type_mapping = {
        constants.SP_FILTER_COMPUTE: ("compute", "Compute"),
        constants.SP_FILTER_DATABASE: ("database", "Database"),
        constants.SP_FILTER_SAGEMAKER: ("sagemaker", "SageMaker"),
    }

    # Check each plan type and adjust coverage if expiring plans exist
    for plan_type, (coverage_key, display_name) in plan_type_mapping.items():
        if any(p["savingsPlanType"] == plan_type for p in expiring_plans):
            logger.info(
                f"{display_name} Savings Plans expiring - setting coverage to 0% to force renewal"
            )
            adjusted_coverage[coverage_key] = 0.0

    return adjusted_coverage


def process_purchase_messages(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
    initial_coverage: dict[str, float],
) -> dict[str, Any]:
    """
    Process all purchase messages from the queue.

    Args:
        clients: Dictionary of AWS clients
        config: Configuration dictionary
        messages: List of SQS messages
        initial_coverage: Current coverage before purchases

    Returns:
        dict: Results summary with successful and skipped purchases
    """
    logger.info(f"Processing {len(messages)} purchase messages")

    results = {
        "successful": [],
        "skipped": [],
        "failed": [],
        "successful_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }

    for message in messages:
        try:
            # Parse message body
            purchase_intent = json.loads(message["Body"])

            # Validate message schema
            try:
                validate_purchase_intent(purchase_intent)
            except ValueError as e:
                logger.error(f"Message validation failed: {e!s}")
                results["failed"].append(
                    {"intent": purchase_intent, "error": f"Validation error: {e!s}"}
                )
                results["failed_count"] += 1
                # Message stays in queue for retry - do not delete
                continue

            # Execute purchase
            sp_id = execute_purchase(clients["savingsplans"], config, purchase_intent)
            logger.info(f"Purchase successful: {sp_id}")

            results["successful"].append({"intent": purchase_intent, "sp_id": sp_id})
            results["successful_count"] += 1

            # Delete message after successful purchase
            delete_message(clients["sqs"], config["queue_url"], message["ReceiptHandle"])

        except ClientError as e:
            logger.error(f"Failed to process purchase: {e!s}")
            results["failed"].append(
                {
                    "intent": purchase_intent if "purchase_intent" in locals() else {},
                    "error": str(e),
                }
            )
            results["failed_count"] += 1
            # Message stays in queue for retry

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e!s}")
            results["failed"].append({"error": str(e)})
            results["failed_count"] += 1
            # Message stays in queue for retry

    logger.info(
        f"Processing complete - Successful: {results['successful_count']}, Skipped: {results['skipped_count']}, Failed: {results['failed_count']}"
    )
    return results


def execute_purchase(
    savingsplans_client: SavingsPlansClient,
    config: dict[str, Any],
    purchase_intent: dict[str, Any],
) -> str:
    """
    Execute a Savings Plan purchase via AWS API.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        config: Configuration dictionary
        purchase_intent: Purchase intent details

    Returns:
        str: Savings Plan ID

    Raises:
        ClientError: If purchase fails
    """
    client_token = purchase_intent.get("client_token")
    offering = purchase_intent.get("offering", {})
    offering_id = (
        offering.get("id") if isinstance(offering, dict) else purchase_intent.get("offering_id")
    )
    commitment = purchase_intent.get("commitment")
    upfront_amount = purchase_intent.get("upfront_amount")

    logger.info(f"Executing purchase: {client_token}")
    logger.info(f"Offering: {offering}, Commitment: ${commitment}/hr")

    try:
        # Prepare tags - merge default tags with custom tags from config
        tags = {
            "ManagedBy": "terraform-aws-sp-autopilot",
            "PurchaseDate": datetime.now(UTC).isoformat(),
            "ClientToken": client_token,
        }
        tags.update(config["tags"])

        # Build CreateSavingsPlan request parameters
        create_params = {
            "savingsPlanOfferingId": offering_id,
            "commitment": commitment,
            "clientToken": client_token,
            "tags": tags,
        }

        # Add upfront payment amount if applicable (for ALL_UPFRONT or PARTIAL_UPFRONT)
        if upfront_amount is not None and float(upfront_amount) > 0:
            create_params["upfrontPaymentAmount"] = upfront_amount
            logger.info(f"Including upfront payment: ${upfront_amount}")

        # Execute CreateSavingsPlan API call
        logger.info(f"Calling CreateSavingsPlan API with offering={offering}")
        response = savingsplans_client.create_savings_plan(**create_params)

        sp_id = response.get("savingsPlanId")
        logger.info(f"Purchase executed successfully: {sp_id}")

        return sp_id

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"CreateSavingsPlan failed - Code: {error_code}, Message: {error_message}")
        raise


def delete_message(sqs_client: SQSClient, queue_url: str, receipt_handle: str) -> None:
    """
    Delete a message from the queue.
    Supports both AWS SQS and local filesystem modes.

    Args:
        sqs_client: Boto3 SQS client (not used in local mode)
        queue_url: SQS queue URL (not used in local mode)
        receipt_handle: Message receipt handle (file path in local mode)
    """
    try:
        queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)
        queue_adapter.delete_message(receipt_handle)
        logger.info("Message deleted from queue")
    except ClientError as e:
        logger.error(f"Failed to delete message: {e!s}")
        raise


def send_summary_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    results: dict[str, Any],
    coverage: dict[str, float],
) -> None:
    """
    Send aggregated summary email for all purchases.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        results: Purchase results
        coverage: Final coverage levels
    """
    logger.info("Sending summary email")

    # Format execution timestamp
    execution_time = datetime.now(UTC).isoformat()

    # Build email subject
    total_purchases = (
        results["successful_count"] + results["skipped_count"] + results["failed_count"]
    )
    subject = f"AWS Savings Plans Purchase Complete - {results['successful_count']} Executed, {results['skipped_count']} Skipped, {results['failed_count']} Failed"

    # Build email body
    body_lines = [
        "AWS Savings Plans Purchaser - Execution Summary",
        "=" * 60,
        f"Execution Time: {execution_time}",
        f"Total Purchase Intents Processed: {total_purchases}",
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

    # Add successful purchases section
    if results["successful"]:
        body_lines.append("SUCCESSFUL PURCHASES:")
        body_lines.append("-" * 60)
        for i, purchase in enumerate(results["successful"], 1):
            intent = purchase["intent"]
            sp_id = purchase["sp_id"]

            # Format term (convert seconds to years)
            term_years = intent["term_seconds"] / (365.25 * 24 * 3600)
            term_str = (
                f"{term_years:.0f}-year"
                if term_years == int(term_years)
                else f"{term_years:.1f}-year"
            )

            # Format SP type (remove "SavingsPlans" suffix for readability)
            sp_type_display = intent["sp_type"].replace("SavingsPlans", " SP")

            offering = intent.get("offering", {})
            offering_desc = offering.get("description", "") if isinstance(offering, dict) else ""

            body_lines.extend(
                [
                    f"{i}. {sp_type_display}",
                    f"   Savings Plan ID: {sp_id}",
                    f"   Commitment: ${intent['commitment']}/hour",
                    f"   Term: {term_str}",
                    f"   Payment Option: {intent['payment_option']}",
                ]
            )
            if offering_desc:
                body_lines.append(f"   Offering: {offering_desc}")

            # Add upfront amount if applicable
            if intent.get("upfront_amount") and float(intent["upfront_amount"]) > 0:
                body_lines.append(f"   Upfront Payment: ${float(intent['upfront_amount']):,.2f}")

            # Add strategy context if available
            if intent.get("strategy"):
                body_lines.append(f"   Strategy: {intent['strategy']}")
            if intent.get("estimated_savings_percentage") is not None:
                body_lines.append(
                    f"   Estimated Savings: {intent['estimated_savings_percentage']}%"
                )
            details = intent.get("details", {})
            coverage = details.get("coverage", {})
            if coverage.get("current") is not None and coverage.get("added") is not None:
                projected = coverage["current"] + coverage["added"]
                body_lines.append(
                    f"   Coverage: {coverage['current']:.2f}% -> {projected:.2f}% (+{coverage['added']:.2f}%)"
                )

            body_lines.append("")
    else:
        body_lines.append("No successful purchases.")
        body_lines.append("")

    # Add skipped purchases section
    if results["skipped"]:
        body_lines.append("SKIPPED PURCHASES:")
        body_lines.append("-" * 60)
        for i, skip in enumerate(results["skipped"], 1):
            intent = skip["intent"]
            reason = skip["reason"]

            # Format term (convert seconds to years)
            term_years = intent["term_seconds"] / (365.25 * 24 * 3600)
            term_str = (
                f"{term_years:.0f}-year"
                if term_years == int(term_years)
                else f"{term_years:.1f}-year"
            )

            # Format SP type
            sp_type_display = intent["sp_type"].replace("SavingsPlans", " SP")

            body_lines.extend(
                [
                    f"{i}. {sp_type_display}",
                    f"   Commitment: ${intent['commitment']}/hour",
                    f"   Term: {term_str}",
                    f"   Reason: {reason}",
                    "",
                ]
            )
    else:
        body_lines.append("No skipped purchases.")
        body_lines.append("")

    # Add failed purchases section
    if results["failed"]:
        body_lines.append("FAILED PURCHASES:")
        body_lines.append("-" * 60)
        for i, failure in enumerate(results["failed"], 1):
            error = failure.get("error", "Unknown error")
            intent = failure.get("intent", {})

            # Try to show basic info if intent is available
            if intent:
                sp_type = intent.get("sp_type", "Unknown")
                commitment = intent.get("commitment", "Unknown")
                body_lines.extend(
                    [
                        f"{i}. Error: {error}",
                        f"   SP Type: {sp_type}",
                        f"   Commitment: ${commitment}/hour",
                        "",
                    ]
                )
            else:
                body_lines.extend(
                    [
                        f"{i}. Error: {error}",
                        "",
                    ]
                )
    else:
        body_lines.append("No failed purchases.")
        body_lines.append("")

    # Add footer
    body_lines.extend(
        [
            "-" * 60,
            "This is an automated message from AWS Savings Plans Automation.",
        ]
    )

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(TopicArn=config["sns_topic_arn"], Subject=subject, Message=message_body)
        logger.info("Summary email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send summary email: {e!s}")
        raise


def _run_purchase_cooldown(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
    cooldown_days: int,
) -> list[dict[str, Any]]:
    """
    Filter out queued purchase intents for SP types that were recently purchased.

    Blocked messages are deleted from the queue. Returns remaining messages.
    """
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    cooldown_types = get_recent_purchase_sp_types(clients["savingsplans"], cooldown_days)
    if not cooldown_types:
        return messages

    processable = []
    blocked_messages = []
    for msg in messages:
        body = json.loads(msg["Body"])
        sp_key = constants.SP_FILTER_TO_KEY.get(body.get("sp_type", ""), body.get("sp_type", ""))
        if sp_key in cooldown_types:
            blocked_messages.append(msg)
        else:
            processable.append(msg)

    if not blocked_messages:
        return messages

    queue_adapter = QueueAdapter(sqs_client=clients["sqs"], queue_url=config["queue_url"])
    for msg in blocked_messages:
        queue_adapter.delete_message(msg["ReceiptHandle"])
    logger.warning(
        f"Deleted {len(blocked_messages)} message(s) blocked by cooldown: {sorted(cooldown_types)}"
    )

    _send_cooldown_notification(
        clients["sns"], config, blocked_messages, cooldown_types, cooldown_days
    )

    return processable


def _send_cooldown_notification(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked_messages: list[dict[str, Any]],
    cooldown_types: set[str],
    cooldown_days: int,
) -> None:
    """Send notification that purchases were blocked at purchase time due to cooldown."""
    lines = [
        "⏳  PURCHASE COOLDOWN — Purchases Blocked at Purchase Time",
        "=" * 60,
        "",
        f"{len(blocked_messages)} purchase intent(s) were blocked and removed from the queue.",
        f"A Savings Plan of the same type was purchased within the last {cooldown_days} days.",
        "This prevents double-purchasing while Cost Explorer data settles.",
        "",
        f"SP Types in Cooldown: {', '.join(sorted(t.upper() for t in cooldown_types))}",
        "",
        "Blocked Purchase Intents:",
        "-" * 50,
    ]

    for i, msg in enumerate(blocked_messages, 1):
        body = json.loads(msg["Body"])
        lines.append(
            f"  {i}. {body.get('sp_type', 'unknown')} — "
            f"${float(body.get('commitment', 0)):.5f}/hour"
        )

    lines.extend(
        [
            "",
            "These messages have been consumed from the queue.",
            "The scheduler will re-evaluate on its next run.",
        ]
    )

    message = "\n".join(lines)
    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked at Purchase Time (Cooldown)",
            Message=message,
        )
        logger.info("Cooldown notification sent")
    except ClientError as e:
        logger.error(f"Failed to send cooldown notification: {e!s}")
        raise


def _run_purchasing_spike_guard(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Run spike guard at purchase time and filter out blocked messages.

    Compares scheduling-time 14d average (from SQS message) against current 14d average.
    If usage dropped since scheduling (confirming the spike was temporary), those messages
    are consumed (deleted) from the queue.

    Returns remaining (non-blocked) messages.
    """
    # Extract scheduling averages from first message
    first_body = json.loads(messages[0]["Body"])
    scheduling_avgs = first_body.get("scheduling_avg_hourly_total")

    if not scheduling_avgs:
        logger.info("No scheduling_avg_hourly_total in message — skipping purchasing spike guard")
        return messages

    from shared.spending_analyzer import SpendingAnalyzer
    from shared.usage_decline_check import run_purchasing_spike_guard

    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    guard_results = run_purchasing_spike_guard(analyzer, scheduling_avgs, config)

    flagged_types = {t for t, r in guard_results.items() if r["flagged"]}
    if not flagged_types:
        return messages

    # Split messages into processable vs blocked
    processable = []
    blocked_messages = []
    for msg in messages:
        body = json.loads(msg["Body"])
        sp_key = constants.SP_FILTER_TO_KEY.get(body.get("sp_type", ""), body.get("sp_type", ""))
        if sp_key in flagged_types:
            blocked_messages.append(msg)
        else:
            processable.append(msg)

    # Consume (delete) blocked messages from the queue
    queue_adapter = QueueAdapter(sqs_client=clients["sqs"], queue_url=config["queue_url"])
    for msg in blocked_messages:
        queue_adapter.delete_message(msg["ReceiptHandle"])
    logger.warning(
        f"Deleted {len(blocked_messages)} blocked message(s) from queue: {flagged_types}"
    )

    # Send spike guard notification
    _send_spike_guard_notification(clients["sns"], config, blocked_messages, guard_results)

    return processable


def _send_spike_guard_notification(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked_messages: list[dict[str, Any]],
    guard_results: dict[str, dict[str, Any]],
) -> None:
    """Send notification that purchases were blocked at purchase time due to usage drop since scheduling."""
    flagged_types = set()
    for msg in blocked_messages:
        body = json.loads(msg["Body"])
        flagged_types.add(body.get("sp_type", "unknown"))

    lines = [
        "⚠️  USAGE DROP SINCE SCHEDULING — Purchases Blocked",
        "=" * 60,
        "",
        f"{len(blocked_messages)} purchase intent(s) were blocked and removed from the queue.",
        "Usage dropped between scheduling and purchase time, confirming the spike was temporary.",
        "",
        "Drop Details:",
        "-" * 50,
    ]

    for sp_type in sorted(flagged_types):
        result = guard_results.get(sp_type, {})
        lines.extend(
            [
                f"  {sp_type.upper()} Savings Plan:",
                f"    Scheduling-time avg: ${result.get('baseline_avg', 0):.4f}/hour",
                f"    Current avg: ${result.get('current_avg', 0):.4f}/hour",
                f"    Drop: -{result.get('change_percent', 0):.1f}%",
                "",
            ]
        )

    lines.extend(
        [
            "Blocked Purchase Intents:",
            "-" * 50,
        ]
    )

    for i, msg in enumerate(blocked_messages, 1):
        body = json.loads(msg["Body"])
        lines.append(
            f"  {i}. {body.get('sp_type', 'unknown')} — "
            f"${float(body.get('commitment', 0)):.5f}/hour"
        )

    lines.extend(
        [
            "",
            "These messages have been consumed from the queue.",
            "The scheduler will re-evaluate on its next run.",
            "",
            "To adjust sensitivity, modify spike_guard settings in your Terraform configuration:",
            "  purchase_strategy.spike_guard.threshold_percent (currently "
            f"{config['spike_guard_threshold_percent']}%)",
            "  purchase_strategy.spike_guard.enabled = false  (to disable entirely)",
        ]
    )

    message = "\n".join(lines)
    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked at Purchase Time (Usage Drop)",
            Message=message,
        )
        logger.info("Usage guard notification sent")
    except ClientError as e:
        logger.error(f"Failed to send spike guard notification: {e!s}")
        raise
