"""Tolerant JSON extraction from model output."""
from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences or surrounding prose."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object found in model output") from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in model output: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("model output JSON was not an object")
    return data
