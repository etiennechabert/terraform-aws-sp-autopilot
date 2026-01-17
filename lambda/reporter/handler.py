"""
Reporter Lambda - Generates periodic coverage and savings reports.

This Lambda:
1. Collects coverage history over the reporting period
2. Gathers savings data from active Savings Plans
3. Calculates estimated savings achieved
4. Generates HTML report with trends and metrics
5. Uploads report to S3 with timestamp-based key
6. Optionally sends email notification with S3 link
"""

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from shared import notifications
from shared.handler_utils import (
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)

# Import storage adapter for local/AWS mode support
try:
    # Try importing from shared package (Lambda deployment structure)
    from shared.storage_adapter import StorageAdapter
except ImportError:
    # Fall back to direct import for local development
    sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
    from storage_adapter import StorageAdapter


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Module-level clients (initialized for backward compatibility with tests)
# These can be patched by tests using patch.object(handler.ce_client, ...)
ce_client = boto3.client("ce")
savingsplans_client = boto3.client("savingsplans")
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")


@lambda_handler_wrapper("Reporter")
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for Reporter Lambda.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        dict: Status and report location

    Raises:
        Exception: All errors are raised (no silent failures)
    """
    try:
        # Load configuration from environment
        config = load_configuration()

        # Create error callback function
        def send_error_email(error_msg: str) -> None:
            """Send error notification using shared utility."""
            # Get SNS client directly (before full client initialization)
            sns = boto3.client("sns")
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=error_msg,
                lambda_name="Reporter",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )

        # Initialize clients (with assume role if configured)
        clients = initialize_clients(config, "sp-autopilot-reporter", send_error_email)
        ce_client = clients["ce"]
        savingsplans_client = clients["savingsplans"]
        s3_client = clients["s3"]
        sns_client = clients["sns"]

        logger.info("Configuration loaded and clients initialized successfully")

        # Step 1: Collect coverage history
        coverage_history = get_coverage_history(ce_client, lookback_days=30)
        logger.info(f"Coverage history collected: {len(coverage_history)} data points")

        # Step 2: Gather savings data
        savings_data = get_savings_data(savingsplans_client, ce_client)
        logger.info(f"Savings data collected: {savings_data.get('plans_count', 0)} active plans")

        # Step 3: Generate report based on format
        if config["report_format"] == "json":
            report_content = generate_json_report(coverage_history, savings_data)
        else:
            report_content = generate_html_report(coverage_history, savings_data)

        # Step 4: Upload report to S3
        s3_object_key = upload_report_to_s3(
            s3_client, config, report_content, config["report_format"]
        )
        logger.info(f"Report uploaded to S3: {s3_object_key}")

        # Step 5: Send email notification (if enabled)
        if config["email_reports"]:
            # Calculate summary metrics for email
            avg_coverage = 0.0
            current_coverage = 0.0
            trend_direction = "→"

            if coverage_history:
                total_coverage = sum(
                    item.get("coverage_percentage", 0.0) for item in coverage_history
                )
                avg_coverage = total_coverage / len(coverage_history)
                current_coverage = coverage_history[-1].get("coverage_percentage", 0.0)

                # Calculate trend
                if len(coverage_history) >= 2:
                    first_coverage = coverage_history[0].get("coverage_percentage", 0.0)
                    last_coverage = coverage_history[-1].get("coverage_percentage", 0.0)
                    trend = last_coverage - first_coverage
                    trend_direction = "↑" if trend > 0 else "↓" if trend < 0 else "→"

            coverage_summary = {
                "current_coverage": current_coverage,
                "avg_coverage": avg_coverage,
                "coverage_days": len(coverage_history),
                "trend_direction": trend_direction,
            }

            send_report_email(sns_client, config, s3_object_key, coverage_summary, savings_data)
            logger.info("Report email notification sent")
        else:
            logger.info("Email notifications disabled - skipping email")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Reporter completed successfully",
                    "s3_object_key": s3_object_key,
                    "coverage_data_points": len(coverage_history),
                    "active_plans": savings_data.get("plans_count", 0),
                }
            ),
        }

    except Exception as e:
        # Try to send error notification
        try:
            config = load_configuration()
            sns = boto3.client("sns")
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=str(e),
                lambda_name="Reporter",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )
        except Exception as notification_error:
            logger.warning(f"Failed to send error notification: {notification_error}")
        raise  # Re-raise to ensure Lambda fails visibly


def load_configuration() -> Dict[str, Any]:
    """Load and validate configuration from environment variables."""
    schema = {
        "reports_bucket": {"required": True, "type": "str", "env_var": "REPORTS_BUCKET"},
        "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
        "report_format": {
            "required": False,
            "type": "str",
            "default": "html",
            "env_var": "REPORT_FORMAT",
        },
        "email_reports": {
            "required": False,
            "type": "bool",
            "default": "false",
            "env_var": "EMAIL_REPORTS",
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

    return load_config_from_env(schema)


def get_coverage_history(ce_client: Any = None, lookback_days: int = 30) -> List[Dict[str, Any]]:
    """
    Get Savings Plans coverage history from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client (defaults to module-level client)
        lookback_days: Number of days to look back for coverage data

    Returns:
        list: Coverage data points by day with timestamps and percentages

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    if ce_client is None:
        ce_client = globals()["ce_client"]

    logger.info(f"Fetching coverage history for last {lookback_days} days")

    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Querying coverage from {start_date} to {end_date}")

        # Get coverage data from Cost Explorer
        response = ce_client.get_savings_plans_coverage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
            Granularity="DAILY",
        )

        coverage_by_time = response.get("SavingsPlansCoverages", [])

        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return []

        # Parse coverage data points
        coverage_history = []
        for coverage_item in coverage_by_time:
            time_period = coverage_item.get("TimePeriod", {})
            coverage_data = coverage_item.get("Coverage", {})

            coverage_percentage = 0.0
            if "CoveragePercentage" in coverage_data:
                coverage_percentage = float(coverage_data["CoveragePercentage"])

            coverage_hours = coverage_data.get("CoverageHours", {})
            on_demand_hours = float(coverage_hours.get("OnDemandHours", "0"))
            covered_hours = float(coverage_hours.get("CoveredHours", "0"))
            total_hours = float(coverage_hours.get("TotalRunningHours", "0"))

            coverage_history.append(
                {
                    "date": time_period.get("Start"),
                    "coverage_percentage": coverage_percentage,
                    "on_demand_hours": on_demand_hours,
                    "covered_hours": covered_hours,
                    "total_hours": total_hours,
                }
            )

        logger.info(f"Retrieved {len(coverage_history)} coverage data points")
        return coverage_history

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get coverage history - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_actual_cost_data(ce_client: Any = None, lookback_days: int = 30) -> Dict[str, Any]:
    """
    Get actual Savings Plans and On-Demand costs from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client (defaults to module-level client)
        lookback_days: Number of days to look back for cost data

    Returns:
        dict: Cost data including Savings Plans spend and On-Demand spend by day

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    if ce_client is None:
        ce_client = globals()["ce_client"]

    logger.info(f"Fetching actual cost data for last {lookback_days} days")

    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Querying costs from {start_date} to {end_date}")

        # Get cost data from Cost Explorer
        # Group by purchase option to separate Savings Plans from On-Demand
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "PURCHASE_OPTION"}],
        )

        results_by_time = response.get("ResultsByTime", [])

        if not results_by_time:
            logger.warning("No cost data available from Cost Explorer")
            return {
                "cost_by_day": [],
                "total_savings_plans_cost": 0.0,
                "total_on_demand_cost": 0.0,
                "total_cost": 0.0,
            }

        # Parse cost data by day
        cost_by_day = []
        total_savings_plans_cost = 0.0
        total_on_demand_cost = 0.0

        for result_item in results_by_time:
            time_period = result_item.get("TimePeriod", {})
            groups = result_item.get("Groups", [])

            daily_savings_plans_cost = 0.0
            daily_on_demand_cost = 0.0

            # Process each purchase option group
            for group in groups:
                keys = group.get("Keys", [])
                metrics = group.get("Metrics", {})

                # Extract purchase option (e.g., 'Savings Plans', 'On Demand')
                purchase_option = keys[0] if keys else "Unknown"

                # Extract cost amount
                unblended_cost = metrics.get("UnblendedCost", {})
                cost_amount = float(unblended_cost.get("Amount", "0"))

                # Categorize by purchase option
                if "Savings Plans" in purchase_option or "SavingsPlan" in purchase_option:
                    daily_savings_plans_cost += cost_amount
                    total_savings_plans_cost += cost_amount
                elif "On Demand" in purchase_option or "OnDemand" in purchase_option:
                    daily_on_demand_cost += cost_amount
                    total_on_demand_cost += cost_amount

            daily_total_cost = daily_savings_plans_cost + daily_on_demand_cost

            cost_by_day.append(
                {
                    "date": time_period.get("Start"),
                    "savings_plans_cost": daily_savings_plans_cost,
                    "on_demand_cost": daily_on_demand_cost,
                    "total_cost": daily_total_cost,
                }
            )

        total_cost = total_savings_plans_cost + total_on_demand_cost

        logger.info(f"Retrieved {len(cost_by_day)} cost data points")
        logger.info(f"Total Savings Plans cost: ${total_savings_plans_cost:.2f}")
        logger.info(f"Total On-Demand cost: ${total_on_demand_cost:.2f}")
        logger.info(f"Total cost: ${total_cost:.2f}")

        return {
            "cost_by_day": cost_by_day,
            "total_savings_plans_cost": total_savings_plans_cost,
            "total_on_demand_cost": total_on_demand_cost,
            "total_cost": total_cost,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get actual cost data - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_savings_data(savingsplans_client: Any = None, ce_client: Any = None) -> Dict[str, Any]:
    """
    Get savings data from active Savings Plans.

    Args:
        savingsplans_client: Boto3 Savings Plans client (defaults to module-level client)
        ce_client: Boto3 Cost Explorer client (defaults to module-level client)

    Returns:
        dict: Savings Plans data including commitment, utilization, and estimated savings

    Raises:
        ClientError: If Savings Plans or Cost Explorer API calls fail
    """
    if savingsplans_client is None:
        savingsplans_client = globals()["savingsplans_client"]
    if ce_client is None:
        ce_client = globals()["ce_client"]

    logger.info("Fetching savings data from active Savings Plans")

    try:
        # Get all active Savings Plans
        response = savingsplans_client.describe_savings_plans(
            filters=[{"name": "state", "values": ["active"]}]
        )

        savings_plans = response.get("savingsPlans", [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        if not savings_plans:
            return {
                "total_commitment": 0.0,
                "plans_count": 0,
                "plans": [],
                "estimated_monthly_savings": 0.0,
                "average_utilization": 0.0,
                "actual_savings": {
                    "actual_sp_cost": 0.0,
                    "on_demand_equivalent_cost": 0.0,
                    "net_savings": 0.0,
                    "savings_percentage": 0.0,
                    "breakdown_by_type": {},
                },
            }

        # Calculate total commitment and collect plan details
        total_hourly_commitment = 0.0
        plans_data = []

        for plan in savings_plans:
            hourly_commitment = float(plan.get("commitment", "0"))
            total_hourly_commitment += hourly_commitment

            plan_type = plan.get("savingsPlanType", "Unknown")
            plan_id = plan.get("savingsPlanId", "Unknown")
            start_date = plan.get("start", "Unknown")
            end_date = plan.get("end", "Unknown")
            payment_option = plan.get("paymentOption", "Unknown")
            term = plan.get("termDurationInSeconds", 0) // (
                365 * 24 * 60 * 60
            )  # Convert seconds to years

            plans_data.append(
                {
                    "plan_id": plan_id,
                    "plan_type": plan_type,
                    "hourly_commitment": hourly_commitment,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payment_option": payment_option,
                    "term_years": term,
                }
            )

        logger.info(f"Total hourly commitment: ${total_hourly_commitment:.2f}/hour")

        # Get utilization and actual savings data from Cost Explorer
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=30)  # Last 30 days for actual savings

            utilization_response = ce_client.get_savings_plans_utilization(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
            )

            utilizations = utilization_response.get("SavingsPlansUtilizationsByTime", [])

            if utilizations:
                # Calculate average utilization and actual savings
                total_utilization = 0.0
                count = 0
                total_net_savings = 0.0
                total_on_demand_equivalent = 0.0
                total_amortized_commitment = 0.0

                for util_item in utilizations:
                    # Extract utilization percentage
                    utilization = util_item.get("Utilization", {})
                    utilization_percentage = utilization.get("UtilizationPercentage")

                    if utilization_percentage:
                        total_utilization += float(utilization_percentage)
                        count += 1

                    # Extract actual savings data
                    savings = util_item.get("Savings", {})
                    net_savings = savings.get("NetSavings", "0")
                    on_demand_equivalent = savings.get("OnDemandCostEquivalent", "0")

                    # Extract amortized commitment
                    amortized = util_item.get("AmortizedCommitment", {})
                    amortized_commitment = amortized.get("TotalAmortizedCommitment", "0")

                    # Accumulate totals
                    total_net_savings += float(net_savings)
                    total_on_demand_equivalent += float(on_demand_equivalent)
                    total_amortized_commitment += float(amortized_commitment)

                average_utilization = total_utilization / count if count > 0 else 0.0
                logger.info(f"Average utilization over last 30 days: {average_utilization:.2f}%")
                logger.info(f"Actual net savings over last 30 days: ${total_net_savings:.2f}")
                logger.info(f"On-demand equivalent cost: ${total_on_demand_equivalent:.2f}")
                logger.info(f"Amortized SP commitment: ${total_amortized_commitment:.2f}")
            else:
                average_utilization = 0.0
                total_net_savings = 0.0
                total_on_demand_equivalent = 0.0
                total_amortized_commitment = 0.0
                logger.warning("No utilization data available")

        except ClientError as e:
            logger.warning(f"Failed to get utilization data: {e!s}")
            average_utilization = 0.0
            total_net_savings = 0.0
            total_on_demand_equivalent = 0.0
            total_amortized_commitment = 0.0

        # Calculate actual savings percentage
        savings_percentage = 0.0
        if total_on_demand_equivalent > 0:
            savings_percentage = (total_net_savings / total_on_demand_equivalent) * 100.0

        # Calculate breakdown by plan type
        breakdown_by_type = {}
        for plan in plans_data:
            plan_type = plan["plan_type"]
            if plan_type not in breakdown_by_type:
                breakdown_by_type[plan_type] = {"plans_count": 0, "total_commitment": 0.0}
            breakdown_by_type[plan_type]["plans_count"] += 1
            breakdown_by_type[plan_type]["total_commitment"] += plan["hourly_commitment"]

        logger.info(f"Actual monthly savings: ${total_net_savings:.2f} ({savings_percentage:.2f}%)")

        return {
            "total_commitment": total_hourly_commitment,
            "plans_count": len(savings_plans),
            "plans": plans_data,
            "estimated_monthly_savings": total_net_savings,  # Now using actual savings
            "average_utilization": average_utilization,
            "actual_savings": {
                "actual_sp_cost": total_amortized_commitment,
                "on_demand_equivalent_cost": total_on_demand_equivalent,
                "net_savings": total_net_savings,
                "savings_percentage": savings_percentage,
                "breakdown_by_type": breakdown_by_type,
            },
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to get savings data - Code: {error_code}, Message: {error_message}")
        raise


def generate_html_report(
    coverage_history: List[Dict[str, Any]], savings_data: Dict[str, Any]
) -> str:
    """
    Generate HTML report with coverage trends and savings metrics.

    Args:
        coverage_history: List of coverage data points by day
        savings_data: Savings Plans data including commitment and estimated savings

    Returns:
        str: HTML report content
    """
    logger.info("Generating HTML report")

    # Calculate report timestamp
    report_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Calculate coverage summary
    avg_coverage = 0.0
    if coverage_history:
        total_coverage = sum(item.get("coverage_percentage", 0.0) for item in coverage_history)
        avg_coverage = total_coverage / len(coverage_history)

    current_coverage = (
        coverage_history[-1].get("coverage_percentage", 0.0) if coverage_history else 0.0
    )

    # Calculate trend direction
    if len(coverage_history) >= 2:
        first_coverage = coverage_history[0].get("coverage_percentage", 0.0)
        last_coverage = coverage_history[-1].get("coverage_percentage", 0.0)
        trend = last_coverage - first_coverage
        trend_symbol = "↑" if trend > 0 else "↓" if trend < 0 else "→"
        trend_color = "#28a745" if trend > 0 else "#dc3545" if trend < 0 else "#6c757d"
    else:
        trend_symbol = "→"
        trend_color = "#6c757d"

    # Build HTML content using string builder pattern
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Savings Plans Coverage & Savings Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #232f3e;
            border-bottom: 3px solid #ff9900;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-card.green {{
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
        }}
        .summary-card.blue {{
            background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
        }}
        .summary-card.orange {{
            background: linear-gradient(135deg, #f46b45 0%, #eea849 100%);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 0.9em;
            font-weight: 500;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            margin: 0;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        h2 {{
            color: #232f3e;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
            margin-bottom: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            background-color: white;
        }}
        th {{
            background-color: #232f3e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .metric {{
            font-weight: bold;
            color: #232f3e;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
        }}
        .trend {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Savings Plans Coverage & Savings Report</h1>
        <div class="subtitle">Generated: {report_timestamp}</div>

        <div class="summary">
            <div class="summary-card blue">
                <h3>Current Coverage</h3>
                <div class="value">{current_coverage:.1f}%</div>
            </div>
            <div class="summary-card green">
                <h3>Average Coverage ({len(coverage_history)} days)</h3>
                <div class="value">{avg_coverage:.1f}%</div>
            </div>
            <div class="summary-card orange">
                <h3>Active Plans</h3>
                <div class="value">{savings_data.get("plans_count", 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Actual Net Savings (30 days)</h3>
                <div class="value">${savings_data.get("actual_savings", {}).get("net_savings", 0):,.0f}</div>
            </div>
            <div class="summary-card green">
                <h3>Savings Percentage</h3>
                <div class="value">{savings_data.get("actual_savings", {}).get("savings_percentage", 0):.1f}%</div>
            </div>
        </div>

        <div class="section">
            <h2>Coverage Trends <span class="trend" style="color: {trend_color};">{trend_symbol}</span></h2>
""")

    # Coverage history table
    if coverage_history:
        html_parts.append("""
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Coverage %</th>
                        <th>Covered Hours</th>
                        <th>On-Demand Hours</th>
                        <th>Total Hours</th>
                    </tr>
                </thead>
                <tbody>
""")
        for item in coverage_history:
            date = item.get("date", "Unknown")
            coverage_pct = item.get("coverage_percentage", 0.0)
            covered_hours = item.get("covered_hours", 0.0)
            on_demand_hours = item.get("on_demand_hours", 0.0)
            total_hours = item.get("total_hours", 0.0)

            html_parts.append(f"""
                    <tr>
                        <td>{date}</td>
                        <td class="metric">{coverage_pct:.2f}%</td>
                        <td>{covered_hours:,.0f}</td>
                        <td>{on_demand_hours:,.0f}</td>
                        <td>{total_hours:,.0f}</td>
                    </tr>
""")
        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <div class="no-data">No coverage data available</div>
