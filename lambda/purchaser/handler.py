"""
Purchaser Lambda - Executes Savings Plan purchases from queued intents.

This Lambda:
1. Checks SQS queue for purchase intents
2. Gets current coverage (excluding plans expiring within renewal_window_days)
3. Processes each message:
   - Validates against max_coverage_cap
   - Executes purchase via CreateSavingsPlan API
   - Deletes message on success
4. Sends aggregated email with results
5. Handles errors with immediate notification
"""

import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
from validation import validate_purchase_intent

from shared import handler_utils


# Import queue adapter for local/AWS mode support
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from queue_adapter import QueueAdapter


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
            config, session_name="sp-autopilot-purchaser", error_callback=send_error_email
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


def load_configuration() -> dict[str, Any]:
    """Load and validate configuration from environment variables."""
    schema = {
        "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
        "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
        "max_coverage_cap": {
            "required": False,
            "type": "float",
            "default": "95",
            "env_var": "MAX_COVERAGE_CAP",
        },
        "renewal_window_days": {
            "required": False,
            "type": "int",
            "default": "7",
            "env_var": "RENEWAL_WINDOW_DAYS",
        },
        "management_account_role_arn": {
            "required": False,
            "type": "str",
            "env_var": "MANAGEMENT_ACCOUNT_ROLE_ARN",
        },
        "tags": {"required": False, "type": "json", "default": "{}", "env_var": "TAGS"},
        "slack_webhook_url": {"required": False, "type": "str", "env_var": "SLACK_WEBHOOK_URL"},
        "teams_webhook_url": {"required": False, "type": "str", "env_var": "TEAMS_WEBHOOK_URL"},
    }

    return handler_utils.load_config_from_env(schema)


