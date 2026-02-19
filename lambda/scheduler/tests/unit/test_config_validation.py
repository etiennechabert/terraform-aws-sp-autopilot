import pytest

from shared.config_validation import (
    _validate_strategy_and_granularity,
    validate_scheduler_config,
)


BASE_CONFIG = {
    "enable_compute_sp": True,
    "enable_database_sp": False,
    "enable_sagemaker_sp": False,
}


class TestStrategyValidation:
    def test_valid_target_strategies(self):
        for strategy in ["fixed", "aws", "dynamic"]:
            config = {**BASE_CONFIG, "target_strategy_type": strategy}
            if strategy == "dynamic":
                config["dynamic_risk_level"] = "balanced"
            if strategy == "aws":
                config["split_strategy_type"] = "one_shot"
            _validate_strategy_and_granularity(config)

    def test_invalid_target_strategy(self):
        config = {**BASE_CONFIG, "target_strategy_type": "invalid"}
        with pytest.raises(ValueError, match="Invalid target_strategy_type"):
            _validate_strategy_and_granularity(config)

    def test_valid_split_strategies(self):
        for strategy in ["one_shot", "linear", "dichotomy"]:
            config = {**BASE_CONFIG, "split_strategy_type": strategy}
            _validate_strategy_and_granularity(config)

    def test_invalid_split_strategy(self):
        config = {**BASE_CONFIG, "split_strategy_type": "invalid"}
        with pytest.raises(ValueError, match="Invalid split_strategy_type"):
            _validate_strategy_and_granularity(config)

    def test_aws_target_requires_one_shot_split(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "aws",
            "split_strategy_type": "linear",
        }
        with pytest.raises(
            ValueError, match="AWS target strategy requires split_strategy_type='one_shot'"
        ):
            _validate_strategy_and_granularity(config)

    def test_aws_target_allows_one_shot(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "aws",
            "split_strategy_type": "one_shot",
        }
        _validate_strategy_and_granularity(config)

    def test_aws_target_allows_no_split(self):
        config = {**BASE_CONFIG, "target_strategy_type": "aws"}
        _validate_strategy_and_granularity(config)

    def test_dynamic_requires_risk_level(self):
        config = {**BASE_CONFIG, "target_strategy_type": "dynamic"}
        with pytest.raises(ValueError, match="requires 'dynamic_risk_level'"):
            _validate_strategy_and_granularity(config)

    def test_dynamic_invalid_risk_level(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "dynamic",
            "dynamic_risk_level": "yolo",
        }
        with pytest.raises(ValueError, match="Invalid dynamic_risk_level"):
            _validate_strategy_and_granularity(config)

    def test_dynamic_valid_risk_levels(self):
        for level in ["too_prudent", "min_hourly", "balanced", "aggressive"]:
            config = {
                **BASE_CONFIG,
                "target_strategy_type": "dynamic",
                "dynamic_risk_level": level,
            }
            _validate_strategy_and_granularity(config)

    def test_valid_granularity(self):
        for gran in ["HOURLY", "DAILY"]:
            config = {**BASE_CONFIG, "granularity": gran}
            _validate_strategy_and_granularity(config)

    def test_invalid_granularity(self):
        config = {**BASE_CONFIG, "granularity": "WEEKLY"}
        with pytest.raises(ValueError, match="Invalid granularity"):
            _validate_strategy_and_granularity(config)


class TestSchedulerConfigStrategies:
    def test_full_config_with_dynamic_strategy(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "dynamic",
            "split_strategy_type": "dichotomy",
            "dynamic_risk_level": "balanced",
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        validate_scheduler_config(config)

    def test_full_config_with_aws_strategy(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "aws",
            "split_strategy_type": "one_shot",
        }
        validate_scheduler_config(config)
