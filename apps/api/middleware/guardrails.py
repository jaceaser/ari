"""
Content guardrails for the ARI API.

Three layers of defense applied before message processing:
1. Prompt injection detection — blocks attempts to override system instructions
2. Content moderation — blocks clearly harmful/illegal content
3. Off-topic detection — redirects non-real-estate queries

Each function returns an error string if blocked, or None if the message is clean.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("api.guardrails")

# ── 1. Prompt Injection Detection ──

# High-confidence patterns → hard block
_INJECTION_PATTERNS: list[re.Pattern] = [
    # Direct instruction override
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|earlier|preceding)\s+"
        r"(instructions|prompts|rules|directives|guidelines|context)",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(all\s+)?(previous|prior|above|your)\s+"
        r"(instructions|prompts|rules|directives|guidelines)",
        re.IGNORECASE,
    ),
    # System prompt extraction
    re.compile(
        r"(reveal|show|repeat|print|output|display|tell\s+me)\s+"
        r"(your|the)\s+(system\s+)?(prompt|instructions|rules|directives|system\s+message)",
        re.IGNORECASE,
    ),
    re.compile(r"what\s+are\s+your\s+(system\s+)?(instructions|rules|directives|prompt)", re.IGNORECASE),
    # Delimiter injection (LLM control tokens)
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"<\|user\|>", re.IGNORECASE),
    re.compile(r"<\|assistant\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<<SYS>>", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    # Jailbreak patterns
    re.compile(r"\bDAN\s+mode\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(
        r"bypass\s+(the\s+)?(safety|filter|restriction|guardrail|content\s+policy)",
        re.IGNORECASE,
    ),
    # Role override
    re.compile(r"forget\s+(all\s+)?(your|previous)\s+(instructions|training|rules|programming)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(?!looking|interested|ready|able|going)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(?!interested|a\s+(buyer|seller|investor|agent))", re.IGNORECASE),
    re.compile(r"new\s+(persona|identity|character|role)\s*:", re.IGNORECASE),
]


def check_prompt_injection(content: str) -> Optional[str]:
    """Check for prompt injection attempts.

    Returns an error message if high-confidence injection detected, None otherwise.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            logger.warning("Prompt injection detected: pattern=%s", pattern.pattern[:60])
            return "Your message was flagged as a potential prompt injection attempt. Please rephrase your real estate question."
    return None


# ── 2. Content Moderation ──

# Each entry: (pattern, description)
# Patterns use word boundaries and require context to avoid false positives
_MODERATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Illegal activity with real estate context
    (
        re.compile(r"\blaunder(ing)?\s+money\b", re.IGNORECASE),
        "money laundering",
    ),
    (
        re.compile(r"\bevade\s+taxes\b", re.IGNORECASE),
        "tax evasion",
    ),
    (
        re.compile(r"\bforge\s+(documents?|signatures?|contracts?)\b", re.IGNORECASE),
        "document forgery",
    ),
    (
        re.compile(r"\bfraudulent(ly)?\s+(deed|title|document|transfer)\b", re.IGNORECASE),
        "deed fraud",
    ),
    # PII solicitation (user trying to extract PII via the AI)
    (
        re.compile(
            r"(give\s+me|what\s+is|tell\s+me)\s+(your|the|a)\s+"
            r"(social\s+security|ssn|credit\s+card|bank\s+account)\s*(number)?",
            re.IGNORECASE,
        ),
        "PII solicitation",
    ),
    # Explicit threats
    (
        re.compile(r"\b(threaten|blackmail|extort)\s+(the\s+)?(seller|buyer|tenant|landlord|owner)\b", re.IGNORECASE),
        "threats",
    ),
    (
        re.compile(r"\bhow\s+to\s+(hack|break\s+into|illegally\s+enter)\b", re.IGNORECASE),
        "illegal activity",
    ),
]


def check_content(content: str) -> Optional[str]:
    """Check for harmful or illegal content.

    Returns an error message if flagged, None otherwise.
    Conservative — prefers false negatives over false positives.
    """
    for pattern, category in _MODERATION_PATTERNS:
        if pattern.search(content):
            logger.warning("Content moderation triggered: category=%s", category)
            return f"Your message was flagged for potentially inappropriate content ({category}). Please rephrase your question."
    return None


# ── 3. Off-Topic Detection ──

