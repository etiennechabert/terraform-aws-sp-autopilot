"""
Savings Plans Spending Analyzer.

Shared module for analyzing Savings Plans spending and coverage across AWS services.
Used by Scheduler (purchase decisions), Purchaser (cap validation), and Reporter (metrics).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient


logger = logging.getLogger(__name__)


# Service name constants for Savings Plans type mapping
# These are the actual SERVICE dimension values returned by AWS Cost Explorer API
#
# IMPORTANT: AWS Savings Plans Coverage
# - Compute SP: EC2, Lambda, Fargate (applied automatically across regions/families/OS)
# - SageMaker SP: All SageMaker usage (training, inference, notebooks, processing, etc.)
# - Database: NO Savings Plan product exists - databases use Reserved Instances
#   (We track database spend separately for coverage analysis and reporting)
#
# These lists include all possible AWS services that may appear in Cost Explorer.
# If a service isn't used in your account, it simply won't match any data.
#
# To see which services appear in YOUR account, run:
#   python3 scripts/discover_services.py

# Compute Savings Plan services
# Compute SP covers: EC2, Lambda, Fargate (across all regions, instance families, OS, tenancy)
# These are the EXACT valid SERVICE dimension values per AWS Cost Explorer API
COMPUTE_SP_SERVICES = [
    "Amazon Elastic Compute Cloud - Compute",
    "AWS Lambda",
    "Amazon EC2 Container Service",  # Alternative name for ECS
    "Amazon Elastic Container Service",
    "Amazon Elastic Container Service for Kubernetes",
    # Note: Fargate usage appears under ECS/EKS services, not as separate SERVICE
]

# Database services tracking
# IMPORTANT: AWS does NOT offer "Database Savings Plans"
# Databases use Reserved Instances or On-Demand pricing
# We track database spend separately for coverage analysis and reporting
# These are the EXACT valid SERVICE dimension values per AWS Cost Explorer API
DATABASE_SP_SERVICES = [
    "Amazon Relational Database Service",
    "Aurora DSQL",  # New serverless distributed SQL service
    "Amazon DynamoDB",
    "Amazon ElastiCache",
    "Amazon DocumentDB (with MongoDB compatibility)",  # Note: exact name includes parenthetical
    "Amazon Neptune",
    "Amazon Timestream",
    "Amazon Keyspaces (for Apache Cassandra)",  # Note: exact name includes parenthetical
    "AWS Database Migration Service",
]

# SageMaker Savings Plan services
# SageMaker SP covers all SageMaker compute (training, inference, notebooks, processing, etc.)
SAGEMAKER_SP_SERVICES = [
    "Amazon SageMaker",
]

# For mapping: Convert exact service names to lowercase for matching
# Used by group_coverage_by_sp_type() for both hourly and daily data
COMPUTE_SERVICE_NAMES_LOWER = {svc.lower() for svc in COMPUTE_SP_SERVICES}
DATABASE_SERVICE_NAMES_LOWER = {svc.lower() for svc in DATABASE_SP_SERVICES}
SAGEMAKER_SERVICE_NAMES_LOWER = {svc.lower() for svc in SAGEMAKER_SP_SERVICES}


def group_coverage_by_sp_type(coverage_data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Group Cost Explorer coverage data by Savings Plan type with time series.

    Takes coverage data and organizes it by SP type (compute, database, sagemaker)
    preserving the time series for graphing and analysis.

    Items are pre-tagged with SP type names ("compute", "database", "sagemaker")
    in _fetch_coverage_data for direct classification.

    Args:
        coverage_data: List of coverage items from SavingsPlansCoverages response

    Returns:
        dict: Time series and summary data by SP type, e.g.:
              {
                  "compute": {
                      "timeseries": [
                          {"timestamp": "2026-01-17T00:00:00Z", "covered": 10.5, "total": 15.2, "coverage": 69.1},
                          ...
                      ],
                      "summary": {
                          "total_covered": 779.16,
                          "total_spend": 939.10,
                          "avg_coverage": 82.97,
                          "min_total": 8.5,
                          "max_total": 18.2
                      }
                  },
                  "database": {...},
                  "sagemaker": {...}
              }
    """
    # Group by timestamp and SP type
    # Structure: {timestamp: {sp_type: {covered, total}}}
    timeseries_by_timestamp = {}

    for item in coverage_data:
        service_name = item.get("Attributes", {}).get("SERVICE", "").lower()
        coverage_info = item.get("Coverage", {})
        time_period = item.get("TimePeriod", {})

        # Parse spend amounts
        covered_spend = float(coverage_info.get("SpendCoveredBySavingsPlans", "0"))
        total_cost = float(coverage_info.get("TotalCost", "0"))

        # Get timestamp (use End as the timestamp)
        timestamp = time_period.get("End", "")
        if not timestamp:
            continue

        # Initialize timestamp entry if needed
        if timestamp not in timeseries_by_timestamp:
            timeseries_by_timestamp[timestamp] = {
                "compute": {"covered": 0.0, "total": 0.0},
                "database": {"covered": 0.0, "total": 0.0},
                "sagemaker": {"covered": 0.0, "total": 0.0},
            }

        # Map to SP type from tagged service names
        # Items are tagged with "compute", "database", or "sagemaker" in _fetch_coverage_data
        if service_name in ("compute", "database", "sagemaker"):
            sp_type = service_name
        else:
            # Should never happen - all items are tagged in _fetch_coverage_data
            logger.warning(f"Unexpected service name without SP type tag: {service_name}")
            continue

        # Accumulate spend for this timestamp and SP type
        timeseries_by_timestamp[timestamp][sp_type]["covered"] += covered_spend
        timeseries_by_timestamp[timestamp][sp_type]["total"] += total_cost

    # Build result with timeseries and summary for each SP type
    result = {
        "compute": {"timeseries": [], "summary": {}},
        "database": {"timeseries": [], "summary": {}},
        "sagemaker": {"timeseries": [], "summary": {}},
    }

    # Convert to timeseries format and calculate summaries
    for sp_type in ["compute", "database", "sagemaker"]:
        total_covered = 0.0
        total_spend = 0.0
        total_points = []

        # Sort timestamps for consistent ordering
        for timestamp in sorted(timeseries_by_timestamp.keys()):
            data = timeseries_by_timestamp[timestamp][sp_type]
            covered = data["covered"]
            total = data["total"]

            # Calculate coverage percentage for this point
            coverage = (covered / total * 100) if total > 0 else 0.0

            # Add to timeseries
            result[sp_type]["timeseries"].append(
                {
                    "timestamp": timestamp,
                    "covered": covered,
                    "total": total,
                    "coverage": coverage,
                }
            )

            # Track for summary
            total_covered += covered
            total_spend += total
            if total > 0:  # Only count non-zero points for min/max
                total_points.append(total)

        # Calculate summary statistics
        num_hours = len(result[sp_type]["timeseries"])
        avg_coverage = (total_covered / total_spend * 100) if total_spend > 0 else 0.0

        # Calculate hourly rates (Savings Plans are $/hour)
        avg_hourly_covered = total_covered / num_hours if num_hours > 0 else 0.0
        avg_hourly_total = total_spend / num_hours if num_hours > 0 else 0.0

        result[sp_type]["summary"] = {
            # Totals over the period
            "total_covered": total_covered,
            "total_spend": total_spend,
            "avg_coverage": avg_coverage,
            # Hourly rates (for purchase calculations)
            "avg_hourly_covered": avg_hourly_covered,
            "avg_hourly_total": avg_hourly_total,
            "min_hourly_total": min(total_points) if total_points else 0.0,
            "max_hourly_total": max(total_points) if total_points else 0.0,
        }

    return result


