"""Flow model and loader for YAML-defined runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FlowStep:
    """One step in a declarative flow file."""

    id: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Flow:
    """A flow with variables and ordered steps."""

    name: str
    variables: dict[str, Any] = field(default_factory=dict)
    steps: list[FlowStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Flow":
        name = str(payload.get("name", "flow"))
        variables = payload.get("variables", {}) or {}
        raw_steps = payload.get("steps", []) or []
        if not isinstance(raw_steps, list):
            raise ValueError("Flow steps must be a list.")

        steps: list[FlowStep] = []
        for idx, item in enumerate(raw_steps):
            if not isinstance(item, dict):
                raise ValueError(f"Flow step at index {idx} must be a mapping.")
            kind = str(item.get("kind", "")).strip()
            if not kind:
                raise ValueError(f"Flow step at index {idx} is missing 'kind'.")
            step_id = str(item.get("id", f"step-{idx + 1}"))
            params = {key: value for key, value in item.items() if key not in {"id", "kind"}}
            steps.append(FlowStep(id=step_id, kind=kind, params=params))

        return cls(name=name, variables=dict(variables), steps=steps)


def load_flow(path: str | Path) -> Flow:
    """Load a flow from YAML on disk."""
    flow_path = Path(path).expanduser().resolve()
    if not flow_path.exists():
        raise ValueError(f"Flow path does not exist: {flow_path}")

    payload = _load_yaml(flow_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Flow file must parse to a top-level mapping.")
    return Flow.from_dict(payload)


def _load_yaml(text: str) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Flow loading requires PyYAML. Install with: pip install -e .[flow]") from exc
    return yaml.safe_load(text)
