"""Shared text matching helpers for recognizers and verification."""

from __future__ import annotations

from typing import Literal

MatchMode = Literal["token", "substring"]

_TOKEN_PUNCTUATION = ".,:;!?()[]{}\"'"


def normalize_text(value: str) -> str:
    """Casefold and collapse whitespace."""
    return " ".join(value.casefold().split())


def tokenize(value: str) -> list[str]:
    """Split into comparison tokens, stripping common punctuation."""
    tokens: list[str] = []
    for raw in value.casefold().split():
        token = raw.strip(_TOKEN_PUNCTUATION)
        if token:
            tokens.append(token)
    return tokens


def text_matches_query(
    text: str,
    query: str,
    *,
    mode: MatchMode = "token",
) -> bool:
    """Return True when ``text`` safely matches ``query``.

    Default ``token`` mode requires whole-token or contiguous token-phrase
    equality after normalization. ``substring`` keeps the legacy containment
    behavior for explicit opt-in callers.
    """
    query_normalized = normalize_text(query)
    if not query_normalized:
        return False

    if mode == "substring":
        return query_normalized in normalize_text(text)

    query_tokens = tokenize(query)
    if not query_tokens:
        return False
    text_tokens = tokenize(text)
    return bool(matching_token_spans(text_tokens, query_tokens))


def matching_token_spans(
    text_tokens: list[str],
    query_tokens: list[str],
) -> list[tuple[int, int]]:
    """Return inclusive-exclusive spans where query tokens match contiguously."""
    if not query_tokens:
        return []
    query_len = len(query_tokens)
    spans: list[tuple[int, int]] = []
    for start in range(len(text_tokens) - query_len + 1):
        end = start + query_len
        if text_tokens[start:end] == query_tokens:
            spans.append((start, end))
    return spans


def ambiguous_target_message(query: str, match_count: int) -> str:
    """Standard error for unresolved multi-match click/fill actions."""
    return (
        f'ambiguous_target: query "{query}" matched {match_count} targets; '
        "provide selector or expect_one=true"
    )


def ensure_actionable_match_count(
    *,
    query: str,
    match_count: int,
    selector: str | None,
    expect_one: bool = False,
) -> None:
    """Fail closed when click/fill cannot safely choose a target.

    Zero matches always fail. Multiple matches fail unless the caller provided
    an explicit ``selector`` or ``expect_one`` (which itself requires exactly
    one match).
    """
    if match_count <= 0:
        raise ValueError(f'No target found for query "{query}".')
    if expect_one and match_count != 1:
        raise ValueError(ambiguous_target_message(query, match_count))
    if selector is None and match_count != 1:
        raise ValueError(ambiguous_target_message(query, match_count))


def explicit_selector(value: object | None) -> str | None:
    """Return a non-empty selector string, or None when none was provided."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