""")

    html_parts.append("""
        </div>

        <div class="section">
            <h2>Active Savings Plans</h2>
""")

    # Savings Plans table
    plans = savings_data.get("plans", [])
    if plans:
        total_commitment = savings_data.get("total_commitment", 0.0)
        avg_utilization = savings_data.get("average_utilization", 0.0)

        html_parts.append(f"""
            <p>
                <strong>Total Hourly Commitment:</strong> ${total_commitment:.4f}/hour
                (${total_commitment * 730:,.2f}/month)
                <br>
                <strong>Average Utilization (7 days):</strong> {avg_utilization:.2f}%
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Plan ID</th>
                        <th>Type</th>
                        <th>Hourly Commitment</th>
                        <th>Term</th>
                        <th>Payment Option</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                    </tr>
                </thead>
                <tbody>
""")
        for plan in plans:
            plan_id = plan.get("plan_id", "Unknown")
            plan_type = plan.get("plan_type", "Unknown")
            hourly_commitment = plan.get("hourly_commitment", 0.0)
            term_years = plan.get("term_years", 0)
            payment_option = plan.get("payment_option", "Unknown")
            start_date = plan.get("start_date", "Unknown")
            end_date = plan.get("end_date", "Unknown")

            # Format dates (extract date part from ISO timestamp)
            if "T" in start_date:
                start_date = start_date.split("T")[0]
            if "T" in end_date:
                end_date = end_date.split("T")[0]

            html_parts.append(f"""
                    <tr>
                        <td style="font-family: monospace; font-size: 0.85em;">{plan_id[:20]}...</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.4f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td>{start_date}</td>
                        <td>{end_date}</td>
                    </tr>
