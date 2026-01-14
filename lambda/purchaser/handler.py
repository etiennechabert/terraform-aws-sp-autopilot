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
import os
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients (initialized as globals, reassigned in handler if using assume role)
ce_client = boto3.client('ce')
sqs_client = boto3.client('sqs')
sns_client = boto3.client('sns')
savingsplans_client = boto3.client('savingsplans')


def get_assumed_role_session(role_arn: str) -> Optional[boto3.Session]:
    """
    Assume a cross-account role and return a session with temporary credentials.

    Args:
        role_arn: ARN of the IAM role to assume

    Returns:
        boto3.Session with assumed credentials, or None if role_arn is empty

    Raises:
        ClientError: If assume role fails
    """
    if not role_arn:
        return None

    logger.info(f"Assuming role: {role_arn}")

    try:
        sts_client = boto3.client('sts')
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='sp-autopilot-purchaser'
        )

        credentials = response['Credentials']

        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )

        logger.info(f"Successfully assumed role, session expires: {credentials['Expiration']}")
        return session

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to assume role {role_arn} - Code: {error_code}, Message: {error_message}")
        raise


def get_clients(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get AWS clients, using assumed role if configured.

    Args:
        config: Configuration dictionary with management_account_role_arn

    Returns:
        Dictionary of boto3 clients
    """
    role_arn = config.get('management_account_role_arn')

    if role_arn:
        session = get_assumed_role_session(role_arn)
        return {
            'ce': session.client('ce'),
            'savingsplans': session.client('savingsplans'),
            # Keep SNS/SQS using local credentials
            'sns': boto3.client('sns'),
            'sqs': boto3.client('sqs'),
        }
    else:
        return {
            'ce': boto3.client('ce'),
            'savingsplans': boto3.client('savingsplans'),
            'sns': boto3.client('sns'),
            'sqs': boto3.client('sqs'),
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
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
    global ce_client, savingsplans_client

    try:
        logger.info("Starting Purchaser Lambda execution")

        # Load configuration from environment
        config = load_configuration()

        # Initialize clients (with assume role if configured)
        try:
            clients = get_clients(config)
            ce_client = clients['ce']
            savingsplans_client = clients['savingsplans']
        except ClientError as e:
            error_msg = f"Failed to initialize AWS clients: {str(e)}"
            if config.get('management_account_role_arn'):
                error_msg = f"Failed to assume role {config['management_account_role_arn']}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            send_error_email(error_msg)
            raise

        # Step 1: Check queue
        messages = receive_messages(config['queue_url'])

        # If queue is empty, exit silently (no email, no error)
        if not messages:
            logger.info("Queue is empty - exiting silently")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No purchases to process',
                    'purchases_executed': 0
                })
            }

        logger.info(f"Found {len(messages)} purchase intents in queue")

        # Step 2: Get current coverage
        coverage = get_current_coverage(config)
        logger.info(f"Current coverage - Compute: {coverage.get('compute', 0)}%, Database: {coverage.get('database', 0)}%")

        # Step 3: Process each message
        results = process_purchase_messages(config, messages, coverage)

        # Step 4: Send aggregated email
        send_summary_email(config, results, coverage)

        logger.info("Purchaser Lambda completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Purchaser completed successfully',
                'purchases_executed': results['successful_count'],
                'purchases_skipped': results['skipped_count']
            })
        }

    except Exception as e:
        logger.error(f"Purchaser Lambda failed: {str(e)}", exc_info=True)
        send_error_email(str(e))
        raise  # Re-raise to ensure Lambda fails visibly


def load_configuration() -> Dict[str, Any]:
    """Load and validate configuration from environment variables."""
    return {
        'queue_url': os.environ['QUEUE_URL'],
        'sns_topic_arn': os.environ['SNS_TOPIC_ARN'],
        'max_coverage_cap': float(os.environ.get('MAX_COVERAGE_CAP', '95')),
        'renewal_window_days': int(os.environ.get('RENEWAL_WINDOW_DAYS', '7')),
        'management_account_role_arn': os.environ.get('MANAGEMENT_ACCOUNT_ROLE_ARN'),
        'tags': json.loads(os.environ.get('TAGS', '{}')),
    }


def receive_messages(queue_url: str, max_messages: int = 10) -> List[Dict[str, Any]]:
    """
    Receive messages from SQS queue.

    Args:
        queue_url: SQS queue URL
        max_messages: Maximum number of messages to retrieve

    Returns:
        list: List of SQS messages
    """
    logger.info(f"Receiving messages from queue: {queue_url}")

    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=5
        )

        messages = response.get('Messages', [])
        logger.info(f"Received {len(messages)} messages from queue")
        return messages

    except ClientError as e:
        logger.error(f"Failed to receive messages: {str(e)}")
        raise


def get_current_coverage(config: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate current Savings Plans coverage, excluding plans expiring soon.

    Args:
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
        raw_coverage = get_ce_coverage(start_date, end_date, config)

        # Get existing Savings Plans
        expiring_plans = get_expiring_plans(config)

        # Adjust coverage to exclude expiring plans
        adjusted_coverage = adjust_coverage_for_expiring_plans(
            raw_coverage,
            expiring_plans
        )

        logger.info(f"Coverage calculated: Compute={adjusted_coverage['compute']:.2f}%, Database={adjusted_coverage['database']:.2f}%")
        logger.info(f"Expiring plans excluded: {len(expiring_plans)} plans")

        return adjusted_coverage

    except ClientError as e:
        logger.error(f"Failed to calculate coverage: {str(e)}")
        raise


def get_ce_coverage(start_date: date, end_date: date, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get Savings Plans coverage from Cost Explorer.

    Args:
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
            TimePeriod={
                'Start': start_date.isoformat(),
                'End': end_date.isoformat()
            },
            Granularity='DAILY',
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SAVINGS_PLANS_TYPE'
                }
            ]
        )

        # Calculate average coverage across the period
        coverage = {
            'compute': 0.0,
            'database': 0.0
        }

        for result in compute_response.get('SavingsPlansCoverages', []):
            for group in result.get('Groups', []):
                sp_type = group.get('Attributes', {}).get('SAVINGS_PLANS_TYPE', '')
                coverage_pct = float(group.get('Coverage', {}).get('CoveragePercentage', '0'))

                if sp_type == 'ComputeSavingsPlans':
                    coverage['compute'] = max(coverage['compute'], coverage_pct)
                elif sp_type == 'DatabaseSavingsPlans':
                    coverage['database'] = max(coverage['database'], coverage_pct)

        logger.info(f"Raw coverage from CE: Compute={coverage['compute']:.2f}%, Database={coverage['database']:.2f}%")
        return coverage

    except ClientError as e:
        logger.error(f"Failed to get Cost Explorer coverage: {str(e)}")
        raise


def get_expiring_plans(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get list of Savings Plans expiring within renewal_window_days.

    Args:
        config: Configuration dictionary

    Returns:
        list: List of expiring Savings Plans
    """
    renewal_window_days = config['renewal_window_days']
    logger.info(f"Getting Savings Plans expiring within {renewal_window_days} days")

    try:
        # Get all active Savings Plans
        response = savingsplans_client.describe_savings_plans(
            states=['active']
        )

        # Calculate expiration threshold
        expiration_threshold = datetime.now(timezone.utc) + timedelta(days=renewal_window_days)

        # Filter to plans expiring within the window
        expiring_plans = []
        for plan in response.get('savingsPlans', []):
            end_time = datetime.fromisoformat(plan['end'].replace('Z', '+00:00'))

            if end_time <= expiration_threshold:
                expiring_plans.append({
                    'savingsPlanId': plan['savingsPlanId'],
                    'savingsPlanType': plan['savingsPlanType'],
                    'commitment': float(plan['commitment']),
                    'end': plan['end']
                })

        logger.info(f"Found {len(expiring_plans)} plans expiring within {renewal_window_days} days")
        return expiring_plans

    except ClientError as e:
        logger.error(f"Failed to get Savings Plans: {str(e)}")
        raise


def adjust_coverage_for_expiring_plans(
    raw_coverage: Dict[str, float],
    expiring_plans: List[Dict[str, Any]]
) -> Dict[str, float]:
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
        p['savingsPlanType'] == 'ComputeSavingsPlans' for p in expiring_plans
    )
    has_expiring_database = any(
        p['savingsPlanType'] == 'DatabaseSavingsPlans' for p in expiring_plans
    )

    # If expiring plans exist for a type, set coverage to 0 to force renewal
    if has_expiring_compute:
        logger.info("Compute Savings Plans expiring - setting coverage to 0% to force renewal")
        adjusted_coverage['compute'] = 0.0

    if has_expiring_database:
        logger.info("Database Savings Plans expiring - setting coverage to 0% to force renewal")
        adjusted_coverage['database'] = 0.0

    return adjusted_coverage


