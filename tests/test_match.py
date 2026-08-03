"""Unit tests for shared token/phrase matching."""

from __future__ import annotations

import pytest

from openframe.recognize.match import (
    ambiguous_target_message,
    ensure_actionable_match_count,
    explicit_selector,
    text_matches_query,
    tokenize,
)


def test_tokenize_strips_punctuation() -> None:
    assert tokenize("Invoice No:") == ["invoice", "no"]
    assert tokenize("  AC  ") == ["ac"]


def test_token_mode_rejects_substring_inside_longer_word() -> None:
    assert text_matches_query("actuation", "AC") is False
    assert text_matches_query("Reaction", "AC") is False


def test_token_mode_matches_exact_token() -> None:
    assert text_matches_query("AC", "AC") is True
    assert text_matches_query("Press AC now", "AC") is True


def test_token_mode_matches_phrase_inside_longer_line() -> None:
    assert text_matches_query("Invoice No 123", "Invoice No") is True
    assert text_matches_query("Invoice No:", "Invoice No") is True


def test_substring_mode_keeps_legacy_containment() -> None:
    assert text_matches_query("actuation", "AC", mode="substring") is True


def test_ensure_actionable_match_count_fail_closed() -> None:
    with pytest.raises(ValueError, match="No target found"):
        ensure_actionable_match_count(query="AC", match_count=0, selector=None)

    with pytest.raises(ValueError, match="ambiguous_target"):
        ensure_actionable_match_count(query="Create", match_count=2, selector=None)

    ensure_actionable_match_count(query="Create", match_count=1, selector=None)
    ensure_actionable_match_count(query="Create", match_count=2, selector="top_most")
    with pytest.raises(ValueError, match="ambiguous_target"):
        ensure_actionable_match_count(query="Create", match_count=2, selector=None, expect_one=True)


def test_explicit_selector_and_message_helpers() -> None:
    assert explicit_selector(None) is None
    assert explicit_selector("  ") is None
    assert explicit_selector("top_most") == "top_most"
    assert "provide selector" in ambiguous_target_message("Create", 3)