""")
        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <div class="no-data">No active Savings Plans found</div>
""")

    # Actual Savings Summary Section
    actual_savings = savings_data.get("actual_savings", {})
    net_savings = actual_savings.get("net_savings", 0.0)
    on_demand_equivalent = actual_savings.get("on_demand_equivalent_cost", 0.0)
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    savings_pct = actual_savings.get("savings_percentage", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    html_parts.append("""
        </div>

        <div class="section">
            <h2>Actual Savings Summary (Last 30 Days)</h2>
""")

    html_parts.append(f"""
            <p>
                <strong>Net Savings:</strong> <span style="color: #28a745; font-size: 1.2em; font-weight: bold;">${net_savings:,.2f}</span>
                <span style="color: #6c757d; margin-left: 10px;">({savings_pct:.2f}% savings)</span>
            </p>
            <p>
                <strong>On-Demand Equivalent Cost:</strong> ${on_demand_equivalent:,.2f}
                <br>
                <strong>Actual Savings Plans Cost:</strong> ${actual_sp_cost:,.2f}
                <br>
                <strong>Net Savings:</strong> ${net_savings:,.2f}
            </p>
""")

    # Breakdown by Plan Type
    if breakdown_by_type:
        html_parts.append("""
            <h3 style="margin-top: 20px; color: #232f3e;">Savings Plans Breakdown by Type</h3>
            <table>
                <thead>
                    <tr>
                        <th>Plan Type</th>
                        <th>Active Plans</th>
                        <th>Total Hourly Commitment</th>
                        <th>Monthly Commitment</th>
                    </tr>
                </thead>
                <tbody>
""")

        for plan_type, type_data in breakdown_by_type.items():
            plans_count = type_data.get("plans_count", 0)
            total_commitment = type_data.get("total_commitment", 0.0)
            monthly_commitment = total_commitment * 730

            # Map plan types to readable names
            plan_type_display = plan_type
            if "Compute" in plan_type:
                plan_type_display = "Compute Savings Plans"
            elif "SageMaker" in plan_type:
                plan_type_display = "SageMaker Savings Plans"
            elif "EC2Instance" in plan_type:
                plan_type_display = "EC2 Instance Savings Plans"

            html_parts.append(f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count}</td>
                        <td class="metric">${total_commitment:.4f}/hr</td>
                        <td class="metric">${monthly_commitment:,.2f}/mo</td>
                    </tr>
""")

        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <p style="color: #6c757d; font-style: italic;">No savings plan type breakdown available</p>
""")

    html_parts.append(f"""
        </div>

        <div class="footer">
            <p><strong>Savings Plans Autopilot</strong> - Automated Coverage & Savings Report</p>
            <p>Report Period: {len(coverage_history)} days | Generated: {report_timestamp}</p>
        </div>
    </div>
</body>
</html>
""")

    html = "".join(html_parts)
    logger.info(f"HTML report generated ({len(html)} bytes)")
    return html