class SpendingAnalyzer:
    """
    Analyzes Savings Plans spending and coverage across AWS services.

    This class provides spending analysis functionality used across multiple lambdas:
    - Scheduler: Make purchase decisions based on current spend and coverage
    - Purchaser: Validate purchases don't exceed coverage cap
    - Reporter: Display spending metrics, coverage, and trends

    The analyzer aggregates spend data across services and time periods to compute
    accurate coverage percentages and spending details by SP type (Compute, Database, SageMaker).
    """

    def __init__(self, savingsplans_client: SavingsPlansClient, ce_client: CostExplorerClient):
        """
        Initialize the spending analyzer.

        Args:
            savingsplans_client: Boto3 Savings Plans client
            ce_client: Boto3 Cost Explorer client
        """
        self.savingsplans_client = savingsplans_client
        self.ce_client = ce_client

    def analyze_current_spending(self, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Analyze current Savings Plans spending and coverage with time series data.

        Note: AWS Cost Explorer returns aggregated coverage data for all active plans.
        The API does not support filtering by plan ID, so coverage includes all plans
        regardless of expiration date.

        Args:
            config: Configuration dictionary containing:
                - lookback_days: Days to look back for coverage data (default: 7)
                - granularity: API granularity - "HOURLY" or "DAILY" (default: "HOURLY")
                - enable_compute_sp: Whether to fetch Compute SP data
                - enable_database_sp: Whether to fetch Database SP data
                - enable_sagemaker_sp: Whether to fetch SageMaker SP data

        Returns:
            dict: Time series and summary data by SP type:
                {
                    "compute": {
                        "timeseries": [
                            {"timestamp": "2026-01-17T00:00:00Z", "covered": 10.5, "total": 15.2, "coverage": 69.1},
                            ...
                        ],
                        "summary": {
                            "total_covered": 779.16,
                            "total_spend": 939.10,
                            "avg_coverage": 82.97,
                            "min_total": 8.5,
                            "max_total": 18.2
                        }
                    },
                    "database": {...},
                    "sagemaker": {...}
                }

        Raises:
            ClientError: If AWS API calls fail
        """
        now = datetime.now(timezone.utc)

        # Step 1: Validate our service constants are complete
        granularity = config.get("granularity", "HOURLY")
        unknown_services = self._validate_service_constants(now, granularity)

        # Step 2: Fetch coverage data from Cost Explorer
        lookback_days = config.get("lookback_days", 7)
        coverage_data = self._fetch_coverage_data(now, lookback_days, config)

        # Step 3: Group coverage by SP type with time series
        sp_type_data = group_coverage_by_sp_type(coverage_data)

        logger.info(
            f"Coverage by type - Compute: {sp_type_data['compute']['summary']['avg_coverage']:.2f}% "
            f"(${sp_type_data['compute']['summary']['avg_hourly_total']:.2f}/h avg, "
            f"${sp_type_data['compute']['summary']['min_hourly_total']:.2f}-${sp_type_data['compute']['summary']['max_hourly_total']:.2f}/h range), "
            f"Database: {sp_type_data['database']['summary']['avg_coverage']:.2f}% "
            f"(${sp_type_data['database']['summary']['avg_hourly_total']:.2f}/h avg), "
            f"SageMaker: {sp_type_data['sagemaker']['summary']['avg_coverage']:.2f}% "
            f"(${sp_type_data['sagemaker']['summary']['avg_hourly_total']:.2f}/h avg)"
        )

        # Include unknown services in result for handler to check
        sp_type_data["_unknown_services"] = list(unknown_services)

        return sp_type_data

    def _fetch_coverage_data(
        self, now: datetime, lookback_days: int, config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetch Savings Plans coverage data from Cost Explorer.

        Supports both HOURLY and DAILY granularity. HOURLY provides better accuracy for
        purchase calculations since Savings Plans are priced as $/hour commitments, but
        DAILY can be used for accounts without hourly granularity enabled.

        AWS retains hourly data for ~14 days. With 1-day processing lag, we can reliably
        get 13 days of hourly data. Daily data is retained for 90+ days. Service filtering
        keeps each call under the 500-item limit.

        Args:
            now: Current timestamp
            lookback_days: Number of days to look back (max 13 for HOURLY, 90 for DAILY)
            config: Configuration dictionary with granularity and enable flags

        Returns:
            list: Coverage data items from Cost Explorer response

        Raises:
            ClientError: If AWS API calls fail
        """
        granularity = config.get("granularity", "HOURLY")
        end_time = now - timedelta(days=1)  # 1 day lag
        start_time = end_time - timedelta(days=lookback_days)

        # Build service filters only for enabled SP types
        service_filters = []
        if config.get("enable_compute_sp", True):
            service_filters.append(("Compute", COMPUTE_SP_SERVICES))
        if config.get("enable_database_sp", False):
            service_filters.append(("Database", DATABASE_SP_SERVICES))
        if config.get("enable_sagemaker_sp", False):
            service_filters.append(("SageMaker", SAGEMAKER_SP_SERVICES))

        if not service_filters:
            logger.warning("No SP types enabled - returning empty coverage data")
            return []

        logger.info(
            f"Fetching {granularity.lower()} coverage data for {lookback_days} days "
            f"using {len(service_filters)} service-filtered calls"
        )

        all_coverages = []

        # Format dates based on granularity
        # HOURLY requires ISO 8601 (yyyy-MM-ddTHH:mm:ssZ)
        # DAILY requires date only (yyyy-MM-dd)
        date_format = "%Y-%m-%d" if granularity == "DAILY" else "%Y-%m-%dT%H:%M:%SZ"

        try:
            for sp_type, service_list in service_filters:
                params = {
                    "TimePeriod": {
                        "Start": start_time.strftime(date_format),
                        "End": end_time.strftime(date_format),
                    },
                    "Granularity": granularity,
                    "Filter": {"Dimensions": {"Key": "SERVICE", "Values": service_list}},
                    # No GroupBy - AWS aggregates across filtered services per time period
                }

                response = self.ce_client.get_savings_plans_coverage(**params)
                coverages = response.get("SavingsPlansCoverages", [])

                # Tag each item with SP type for downstream grouping
                for item in coverages:
                    if "Attributes" not in item:
                        item["Attributes"] = {}
                    # Tag with lowercase SP type directly
                    item["Attributes"]["SERVICE"] = sp_type.lower()

                all_coverages.extend(coverages)

                logger.debug(
                    f"SP type '{sp_type}': Fetched {len(coverages)} items "
                    f"(total: {len(all_coverages)})"
                )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "DataUnavailableException":
                logger.warning(
                    "Cost Explorer data not available (new account or no usage data). "
                    "Returning empty coverage data."
                )
                return []
            raise

        if not all_coverages:
            logger.warning(f"No {granularity.lower()} coverage data available from Cost Explorer")
            return []

        logger.info(
            f"Fetched {len(all_coverages)} total {granularity.lower()} coverage data points "
            f"from {len(service_filters)} service-filtered calls"
        )

        return all_coverages

    def _validate_service_constants(self, now: datetime, granularity: str = "HOURLY") -> set[str]:
        """
        Validate that our service constants include all AWS services with SP coverage.

        Makes a single-day GROUP BY SERVICE call to discover all services with coverage data,
        then compares against our predefined service constants. This helps detect when AWS
        adds new services that support Savings Plans.

        Uses 1-day period to stay well under the 500-item limit while still discovering
        all active services.

        Args:
            now: Current timestamp
            granularity: API granularity - "HOURLY" or "DAILY" (default: "HOURLY")

        Returns:
            set: Unknown services found (empty if all services are known)

        Raises:
            ClientError: If AWS API call fails
        """
        end_time = now - timedelta(days=1)
        start_time = end_time - timedelta(days=1)  # 1 day only

        logger.debug("Validating service constants against AWS API (1-day GROUP BY SERVICE call)")

        try:
            params = {
                "TimePeriod": {
                    "Start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "End": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "Granularity": granularity,
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            }

            response = self.ce_client.get_savings_plans_coverage(**params)
            coverages = response.get("SavingsPlansCoverages", [])

            # Collect all unique services from the response
            discovered_services = set()
            for item in coverages:
                service = item.get("Attributes", {}).get("SERVICE")
                if service:
                    discovered_services.add(service)

            # Check against our known services
            all_known_services = set(
                COMPUTE_SP_SERVICES + DATABASE_SP_SERVICES + SAGEMAKER_SP_SERVICES
            )
            unknown_services = discovered_services - all_known_services

            if unknown_services:
                logger.warning(
                    f"Discovered {len(unknown_services)} unknown service(s) with Savings Plans coverage: "
                    f"{sorted(unknown_services)}. Analysis will continue with known services only."
                )
            else:
                logger.debug(
                    f"Service validation successful: {len(discovered_services)} services matched, "
                    f"{len(all_known_services)} total known services"
                )

            return unknown_services

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "DataUnavailableException":
                logger.debug("No coverage data available for validation (new account or no usage)")
                return set()
            raise
