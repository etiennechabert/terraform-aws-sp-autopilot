from typing import Any


def resolve_fixed(
    config: dict[str, Any],
    spending_data: dict[str, Any] | None = None,
    sp_type_key: str | None = None,
) -> float:
    return config["coverage_target_percent"]