# Real estate signal words — if ANY match, the message is on-topic
_RE_SIGNALS: set[str] = {
    # Core RE terms
    "property", "real estate", "house", "home", "apartment", "condo",
    "mortgage", "foreclosure", "pre-foreclosure", "preforeclosure",
    "wholesale", "flip", "rehab", "rental", "tenant", "landlord",
    "lease", "eviction", "vacancy", "occupancy",
    # Financial
    "arv", "after repair value", "roi", "cash flow", "cap rate",
    "closing cost", "earnest money", "down payment", "equity",
    "appraisal", "assessment", "lien", "title",
    # Deal terms
    "comp", "comps", "comparable", "zillow", "mls", "listing",
    "offer", "contract", "assignment", "purchase agreement",
    "due diligence", "inspection", "contingency",
    # People/roles
    "buyer", "seller", "investor", "agent", "broker", "attorney",
    "contractor", "appraiser", "underwriter",
    # Lead gen
    "lead", "leads", "off-market", "offmarket", "distressed",
    "fsbo", "probate", "absentee", "owner",
    # Strategy
    "strategy", "deal", "market", "neighborhood", "zip code",
    "county", "subdivision", "zoning",
    # Education
    "how do i", "what is a", "explain", "guide", "education",
    "learn about", "teach me",
}

# Off-topic signals — block if present AND no RE signal found
_OFFTOPIC_PATTERNS: list[re.Pattern] = [
    # Entertainment
    re.compile(r"\b(sports?\s+score|game\s+score|who\s+won\s+the\s+game)\b", re.IGNORECASE),
    re.compile(r"\b(movie|tv\s+show|netflix|celebrity|gossip)\s+(recommend|suggestion|review)\b", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+a\s+joke\b", re.IGNORECASE),
    re.compile(r"\bwrite\s+(me\s+)?a\s+poem\b", re.IGNORECASE),
    re.compile(r"\bsing\s+(me\s+)?a\s+song\b", re.IGNORECASE),
    re.compile(r"\bplay\s+a\s+game\b", re.IGNORECASE),
    # Food/cooking
    re.compile(r"\b(recipe|cooking\s+tip|restaurant\s+recommend)\b", re.IGNORECASE),
    # Weather (standalone, not RE market context)
    re.compile(r"\b(weather|forecast|temperature)\s+(today|tomorrow|this\s+week)\b", re.IGNORECASE),
    re.compile(r"\bwhat('s|\s+is)\s+the\s+weather\b", re.IGNORECASE),
    # Code/tech (not RE related)
    re.compile(r"\b(write|debug|fix)\s+(me\s+)?(a\s+)?(python|javascript|java|html|css|sql)\b", re.IGNORECASE),
    re.compile(r"\bwrite\s+(a\s+)?code\b", re.IGNORECASE),
    # Health/medical
    re.compile(r"\b(medical\s+advice|diagnos[ei]s|symptoms?\s+(of|for)|symptoms?\b)", re.IGNORECASE),
    # Academic
    re.compile(r"\b(math\s+homework|solve\s+(this|the)\s+equation|write\s+my\s+essay)\b", re.IGNORECASE),
    re.compile(r"\bhelp\s+with\s+(my\s+)?(math\s+)?homework\b", re.IGNORECASE),
    # General non-RE
    re.compile(r"\b(horoscope|zodiac|fortune)\b", re.IGNORECASE),
    re.compile(r"\btranslate\s+(this|the\s+following)\s+(to|into)\b", re.IGNORECASE),
]

_OFFTOPIC_RESPONSE = (
    "I'm ARI, your real estate investment assistant! "
    "I'm best at helping with leads, comps, contracts, strategy, and education. "
    "What real estate topic can I help you with?"
)


# Compiled word-boundary patterns for RE signals (avoids substring matches like "home" in "homework")
_RE_SIGNAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + re.escape(signal) + r"\b", re.IGNORECASE)
    for signal in _RE_SIGNALS
]


def _has_re_signal(text: str) -> bool:
    """Check if text contains any real estate signal words (word-boundary match)."""
    return any(pattern.search(text) for pattern in _RE_SIGNAL_PATTERNS)


def check_off_topic(content: str) -> Optional[str]:
    """Check if message is off-topic for real estate assistant.

    Two-pass approach:
    1. If any real estate signal found → on-topic, allow
    2. If off-topic pattern matches and no RE signal → block with redirect

    Returns friendly redirect message if off-topic, None otherwise.
    """
    if _has_re_signal(content):
        return None

    for pattern in _OFFTOPIC_PATTERNS:
        if pattern.search(content):
            logger.info("Off-topic message blocked: pattern=%s", pattern.pattern[:60])
            return _OFFTOPIC_RESPONSE

    return None


# ── 4. MCP Prompt Sanitization ──

MAX_INJECTED_PROMPT_LENGTH = 2000


def sanitize_mcp_prompt(prompt: str) -> Optional[str]:
    """Validate and sanitize a prompt extracted from MCP tool response.

    Returns the sanitized prompt, or None if it should be rejected.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return None

    prompt = prompt.strip()

    # Reject if too long
    if len(prompt) > MAX_INJECTED_PROMPT_LENGTH:
        logger.warning("MCP prompt too long (%d chars), truncating", len(prompt))
        prompt = prompt[:MAX_INJECTED_PROMPT_LENGTH]

    # Reject if it contains injection patterns
    if check_prompt_injection(prompt):
        logger.warning("MCP prompt contains injection patterns, rejecting")
        return None

    return prompt
