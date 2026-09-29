"""Task validation and canonical targets, independent of any model backend."""

from dataclasses import dataclass
import json
import math
from typing import Any


class DataError(ValueError):
    """An actionable configuration or dataset validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DataError(message)


def identifier(value: Any, name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be a nonempty string")
    require(value == value.strip(), f"{name} must not have surrounding whitespace")
    return value


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"Expected finite JSON-compatible data: {exc}") from exc


def probability(value: Any, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} must be numeric")
    require(math.isfinite(value) and 0 <= value <= 1, f"{name} must be finite and between 0 and 1")
    return float(value)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    schema_version: str
    kind: str
    class_ids: tuple[str, ...]
    aliases: dict[str, str]
    unit: str = "example"

    @classmethod
    def from_dict(cls, spec: dict) -> "TaskSpec":
        require(isinstance(spec, dict), "task must be an object")
        kind = spec.get("kind")
        require(kind in {"single_label", "multi_label", "independent_binary"}, f"Unsupported task kind: {kind}")
        classes = spec.get("classes")
        require(isinstance(classes, list) and bool(classes), "task.classes must be a nonempty list")
        ids = []
        for item in classes:
            require(isinstance(item, dict), "Each class must be an object")
            ids.append(identifier(item.get("id"), "class ID"))
            identifier(item.get("description"), "class description")
        require(len(set(ids)) == len(ids), "Duplicate class IDs")
        if kind == "single_label":
            require(len(ids) >= 2, "single_label requires at least two classes")
        aliases = {}
        for item in classes:
            values = item.get("aliases", [])
            require(isinstance(values, list), "aliases must be a list")
            for alias in values:
                alias = identifier(alias, "alias")
                require(alias not in ids and alias not in aliases, f"Ambiguous alias: {alias}")
                aliases[alias] = item["id"]
        unit = spec.get("unit", "example")
        require(unit in {"example", "agent_step"}, f"Unsupported unit: {unit}")
        require(spec.get("unknown_label_policy", "error") == "error", "Only unknown_label_policy=error is supported")
        return cls(identifier(spec.get("task_id"), "task_id"),
                   identifier(spec.get("schema_version"), "task schema_version"),
                   kind, tuple(ids), aliases, unit)

    def label_id(self, value: Any) -> str:
        value = identifier(value, "label")
        result = self.aliases.get(value, value)
        require(result in self.class_ids, f"Unknown label: {value}")
        return result

    def targets(self, raw: Any, encoding: str, completeness: str) -> dict:
        """Null targets are unknown. Only declared complete label sets imply negatives."""
        require(completeness in {"complete", "positive_only"}, "label_completeness must be complete or positive_only")
        values = dict.fromkeys(self.class_ids)
        if raw is None:
            return {"encoding": "unlabeled", "values": values}
        if encoding == "probabilities":
            require(isinstance(raw, dict) and bool(raw), "probabilities must be a nonempty object; use null for unlabeled")
            seen = set()
            for key, value in raw.items():
                key = self.label_id(key)
                require(key not in seen, f"Duplicate normalized target: {key}")
                seen.add(key)
                values[key] = None if value is None else probability(value, key)
            if self.kind == "single_label":
                require(all(v is not None for v in values.values()), "single_label probabilities must cover every class")
                require(abs(sum(values.values()) - 1) <= 1e-6, "single_label probabilities must sum to one")
            return {"encoding": "probabilities", "values": values}
        require(encoding in {"label", "labels"}, f"Unknown target encoding: {encoding}")
        if encoding == "label":
            raw = [raw]
        require(isinstance(raw, list), "labels must be an array")
        labels = [self.label_id(v) for v in raw]
        require(len(set(labels)) == len(labels), "Duplicate normalized labels")
        if self.kind == "single_label":
            require(len(labels) == 1, "single_label needs exactly one label; use null for unlabeled")
            values = dict.fromkeys(self.class_ids, 0.0)
        elif completeness == "complete":
            values = dict.fromkeys(self.class_ids, 0.0)
        for label in labels:
            values[label] = 1.0
        return {"encoding": "hard", "values": values}


# Structural evidence fields must never enter the model input. This cannot detect
# future leakage hidden inside free text: source timestamp/semantic audits remain necessary.
FORBIDDEN_INPUT_KEYS = frozenset({
    "targets", "label_evidence", "future_events", "future_actions", "final_outcome",
    "candidate_outputs", "judge_rationale", "reference_answer", "downstream_outcome",
})


def validate_input(value: Any, path: str = "input") -> None:
    canonical_json(value)
    if isinstance(value, dict):
        for key, item in value.items():
            require(key not in FORBIDDEN_INPUT_KEYS, f"Forbidden model-input field: {path}.{key}")
            validate_input(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            validate_input(item, f"{path}[{i}]")


def model_input(record: dict) -> dict:
    """The only supported model-input projection; labels and metadata stay outside."""
    value = record["input"]
    validate_input(value)
    return value
