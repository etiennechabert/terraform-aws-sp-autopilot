"""
Shared constants for Savings Plans autopilot.

Centralizes all string constants to prevent typos and provide single source of truth.
Use AWS naming conventions everywhere for consistency.
"""

# ============================================================================
# Savings Plan Types (AWS Naming)
# ============================================================================
# These are the values returned by AWS APIs in describe_savings_plans
# Use these everywhere in code - only config keys use snake_case

PLAN_TYPE_COMPUTE = "Compute"
PLAN_TYPE_SAGEMAKER = "SageMaker"
PLAN_TYPE_DATABASE = "Database"
PLAN_TYPE_EC2_INSTANCE = "EC2Instance"


# ============================================================================
# AWS Cost Explorer Filter Values
# ============================================================================
# These are the exact values used in Cost Explorer SAVINGS_PLANS_TYPE dimension filters
# Format: CamelCase with no spaces (e.g., "ComputeSavingsPlans")

SP_FILTER_COMPUTE = "ComputeSavingsPlans"
SP_FILTER_SAGEMAKER = "SageMakerSavingsPlans"
SP_FILTER_DATABASE = "DatabaseSavingsPlans"
SP_FILTER_EC2_INSTANCE = "EC2InstanceSavingsPlans"


# ============================================================================
# Mappings
# ============================================================================

# Map plan type names to Cost Explorer filter values
PLAN_TYPE_TO_API_FILTER = {
    PLAN_TYPE_COMPUTE: SP_FILTER_COMPUTE,
    PLAN_TYPE_SAGEMAKER: SP_FILTER_SAGEMAKER,
    PLAN_TYPE_DATABASE: SP_FILTER_DATABASE,
    PLAN_TYPE_EC2_INSTANCE: SP_FILTER_EC2_INSTANCE,
}


# ============================================================================
# AWS Dimension Keys
# ============================================================================
# Cost Explorer API dimension keys

DIMENSION_SAVINGS_PLANS_TYPE = "SAVINGS_PLANS_TYPE"
DIMENSION_SERVICE = "SERVICE"
DIMENSION_REGION = "REGION"
DIMENSION_LINKED_ACCOUNT = "LINKED_ACCOUNT"


# ============================================================================
# Config Keys
# ============================================================================
# Configuration field names

CONFIG_ENABLE_COMPUTE_SP = "enable_compute_sp"
CONFIG_ENABLE_SAGEMAKER_SP = "enable_sagemaker_sp"
CONFIG_ENABLE_DATABASE_SP = "enable_database_sp"
CONFIG_LOOKBACK_DAYS = "lookback_days"
