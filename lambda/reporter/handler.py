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
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients (initialized as globals, reassigned in handler if using assume role)
ce_client = boto3.client('ce')
s3_client = boto3.client('s3')
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
            RoleSessionName='sp-autopilot-reporter'
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
            # Keep SNS/S3 using local credentials
            'sns': boto3.client('sns'),
            's3': boto3.client('s3'),
        }
    else:
        return {
            'ce': boto3.client('ce'),
            'savingsplans': boto3.client('savingsplans'),
            'sns': boto3.client('sns'),
            's3': boto3.client('s3'),
        }


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
    global ce_client, savingsplans_client, s3_client

    try:
        logger.info("Starting Reporter Lambda execution")

        # Load configuration from environment
        config = load_configuration()

        # Initialize clients (with assume role if configured)
        try:
            clients = get_clients(config)
            ce_client = clients['ce']
            savingsplans_client = clients['savingsplans']
            s3_client = clients['s3']
        except ClientError as e:
            error_msg = f"Failed to initialize AWS clients: {str(e)}"
            if config.get('management_account_role_arn'):
                error_msg = f"Failed to assume role {config['management_account_role_arn']}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            send_error_email(config, error_msg)
            raise

        # Step 1: Collect coverage history
        coverage_history = get_coverage_history(lookback_days=30)
        logger.info(f"Coverage history collected: {len(coverage_history)} data points")

        # Step 2: Gather savings data
        savings_data = get_savings_data()
        logger.info(f"Savings data collected: {savings_data.get('plans_count', 0)} active plans")

        # Step 3: Generate HTML report
        report_content = generate_html_report(coverage_history, savings_data)

        # Step 4: Upload report to S3
        s3_object_key = upload_report_to_s3(config, report_content, config['report_format'])
        logger.info(f"Report uploaded to S3: {s3_object_key}")

        # Step 5: Send email notification (if enabled)
        if config['email_reports']:
            # Calculate summary metrics for email
            avg_coverage = 0.0
            current_coverage = 0.0
            trend_direction = '→'

            if coverage_history:
                total_coverage = sum(item.get('coverage_percentage', 0.0) for item in coverage_history)
                avg_coverage = total_coverage / len(coverage_history)
                current_coverage = coverage_history[-1].get('coverage_percentage', 0.0)

                # Calculate trend
                if len(coverage_history) >= 2:
                    first_coverage = coverage_history[0].get('coverage_percentage', 0.0)
                    last_coverage = coverage_history[-1].get('coverage_percentage', 0.0)
                    trend = last_coverage - first_coverage
                    trend_direction = '↑' if trend > 0 else '↓' if trend < 0 else '→'

            coverage_summary = {
                'current_coverage': current_coverage,
                'avg_coverage': avg_coverage,
                'coverage_days': len(coverage_history),
                'trend_direction': trend_direction
            }

            send_report_email(config, s3_object_key, coverage_summary, savings_data)
            logger.info("Report email notification sent")
        else:
            logger.info("Email notifications disabled - skipping email")

        logger.info("Reporter Lambda completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Reporter completed successfully',
                's3_object_key': s3_object_key,
                'coverage_data_points': len(coverage_history),
                'active_plans': savings_data.get('plans_count', 0)
            })
        }

    except Exception as e:
        logger.error(f"Reporter Lambda failed: {str(e)}", exc_info=True)
        send_error_email(config, str(e))
        raise  # Re-raise to ensure Lambda fails visibly


def load_configuration() -> Dict[str, Any]:
    """Load and validate configuration from environment variables."""
    return {
        'reports_bucket': os.environ['REPORTS_BUCKET'],
        'sns_topic_arn': os.environ['SNS_TOPIC_ARN'],
        'report_format': os.environ.get('REPORT_FORMAT', 'html'),
        'email_reports': os.environ.get('EMAIL_REPORTS', 'false').lower() == 'true',
        'management_account_role_arn': os.environ.get('MANAGEMENT_ACCOUNT_ROLE_ARN'),
        'tags': json.loads(os.environ.get('TAGS', '{}')),
    }


