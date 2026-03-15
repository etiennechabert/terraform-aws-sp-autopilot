SP_TYPE_TOGGLES = {
    "enable_compute_sp": {
        "required": False,
        "type": "bool",
        "default": "true",
        "env_var": "ENABLE_COMPUTE_SP",
    },
    "enable_database_sp": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "ENABLE_DATABASE_SP",
    },
    "enable_sagemaker_sp": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "ENABLE_SAGEMAKER_SP",
    },
}

STRATEGY_PARAMS = {
    "target_strategy_type": {
        "required": False,
        "type": "str",
        "default": "dynamic",
        "env_var": "TARGET_STRATEGY_TYPE",
    },
    "split_strategy_type": {
        "required": False,
        "type": "str",
        "default": "gap_split",
        "env_var": "SPLIT_STRATEGY_TYPE",
    },
    "dynamic_risk_level": {
        "required": False,
        "type": "str",
        "default": "min_hourly",
        "env_var": "DYNAMIC_RISK_LEVEL",
    },
    "prudent_percentage": {
        "required": False,
        "type": "float",
        "default": "85.0",
        "env_var": "PRUDENT_PERCENTAGE",
    },
    "savings_percentage": {
        "required": False,
        "type": "float",
        "default": "30.0",
        "env_var": "SAVINGS_PERCENTAGE",
    },
    "max_purchase_percent": {
        "required": False,
        "type": "float",
        "env_var": "MAX_PURCHASE_PERCENT",
    },
    "min_purchase_percent": {
        "required": False,
        "type": "float",
        "default": "1.0",
        "env_var": "MIN_PURCHASE_PERCENT",
    },
    "fixed_step_percent": {
        "required": False,
        "type": "float",
        "default": "10.0",
        "env_var": "FIXED_STEP_PERCENT",
    },
    "gap_split_divider": {
        "required": False,
        "type": "float",
        "default": "2.0",
        "env_var": "GAP_SPLIT_DIVIDER",
    },
}

SP_TERM_PAYMENT_OPTIONS = {
    "compute_sp_term": {
        "required": False,
        "type": "str",
        "default": "THREE_YEAR",
        "env_var": "COMPUTE_SP_TERM",
    },
    "compute_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "COMPUTE_SP_PAYMENT_OPTION",
    },
    "database_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "NO_UPFRONT",
        "env_var": "DATABASE_SP_PAYMENT_OPTION",
    },
    "sagemaker_sp_term": {
        "required": False,
        "type": "str",
        "default": "THREE_YEAR",
        "env_var": "SAGEMAKER_SP_TERM",
    },
    "sagemaker_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "SAGEMAKER_SP_PAYMENT_OPTION",
    },
}

SPIKE_GUARD_PARAMS = {
    "spike_guard_enabled": {
        "required": False,
        "type": "bool",
        "default": "true",
        "env_var": "SPIKE_GUARD_ENABLED",
    },
    "spike_guard_long_lookback_days": {
        "required": False,
        "type": "int",
        "default": "90",
        "env_var": "SPIKE_GUARD_LONG_LOOKBACK_DAYS",
    },
    "spike_guard_short_lookback_days": {
        "required": False,
        "type": "int",
        "default": "14",
        "env_var": "SPIKE_GUARD_SHORT_LOOKBACK_DAYS",
    },
    "spike_guard_threshold_percent": {
        "required": False,
        "type": "float",
        "default": "20",
        "env_var": "SPIKE_GUARD_THRESHOLD_PERCENT",
    },
}

AWS_COMMON = {
    "management_account_role_arn": {
        "required": False,
        "type": "str",
        "env_var": "MANAGEMENT_ACCOUNT_ROLE_ARN",
    },
    "tags": {"required": False, "type": "json", "default": "{}", "env_var": "TAGS"},
}
