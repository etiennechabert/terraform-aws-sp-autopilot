"""Runtime validation of Lambda config loaded from env vars.

Terraform's variable validation blocks are the primary defense — this is a
second line of defense against drift between the Terraform and Lambda layers.
"""

from typing import Any


VALID_PAYMENT_OPTIONS = ["NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT"]
VALID_TERMS = ["ONE_YEAR", "THREE_YEAR"]
VALID_TARGET_STRATEGIES = ["aws", "dynamic", "static"]
VALID_SPLIT_STRATEGIES = ["one_shot", "fixed_step", "gap_split"]
VALID_RISK_LEVELS = ["prudent", "min_hourly", "optimal", "maximum"]
VALID_REPORT_FORMATS = ["html", "json", "csv"]


def _validate_number(
    value: Any,
    name: str,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    integer: bool = False,
) -> None:
    """Assert `value` is numeric and (optionally) within bounds."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Field '{name}' must be a number, got {type(value).__name__}: {value}")
    if integer and not isinstance(value, int):
        raise ValueError(f"Field '{name}' must be an integer, got {type(value).__name__}: {value}")
    if min_val is not None and value < min_val:
        raise ValueError(f"Field '{name}' must be >= {min_val}, got {value}")
    if max_val is not None and value > max_val:
        raise ValueError(f"Field '{name}' must be <= {max_val}, got {value}")


def _validate_choice(value: Any, name: str, choices: list[str]) -> None:
    if value not in choices:
        raise ValueError(f"Invalid {name}: '{value}'. Must be one of: {', '.join(choices)}")


def _validate_sp_types_enabled(config: dict[str, Any], context: str = "") -> None:
    if not any(
        config.get(k, False)
        for k in ("enable_compute_sp", "enable_database_sp", "enable_sagemaker_sp")
    ):
        suffix = f" for {context}" if context else ""
        raise ValueError(
            f"At least one Savings Plan type must be enabled{suffix}. "
            "Set ENABLE_COMPUTE_SP, ENABLE_DATABASE_SP, or ENABLE_SAGEMAKER_SP to true."
        )


def _validate_lookback_hours(config: dict[str, Any]) -> None:
    if "lookback_hours" not in config:
        return
    # AWS Cost Explorer retains hourly data for 14 days (336h).
    _validate_number(
        config["lookback_hours"], "lookback_hours", min_val=1, max_val=336, integer=True
    )


def _validate_strategies(config: dict[str, Any]) -> None:
    if "target_strategy_type" in config:
        _validate_choice(
            config["target_strategy_type"], "target_strategy_type", VALID_TARGET_STRATEGIES
        )
    if "split_strategy_type" in config:
        _validate_choice(
            config["split_strategy_type"], "split_strategy_type", VALID_SPLIT_STRATEGIES
        )
    if config.get("dynamic_risk_level"):
        _validate_choice(config["dynamic_risk_level"], "dynamic_risk_level", VALID_RISK_LEVELS)


def _validate_spike_guard_params(config: dict[str, Any]) -> None:
    if "spike_guard_long_lookback_days" in config:
        _validate_number(
            config["spike_guard_long_lookback_days"],
            "spike_guard_long_lookback_days",
            min_val=1,
            max_val=90,
            integer=True,
        )
    if "spike_guard_short_lookback_days" in config:
        _validate_number(
            config["spike_guard_short_lookback_days"],
            "spike_guard_short_lookback_days",
            min_val=1,
            integer=True,
        )
    if (
        "spike_guard_long_lookback_days" in config
        and "spike_guard_short_lookback_days" in config
        and config["spike_guard_long_lookback_days"] <= config["spike_guard_short_lookback_days"]
    ):
        raise ValueError(
            "spike_guard_long_lookback_days must be greater than spike_guard_short_lookback_days"
        )
    if "spike_guard_threshold_percent" in config:
        _validate_number(
            config["spike_guard_threshold_percent"],
            "spike_guard_threshold_percent",
            min_val=1.0,
            max_val=100.0,
        )


def _validate_non_empty_strings(config: dict[str, Any], fields: list[str]) -> None:
    for name in fields:
        if name in config:
            value = config[name]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Field '{name}' must be a non-empty string, got {type(value).__name__}"
                )


def _ensure_dict(config: Any) -> None:
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a dictionary, got {type(config).__name__}")


def validate_scheduler_config(config: dict[str, Any]) -> None:
    _ensure_dict(config)
    _validate_sp_types_enabled(config)

    for name in ("max_purchase_percent", "min_purchase_percent"):
        if name in config and config[name] is not None:
            _validate_number(config[name], name, min_val=0.0, max_val=100.0)

    if config.get("min_purchase_percent") is not None and config["min_purchase_percent"] <= 0:
        raise ValueError(
            f"Field 'min_purchase_percent' must be greater than 0, got {config['min_purchase_percent']}"
        )

    if "gap_split_divider" in config:
        _validate_number(config["gap_split_divider"], "gap_split_divider", min_val=0.000001)

    if "renewal_window_days" in config:
        _validate_number(
            config["renewal_window_days"], "renewal_window_days", min_val=1, integer=True
        )

    if "purchase_cooldown_days" in config:
        _validate_number(
            config["purchase_cooldown_days"], "purchase_cooldown_days", min_val=0, integer=True
        )

    _validate_lookback_hours(config)

    if "min_commitment_per_plan" in config:
        _validate_number(config["min_commitment_per_plan"], "min_commitment_per_plan", min_val=0)

    for name in ("compute_sp_term", "sagemaker_sp_term"):
        if name in config:
            _validate_choice(config[name], name, VALID_TERMS)

    for name in (
        "compute_sp_payment_option",
        "sagemaker_sp_payment_option",
        "database_sp_payment_option",
    ):
        if name in config:
            _validate_choice(config[name], name, VALID_PAYMENT_OPTIONS)

    _validate_strategies(config)
    _validate_spike_guard_params(config)


def validate_reporter_config(config: dict[str, Any]) -> None:
    _ensure_dict(config)
    _validate_sp_types_enabled(config, "reporting")

    if "report_format" in config:
        _validate_choice(config["report_format"], "report_format", VALID_REPORT_FORMATS)

    if "email_reports" in config and not isinstance(config["email_reports"], bool):
        raise ValueError(
            f"Field 'email_reports' must be a boolean, "
            f"got {type(config['email_reports']).__name__}: {config['email_reports']}"
        )

    if "tags" in config and not isinstance(config["tags"], dict):
        raise ValueError(
            f"Field 'tags' must be a dictionary, got {type(config['tags']).__name__}: {config['tags']}"
        )

    _validate_lookback_hours(config)

    if "low_utilization_threshold" in config:
        _validate_number(
            config["low_utilization_threshold"],
            "low_utilization_threshold",
            min_val=0.0,
            max_val=100.0,
        )

    _validate_non_empty_strings(
        config,
        [
            "reports_bucket",
            "sns_topic_arn",
            "management_account_role_arn",
            "slack_webhook_url",
            "teams_webhook_url",
        ],
    )
    _validate_spike_guard_params(config)


def validate_purchaser_config(config: dict[str, Any]) -> None:
    _ensure_dict(config)

    if "renewal_window_days" in config:
        _validate_number(
            config["renewal_window_days"], "renewal_window_days", min_val=1, integer=True
        )

    _validate_lookback_hours(config)

    if "tags" in config and not isinstance(config["tags"], dict):
        raise ValueError(
            f"Field 'tags' must be a dictionary, got {type(config['tags']).__name__}: {config['tags']}"
        )

    _validate_non_empty_strings(
        config,
        [
            "queue_url",
            "sns_topic_arn",
            "management_account_role_arn",
            "slack_webhook_url",
            "teams_webhook_url",
        ],
    )
    _validate_spike_guard_params(config)
