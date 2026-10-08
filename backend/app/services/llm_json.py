"""Tolerant JSON extraction for LLM answers.

Small local models often wrap JSON in markdown, stop mid-object, leave trailing
commas, or restart the object per item. These helpers recover what the model
actually wrote; they never invent content.
"""

import json
import re
from typing import Any

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _merge_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """A small local model asked for many items (e.g. a dozen classes) sometimes
    "restarts" the JSON object per item instead of accumulating into one array -
    {"classes": [Patient]}, then later in the same response {"classes": [Doctor]},
    etc. Plain json.loads silently keeps only the LAST occurrence of a duplicate
    key, discarding every class but one with no error and no warning. This is a
    pure parsing-correctness fix (concatenate list values for a repeated key
    instead of overwriting) - it recovers data the model actually produced, it
    does not add or infer anything. Non-list duplicates keep the standard
    last-value-wins behavior, since concatenating scalars isn't meaningful.
    """
    merged: dict[str, Any] = {}
    for key, value in pairs:
        existing = merged.get(key)
        if isinstance(existing, list) and isinstance(value, list):
            merged[key] = existing + value
        else:
            merged[key] = value
    return merged


def _try_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text, object_pairs_hook=_merge_duplicate_json_keys)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _repair_candidates(text: str) -> list[str]:
    """Ways to close JSON that was cut off mid-generation (the usual small-model failure).

    1. Close whatever is still open (string, arrays, objects) at the very end.
    2. Cut back to the last complete array item / object member and close from there,
       which drops a half-written trailing item instead of keeping it mangled.
    Trailing commas before a closing bracket are removed first.
    """
    text = re.sub(r",\s*([}\]])", r"\1", text)
    stack: list[str] = []
    in_string = False
    escape = False
    last_safe: int | None = None
    safe_stack: list[str] = []
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if stack:
                stack.pop()
            last_safe, safe_stack = index + 1, list(stack)
        elif char == ",":
            last_safe, safe_stack = index, list(stack)

    def closers(open_brackets: list[str]) -> str:
        return "".join("}" if bracket == "{" else "]" for bracket in reversed(open_brackets))

    candidates = [text + ('"' if in_string else "") + closers(stack)]
    if last_safe is not None:
        candidates.append(re.sub(r",\s*$", "", text[:last_safe]) + closers(safe_stack))
    return candidates


def parse_json_response(content: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction. Returns None (never raises) when nothing usable
    is found, so the caller can fall back to a plain-text extraction instead of
    failing the whole stage outright - small local models frequently answer in prose
    or near-JSON rather than the requested strict shape.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = _try_json_object(cleaned)
    if parsed is not None:
        return parsed
    match = JSON_OBJECT_PATTERN.search(cleaned)
    candidate = match.group(0) if match is not None else cleaned[cleaned.find("{") :] if "{" in cleaned else cleaned
    parsed = _try_json_object(candidate)
    if parsed is not None:
        return parsed
    for repaired in _repair_candidates(candidate):
        parsed = _try_json_object(repaired)
        if parsed is not None:
            return parsed
    return None
