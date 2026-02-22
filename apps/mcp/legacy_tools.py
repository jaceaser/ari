"""
First-pass deterministic tools migrated from legacy behavior.

These are intentionally side-effect free so app/api can call them directly
while the MCP server layer is being built out.
"""

from __future__ import annotations

import re
from typing import Optional

_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "with",
    "on",
    "at",
    "by",
    "from",
    "please",
    "show",
    "tell",
    "explain",
    "give",
    "make",
    "create",
    "return",
    "format",
    "context",
    "question",
    "answer",
}


def build_retrieval_query(text: str, max_terms: int = 18) -> str:
    """
    Legacy behavior from `legacy/azure_openai.py:_build_retrieval_query`.
    Turns a verbose prompt into keyword-heavy retrieval text.
    """
    content = (text or "").lower()

    numbers = re.findall(r"\b\d{3,}\b", content)
    words = re.findall(r"[a-z0-9]{3,}", content)
    words = [w for w in words if w not in _STOP_WORDS]

    seen: set[str] = set()
    terms: list[str] = []

    for token in numbers + words:
        if token not in seen:
            seen.add(token)
            terms.append(token)

    return " ".join(terms[:max_terms])


def infer_lead_type_from_url(url: str) -> str:
    """
    Legacy behavior from `legacy/chat_handler.py:_infer_lead_type_from_url`.
    """
    if not url:
        return "Unknown"
    if "fixer-upper_att" in url:
        return "Fixer Upper"
    if "/rentals/" in url:
        return "Tired Landlords"
    if '"pf":{"value":true}' in url:
        return "Pre-Foreclosure"
    if '"att":{"value":"as is"}' in url:
        return "As-Is"
    if '"built":{"min":2015}' in url and '"ac":{"value":true}' in url:
        return "Subject To"
    if '"doz":{"value":"36m"}' in url and '"category":"cat2"' in url:
        return "FSBO"
    return "General Lead"


def extract_first_url(text: str) -> Optional[str]:
    """
    Utility for routing lead-type detection from free-form user prompts.
    """
    if not text:
        return None

    match = re.search(r"https?://[^\s]+", text)
    return match.group(0) if match else None