def receive_messages(
    sqs_client: Any, queue_url: str, max_messages: int = 10
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
        # Get date range for coverage query (last 7 days average for stability)
        end_date = datetime.now(timezone.utc).date()
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).date()

        # Get raw coverage from Cost Explorer
        raw_coverage = get_ce_coverage(clients["ce"], start_date, end_date, config)

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
    ce_client: Any, start_date: date, end_date: date, config: dict[str, Any]
) -> dict[str, Any]:
    """
    Get Savings Plans coverage from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client
        start_date: Start date for coverage period
        end_date: End date for coverage period
        config: Configuration dictionary

    Returns:
        dict: Raw coverage data by SP type
    """
    logger.info(f"Getting coverage from Cost Explorer for {start_date} to {end_date}")

    try:
        # Get coverage for Compute Savings Plans
        compute_response = ce_client.get_savings_plans_coverage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
            Granularity="DAILY",
            GroupBy=[{"Type": "DIMENSION", "Key": "SAVINGS_PLANS_TYPE"}],
        )

        # Calculate average coverage across the period
        coverage = {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        for result in compute_response.get("SavingsPlansCoverages", []):
            for group in result.get("Groups", []):
                sp_type = group.get("Attributes", {}).get("SAVINGS_PLANS_TYPE", "")
                coverage_pct = float(group.get("Coverage", {}).get("CoveragePercentage", "0"))

                if sp_type == "ComputeSavingsPlans":
                    coverage["compute"] = max(coverage["compute"], coverage_pct)
                elif sp_type == "DatabaseSavingsPlans":
                    coverage["database"] = max(coverage["database"], coverage_pct)
                elif sp_type == "SageMakerSavingsPlans":
                    coverage["sagemaker"] = max(coverage["sagemaker"], coverage_pct)

        logger.info(
            f"Raw coverage from CE: Compute={coverage['compute']:.2f}%, Database={coverage['database']:.2f}%, SageMaker={coverage['sagemaker']:.2f}%"
        )
        return coverage

    except ClientError as e:
        logger.error(f"Failed to get Cost Explorer coverage: {e!s}")
        raise


def get_expiring_plans(savingsplans_client: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
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
        expiration_threshold = datetime.now(timezone.utc) + timedelta(days=renewal_window_days)

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

    # Check if we have expiring plans by type
    has_expiring_compute = any(
        p["savingsPlanType"] == "ComputeSavingsPlans" for p in expiring_plans
    )
    has_expiring_database = any(
        p["savingsPlanType"] == "DatabaseSavingsPlans" for p in expiring_plans
    )
    has_expiring_sagemaker = any(
        p["savingsPlanType"] == "SageMakerSavingsPlans" for p in expiring_plans
    )

    # If expiring plans exist for a type, set coverage to 0 to force renewal
    if has_expiring_compute:
        logger.info("Compute Savings Plans expiring - setting coverage to 0% to force renewal")
        adjusted_coverage["compute"] = 0.0

    if has_expiring_database:
        logger.info("Database Savings Plans expiring - setting coverage to 0% to force renewal")
        adjusted_coverage["database"] = 0.0

    if has_expiring_sagemaker:
        logger.info("SageMaker Savings Plans expiring - setting coverage to 0% to force renewal")
        adjusted_coverage["sagemaker"] = 0.0

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

    current_coverage = initial_coverage.copy()

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

            # Validate against coverage cap
            if would_exceed_cap(config, purchase_intent, current_coverage):
                logger.warning(
                    f"Skipping purchase - would exceed coverage cap: {purchase_intent.get('client_token')}"
                )
                results["skipped"].append(
                    {"intent": purchase_intent, "reason": "Would exceed max_coverage_cap"}
                )
                results["skipped_count"] += 1

                # Delete message even though we skipped it
                delete_message(clients["sqs"], config["queue_url"], message["ReceiptHandle"])

            else:
                # Execute purchase
                sp_id = execute_purchase(clients["savingsplans"], config, purchase_intent)
                logger.info(f"Purchase successful: {sp_id}")

                results["successful"].append({"intent": purchase_intent, "sp_id": sp_id})
                results["successful_count"] += 1

                # Update coverage tracking
                current_coverage = update_coverage_tracking(current_coverage, purchase_intent)

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


def would_exceed_cap(
    config: dict[str, Any], purchase_intent: dict[str, Any], current_coverage: dict[str, float]
) -> bool:
    """
    Check if purchase would exceed max_coverage_cap.

    Args:
        config: Configuration dictionary
        purchase_intent: Purchase intent details
        current_coverage: Current coverage levels

    Returns:
        bool: True if purchase would exceed cap
    """
    max_cap = config["max_coverage_cap"]
    sp_type = purchase_intent.get("sp_type", "")
    projected_coverage = purchase_intent.get("projected_coverage_after", 0.0)

    # Determine which coverage type to check
    if sp_type == "ComputeSavingsPlans":
        coverage_type = "compute"
    elif sp_type == "DatabaseSavingsPlans":
        coverage_type = "database"
    elif sp_type == "SageMakerSavingsPlans":
        coverage_type = "sagemaker"
    else:
        logger.warning(f"Unknown SP type: {sp_type}, defaulting to compute")
        coverage_type = "compute"

    # Check if projected coverage would exceed cap
    if projected_coverage > max_cap:
        logger.warning(
            f"Purchase would exceed cap - Type: {coverage_type}, "
            f"Projected: {projected_coverage:.2f}%, Cap: {max_cap:.2f}%"
        )
        return True

    logger.info(
        f"Purchase within cap - Type: {coverage_type}, "
        f"Projected: {projected_coverage:.2f}%, Cap: {max_cap:.2f}%"
    )
    return False


def execute_purchase(
    savingsplans_client: Any, config: dict[str, Any], purchase_intent: dict[str, Any]
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
    offering_id = purchase_intent.get("offering_id")
    commitment = purchase_intent.get("commitment")
    upfront_amount = purchase_intent.get("upfront_amount")

    logger.info(f"Executing purchase: {client_token}")
    logger.info(f"Offering ID: {offering_id}, Commitment: ${commitment}/hr")

    try:
        # Prepare tags - merge default tags with custom tags from config
        tags = {
            "ManagedBy": "terraform-aws-sp-autopilot",
            "PurchaseDate": datetime.now(timezone.utc).isoformat(),
            "ClientToken": client_token,
        }
        tags.update(config.get("tags", {}))

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
        logger.info(f"Calling CreateSavingsPlan API with offering_id={offering_id}")
        response = savingsplans_client.create_savings_plan(**create_params)

        sp_id = response.get("savingsPlanId")
        logger.info(f"Purchase executed successfully: {sp_id}")

        return sp_id

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"CreateSavingsPlan failed - Code: {error_code}, Message: {error_message}")
        raise


def update_coverage_tracking(
    current_coverage: dict[str, float], purchase_intent: dict[str, Any]
) -> dict[str, float]:
    """
    Update coverage tracking after a purchase.

    This function updates the in-memory coverage tracking to reflect a completed purchase.
    This enables accurate cap validation for subsequent purchases in the same run - each
    purchase validates against coverage including all previous purchases.

    Args:
        current_coverage: Current coverage levels
        purchase_intent: Purchase intent that was executed

    Returns:
        dict: Updated coverage levels
    """
    updated_coverage = current_coverage.copy()

    # Determine which coverage type to update
    sp_type = purchase_intent.get("sp_type", "")
    projected_coverage = purchase_intent.get("projected_coverage_after", 0.0)

    if sp_type == "ComputeSavingsPlans":
        updated_coverage["compute"] = projected_coverage
        logger.info(
            f"Updated Compute coverage tracking: {current_coverage['compute']:.2f}% -> {projected_coverage:.2f}%"
        )
    elif sp_type == "DatabaseSavingsPlans":
        updated_coverage["database"] = projected_coverage
        logger.info(
            f"Updated Database coverage tracking: {current_coverage['database']:.2f}% -> {projected_coverage:.2f}%"
        )
    elif sp_type == "SageMakerSavingsPlans":
        updated_coverage["sagemaker"] = projected_coverage
        logger.info(
            f"Updated SageMaker coverage tracking: {current_coverage['sagemaker']:.2f}% -> {projected_coverage:.2f}%"
        )
    else:
        logger.warning(f"Unknown SP type for coverage tracking: {sp_type}")
        # Return unchanged coverage for unknown types
        return updated_coverage

    return updated_coverage


def delete_message(sqs_client: Any, queue_url: str, receipt_handle: str) -> None:
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
    sns_client: Any, config: dict[str, Any], results: dict[str, Any], coverage: dict[str, float]
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
    execution_time = datetime.now(timezone.utc).isoformat()

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

            body_lines.extend(
                [
                    f"{i}. {sp_type_display}",
                    f"   Savings Plan ID: {sp_id}",
                    f"   Commitment: ${intent['commitment']}/hour",
                    f"   Term: {term_str}",
                    f"   Payment Option: {intent['payment_option']}",
                ]
            )

            # Add upfront amount if applicable
            if intent.get("upfront_amount") and float(intent["upfront_amount"]) > 0:
                body_lines.append(f"   Upfront Payment: ${float(intent['upfront_amount']):,.2f}")

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


# Backward-compatible imports for AWS utils (required by existing tests)


def send_error_email(error_msg: str, sns_topic_arn: str = None) -> None:
    """
    Send error notification email - backward compatible wrapper.

    This function provides backward compatibility for tests that expect
    send_error_email at module level.

    Args:
        error_msg: Error message to send
        sns_topic_arn: SNS topic ARN (if None, loads from env)
    """
    if sns_topic_arn is None:
        # Try to get SNS topic ARN from environment
        import os

        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
        if not sns_topic_arn:
            logger.warning("SNS_TOPIC_ARN not found in environment")
            return

    try:
        config = load_configuration()
        sns = boto3.client("sns")
        handler_utils.send_error_notification(
            sns_client=sns,
            sns_topic_arn=sns_topic_arn,
            error_message=error_msg,
            lambda_name="Purchaser",
            slack_webhook_url=config.get("slack_webhook_url"),
            teams_webhook_url=config.get("teams_webhook_url"),
        )
    except Exception as e:
        logger.warning(f"Failed to send error email: {e}")