def process_purchase_messages(
    config: Dict[str, Any],
    messages: List[Dict[str, Any]],
    initial_coverage: Dict[str, float]
) -> Dict[str, Any]:
    """
    Process all purchase messages from the queue.

    Args:
        config: Configuration dictionary
        messages: List of SQS messages
        initial_coverage: Current coverage before purchases

    Returns:
        dict: Results summary with successful and skipped purchases
    """
    logger.info(f"Processing {len(messages)} purchase messages")

    results = {
        'successful': [],
        'skipped': [],
        'failed': [],
        'successful_count': 0,
        'skipped_count': 0,
        'failed_count': 0
    }

    current_coverage = initial_coverage.copy()

    for message in messages:
        try:
            # Parse message body
            purchase_intent = json.loads(message['Body'])

            # Validate against coverage cap
            if would_exceed_cap(config, purchase_intent, current_coverage):
                logger.warning(f"Skipping purchase - would exceed coverage cap: {purchase_intent.get('client_token')}")
                results['skipped'].append({
                    'intent': purchase_intent,
                    'reason': 'Would exceed max_coverage_cap'
                })
                results['skipped_count'] += 1

                # Delete message even though we skipped it
                delete_message(config['queue_url'], message['ReceiptHandle'])

            else:
                # Execute purchase
                sp_id = execute_purchase(config, purchase_intent)
                logger.info(f"Purchase successful: {sp_id}")

                results['successful'].append({
                    'intent': purchase_intent,
                    'sp_id': sp_id
                })
                results['successful_count'] += 1

                # Update coverage tracking
                current_coverage = update_coverage_tracking(current_coverage, purchase_intent)

                # Delete message after successful purchase
                delete_message(config['queue_url'], message['ReceiptHandle'])

        except ClientError as e:
            logger.error(f"Failed to process purchase: {str(e)}")
            results['failed'].append({
                'intent': purchase_intent if 'purchase_intent' in locals() else {},
                'error': str(e)
            })
            results['failed_count'] += 1
            # Message stays in queue for retry

        except Exception as e:
            logger.error(f"Unexpected error processing message: {str(e)}")
            results['failed'].append({
                'error': str(e)
            })
            results['failed_count'] += 1
            # Message stays in queue for retry

    logger.info(f"Processing complete - Successful: {results['successful_count']}, Skipped: {results['skipped_count']}, Failed: {results['failed_count']}")
    return results


