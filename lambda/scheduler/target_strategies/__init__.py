from typing import Any

from target_strategies.aws_target import resolve_aws
from target_strategies.dynamic_target import resolve_dynamic
from target_strategies.fixed_target import resolve_fixed


TARGET_STRATEGIES = {
    "fixed": resolve_fixed,
    "aws": resolve_aws,
    "dynamic": resolve_dynamic,
}


def resolve_target(
    config: dict[str, Any],
    spending_data: dict[str, Any] | None = None,
    sp_type_key: str | None = None,
) -> float | None:
    strategy_type = config["target_strategy_type"]
    strategy_func = TARGET_STRATEGIES.get(strategy_type)
    if not strategy_func:
        available = ", ".join(TARGET_STRATEGIES.keys())
        raise ValueError(f"Unknown target strategy '{strategy_type}'. Available: {available}")
    return strategy_func(config, spending_data, sp_type_key=sp_type_key)
