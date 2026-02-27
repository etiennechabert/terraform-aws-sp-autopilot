import pytest

from shared.config_validation import (
    _validate_strategies,
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
                config["dynamic_risk_level"] = "optimal"
            if strategy == "aws":
                config["split_strategy_type"] = "one_shot"
            _validate_strategies(config)

    def test_invalid_target_strategy(self):
        config = {**BASE_CONFIG, "target_strategy_type": "invalid"}
        with pytest.raises(ValueError, match="Invalid target_strategy_type"):
            _validate_strategies(config)

    def test_valid_split_strategies(self):
        for strategy in ["one_shot", "fixed_step", "gap_split"]:
            config = {**BASE_CONFIG, "split_strategy_type": strategy}
            _validate_strategies(config)

    def test_invalid_split_strategy(self):
        config = {**BASE_CONFIG, "split_strategy_type": "invalid"}
        with pytest.raises(ValueError, match="Invalid split_strategy_type"):
            _validate_strategies(config)

    def test_aws_target_with_any_split(self):
        for split in ["one_shot", "fixed_step", "gap_split"]:
            config = {
                **BASE_CONFIG,
                "target_strategy_type": "aws",
                "split_strategy_type": split,
            }
            _validate_strategies(config)

    def test_dynamic_requires_risk_level(self):
        config = {**BASE_CONFIG, "target_strategy_type": "dynamic"}
        with pytest.raises(ValueError, match="requires 'dynamic_risk_level'"):
            _validate_strategies(config)

    def test_dynamic_invalid_risk_level(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "dynamic",
            "dynamic_risk_level": "yolo",
        }
        with pytest.raises(ValueError, match="Invalid dynamic_risk_level"):
            _validate_strategies(config)

    def test_dynamic_valid_risk_levels(self):
        for level in ["prudent", "min_hourly", "optimal", "maximum"]:
            config = {
                **BASE_CONFIG,
                "target_strategy_type": "dynamic",
                "dynamic_risk_level": level,
            }
            _validate_strategies(config)


class TestSchedulerConfigStrategies:
    def test_full_config_with_dynamic_strategy(self):
        config = {
            **BASE_CONFIG,
            "target_strategy_type": "dynamic",
            "split_strategy_type": "gap_split",
            "dynamic_risk_level": "optimal",
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