def would_exceed_cap(
    config: Dict[str, Any],
    purchase_intent: Dict[str, Any],
    current_coverage: Dict[str, float]
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
    max_cap = config['max_coverage_cap']
    sp_type = purchase_intent.get('sp_type', '')
    projected_coverage = purchase_intent.get('projected_coverage_after', 0.0)

    # Determine which coverage type to check
    if sp_type == 'ComputeSavingsPlans':
        coverage_type = 'compute'
    elif sp_type == 'DatabaseSavingsPlans':
        coverage_type = 'database'
    else:
        logger.warning(f"Unknown SP type: {sp_type}, defaulting to compute")
        coverage_type = 'compute'

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
    config: Dict[str, Any],
    purchase_intent: Dict[str, Any]
) -> str:
    """
    Execute a Savings Plan purchase via AWS API.

    Args:
        config: Configuration dictionary
        purchase_intent: Purchase intent details

    Returns:
        str: Savings Plan ID

    Raises:
        ClientError: If purchase fails
    """
    client_token = purchase_intent.get('client_token')
    offering_id = purchase_intent.get('offering_id')
    commitment = purchase_intent.get('commitment')
    upfront_amount = purchase_intent.get('upfront_amount')

    logger.info(f"Executing purchase: {client_token}")
    logger.info(f"Offering ID: {offering_id}, Commitment: ${commitment}/hr")

    try:
        # Prepare tags - merge default tags with custom tags from config
        tags = {
            'ManagedBy': 'terraform-aws-sp-autopilot',
            'PurchaseDate': datetime.now(timezone.utc).isoformat(),
            'ClientToken': client_token
        }
        tags.update(config.get('tags', {}))

        # Build CreateSavingsPlan request parameters
        create_params = {
            'savingsPlanOfferingId': offering_id,
            'commitment': commitment,
            'clientToken': client_token,
            'tags': tags
        }

        # Add upfront payment amount if applicable (for ALL_UPFRONT or PARTIAL_UPFRONT)
        if upfront_amount is not None and float(upfront_amount) > 0:
            create_params['upfrontPaymentAmount'] = upfront_amount
            logger.info(f"Including upfront payment: ${upfront_amount}")

        # Execute CreateSavingsPlan API call
        logger.info(f"Calling CreateSavingsPlan API with offering_id={offering_id}")
        response = savingsplans_client.create_savings_plan(**create_params)

        sp_id = response.get('savingsPlanId')
        logger.info(f"Purchase executed successfully: {sp_id}")

        return sp_id

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"CreateSavingsPlan failed - Code: {error_code}, Message: {error_message}")
        raise


