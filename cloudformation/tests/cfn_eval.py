"""Reads a CloudFormation template and evaluates it for a set of parameters.

Just enough of CloudFormation for the tests: short-form tags, Conditions, Rules,
Ref, Fn::If, Fn::FindInMap, Fn::Sub, Fn::Equals/And/Or/Not/Contains and
AWS::NoValue. References to resources resolve to placeholders such as
"<NotificationsTopic>" or "<SchedulerRole.Arn>".
"""

import re
from typing import Any

import yaml


PSEUDO_PARAMETERS = {
    "AWS::AccountId": "123456789012",
    "AWS::Region": "eu-west-1",
    "AWS::Partition": "aws",
    "AWS::StackName": "sp-autopilot",
}
NO_VALUE = object()


class CfnLoader(yaml.SafeLoader):
    """SafeLoader that reads !Ref, !Sub, !GetAtt... into their long forms."""


def _construct_intrinsic(loader: CfnLoader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    name = "Ref" if suffix == "Ref" else f"Fn::{suffix}"
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
        if suffix == "GetAtt":
            value = value.split(".", 1)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {name: value}


CfnLoader.add_multi_constructor("!", _construct_intrinsic)


def load(text: str) -> dict[str, Any]:
    return yaml.load(text, Loader=CfnLoader)  # CfnLoader is a SafeLoader


def _as_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class Stack:
    """A template evaluated for some parameter values (defaults for the rest)."""

    def __init__(self, template: dict[str, Any], **parameters: Any):
        self.template = template
        declared = template.get("Parameters", {})
        unknown = set(parameters) - set(declared)
        if unknown:
            raise KeyError(f"not template parameters: {sorted(unknown)}")
        self.parameters = {
            name: _as_string(parameters.get(name, spec.get("Default", "")))
            for name, spec in declared.items()
        }
        for name, value in self.parameters.items():
            allowed = declared[name].get("AllowedValues")
            if allowed is not None and value not in [_as_string(v) for v in allowed]:
                raise ValueError(f"{name}={value!r} is not one of {allowed}")
        self._conditions: dict[str, bool] = {}

    def condition(self, name: str) -> bool:
        if name not in self._conditions:
            self._conditions[name] = bool(self.resolve(self.template["Conditions"][name]))
        return self._conditions[name]

    def resources(self) -> dict[str, dict[str, Any]]:
        """The resources this stack creates, by logical id."""
        return {
            logical_id: resource
            for logical_id, resource in self.template["Resources"].items()
            if "Condition" not in resource or self.condition(resource["Condition"])
        }

    def properties(self, logical_id: str) -> dict[str, Any]:
        return self.resolve(self.resources()[logical_id].get("Properties", {}))

    def failing_rules(self) -> list[str]:
        failing = []
        for name, rule in self.template.get("Rules", {}).items():
            if "RuleCondition" in rule and not self.resolve(rule["RuleCondition"]):
                continue
            if not all(self.resolve(a["Assert"]) for a in rule["Assertions"]):
                failing.append(name)
        return failing

    def resolve(self, value: Any) -> Any:
        if isinstance(value, list):
            items = [self.resolve(v) for v in value]
            return [v for v in items if v is not NO_VALUE]
        if not isinstance(value, dict):
            return value
        if len(value) == 1:
            ((key, arg),) = value.items()
            handler = getattr(self, f"_fn_{key.replace('Fn::', '').lower()}", None)
            if key in ("Ref", "Condition") or key.startswith("Fn::"):
                if handler is None:
                    raise NotImplementedError(key)
                return handler(arg)
        resolved = {k: self.resolve(v) for k, v in value.items()}
        return {k: v for k, v in resolved.items() if v is not NO_VALUE}

    def _fn_ref(self, name: str) -> Any:
        if name == "AWS::NoValue":
            return NO_VALUE
        if name in PSEUDO_PARAMETERS:
            return PSEUDO_PARAMETERS[name]
        if name in self.parameters:
            return self.parameters[name]
        if name in self.template["Resources"]:
            return f"<{name}>"
        raise KeyError(f"Ref to unknown {name}")

    def _fn_condition(self, name: str) -> bool:
        return self.condition(name)

    def _fn_if(self, arg: list[Any]) -> Any:
        name, when_true, when_false = arg
        return self.resolve(when_true if self.condition(name) else when_false)

    def _fn_equals(self, arg: list[Any]) -> bool:
        left, right = (_as_string(self.resolve(v)) for v in arg)
        return left == right

    def _fn_not(self, arg: list[Any]) -> bool:
        return not self.resolve(arg[0])

    def _fn_and(self, arg: list[Any]) -> bool:
        return all(self.resolve(v) for v in arg)

    def _fn_or(self, arg: list[Any]) -> bool:
        return any(self.resolve(v) for v in arg)

    def _fn_contains(self, arg: list[Any]) -> bool:
        values, value = arg
        return _as_string(self.resolve(value)) in [_as_string(v) for v in self.resolve(values)]

    def _fn_findinmap(self, arg: list[Any]) -> Any:
        mapping, top, second = (self.resolve(v) for v in arg)
        return self.template["Mappings"][mapping][top][second]

    def _fn_getatt(self, arg: list[str]) -> str:
        logical_id, attribute = arg
        if logical_id not in self.template["Resources"]:
            raise KeyError(f"GetAtt on unknown {logical_id}")
        return f"<{logical_id}.{attribute}>"

    def _fn_sub(self, arg: Any) -> str:
        text, variables = (arg, {}) if isinstance(arg, str) else arg
        variables = {k: self.resolve(v) for k, v in variables.items()}

        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in variables:
                return _as_string(variables[name])
            if "." in name:
                return self._fn_getatt(name.split(".", 1))
            return _as_string(self._fn_ref(name))

        return re.sub(r"\$\{([^}!]+)\}", substitute, text)