def generate_json_report(
    coverage_history: List[Dict[str, Any]], savings_data: Dict[str, Any]
) -> str:
    """
    Generate JSON report with coverage trends and savings metrics.

    Args:
        coverage_history: List of coverage data points by day
        savings_data: Savings Plans data including commitment and estimated savings

    Returns:
        str: JSON report content
    """
    logger.info("Generating JSON report")

    # Calculate report timestamp
    report_timestamp = datetime.now(timezone.utc).isoformat()

    # Calculate coverage summary
    avg_coverage = 0.0
    if coverage_history:
        total_coverage = sum(item.get("coverage_percentage", 0.0) for item in coverage_history)
        avg_coverage = total_coverage / len(coverage_history)

    current_coverage = (
        coverage_history[-1].get("coverage_percentage", 0.0) if coverage_history else 0.0
    )

    # Calculate trend direction
    trend_direction = "stable"
    trend_value = 0.0
    if len(coverage_history) >= 2:
        first_coverage = coverage_history[0].get("coverage_percentage", 0.0)
        last_coverage = coverage_history[-1].get("coverage_percentage", 0.0)
        trend_value = last_coverage - first_coverage
        if trend_value > 0:
            trend_direction = "increasing"
        elif trend_value < 0:
            trend_direction = "decreasing"

    # Extract actual savings data
    actual_savings = savings_data.get("actual_savings", {})
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    on_demand_equivalent_cost = actual_savings.get("on_demand_equivalent_cost", 0.0)
    net_savings = actual_savings.get("net_savings", 0.0)
    savings_percentage = actual_savings.get("savings_percentage", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    # Format breakdown as array of objects
    breakdown_array = []
    for plan_type, type_data in breakdown_by_type.items():
        breakdown_array.append(
            {
                "type": plan_type,
                "plans_count": type_data.get("plans_count", 0),
                "total_hourly_commitment": round(type_data.get("total_commitment", 0.0), 4),
                "total_monthly_commitment": round(type_data.get("total_commitment", 0.0) * 730, 2),
            }
        )

    # Build JSON report structure
    report = {
        "report_metadata": {
            "generated_at": report_timestamp,
            "report_type": "savings_plans_coverage_and_savings",
            "generator": "sp-autopilot-reporter",
            "reporting_period_days": len(coverage_history),
        },
        "coverage_summary": {
            "current_coverage_percentage": round(current_coverage, 2),
            "average_coverage_percentage": round(avg_coverage, 2),
            "trend_direction": trend_direction,
            "trend_value": round(trend_value, 2),
            "data_points": len(coverage_history),
        },
        "coverage_history": coverage_history,
        "savings_summary": {
            "active_plans_count": savings_data.get("plans_count", 0),
            "total_hourly_commitment": round(savings_data.get("total_commitment", 0.0), 4),
            "total_monthly_commitment": round(savings_data.get("total_commitment", 0.0) * 730, 2),
            "estimated_monthly_savings": round(
                savings_data.get("estimated_monthly_savings", 0.0), 2
            ),
            "average_utilization_percentage": round(
                savings_data.get("average_utilization", 0.0), 2
            ),
        },
        "actual_savings": {
            "sp_cost": round(actual_sp_cost, 2),
            "on_demand_cost": round(on_demand_equivalent_cost, 2),
            "net_savings": round(net_savings, 2),
            "savings_percentage": round(savings_percentage, 2),
            "breakdown": breakdown_array,
            "historical_trend": [],  # Placeholder for future enhancement
        },
        "active_savings_plans": savings_data.get("plans", []),
    }

    # Convert to JSON string with pretty formatting
    json_content = json.dumps(report, indent=2, default=str)

    logger.info(f"JSON report generated ({len(json_content)} bytes)")
    return json_content


def upload_report_to_s3(
    config: Dict[str, Any], report_content: str, report_format: str = "html"
) -> str:
    """
    Upload report to storage.
    Supports both AWS S3 and local filesystem modes.

    Uses module-level s3_client for S3 operations.

    Args:
        config: Configuration dictionary with reports_bucket
        report_content: HTML report content
        report_format: Report format (default: 'html')

    Returns:
        str: S3 object key (AWS mode) or file path (local mode)

    Raises:
        ClientError: If upload fails
    """
    bucket_name = config["reports_bucket"]
    logger.info(f"Uploading report to storage: {bucket_name}")

    try:
        # Use storage adapter for both local and AWS modes
        storage_adapter = StorageAdapter(s3_client=s3_client, bucket_name=bucket_name)
        object_key = storage_adapter.upload_report(
            report_content=report_content, report_format=report_format
        )

        logger.info(f"Report uploaded successfully: {object_key}")
        return object_key

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to upload report - Code: {error_code}, Message: {error_message}")
        raise


def send_report_email(
    config: Dict[str, Any],
    s3_object_key: str,
    coverage_summary: Dict[str, Any],
    savings_summary: Dict[str, Any],
) -> None:
    """
    Send email notification with S3 report link and summary.

    Uses module-level sns_client for sending notifications.

    Args:
        config: Configuration dictionary with sns_topic_arn and reports_bucket
        s3_object_key: S3 object key of the uploaded report
        coverage_summary: Coverage summary metrics
        savings_summary: Savings data summary

    Raises:
        ClientError: If SNS publish fails
    """
    logger.info("Sending report email notification")

    # Format execution timestamp
    execution_time = datetime.now(timezone.utc).isoformat()

    # Build S3 URL
    bucket_name = config["reports_bucket"]
    s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_object_key}"
    s3_console_url = (
        f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}?prefix={s3_object_key}"
    )

    # Extract summary metrics
    current_coverage = coverage_summary.get("current_coverage", 0.0)
    avg_coverage = coverage_summary.get("avg_coverage", 0.0)
    coverage_days = coverage_summary.get("coverage_days", 0)
    trend_direction = coverage_summary.get("trend_direction", "→")

    active_plans = savings_summary.get("plans_count", 0)
    total_commitment = savings_summary.get("total_commitment", 0.0)
    estimated_monthly_savings = savings_summary.get("estimated_monthly_savings", 0.0)
    average_utilization = savings_summary.get("average_utilization", 0.0)

    # Extract actual savings data
    actual_savings = savings_summary.get("actual_savings", {})
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    on_demand_equivalent_cost = actual_savings.get("on_demand_equivalent_cost", 0.0)
    net_savings = actual_savings.get("net_savings", 0.0)
    savings_percentage = actual_savings.get("savings_percentage", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    # Build email subject
    subject = f"Savings Plans Report - {current_coverage:.1f}% Coverage, ${net_savings:,.0f}/mo Actual Savings"

    # Build email body
    body_lines = [
        "AWS Savings Plans - Coverage & Savings Report",
        "=" * 60,
        f"Report Generated: {execution_time}",
        f"Reporting Period: {coverage_days} days",
        "",
        "COVERAGE SUMMARY:",
        "-" * 60,
        f"Current Coverage: {current_coverage:.2f}%",
        f"Average Coverage ({coverage_days} days): {avg_coverage:.2f}%",
        f"Trend: {trend_direction}",
        "",
        "SAVINGS SUMMARY:",
        "-" * 60,
        f"Active Savings Plans: {active_plans}",
        f"Total Hourly Commitment: ${total_commitment:.4f}/hour (${total_commitment * 730:,.2f}/month)",
        f"Average Utilization (7 days): {average_utilization:.2f}%",
        f"Estimated Monthly Savings: ${estimated_monthly_savings:,.2f}",
        "",
        "ACTUAL SAVINGS SUMMARY (30 days):",
        "-" * 60,
        f"On-Demand Equivalent Cost: ${on_demand_equivalent_cost:,.2f}",
        f"Actual Savings Plans Cost: ${actual_sp_cost:,.2f}",
        f"Net Savings: ${net_savings:,.2f}",
        f"Savings Percentage: {savings_percentage:.2f}%",
    ]

    # Add breakdown by type if available
    if breakdown_by_type:
        body_lines.append("")
        body_lines.append("Breakdown by Plan Type:")
        for plan_type, breakdown in breakdown_by_type.items():
            plans_count = breakdown.get("plans_count", 0)
            total_commitment_type = breakdown.get("total_commitment", 0.0)
            body_lines.append(
                f"  {plan_type}: {plans_count} plan(s), ${total_commitment_type:.4f}/hr"
            )

    body_lines.extend(
        [
            "",
            "REPORT ACCESS:",
            "-" * 60,
            f"S3 Location: s3://{bucket_name}/{s3_object_key}",
            f"Direct Link: {s3_url}",
            f"Console Link: {s3_console_url}",
            "",
            "-" * 60,
            "This is an automated report from AWS Savings Plans Automation.",
        ]
    )

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(TopicArn=config["sns_topic_arn"], Subject=subject, Message=message_body)
        logger.info("Report email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send report email: {e!s}")
        raise

    # Notifications after SNS (errors should not break email sending)
    try:
        slack_webhook_url = config.get("slack_webhook_url")
        if slack_webhook_url:
            slack_message = notifications.format_slack_message(subject, body_lines, severity="info")
            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Slack notification sent successfully")
            else:
                logger.warning("Slack notification failed")
    except Exception as e:
        logger.warning(f"Slack notification error (non-fatal): {e!s}")

    try:
        teams_webhook_url = config.get("teams_webhook_url")
        if teams_webhook_url:
            teams_message = notifications.format_teams_message(subject, body_lines)
            if notifications.send_teams_notification(teams_webhook_url, teams_message):
                logger.info("Teams notification sent successfully")
            else:
                logger.warning("Teams notification failed")
    except Exception as e:
        logger.warning(f"Teams notification error (non-fatal): {e!s}")


def send_error_email(config: Dict[str, Any] = None, error_msg: str = None) -> None:
    """
    Send error notification email - backward compatible wrapper.

    This function provides backward compatibility for tests that expect
    send_error_email at module level.

    Args:
        config: Configuration dictionary (if None, loads from env)
        error_msg: Error message to send
    """
    if config is None:
        config = load_configuration()

    try:
        sns_client = globals()["sns_client"]
        send_error_notification(
            sns_client=sns_client,
            sns_topic_arn=config["sns_topic_arn"],
            error_message=error_msg,
            lambda_name="Reporter",
            slack_webhook_url=config.get("slack_webhook_url"),
            teams_webhook_url=config.get("teams_webhook_url"),
        )
    except Exception as e:
        logger.warning(f"Failed to send error email: {e}")


# Backward-compatible imports for AWS utils (required by existing tests)