def update_coverage_tracking(
    current_coverage: Dict[str, float],
    purchase_intent: Dict[str, Any]
) -> Dict[str, float]:
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
    sp_type = purchase_intent.get('sp_type', '')
    projected_coverage = purchase_intent.get('projected_coverage_after', 0.0)

    if sp_type == 'ComputeSavingsPlans':
        updated_coverage['compute'] = projected_coverage
        logger.info(
            f"Updated Compute coverage tracking: {current_coverage['compute']:.2f}% -> {projected_coverage:.2f}%"
        )
    elif sp_type == 'DatabaseSavingsPlans':
        updated_coverage['database'] = projected_coverage
        logger.info(
            f"Updated Database coverage tracking: {current_coverage['database']:.2f}% -> {projected_coverage:.2f}%"
        )
    else:
        logger.warning(f"Unknown SP type for coverage tracking: {sp_type}")
        # Return unchanged coverage for unknown types
        return updated_coverage

    return updated_coverage


def delete_message(queue_url: str, receipt_handle: str) -> None:
    """
    Delete a message from the SQS queue.

    Args:
        queue_url: SQS queue URL
        receipt_handle: Message receipt handle
    """
    try:
        sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        logger.info("Message deleted from queue")
    except ClientError as e:
        logger.error(f"Failed to delete message: {str(e)}")
        raise