def get_coverage_history(lookback_days: int = 30) -> List[Dict[str, Any]]:
    """
    Get Savings Plans coverage history from Cost Explorer.

    Args:
        lookback_days: Number of days to look back for coverage data

    Returns:
        list: Coverage data points by day with timestamps and percentages

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    logger.info(f"Fetching coverage history for last {lookback_days} days")

    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Querying coverage from {start_date} to {end_date}")

        # Get coverage data from Cost Explorer
        response = ce_client.get_savings_plans_coverage(
            TimePeriod={
                'Start': start_date.isoformat(),
                'End': end_date.isoformat()
            },
            Granularity='DAILY'
        )

        coverage_by_time = response.get('SavingsPlansCoverages', [])

        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return []

        # Parse coverage data points
        coverage_history = []
        for coverage_item in coverage_by_time:
            time_period = coverage_item.get('TimePeriod', {})
            coverage_data = coverage_item.get('Coverage', {})

            coverage_percentage = 0.0
            if 'CoveragePercentage' in coverage_data:
                coverage_percentage = float(coverage_data['CoveragePercentage'])

            coverage_hours = coverage_data.get('CoverageHours', {})
            on_demand_hours = float(coverage_hours.get('OnDemandHours', '0'))
            covered_hours = float(coverage_hours.get('CoveredHours', '0'))
            total_hours = float(coverage_hours.get('TotalRunningHours', '0'))

            coverage_history.append({
                'date': time_period.get('Start'),
                'coverage_percentage': coverage_percentage,
                'on_demand_hours': on_demand_hours,
                'covered_hours': covered_hours,
                'total_hours': total_hours
            })

        logger.info(f"Retrieved {len(coverage_history)} coverage data points")
        return coverage_history

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to get coverage history - Code: {error_code}, Message: {error_message}")
        raise


def get_savings_data() -> Dict[str, Any]:
    """
    Get savings data from active Savings Plans.

    Returns:
        dict: Savings Plans data including commitment, utilization, and estimated savings

    Raises:
        ClientError: If Savings Plans or Cost Explorer API calls fail
    """
    logger.info("Fetching savings data from active Savings Plans")

    try:
        # Get all active Savings Plans
        response = savingsplans_client.describe_savings_plans(
            filters=[
                {
                    'name': 'state',
                    'values': ['active']
                }
            ]
        )

        savings_plans = response.get('savingsPlans', [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        if not savings_plans:
            return {
                'total_commitment': 0.0,
                'plans_count': 0,
                'plans': [],
                'estimated_monthly_savings': 0.0,
                'average_utilization': 0.0
            }

        # Calculate total commitment and collect plan details
        total_hourly_commitment = 0.0
        plans_data = []

        for plan in savings_plans:
            hourly_commitment = float(plan.get('commitment', '0'))
            total_hourly_commitment += hourly_commitment

            plan_type = plan.get('savingsPlanType', 'Unknown')
            plan_id = plan.get('savingsPlanId', 'Unknown')
            start_date = plan.get('start', 'Unknown')
            end_date = plan.get('end', 'Unknown')
            payment_option = plan.get('paymentOption', 'Unknown')
            term = plan.get('termDurationInSeconds', 0) // (365 * 24 * 60 * 60)  # Convert seconds to years

            plans_data.append({
                'plan_id': plan_id,
                'plan_type': plan_type,
                'hourly_commitment': hourly_commitment,
                'start_date': start_date,
                'end_date': end_date,
                'payment_option': payment_option,
                'term_years': term
            })

        logger.info(f"Total hourly commitment: ${total_hourly_commitment:.2f}/hour")

        # Get utilization data from Cost Explorer
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=7)  # Last 7 days for utilization

            utilization_response = ce_client.get_savings_plans_utilization(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='DAILY'
            )

            utilizations = utilization_response.get('SavingsPlansUtilizationsByTime', [])

            if utilizations:
                # Calculate average utilization
                total_utilization = 0.0
                count = 0

                for util_item in utilizations:
                    utilization = util_item.get('Utilization', {})
                    utilization_percentage = utilization.get('UtilizationPercentage')

                    if utilization_percentage:
                        total_utilization += float(utilization_percentage)
                        count += 1

                average_utilization = total_utilization / count if count > 0 else 0.0
                logger.info(f"Average utilization over last 7 days: {average_utilization:.2f}%")
            else:
                average_utilization = 0.0
                logger.warning("No utilization data available")

        except ClientError as e:
            logger.warning(f"Failed to get utilization data: {str(e)}")
            average_utilization = 0.0

        # Estimate monthly savings
        # Rough estimate: commitment * hours per month * (1 - discount rate)
        # Assume typical savings rate of 25% vs On-Demand
        monthly_hours = 730  # Average hours per month
        estimated_monthly_savings = total_hourly_commitment * monthly_hours * 0.25

        logger.info(f"Estimated monthly savings: ${estimated_monthly_savings:.2f}")

        return {
            'total_commitment': total_hourly_commitment,
            'plans_count': len(savings_plans),
            'plans': plans_data,
            'estimated_monthly_savings': estimated_monthly_savings,
            'average_utilization': average_utilization
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to get savings data - Code: {error_code}, Message: {error_message}")
        raise


def generate_html_report(
    coverage_history: List[Dict[str, Any]],
    savings_data: Dict[str, Any]
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
    report_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    # Calculate coverage summary
    avg_coverage = 0.0
    if coverage_history:
        total_coverage = sum(item.get('coverage_percentage', 0.0) for item in coverage_history)
        avg_coverage = total_coverage / len(coverage_history)

    current_coverage = coverage_history[-1].get('coverage_percentage', 0.0) if coverage_history else 0.0

    # Calculate trend direction
    if len(coverage_history) >= 2:
        first_coverage = coverage_history[0].get('coverage_percentage', 0.0)
        last_coverage = coverage_history[-1].get('coverage_percentage', 0.0)
        trend = last_coverage - first_coverage
        trend_symbol = '↑' if trend > 0 else '↓' if trend < 0 else '→'
        trend_color = '#28a745' if trend > 0 else '#dc3545' if trend < 0 else '#6c757d'
    else:
        trend_symbol = '→'
        trend_color = '#6c757d'

    # Build HTML content
    html = f"""<!DOCTYPE html>
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
                <div class="value">{savings_data.get('plans_count', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Est. Monthly Savings</h3>
                <div class="value">${savings_data.get('estimated_monthly_savings', 0):,.0f}</div>
            </div>
        </div>

        <div class="section">
            <h2>Coverage Trends <span class="trend" style="color: {trend_color};">{trend_symbol}</span></h2>
"""

    # Coverage history table
    if coverage_history:
        html += """
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
"""
        for item in coverage_history:
            date = item.get('date', 'Unknown')
            coverage_pct = item.get('coverage_percentage', 0.0)
            covered_hours = item.get('covered_hours', 0.0)
            on_demand_hours = item.get('on_demand_hours', 0.0)
            total_hours = item.get('total_hours', 0.0)

            html += f"""
                    <tr>
                        <td>{date}</td>
                        <td class="metric">{coverage_pct:.2f}%</td>
                        <td>{covered_hours:,.0f}</td>
                        <td>{on_demand_hours:,.0f}</td>
                        <td>{total_hours:,.0f}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-data">No coverage data available</div>
"""

    html += """
        </div>

        <div class="section">
            <h2>Active Savings Plans</h2>
"""

    # Savings Plans table
    plans = savings_data.get('plans', [])
    if plans:
        total_commitment = savings_data.get('total_commitment', 0.0)
        avg_utilization = savings_data.get('average_utilization', 0.0)

        html += f"""
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
"""
        for plan in plans:
            plan_id = plan.get('plan_id', 'Unknown')
            plan_type = plan.get('plan_type', 'Unknown')
            hourly_commitment = plan.get('hourly_commitment', 0.0)
            term_years = plan.get('term_years', 0)
            payment_option = plan.get('payment_option', 'Unknown')
            start_date = plan.get('start_date', 'Unknown')
            end_date = plan.get('end_date', 'Unknown')

            # Format dates (extract date part from ISO timestamp)
            if 'T' in start_date:
                start_date = start_date.split('T')[0]
            if 'T' in end_date:
                end_date = end_date.split('T')[0]

            html += f"""
                    <tr>
                        <td style="font-family: monospace; font-size: 0.85em;">{plan_id[:20]}...</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.4f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td>{start_date}</td>
                        <td>{end_date}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-data">No active Savings Plans found</div>
"""

    html += f"""
        </div>

        <div class="footer">
            <p><strong>Savings Plans Autopilot</strong> - Automated Coverage & Savings Report</p>
            <p>Report Period: {len(coverage_history)} days | Generated: {report_timestamp}</p>
        </div>
    </div>
</body>
</html>
"""

    logger.info(f"HTML report generated ({len(html)} bytes)")
    return html


def upload_report_to_s3(
    config: Dict[str, Any],
    report_content: str,
    report_format: str = 'html'
) -> str:
    """
    Upload report to S3 with timestamp-based key.

    Args:
        config: Configuration dictionary with reports_bucket
        report_content: HTML report content
        report_format: Report format (default: 'html')

    Returns:
        str: S3 object key for the uploaded report

    Raises:
        ClientError: If S3 upload fails
    """
    bucket_name = config['reports_bucket']
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')
    object_key = f"savings-plans-report_{timestamp}.{report_format}"

    logger.info(f"Uploading report to S3: s3://{bucket_name}/{object_key}")

    try:
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=report_content.encode('utf-8'),
            ContentType='text/html' if report_format == 'html' else 'text/plain',
            ServerSideEncryption='AES256',
            Metadata={
                'generated-at': datetime.now(timezone.utc).isoformat(),
                'generator': 'sp-autopilot-reporter'
            }
        )

        logger.info(f"Report uploaded successfully: {object_key}")
        return object_key

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to upload report to S3 - Code: {error_code}, Message: {error_message}")
        raise


def send_report_email(
    config: Dict[str, Any],
    s3_object_key: str,
    coverage_summary: Dict[str, Any],
    savings_summary: Dict[str, Any]
) -> None:
    """
    Send email notification with S3 report link and summary.

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
    bucket_name = config['reports_bucket']
    s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_object_key}"
    s3_console_url = f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}?prefix={s3_object_key}"

    # Extract summary metrics
    current_coverage = coverage_summary.get('current_coverage', 0.0)
    avg_coverage = coverage_summary.get('avg_coverage', 0.0)
    coverage_days = coverage_summary.get('coverage_days', 0)
    trend_direction = coverage_summary.get('trend_direction', '→')

    active_plans = savings_summary.get('plans_count', 0)
    total_commitment = savings_summary.get('total_commitment', 0.0)
    estimated_monthly_savings = savings_summary.get('estimated_monthly_savings', 0.0)
    average_utilization = savings_summary.get('average_utilization', 0.0)

    # Build email subject
    subject = f"Savings Plans Report - {current_coverage:.1f}% Coverage, ${estimated_monthly_savings:,.0f}/mo Est. Savings"

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
        "REPORT ACCESS:",
        "-" * 60,
        f"S3 Location: s3://{bucket_name}/{s3_object_key}",
        f"Direct Link: {s3_url}",
        f"Console Link: {s3_console_url}",
        "",
        "-" * 60,
        "This is an automated report from AWS Savings Plans Automation.",
    ]

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(
            TopicArn=config['sns_topic_arn'],
            Subject=subject,
            Message=message_body
        )
        logger.info("Report email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send report email: {str(e)}")
        raise


def send_error_email(config: Dict[str, Any], error_message: str) -> None:
    """
    Send error notification via SNS.

    Args:
        config: Configuration dictionary with sns_topic_arn
        error_message: Error message to send
    """
    try:
        subject = "[SP Autopilot] Reporter Lambda Failed"
        message = f"""
Savings Plans Autopilot - Reporter Lambda Error

ERROR: {error_message}

Time: {datetime.now(timezone.utc).isoformat()}

Please check CloudWatch Logs for full details.
"""

        sns_client.publish(
            TopicArn=config['sns_topic_arn'],
            Subject=subject,
            Message=message
        )

        logger.info("Error notification sent via SNS")

    except Exception as e:
        logger.error(f"Failed to send error notification: {str(e)}")
        # Don't raise - we already have an error, don't mask it
