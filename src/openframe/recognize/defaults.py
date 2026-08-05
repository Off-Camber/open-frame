"""Shared default locator construction for CLI, runner, MCP, and Session."""

from __future__ import annotations

from typing import Any

from openframe.recognize.a11y import MacOSA11yRecognizer
from openframe.recognize.locator import Locator
from openframe.recognize.ocr import TesseractRecognizer


def build_default_locator() -> Locator:
    """Return the standard recognizer chain (a11y + OCR + optional template).

    ``TemplateRecognizer`` is registered when importable. It only emits targets
    when callers pass ``options["template"]``, so default text recognition is
    unchanged without that param.
    """
    recognizers: list[Any] = [MacOSA11yRecognizer(), TesseractRecognizer()]
    try:
        from openframe.recognize.template import TemplateRecognizer
    except ImportError:  # pragma: no cover - package always importable; deps checked at match time
        pass
    else:
        recognizers.append(TemplateRecognizer())
    return Locator(recognizers)


def recognition_options_from_mapping(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract recognizer options (template path, threshold, scales, match_mode)."""
    if not params:
        return None
    options: dict[str, Any] = {}
    template = params.get("template")
    if template is not None and str(template).strip():
        options["template"] = str(template).strip()
    if "template_threshold" in params and params.get("template_threshold") is not None:
        options["template_threshold"] = float(params["template_threshold"])
    if "template_max_matches" in params and params.get("template_max_matches") is not None:
        options["template_max_matches"] = int(params["template_max_matches"])
    if "template_scales" in params and params.get("template_scales") is not None:
        options["template_scales"] = params["template_scales"]
    if "match_mode" in params and params.get("match_mode") is not None:
        options["match_mode"] = params["match_mode"]
    return options or None