def send_summary_email(
    config: Dict[str, Any],
    results: Dict[str, Any],
    coverage: Dict[str, float]
) -> None:
    """
    Send aggregated summary email for all purchases.

    Args:
        config: Configuration dictionary
        results: Purchase results
        coverage: Final coverage levels
    """
    logger.info("Sending summary email")

    # Format execution timestamp
    execution_time = datetime.now(timezone.utc).isoformat()

    # Build email subject
    total_purchases = results['successful_count'] + results['skipped_count']
    subject = f"AWS Savings Plans Purchase Complete - {results['successful_count']} Executed, {results['skipped_count']} Skipped"

    # Build email body
    body_lines = [
        "AWS Savings Plans Purchaser - Execution Summary",
        "=" * 60,
        f"Execution Time: {execution_time}",
        f"Total Purchase Intents Processed: {total_purchases}",
        f"Successful Purchases: {results['successful_count']}",
        f"Skipped Purchases: {results['skipped_count']}",
        "",
        "Current Coverage After Execution:",
        f"  Compute Savings Plans: {coverage.get('compute', 0):.2f}%",
        f"  Database Savings Plans: {coverage.get('database', 0):.2f}%",
        "",
    ]

    # Add successful purchases section
    if results['successful']:
        body_lines.append("SUCCESSFUL PURCHASES:")
        body_lines.append("-" * 60)
        for i, purchase in enumerate(results['successful'], 1):
            intent = purchase['intent']
            sp_id = purchase['sp_id']

            # Format term (convert seconds to years)
            term_years = intent['term_seconds'] / (365.25 * 24 * 3600)
            term_str = f"{term_years:.0f}-year" if term_years == int(term_years) else f"{term_years:.1f}-year"

            # Format SP type (remove "SavingsPlans" suffix for readability)
            sp_type_display = intent['sp_type'].replace('SavingsPlans', ' SP')

            body_lines.extend([
                f"{i}. {sp_type_display}",
                f"   Savings Plan ID: {sp_id}",
                f"   Commitment: ${intent['commitment']}/hour",
                f"   Term: {term_str}",
                f"   Payment Option: {intent['payment_option']}",
            ])

            # Add upfront amount if applicable
            if intent.get('upfront_amount') and float(intent['upfront_amount']) > 0:
                body_lines.append(f"   Upfront Payment: ${float(intent['upfront_amount']):,.2f}")

            body_lines.append("")
    else:
        body_lines.append("No successful purchases.")
        body_lines.append("")

    # Add skipped purchases section
    if results['skipped']:
        body_lines.append("SKIPPED PURCHASES:")
        body_lines.append("-" * 60)
        for i, skip in enumerate(results['skipped'], 1):
            intent = skip['intent']
            reason = skip['reason']

            # Format term (convert seconds to years)
            term_years = intent['term_seconds'] / (365.25 * 24 * 3600)
            term_str = f"{term_years:.0f}-year" if term_years == int(term_years) else f"{term_years:.1f}-year"

            # Format SP type
            sp_type_display = intent['sp_type'].replace('SavingsPlans', ' SP')

            body_lines.extend([
                f"{i}. {sp_type_display}",
                f"   Commitment: ${intent['commitment']}/hour",
                f"   Term: {term_str}",
                f"   Reason: {reason}",
                "",
            ])
    else:
        body_lines.append("No skipped purchases.")
        body_lines.append("")

    # Add footer
    body_lines.extend([
        "-" * 60,
        "This is an automated message from AWS Savings Plans Automation.",
    ])

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(
            TopicArn=config['sns_topic_arn'],
            Subject=subject,
            Message=message_body
        )
        logger.info("Summary email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send summary email: {str(e)}")
        raise


def send_error_email(error_message: str) -> None:
    """
    Send error notification email.

    Args:
        error_message: Error details
    """
    logger.error("Sending error notification email")

    # Get configuration from environment
    try:
        sns_topic_arn = os.environ['SNS_TOPIC_ARN']
        queue_url = os.environ['QUEUE_URL']
    except KeyError as e:
        logger.error(f"Missing required environment variable for error email: {e}")
        return  # Cannot send email without SNS topic ARN

    # Format execution timestamp
    execution_time = datetime.now(timezone.utc).isoformat()

    # Build email subject
    subject = "AWS Savings Plans Purchaser - ERROR"

    # Build email body
    body_lines = [
        "AWS Savings Plans Purchaser - ERROR NOTIFICATION",
        "=" * 60,
        f"Execution Time: {execution_time}",
        "",
        "ERROR DETAILS:",
        "-" * 60,
        error_message,
        "",
        "INVESTIGATION:",
        "-" * 60,
        "Review the SQS queue for pending purchase intents:",
        f"Queue URL: {queue_url}",
        "",
        "Messages in the queue were NOT processed due to this error.",
        "The Lambda will retry on the next scheduled execution.",
        "",
        "NEXT STEPS:",
        "1. Check CloudWatch Logs for detailed error context",
        "2. Verify queue messages are still valid",
        "3. Review Lambda execution role permissions",
        "4. Contact your AWS administrator if the issue persists",
        "",
        "-" * 60,
        "This is an automated error notification from AWS Savings Plans Automation.",
    ]

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message_body
        )
        logger.info("Error notification email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send error notification email: {str(e)}")
        # Don't raise - we're already in error handling, don't want to mask the original error
