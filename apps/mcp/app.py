"""
ARI MCP Tool Server (Milestone 3 slice)

This server exposes route-oriented tools inspired by the legacy ChatHandler.
It is intended to be called by apps/api only.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from quart import Quart, request

from legacy_tools import build_retrieval_query, extract_first_url, infer_lead_type_from_url
from middleware.guardrails import (
    Intent,
    classify_intent,
    check_injection,
    is_path_allowed,
    DOMAIN_RESTRICTION,
)
from schemas import ToolRequest

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mcp")

try:
    import certifi
except Exception:
    certifi = None

try:
    import httpx
except Exception:
    httpx = None

try:
    from azure.cosmos.aio import CosmosClient
except Exception:
    CosmosClient = None


def _load_env_file(path: Path) -> None:
    """
    Load key/value pairs from local .env without strict dotenv parsing.
    This tolerates complex quoted prompt lines in config values.
    """
    if not path.exists():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue

        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


LOCAL_ENV_PATH = Path(__file__).resolve().parent / ".env"

# Precedence: process env > apps/mcp/.env
# Custom parser handles complex quoted JSON values that python-dotenv can't parse
_load_env_file(LOCAL_ENV_PATH)
if LOCAL_ENV_PATH.exists():
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", module="dotenv")
        load_dotenv(LOCAL_ENV_PATH, override=False)

app = Quart(__name__)

# ---------------------------------------------------------------------------
# Domain guardrail — runs before every tool POST
# ---------------------------------------------------------------------------

_GUARD_SKIP_METHODS = frozenset({"GET", "OPTIONS"})
_GUARD_SKIP_PATHS = frozenset({
    "/",
    "/health",
    "/tools",
    "/tools/integration-config",
})


@app.before_request
async def _domain_guard():
    """
    Enforce domain guardrails on every POST to /tools/*.

    1. Extract prompt from JSON body.
    2. Reject prompt injection attempts (400).
    3. Classify intent (REAL_ESTATE_CORE / GENERAL / OFF_TOPIC / MALICIOUS).
    4. Refuse MALICIOUS requests (403).
    5. Block tools not in the intent's allowlist (422).
    """
    from quart import jsonify

    if request.method in _GUARD_SKIP_METHODS:
        return None

    if request.path in _GUARD_SKIP_PATHS:
        return None

    if not request.path.startswith("/tools/"):
        return None

    body = await request.get_json(silent=True) or {}
    prompt = (
        str(body.get("prompt") or "")
        or str((body.get("arguments") or {}).get("prompt") or "")
    ).strip()

    if not prompt:
        return None  # no prompt to check — let the handler decide

    # 1) Injection guard
    injection_err = check_injection(prompt)
    if injection_err:
        logger.warning("[guard] Injection detected on %s: %.120s", request.path, prompt)
        return jsonify({"error": "blocked", "detail": injection_err}), 400

    # 2) Intent classification
    intent = classify_intent(prompt)
    logger.info("[guard] path=%s intent=%s", request.path, intent.value)

    # 3) Malicious → refuse
    if intent == Intent.MALICIOUS:
        logger.warning("[guard] Malicious request on %s: %.120s", request.path, prompt)
        return jsonify({"error": "blocked", "detail": "Request refused"}), 403

    # 4) Tool allowlist by intent
    if not is_path_allowed(request.path, intent):
        logger.info(
            "[guard] Path %s not allowed for intent %s", request.path, intent.value
        )
        detail = (
            "I'm ARI, your real estate investment assistant. "
            "That question doesn't match real estate topics. "
            "Ask me about leads, comps, buyers, contracts, or strategy instead."
            if intent == Intent.OFF_TOPIC
            else f"This tool is not available for the current query intent ({intent.value})."
        )
        return jsonify({"error": "off_topic", "detail": detail}), 422

    return None


# ---------------------------------------------------------------------------


ROUTE_KEYWORDS: dict[str, set[str]] = {
    "Leads": {
        "lead",
        "leads",
        "seller",
        "sellers",
        "zillow",
        "offmarket",
        "off-market",
        "off market",
        "distressed",
        "preforeclosure",
        "pre-foreclosure",
        "pre foreclosure",
        "fsbo",
        "for sale by owner",
        "for-sale-by-owner",
        "landlord",
        "landlords",
        "tired landlord",
        "tired landlords",
        "absentee",
        "absentee owner",
        "absentee owners",
        "vacant",
        "vacant property",
        "vacant properties",
        "foreclosure",
        "foreclosures",
        "tax delinquent",
        "tax lien",
        "delinquent",
        "motivated",
        "motivated seller",
        "motivated sellers",
        "probate",
        "inherited",
        "inheritance",
        "divorce",
        "code violation",
        "code violations",
        "lis pendens",
        "pre-foreclosures",
        "high equity",
        "free and clear",
        "out of state",
        "out-of-state",
        "behind on payments",
        "behind on mortgage",
        "underwater",
        "upside down",
        "bankruptcy",
        "reo",
        "bank owned",
        "bank-owned",
        "agent owned",
        "agent listed",
        "agent-owned",
        "mls listed",
        "broker listed",
        "realtor listed",
        "high equity",
        "free and clear",
        "equity rich",
        "county",
        "foreclosed",
        "hud home",
        "hud homes",
        # Spanish
        "propietarios cansados",
        "propietario cansado",
        "dueños cansados",
        "dueño cansado",
        "vendedores motivados",
        "vendedor motivado",
        "propietarios ausentes",
        "propietario ausente",
        "propiedades vacantes",
        "propiedad vacante",
        "ejecuciones hipotecarias",
        "ejecución hipotecaria",
        "pre-ejecución",
        "embargo hipotecario",
        "banco dueño",
        "propiedad del banco",
        "en venta por dueño",
        "en venta por el dueño",
        "terreno",
        "terrenos",
        "lote",
        "lotes",
        "alta equidad",
        "libre de hipoteca",
        "listado por agente",
        "propiedad de agente",
        "sujeto a hipoteca",
        "heredada",
        "heredadas",
        "sucesión",
        "sucesion",
        "impuestos atrasados",
        "deuda atrasada",
        "dame una lista",
        "dame los leads",
        "busca una lista",
        "encuentra una lista",
    },
    "Comps": {
        "comp",
        "comps",
        "comparable",
        "arv",
        "after repair value",
        "valuation",
        "estimate value",
        # Spanish
        "comparables",
        "valor arv",
        "valor después de reparaciones",
        "valor despues de reparaciones",
        "cuánto vale",
        "cuanto vale",
        "análisis de mercado",
        "analisis de mercado",
    },
    "Attorneys": {
        "attorney", "attorneys", "lawyer", "probate", "eviction", "legal",
        # Spanish
        "abogado", "abogados", "abogado inmobiliario", "abogados de bienes raices",
        "abogados de bienes raíces", "abogados de desalojo", "abogados de embargo",
        "busca abogados", "encuentra abogados",
    },
    "Strategy": {"strategy", "plan", "business plan", "approach", "roadmap", "deal flow"},
    "Education": {"how", "explain", "learn", "education", "what is", "why", "guide"},
    "Contracts": {"contract", "assignment", "purchase agreement", "clause", "legal doc"},
    "Buyers": {
        "buyer", "buyers list", "cash buyer", "investor buyer", "disposition",
        # Spanish
        "compradores", "compradores en efectivo", "compradores de contado",
        "compradores de efectivo", "inversionistas compradores",
        "encuentra compradores", "busca compradores", "lista de compradores",
    },
}

STATE_ABBREVIATIONS: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

ADDRESS_REGEX = re.compile(
    r"(?P<addr>\b\d{1,6}\s+[A-Za-z0-9#.\-'\s]+?\s+"
    r"(?:Ave|Avenue|St|Street|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Cir|Circle|Pl|Place|Way|Pkwy|Parkway|Ter|Terrace)\b"
    r"(?:\s*(?:#|Unit|Apt|Suite)\s*[A-Za-z0-9\-]+)?"
    r"(?:\s*,?\s*[A-Za-z.\-'\s]+)?\s*,?\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b)",
    re.IGNORECASE,
)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value is not None else default


def _is_configured(*keys: str) -> bool:
    return all(bool(_env(key).strip()) for key in keys)


def _normalize_state(state: str) -> str:
    text = (state or "").strip()
    if len(text) == 2:
        return text.upper()

    normalized = " ".join(text.lower().split())
    return STATE_ABBREVIATIONS.get(normalized, text.upper())


INTEGRATION_CONFIG = {
    "azure_openai": _is_configured("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY"),
    "azure_search": _is_configured("AZURE_SEARCH_API_ENDPOINT", "AZURE_SEARCH_KEY"),
    "azure_cosmos": _is_configured("AZURE_COSMOSDB_ACCOUNT", "AZURE_COSMOSDB_ACCOUNT_KEY"),
    "azure_cosmos_buyers": _is_configured(
        "AZURE_COSMOSDB_ACCOUNT",
        "AZURE_COSMOSDB_ACCOUNT_KEY",
        "AZURE_COSMOSDB_BUYERS_DATABASE",
        "AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER",
    ),
    "bricked": _is_configured("BRICKED_API_KEY"),
    "stripe": _is_configured("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
}


ROUTE_PROMPTS: dict[str, str] = {
    "Classification": _env("AZURE_OPENAI_CLASSIFICATION_SYSTEM_MESSAGE"),
    "Education": _env("AZURE_OPENAI_SYSTEM_MESSAGE"),
    "Leads": _env("AZURE_OPENAI_LEADS_SYSTEM_MESSAGE"),
    "LeadsLink": _env("AZURE_OPENAI_LEAD_LINK_MESSAGE"),
    "Comps": _env("AZURE_OPENAI_COMP_PROPERTIES_MESSAGE"),
    "CompsLink": _env("AZURE_OPENAI_COMP_PROPERTIES_LINK_MESSAGE"),
    "Attorneys": _env("AZURE_OPENAI_ATTORNEYS_SYSTEM_MESSAGE"),
    "AttorneyLink": _env("AZURE_OPENAI_ATTORNEY_LINK_MESSAGE"),
    "Strategy": _env("AZURE_OPENAI_STRATEGY_PROMPT"),
    "Contracts": _env("AZURE_OPENAI_CONTRACTS_MESSAGE"),
    "ContractsExpansion": _env("AZURE_OPENAI_CONTRACTS_EXPANSION_MESSAGE"),
    "Buyers": _env("AZURE_OPENAI_BUYERS_SYSTEM_MESSAGE"),
    "Offtopic": _env("AZURE_OPENAI_OFFTOPIC_MESSAGE"),
    "CityState": _env("AZURE_OPENAI_CITY_STATE_PROMPT"),
}


def _latest_user_prompt(req: ToolRequest) -> str:
    if req.prompt and req.prompt.strip():
        return req.prompt.strip()

    for message in reversed(req.messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


_LEAD_TYPE_LIST = ", ".join([
    "fsbo", "pre-foreclosure", "fixer-upper", "as-is", "tired-landlords",
    "subject-to", "land", "agent-owned", "reo", "high-equity",
])

_LOCATION_EXTRACT_SYSTEM = (
    "You extract real estate lead search parameters from a user prompt.\n"
    "The prompt may be in English OR Spanish — handle both.\n"
    "Return ONLY a JSON object (no markdown, no explanation) with these fields:\n"
    "  city: string (city or county name, title case) or null\n"
    "  state: string (2-letter abbreviation, uppercase) or null\n"
    f"  lead_type: one of [{_LEAD_TYPE_LIST}] — pick the closest match\n"
    "Spanish → lead_type mappings: "
    "propietarios cansados / dueños cansados / arrendadores cansados = tired-landlords; "
    "propietarios ausentes = tired-landlords; "
    "vendedores motivados / vendedores en apuros = fixer-upper; "
    "pre-ejecución / ejecución hipotecaria / embargo = pre-foreclosure; "
    "banco dueño / propiedad del banco / REO = reo; "
    "en venta por dueño / por el dueño = fsbo; "
    "propiedades vacantes = fixer-upper; "
    "alta equidad / libre de hipoteca = high-equity.\n"
    "Examples:\n"
    '  "tired landlords in Fort Worth TX" → {"city":"Fort Worth","state":"TX","lead_type":"tired-landlords"}\n'
    '  "fsbo in Austin, Texas" → {"city":"Austin","state":"TX","lead_type":"fsbo"}\n'
    '  "bank owned homes Dallas TX" → {"city":"Dallas","state":"TX","lead_type":"reo"}\n'
    '  "agent listed properties San Antonio" → {"city":"San Antonio","state":"TX","lead_type":"agent-owned"}\n'
    '  "pre-foreclosures Harris County TX" → {"city":"Harris County","state":"TX","lead_type":"pre-foreclosure"}\n'
    '  "propietarios cansados en Dallas, TX" → {"city":"Dallas","state":"TX","lead_type":"tired-landlords"}\n'
    '  "dame una lista de propietarios cansados en Houston TX" → {"city":"Houston","state":"TX","lead_type":"tired-landlords"}\n'
    '  "ejecuciones hipotecarias en Miami FL" → {"city":"Miami","state":"FL","lead_type":"pre-foreclosure"}\n'
    '  "compradores en efectivo en Atlanta GA" → {"city":"Atlanta","state":"GA","lead_type":"fixer-upper"}\n'
)


def _get_aoai_client():
    """Return a cached AsyncAzureOpenAI client, or None if not configured."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or (
        f"https://{os.getenv('AZURE_OPENAI_RESOURCE', '')}.openai.azure.com/"
        if os.getenv("AZURE_OPENAI_RESOURCE") else ""
    )
    key = os.getenv("AZURE_OPENAI_KEY", "")
    if not endpoint or not key:
        return None
    try:
        from openai import AsyncAzureOpenAI
        return AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
    except Exception:
        return None


async def _ai_extract_lead_params(prompt: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Use Azure OpenAI mini model to extract city, state, and lead_type from a prompt.
    Falls back to regex extraction if the model call fails.
    Returns (city, state, lead_type).
    """
    client = _get_aoai_client()
    model = os.getenv("AZURE_OPENAI_CLASSIFICATION_MODEL", os.getenv("AZURE_OPENAI_MODEL", "gpt-5.2-chat"))
    if client:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _LOCATION_EXTRACT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=80,
                temperature=0,
            )
            raw = (response.choices[0].message.content or "").strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            parsed = json.loads(raw)
            city = parsed.get("city") or None
            state = (parsed.get("state") or "").upper() or None
            lead_type = parsed.get("lead_type") or "fixer-upper"
            if lead_type not in _ZILLOW_URL_TEMPLATES:
                lead_type = "fixer-upper"
            logger.info("[leads] AI extracted: city=%r state=%r lead_type=%r", city, state, lead_type)
            return city, state, lead_type
        except Exception:
            logger.exception("[leads] AI extraction failed; falling back to regex")

    # Regex fallback
    city, state = _extract_city_state(prompt)
    lead_type = _infer_lead_type_from_prompt(prompt)
    return city, state, lead_type


async def _ai_extract_city_state(prompt: str) -> tuple[Optional[str], Optional[str]]:
    """
    Use Azure OpenAI mini model to extract city and state for buyers queries.
    Falls back to regex if the model call fails.
    """
    city, state, _ = await _ai_extract_lead_params(prompt)
    return city, state


def _extract_city_state(text: str) -> tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None

    # Preposition-anchored extraction: English "in" OR Spanish "en"
    # NOTE: The character class [A-Za-z .'-] does NOT match digits or slashes.
    # This means "en efectivo para una casa 3/2 en Houston, TX" cannot lazily match
    # from the first "en" all the way through "3/2" to "Houston" — the regex stalls
    # at the digit boundary and retries from the second "en", correctly extracting Houston.
    match = re.search(
        r"\b(?:in|en)\s+([A-Za-z][A-Za-z .'-]{1,60}?),\s*([A-Za-z]{2})\b",
        text, re.IGNORECASE,
    )
    if match:
        city_candidate = match.group(1).strip()
        # Strip leading Spanish/English prepositions that may have been captured
        # e.g., "en Houston" → first word "en" is a preposition → return "Houston"
        _PREPOSITIONS = {"en", "in", "de", "del", "para", "a", "al", "la", "el",
                         "los", "las", "por", "con", "sobre"}
        parts = city_candidate.split()
        while parts and parts[0].lower() in _PREPOSITIONS:
            parts = parts[1:]
        if parts:
            return " ".join(parts), _normalize_state(match.group(2))

    # "in/en {city}, {full state name}"
    match = re.search(
        r"\b(?:in|en)\s+([A-Za-z][A-Za-z .'-]{1,60}?),\s*"
        r"(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming)\b",
        text, re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(), _normalize_state(match.group(2))

    # "for/near/around/para {city}, {state}"
    match = re.search(
        r"\b(?:for|near|around|para)\s+([A-Za-z][A-Za-z .'-]{1,60}?),\s*([A-Za-z]{2})\b",
        text, re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(), _normalize_state(match.group(2))

    # Short location: 1-4 words before ", XX" (case-insensitive)
    match = re.search(
        r"\b([A-Za-z][A-Za-z .'-]{1,40}?)\s*,\s*([A-Za-z]{2})\b",
        text.strip(), re.IGNORECASE,
    )
    if match:
        # Reject if the captured "city" looks like a full sentence (has common verbs/articles)
        city_candidate = match.group(1).strip()
        noise_words = {
            "can", "get", "find", "show", "list", "give", "what", "the", "a", "me", "i",
            # Spanish prepositions/articles that shouldn't start a city name
            "en", "para", "de", "del", "una", "un", "los", "las", "el", "la",
            "con", "por", "sobre", "desde", "hacia", "busca", "dame", "encuentra",
        }
        first_word = city_candidate.split()[0].lower()
        if first_word not in noise_words:
            return city_candidate, _normalize_state(match.group(2))
        # Try stripping the leading noise/preposition word (e.g., "en Houston" → "Houston")
        stripped = " ".join(city_candidate.split()[1:]).strip()
        if stripped and stripped[0].isalpha():
            stripped_first = stripped.split()[0].lower()
            if stripped_first not in noise_words:
                return stripped, _normalize_state(match.group(2))

    # Preposition-anchored no-comma: "in {city} {state}" or "in {city} {full state}"
    match = re.search(
        r"\bin\s+([A-Za-z][A-Za-z .'-]{1,40}?)\s+([A-Za-z]{2})\b",
        text, re.IGNORECASE,
    )
    if match:
        city_candidate = match.group(1).strip()
        state_candidate = _normalize_state(match.group(2))
        # Only accept if state_candidate is a valid US state abbreviation
        _VALID_STATES = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
            "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
            "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
            "VA","WA","WV","WI","WY","DC",
        }
        if state_candidate in _VALID_STATES:
            return city_candidate, state_candidate

    # No-comma fallback: "{location} {2-letter state}" e.g. "hidalgo county tx"
    # Limit city to 1-3 words max to avoid capturing lead-type phrases
    match = re.search(
        r"\b([A-Za-z][A-Za-z .'-]{1,30}?)\s+([A-Z]{2})\b",
        text, re.IGNORECASE,
    )
    if match:
        city_candidate = match.group(1).strip()
        state_candidate = _normalize_state(match.group(2))
        noise_words = {
            "can", "get", "find", "show", "list", "give", "what", "the", "a", "me", "i",
            "in", "for", "near", "around",
            "en", "para", "de", "del", "una", "un", "los", "las", "el", "la",
            "busca", "dame", "encuentra",
        }
        first_word = city_candidate.split()[0].lower()
        _VALID_STATES = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
            "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
            "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
            "VA","WA","WV","WI","WY","DC",
        }
        if first_word not in noise_words and state_candidate in _VALID_STATES:
            return city_candidate, state_candidate

    return None, None


def _extract_address_candidates(text: str) -> list[str]:
    if not text:
        return []

    pattern = re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Drive|Dr|Lane|Ln|Way|Ct|Court)\b",
        re.IGNORECASE,
    )

    seen: set[str] = set()
    results: list[str] = []
    for match in pattern.findall(text):
        normalized = " ".join(match.split()).strip()
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)

    return results[:5]


def _extract_full_address(text: str) -> Optional[str]:
    if not text:
        return None

    match = ADDRESS_REGEX.search(text)
    if match:
        return " ".join(match.group("addr").split()).strip()

    candidates = _extract_address_candidates(text)
    if candidates:
        return candidates[0]

    return None


def _parse_positive_int(value: Any, default: int, min_value: int = 1, max_value: int = 100) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


def _classify_prompt(prompt: str) -> dict[str, Any]:
    text = prompt.lower()
    scores: dict[str, int] = {}

    for route, keywords in ROUTE_KEYWORDS.items():
        score = 0
        for token in keywords:
            if token in text:
                score += 1
        scores[route] = score

    if max(scores.values(), default=0) == 0:
        route = "Education"
    else:
        route = max(scores, key=scores.get)

    if any(token in text for token in {"weather", "sports score", "joke", "recipe"}):
        route = "Offtopic"

    return {
        "route": route,
        "scores": scores,
        "explanation": "Keyword-based classifier; API model may combine multiple tool outputs.",
        "route_system_prompt_available": bool(ROUTE_PROMPTS.get(route)),
        "classification_prompt": ROUTE_PROMPTS.get("Classification", ""),
    }


def _build_system_prompt(key: str) -> str:
    """Prepend DOMAIN_RESTRICTION to any route system prompt from env."""
    base = ROUTE_PROMPTS.get(key, "")
    if base:
        return f"{DOMAIN_RESTRICTION}\n\n{base}"
    return DOMAIN_RESTRICTION


def _education_payload(prompt: str) -> dict[str, Any]:
    retrieval_query = build_retrieval_query(prompt)
    tokens = [t for t in retrieval_query.split() if len(t) > 3][:8]
    return {
        "route": "Education",
        "retrieval_query": retrieval_query,
        "subtopics": tokens,
        "route_system_prompt": _build_system_prompt("Education"),
        "context_hint": (
            "User asked for educational context. Explain concepts, assumptions, and "
            "tradeoffs in plain language before tactical recommendations."
        ),
    }


def _comps_payload(prompt: str) -> dict[str, Any]:
    addresses = _extract_address_candidates(prompt)
    return {
        "route": "Comps",
        "retrieval_query": build_retrieval_query(prompt),
        "address_candidates": addresses,
        "route_system_prompt": ROUTE_PROMPTS.get("Comps", ""),
        "comp_link_prompt": ROUTE_PROMPTS.get("CompsLink", ""),
        "context_hint": (
            "Run comparable analysis: verify subject property, select recent and nearby "
            "comps, normalize condition/features, and present valuation range."
        ),
        "workflow": [
            "Validate subject address",
            "Find recent nearby comps",
            "Adjust for beds/baths/sqft/condition",
            "Provide value range with confidence notes",
        ],
    }


_ZILLOW_URL_TEMPLATES: dict[str, str] = {
    "fsbo": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"fsbo":{"value":true},"fsba":{"value":false},'
        '"price":{"min":null},"mp":{"min":null},"tow":{"value":false},"con":{"value":false},'
        '"apa":{"value":false},"apco":{"value":false},"sort":{"value":"globalrelevanceex"},'
        '"mf":{"value":false},"land":{"value":false},"manu":{"value":false},"auc":{"value":false},'
        '"fore":{"value":false},"nc":{"value":false},"cmsn":{"value":false},'
        '"doz":{"value":"36m"}},"isListVisible":true,"category":"cat2"}'
    ),
    "pre-foreclosure": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"price":{"min":null},"mp":{"min":null},'
        '"tow":{"value":false},"con":{"value":false},"apa":{"value":false},'
        '"apco":{"value":false},"sort":{"value":"globalrelevanceex"},"nc":{"value":false},'
        '"cmsn":{"value":false},"mf":{"value":false},"land":{"value":false},'
        '"manu":{"value":false},"doz":{"value":"30"},"fsba":{"value":false},'
        '"fsbo":{"value":false},"fore":{"value":false},'
        '"pf":{"value":true}},"isListVisible":true,"category":"cat2"}'
    ),
    "fixer-upper": (
        "https://www.zillow.com/%%SLUG%%/fixer-upper_att/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"price":{"min":null,"max":650000},"doz":{"value":"90"},'
        '"att":{"value":"fixer upper"}},"isListVisible":true,"category":"cat1"}'
    ),
    "as-is": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"price":{"min":null,"max":null},"doz":{"value":"36m"},'
        '"att":{"value":"as is"}},"isListVisible":true,"category":"cat1"}'
    ),
    "tired-landlords": (
        "https://www.zillow.com/%%SLUG%%/rentals/?searchQueryState="
        '{"pagination":{},"filterState":{"fr":{"value":true},"fsba":{"value":false},'
        '"fsbo":{"value":false},"nc":{"value":false},"cmsn":{"value":false},'
        '"auc":{"value":false},"fore":{"value":false},"price":{"max":626745},'
        '"mp":{"max":3000},"ah":{"value":true},"doz":{"value":"36m"},'
        '"att":{"value":""},"apco":{"value":false},"tow":{"value":false},'
        '"apa":{"value":false},"con":{"value":false}},"isListVisible":true}'
    ),
    "subject-to": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"price":{"min":50000,"max":650000},'
        '"mp":{"min":258,"max":3359},"tow":{"value":false},"con":{"value":false},'
        '"apa":{"value":false},"apco":{"value":false},"sort":{"value":"globalrelevanceex"},'
        '"nc":{"value":false},"fore":{"value":false},"auc":{"value":false},'
        '"cmsn":{"value":false},"mf":{"value":false},"land":{"value":false},'
        '"manu":{"value":false},"doz":{"value":"6m"},"built":{"min":2015},'
        '"ac":{"value":true}},"category":"cat1","isListVisible":true}'
    ),
    "land": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"doz":{"value":"90"},"nc":{"value":false},"fore":{"value":false},'
        '"auc":{"value":false},"cmsn":{"value":false},"sf":{"value":false},'
        '"tow":{"value":false},"mf":{"value":false},"con":{"value":false},'
        '"apa":{"value":false},"manu":{"value":false},"apco":{"value":false},'
        '"lot":{"min":21780,"max":4356000}},"isListVisible":true,"category":"cat1"}'
    ),
    "agent-owned": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"fsba":{"value":true},"fsbo":{"value":false},"nc":{"value":false},'
        '"cmsn":{"value":false},"auc":{"value":false},"fore":{"value":false},'
        '"doz":{"value":"90"}},"isListVisible":true,"category":"cat1"}'
    ),
    "reo": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"fore":{"value":true},"fsba":{"value":false},"fsbo":{"value":false},'
        '"nc":{"value":false},"cmsn":{"value":false},"auc":{"value":false},'
        '"doz":{"value":"36m"}},"isListVisible":true,"category":"cat1"}'
    ),
    "high-equity": (
        "https://www.zillow.com/%%SLUG%%/?searchQueryState="
        '{"pagination":{},"filterState":{"sort":{"value":"globalrelevanceex"},'
        '"fsba":{"value":true},"fsbo":{"value":true},"nc":{"value":false},'
        '"cmsn":{"value":false},"auc":{"value":false},"fore":{"value":false},'
        '"price":{"min":50000,"max":400000},"mp":{"min":0,"max":2000},'
        '"doz":{"value":"36m"}},"isListVisible":true,"category":"cat1"}'
    ),
}

# Keywords that map to a template
_LEAD_TYPE_KEYWORDS: dict[str, list[str]] = {
    "fsbo": [
        "fsbo", "for sale by owner", "by owner", "owner listed",
        # Spanish
        "en venta por el dueño", "en venta por dueño", "por el propietario",
        "venta directa por propietario", "sin agente",
    ],
    "pre-foreclosure": [
        "pre-foreclosure", "preforeclosure", "pre foreclosure", "auction", "lis pendens",
        # Spanish
        "pre-ejecución", "pre ejecución", "ejecución hipotecaria", "embargo hipotecario",
        "pendiente de ejecución", "remate hipotecario", "subasta hipotecaria",
    ],
    "fixer-upper": [
        "fixer", "fixer-upper", "fixer upper", "rehab", "wholesale", "distressed",
        # Spanish
        "para remodelar", "necesita reparaciones", "en mal estado", "propiedad distressed",
        "venta al mayoreo", "wholesale", "vendedores motivados", "vendedor motivado",
    ],
    "as-is": ["as-is", "as is", "tal cual", "tal como está"],
    "tired-landlords": [
        "tired landlord", "landlord", "rental", "absentee owner", "absentee",
        # Spanish
        "propietarios cansados", "propietario cansado", "dueños cansados", "dueño cansado",
        "propietarios ausentes", "propietario ausente", "arrendadores cansados",
        "arrendador cansado", "casero cansado", "caseros cansados",
    ],
    "subject-to": [
        "subject to", "subject-to", "subto", "sub to", "sub2",
        # Spanish
        "sujeto a hipoteca", "sujeto a deuda", "sujeto a", "tomar la hipoteca",
    ],
    "land": [
        "land", "lot", "vacant land", "acreage",
        # Spanish
        "terreno", "terrenos", "lote", "lotes", "tierra", "tierras",
        "predio", "predios", "parcela", "parcelas", "suelo vacante",
    ],
    "agent-owned": [
        "agent owned", "agent listed", "agent-owned", "realtor listed",
        "mls listed", "listed by agent", "broker listed",
        # Spanish
        "listado por agente", "propiedad de agente", "agente dueño",
        "listado en mls", "corredor listado",
    ],
    "reo": [
        "reo", "bank owned", "bank-owned", "foreclosure", "foreclosed",
        "hud home", "hud homes",
        # Spanish
        "banco dueño", "propiedad del banco", "propiedad bancaria", "banco propietario",
        "ejecución", "ejecutada", "rematada", "en remate", "hud casa",
    ],
    "high-equity": [
        "high equity", "free and clear", "no mortgage", "paid off", "equity rich",
    ],
}


def _infer_lead_type_from_prompt(prompt: str) -> str:
    """Infer lead type from user prompt text."""
    lower = prompt.lower()
    for lead_type, keywords in _LEAD_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return lead_type
    # Default to fixer-upper / wholesale — most common investor search
    return "fixer-upper"


def _build_zillow_url(city: Optional[str], state: Optional[str], lead_type: str) -> Optional[str]:
    """Build a Zillow search URL from city/state and lead type."""
    if not city:
        return None
    template = _ZILLOW_URL_TEMPLATES.get(lead_type)
    if not template:
        return None
    # Build slug: "san antonio-tx" format
    slug = city.lower().replace(" ", "-")
    if state:
        slug = f"{slug}-{state.lower()}"
    url = template.replace("%%SLUG%%", slug)

    # Inject usersSearchTerm into searchQueryState so Zillow resolves the
    # correct location instead of falling back to the proxy IP's geolocation.
    search_term = f"{city}, {state.upper()}" if state else city
    url = url.replace(
        '"isListVisible":true',
        f'"usersSearchTerm":"{search_term}","isListVisible":true',
    )
    return url


def _leads_payload(prompt: str) -> dict[str, Any]:
    detected_url = extract_first_url(prompt)
    lead_type = infer_lead_type_from_url(detected_url) if detected_url else "Unknown"
    return {
        "route": "Leads",
        "retrieval_query": build_retrieval_query(prompt),
        "detected_url": detected_url,
        "lead_type": lead_type,
        "route_system_prompt": ROUTE_PROMPTS.get("Leads", ""),
        "lead_link_prompt": ROUTE_PROMPTS.get("LeadsLink", ""),
        "context_hint": (
            "Lead generation route. Prioritize seller motivation signals, list hygiene, "
            "and next best outreach actions."
        ),
    }


def _attorneys_payload(prompt: str) -> dict[str, Any]:
    city, state = _extract_city_state(prompt)
    return {
        "route": "Attorneys",
        "city": city,
        "state": state,
        "retrieval_query": build_retrieval_query(prompt),
        "route_system_prompt": ROUTE_PROMPTS.get("Attorneys", ""),
        "attorney_link_prompt": ROUTE_PROMPTS.get("AttorneyLink", ""),
        "city_state_prompt": ROUTE_PROMPTS.get("CityState", ""),
        "context_hint": (
            "Attorney route. Focus on relevance to real-estate investing workflows "
            "(probate, foreclosure, eviction, title)."
        ),
    }


def _buyers_payload(prompt: str) -> dict[str, Any]:
    city, state = _extract_city_state(prompt)
    return {
        "route": "Buyers",
        "city": city,
        "state": state,
        "retrieval_query": build_retrieval_query(prompt),
        "route_system_prompt": ROUTE_PROMPTS.get("Buyers", ""),
        "context_hint": (
            "Buyer route. Prioritize active cash buyers, match buy box criteria, and "
            "suggest disposition sequencing."
        ),
    }


def _contracts_payload(prompt: str) -> dict[str, Any]:
    expanded_prompt = (
        "Review this real-estate contract request and provide: "
        "1) key clauses to include, 2) risk flags, 3) negotiation levers, "
        "4) state-specific caveats to verify with counsel.\n\n"
        f"User request: {prompt}"
    )
    return {
        "route": "Contracts",
        "retrieval_query": build_retrieval_query(prompt),
        "route_system_prompt": _build_system_prompt("Contracts"),
        "contracts_expansion_prompt": ROUTE_PROMPTS.get("ContractsExpansion", ""),
        "expanded_prompt": expanded_prompt,
        "context_hint": "Contracts route. Be explicit about legal uncertainty and attorney review boundaries.",
    }


def _strategy_payload(prompt: str) -> dict[str, Any]:
    return {
        "route": "Strategy",
        "retrieval_query": build_retrieval_query(prompt),
        "route_system_prompt": _build_system_prompt("Strategy"),
        "context_hint": (
            "Strategy route. Return phased plan (0-30, 31-90, 90+) with KPI checkpoints, "
            "constraints, and execution risks."
        ),
    }


def _offtopic_payload(prompt: str) -> dict[str, Any]:
    return {
        "route": "Offtopic",
        "route_system_prompt": ROUTE_PROMPTS.get("Offtopic", ""),
        "context_hint": (
            "User request appears off-domain. Answer helpfully, then steer back to ARI "
            "core areas (leads, comps, valuation, contracts, buyers)."
        ),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prompt": prompt,
    }


def _pick_details(details: dict[str, Any]) -> dict[str, Any]:
    data = details or {}
    return {
        "bedrooms": data.get("bedrooms"),
        "bathrooms": data.get("bathrooms"),
        "squareFeet": data.get("squareFeet"),
        "yearBuilt": data.get("yearBuilt"),
        "lotSquareFeet": data.get("lotSquareFeet"),
        "stories": data.get("stories"),
        "lastSaleDate": data.get("lastSaleDate"),
        "lastSaleAmount": data.get("lastSaleAmount"),
        "daysOnMarket": data.get("daysOnMarket"),
        "marketStatus": data.get("marketStatus"),
    }


def _trim_bricked_payload(payload: dict[str, Any], full_address: str, max_comps: int) -> dict[str, Any]:
    prop = payload.get("property") or {}
    prop_addr = (prop.get("address") or {}).get("fullAddress") or full_address

    comps_out: list[dict[str, Any]] = []
    for comp in (payload.get("comps") or [])[:max_comps]:
        comp_addr = (comp.get("address") or {}).get("fullAddress")
        comps_out.append(
            {
                "address": comp_addr,
                "details": _pick_details(comp.get("details") or {}),
                "adjusted_value": comp.get("adjusted_value"),
                "selected": comp.get("selected"),
                "compType": comp.get("compType"),
                "listingType": comp.get("listingType"),
            }
        )

    return {
        "subject": {
            "address": prop_addr,
            "details": _pick_details(prop.get("details") or {}),
            "latitude": prop.get("latitude"),
            "longitude": prop.get("longitude"),
        },
        "arv": payload.get("arv"),
        "cmv": payload.get("cmv"),
        "shareLink": payload.get("shareLink"),
        "dashboardLink": payload.get("dashboardLink"),
        "comps": comps_out,
    }


def _normalize_city_state(
    prompt: str, arguments: dict[str, Any]
) -> tuple[Optional[str], Optional[str], str]:
    from_prompt_city, from_prompt_state = _extract_city_state(prompt)
    city = str(arguments.get("city") or from_prompt_city or "").strip()
    raw_state = str(arguments.get("state") or from_prompt_state or "").strip()
    state = _normalize_state(raw_state) if raw_state else None

    source = "arguments" if arguments.get("city") or arguments.get("state") else "prompt"
    if not city or not state:
        source = "not_found"

    return (city or None, state, source)


def _format_phone(raw_phone: Any) -> str:
    if isinstance(raw_phone, list):
        return ", ".join(str(v).strip() for v in raw_phone if str(v).strip())
    if raw_phone is None:
        return ""
    return str(raw_phone).strip()


def _build_buyer_preview_rows(items: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for buyer in items[:limit]:
        full_name = (
            buyer.get("fullName")
            or buyer.get("Full Name")
            or (
                f"{(buyer.get('firstName') or buyer.get('First Name') or '').strip()} "
                f"{(buyer.get('lastName') or buyer.get('Last Name') or '').strip()}"
            ).strip()
        )

        phone = _format_phone(
            buyer.get("Phones_Formatted")
            or buyer.get("Phones")
            or buyer.get("phone")
        )
        email = str(buyer.get("Email") or buyer.get("email") or "").strip()

        rows.append({"Name": full_name, "Phone": phone, "Email": email})
    return rows


async def _query_buyers(
    container_client: Any,
    city: str,
    state: str,
    sample_size: int,
    use_partition_key: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    city_value = city.lower().strip()
    city_title = city.strip().title()
    state_value = state.upper().strip()

    # Handle both string c.cities ("Houston, Dallas") and array c.cities (["Houston"]).
    # UPPER(c.state) makes the state comparison case-insensitive regardless of how the
    # data was imported ("TX" vs "tx").
    count_query = """
        SELECT VALUE COUNT(1) FROM c
        WHERE (
            CONTAINS(LOWER(c.cities), @city) OR
            ARRAY_CONTAINS(c.cities, @city) OR
            ARRAY_CONTAINS(c.cities, @city_title)
        )
        AND UPPER(c.state) = @state
    """
    count_params = [
        {"name": "@city", "value": city_value},
        {"name": "@city_title", "value": city_title},
        {"name": "@state", "value": state_value},
    ]

    query_kwargs: dict[str, Any] = {"max_item_count": 1, "continuation_token_limit": 8}
    if use_partition_key:
        query_kwargs["partition_key"] = state_value

    logger.info(
        "[buyers] query city=%r city_title=%r state=%r partition_key=%s",
        city_value, city_title, state_value, use_partition_key,
    )

    total_count = 0
    count_iter = container_client.query_items(
        query=count_query,
        parameters=count_params,
        **query_kwargs,
    )
    async for item in count_iter:
        try:
            total_count = int(item)
        except Exception:
            total_count = 0
        break

    logger.info("[buyers] count query returned total_count=%d", total_count)

    max_offset = min(500, max(0, total_count - sample_size))
    offset = 0 if total_count <= sample_size else random.randint(0, max_offset)

    data_query = """
        SELECT
            c["First Name"] AS "First Name",
            c["Last Name"] AS "Last Name",
            c["Full Name"] AS "Full Name",
            c.Phones_Formatted AS Phones,
            c.Email
        FROM c
        WHERE (
            CONTAINS(LOWER(c.cities), @city) OR
            ARRAY_CONTAINS(c.cities, @city) OR
            ARRAY_CONTAINS(c.cities, @city_title)
        )
        AND UPPER(c.state) = @state
        ORDER BY c.id
        OFFSET @offset LIMIT @sample_size
    """
    data_params = [
        {"name": "@city", "value": city_value},
        {"name": "@city_title", "value": city_title},
        {"name": "@state", "value": state_value},
        {"name": "@offset", "value": offset},
        {"name": "@sample_size", "value": sample_size},
    ]

    data_kwargs: dict[str, Any] = {
        "max_item_count": sample_size,
        "continuation_token_limit": 8,
    }
    if use_partition_key:
        data_kwargs["partition_key"] = state_value

    items: list[dict[str, Any]] = []
    results_iter = container_client.query_items(
        query=data_query,
        parameters=data_params,
        **data_kwargs,
    )
    async for item in results_iter:
        items.append(item)

    return items, total_count, offset


async def _fetch_buyers_from_cosmos(city: str, state: str, sample_size: int = 50) -> dict[str, Any]:
    if CosmosClient is None:
        return {"ok": False, "error": "azure-cosmos package is not installed in apps/mcp."}
    if certifi is None:
        return {"ok": False, "error": "certifi package is not installed in apps/mcp."}

    required_keys = [
        "AZURE_COSMOSDB_ACCOUNT",
        "AZURE_COSMOSDB_ACCOUNT_KEY",
        "AZURE_COSMOSDB_BUYERS_DATABASE",
        "AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER",
    ]
    missing = [key for key in required_keys if not _env(key).strip()]
    if missing:
        return {"ok": False, "error": f"Missing Cosmos config: {', '.join(missing)}"}

    account = _env("AZURE_COSMOSDB_ACCOUNT").strip()
    key = _env("AZURE_COSMOSDB_ACCOUNT_KEY").strip()
    database_name = _env("AZURE_COSMOSDB_BUYERS_DATABASE").strip()
    container_name = _env("AZURE_COSMOSDB_NATIONWIDE_BUYERS_CONTAINER").strip()
    endpoint = f"https://{account}.documents.azure.com:443/"

    os.environ["SSL_CERT_FILE"] = certifi.where()

    clamped_size = _parse_positive_int(sample_size, default=50, min_value=1, max_value=100)
    state_value = _normalize_state(state)

    try:
        async with CosmosClient(endpoint, credential=key) as cosmos_client:
            database = cosmos_client.get_database_client(database_name)
            container = database.get_container_client(container_name)

            # Diagnostic: fetch one record to understand actual schema
            try:
                diag_iter = container.query_items(
                    query="SELECT TOP 1 * FROM c",
                    max_item_count=1,
                )
                async for diag_item in diag_iter:
                    schema_keys = [k for k in diag_item.keys() if not k.startswith("_")]
                    logger.info(
                        "[buyers] schema sample — keys=%s cities=%r state=%r",
                        schema_keys,
                        diag_item.get("cities") or diag_item.get("city") or diag_item.get("Cities") or diag_item.get("City"),
                        diag_item.get("state") or diag_item.get("State") or diag_item.get("stateCode"),
                    )
                    break
            except Exception as diag_exc:
                logger.warning("[buyers] diagnostic query failed: %s", diag_exc)

            try:
                buyers, total_count, offset = await _query_buyers(
                    container_client=container,
                    city=city,
                    state=state_value,
                    sample_size=clamped_size,
                    use_partition_key=True,
                )
                query_mode = "partition_key"
            except Exception as qe:
                logger.warning("[buyers] partition_key query failed (%s), trying cross-partition", qe)
                buyers, total_count, offset = await _query_buyers(
                    container_client=container,
                    city=city,
                    state=state_value,
                    sample_size=clamped_size,
                    use_partition_key=False,
                )
                query_mode = "cross_partition"
    except Exception as exc:
        return {"ok": False, "error": f"Cosmos buyers query failed: {str(exc)}"}

    return {
        "ok": True,
        "buyers": buyers,
        "city": city,
        "state": state_value,
        "sample_size": clamped_size,
        "total_count": total_count,
        "offset": offset,
        "query_mode": query_mode,
    }


async def _fetch_bricked_comps(address: str, max_comps: int = 12) -> dict[str, Any]:
    if httpx is None:
        return {"ok": False, "error": "httpx package is not installed in apps/mcp."}

    api_key = _env("BRICKED_API_KEY").strip()
    if not api_key:
        return {"ok": False, "error": "BRICKED_API_KEY is not configured."}

    max_items = _parse_positive_int(max_comps, default=12, min_value=1, max_value=50)
    url = "https://api.bricked.ai/v1/property/create"
    headers = {"x-api-key": api_key}
    attempts: list[tuple[str, dict[str, Any]]] = [
        ("GET", {"params": {"address": address}}),
        ("GET", {"params": {"property_address": address}}),
        ("POST", {"json": {"address": address}}),
        ("POST", {"json": {"fullAddress": address}}),
        ("POST", {"json": {"property_address": address}}),
    ]

    last_error = ""
    last_status: Optional[int] = None
    last_body = ""

    async with httpx.AsyncClient(timeout=45.0) as client:
        for method, kwargs in attempts:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
            except Exception as exc:
                last_error = str(exc)
                continue

            if 200 <= response.status_code < 300:
                try:
                    payload = response.json()
                except Exception as exc:
                    return {"ok": False, "error": f"Bricked returned invalid JSON: {str(exc)}"}

                return {
                    "ok": True,
                    "address": address,
                    "request_method": method,
                    "trimmed": _trim_bricked_payload(payload, address, max_items),
                }

            last_status = response.status_code
            last_body = response.text[:700]

    error_details = f"Bricked request failed. status={last_status} body={last_body}".strip()
    if last_error:
        error_details = f"{error_details} last_error={last_error}".strip()
    return {"ok": False, "error": error_details}


def _generate_buyers_excel(
    buyers: list[dict[str, Any]], city: str, state: str,
) -> str | None:
    """Build an Excel file from buyer rows and upload to Azure Blob.

    Returns the download URL, or *None* if upload is unavailable.
    """
    try:
        import pandas as pd
        from services.azure_blob import AzureBlobService
    except ImportError:
        logger.warning("pandas or azure_blob not available — skipping Excel generation")
        return None

    blob = AzureBlobService.get_instance()
    if not blob:
        return None

    rows = _build_buyer_preview_rows(buyers, limit=len(buyers))
    if not rows:
        return None

    df = pd.DataFrame(rows)

    slug_city = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
    slug_state = state.lower()
    ts = int(datetime.utcnow().timestamp())
    filename = f"{slug_city}-{slug_state}-cash-buyers-list_{ts}.xlsx"

    try:
        url = blob.upload_dataframe(
            container_name="documents",
            file_name=filename,
            df=df,
            sheet_name="Cash Buyers",
        )
        return url
    except Exception:
        logger.exception("Buyers Excel upload failed")
        return None


async def _buyers_payload_with_data(prompt: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _buyers_payload(prompt)

    # Priority 1: explicit city/state arguments passed by the orchestration model
    explicit_city = str(arguments.get("city") or "").strip() or None
    explicit_state = str(arguments.get("state") or "").strip() or None

    if explicit_city and explicit_state:
        # Orchestration model extracted location — use directly
        city, state = explicit_city, explicit_state
        source = "arguments"
    else:
        # Priority 2: mini model extraction from the prompt text
        city, state = await _ai_extract_city_state(prompt)
        if not city:
            city = explicit_city
        if not state:
            state = explicit_state
        source = "ai" if (city or state) else "none"
    payload["city"] = city
    payload["state"] = state
    payload["location_source"] = source

    raw_max = arguments.get("max_results")
    sample_size = _parse_positive_int(raw_max, default=50, min_value=50, max_value=100)
    payload["max_results"] = sample_size

    if not city or not state:
        payload["status"] = "missing_location"
        payload["data_source"] = "cosmos"
        payload["buyers_preview"] = []
        payload["message"] = (
            "No city/state detected. Ask user to provide a location like 'Houston, TX' "
            "or call buyers-search with explicit city/state arguments."
        )
        return payload

    result = await _fetch_buyers_from_cosmos(city=city, state=state, sample_size=sample_size)
    payload["data_source"] = "cosmos"

    if not result.get("ok"):
        payload["status"] = "error"
        payload["buyers_preview"] = []
        payload["message"] = result.get("error", "Cosmos buyers lookup failed.")
        return payload

    buyers = result.get("buyers", [])
    preview = _build_buyer_preview_rows(buyers, limit=10)
    payload["query_meta"] = {
        "city": result.get("city"),
        "state": result.get("state"),
        "total_count": result.get("total_count"),
        "offset": result.get("offset"),
        "query_mode": result.get("query_mode"),
    }
    payload["buyers_preview"] = preview
    payload["buyers_count"] = len(buyers)

    if buyers:
        payload["status"] = "ok"

        # Generate Excel and upload to Azure Blob
        excel_link = _generate_buyers_excel(buyers, city, state)
        payload["excel_link"] = excel_link or ""

        payload["message"] = (
            f"Retrieved {len(buyers)} buyers for {result.get('city')}, {result.get('state')}."
        )

        # Inject download instructions into the system prompt so the model
        # shows the real link prominently and never fabricates a URL.
        if excel_link:
            payload["route_system_prompt"] = (
                payload.get("route_system_prompt", "") +
                f"\n\nIMPORTANT — MANDATORY DOWNLOAD LINK: You MUST include this "
                f"download link in your response. Display it prominently after "
                f"the buyer preview list:\n"
                f"📥 **[Download Full Buyers List ({len(buyers)} buyers)]({excel_link})**\n"
                f"Do NOT omit this link. Do NOT generate any other download URL. "
                f"The user expects to download the Excel file."
            )
        else:
            payload["route_system_prompt"] = (
                payload.get("route_system_prompt", "") +
                "\n\nNOTE: Excel export is unavailable. Present all buyer data "
                "inline. NEVER generate fake download links."
            )
    else:
        payload["status"] = "no_results"
        payload["message"] = (
            f"No buyers found for {result.get('city')}, {result.get('state')}. "
            "Try another nearby city or state."
        )

    return payload


async def _fetch_zillow_comps_fallback(address: str) -> dict[str, Any]:
    """Fallback: scrape nearby Zillow listings as comp candidates when Bricked is unavailable."""
    try:
        from services.lead_gen import fetch_page_content, parse_property_data
    except ImportError:
        return {"ok": False, "error": "lead_gen service unavailable"}

    # Extract city/state from address string (e.g. "123 Main St, Houston, TX 77001")
    city, state = _extract_city_state(address)
    if not city or not state:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 3:
            city = parts[-2].strip()
            state = parts[-1].strip().split()[0]
        elif len(parts) == 2:
            city = parts[0].strip()
            state = parts[1].strip().split()[0]

    city = (city or "").strip()
    state = _normalize_state(state or "")

    if not city or not state:
        return {"ok": False, "error": "Could not extract city/state from address for Zillow fallback"}

    url = _build_zillow_url(city, state, "fixer-upper")
    if not url:
        return {"ok": False, "error": "Could not build Zillow URL for comps fallback"}

    logger.info("[comps fallback] Scraping Zillow for %s, %s: %s", city, state, url[:80])
    content = await fetch_page_content(url)
    if not content:
        return {"ok": False, "error": "ScrapingBee fetch failed for Zillow comps fallback"}

    df = parse_property_data(content)
    if df.empty:
        return {"ok": False, "error": f"No Zillow listings found for {city}, {state}"}

    listings = df.to_dict(orient="records")
    return {"ok": True, "listings": listings, "city": city, "state": state}


async def _comps_payload_with_data(prompt: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _comps_payload(prompt)
    explicit_address = str(arguments.get("address") or "").strip()
    selected_address = explicit_address or _extract_full_address(prompt) or ""
    max_comps = _parse_positive_int(arguments.get("max_comps"), default=12, min_value=1, max_value=50)

    payload["subject_address"] = selected_address
    payload["max_comps"] = max_comps
    payload["data_source"] = "bricked"

    if not selected_address:
        payload["status"] = "missing_address"
        payload["message"] = (
            "No full address detected. Ask user for street, city, state, zip "
            "or call bricked-comps with an explicit address argument."
        )
        payload["bricked"] = None
        return payload

    result = await _fetch_bricked_comps(selected_address, max_comps=max_comps)
    if not result.get("ok"):
        logger.warning("[comps] Bricked failed (%s); trying Zillow fallback", result.get("error"))
        zillow = await _fetch_zillow_comps_fallback(selected_address)
        if zillow.get("ok"):
            listings = zillow.get("listings", [])
            payload["status"] = "ok"
            payload["data_source"] = "zillow_fallback"
            payload["bricked"] = None
            payload["zillow_comps"] = listings[:20]
            payload["comps_count"] = len(listings)
            payload["message"] = (
                f"Retrieved {len(listings)} nearby listings for {zillow['city']}, {zillow['state']} "
                f"as comp candidates (Bricked unavailable)."
            )
        else:
            payload["status"] = "error"
            payload["message"] = result.get("error", "Bricked lookup failed.")
            payload["bricked"] = None
        return payload

    trimmed = result.get("trimmed") or {}
    payload["status"] = "ok"
    payload["message"] = f"Retrieved comps for {selected_address}."
    payload["request_method"] = result.get("request_method")
    payload["bricked"] = trimmed
    payload["arv"] = trimmed.get("arv")
    payload["cmv"] = trimmed.get("cmv")
    payload["comps_count"] = len(trimmed.get("comps") or [])
    return payload


def _ok(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool_name, "ok": True, "result": payload}


async def _read_tool_request() -> ToolRequest:
    data = await request.get_json(silent=True)
    if not isinstance(data, dict):
        return ToolRequest()

    try:
        return ToolRequest(**data)
    except Exception:
        prompt = str(data.get("prompt", "")) if isinstance(data, dict) else ""
        return ToolRequest(prompt=prompt)


@app.get("/")
async def root():
    return {
        "name": "ARI MCP Tool Server",
        "version": "0.2.0",
        "integration_config": INTEGRATION_CONFIG,
        "endpoints": [
            "GET /health",
            "GET /tools",
            "POST /tools/integration-config",
            "POST /tools/classify",
            "POST /tools/classify-intent",
            "POST /tools/education",
            "POST /tools/comps",
            "POST /tools/leads",
            "POST /tools/attorneys",
            "POST /tools/strategy",
            "POST /tools/contracts",
            "POST /tools/buyers",
            "POST /tools/offtopic",
            "POST /tools/build-retrieval-query",
            "POST /tools/infer-lead-type",
            "POST /tools/extract-city-state",
            "POST /tools/extract-address",
            "POST /tools/buyers-search",
            "POST /tools/bricked-comps",
        ],
    }, 200


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mcp",
        "integration_config": INTEGRATION_CONFIG,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }, 200


@app.get("/tools")
async def tools():
    return {
        "tools": [
            "integration-config",
            "classify",
            "education",
            "comps",
            "leads",
            "attorneys",
            "strategy",
            "contracts",
            "buyers",
            "offtopic",
            "build-retrieval-query",
            "infer-lead-type",
            "extract-city-state",
            "extract-address",
            "buyers-search",
            "bricked-comps",
        ]
    }, 200


@app.post("/tools/classify")
async def tool_classify():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    return _ok("classify", _classify_prompt(prompt)), 200


@app.post("/tools/classify-intent")
async def tool_classify_intent():
    """
    Return the domain intent category for a given prompt.

    Response fields:
        intent          — REAL_ESTATE_CORE | REAL_ESTATE_GENERAL | OFF_TOPIC | MALICIOUS
        allowed_tools   — list of tool paths the intent may access
    """
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    intent = classify_intent(prompt)
    from middleware.guardrails import TOOL_ALLOWLIST, _BYPASS_PATHS
    allowed = sorted(
        TOOL_ALLOWLIST.get(intent, set()) | _BYPASS_PATHS
    )
    return _ok("classify-intent", {
        "intent": intent.value,
        "prompt": prompt,
        "allowed_tools": allowed,
    }), 200


@app.post("/tools/integration-config")
async def tool_integration_config():
    return _ok("integration-config", INTEGRATION_CONFIG), 200


@app.post("/tools/education")
async def tool_education():
    req = await _read_tool_request()
    return _ok("education", _education_payload(_latest_user_prompt(req))), 200


@app.post("/tools/comps")
async def tool_comps():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    return _ok("comps", await _comps_payload_with_data(prompt, req.arguments)), 200


@app.post("/tools/leads")
async def tool_leads():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    payload = _leads_payload(prompt)

    scrape_url = req.arguments.get("url") or payload.get("detected_url")
    _debug_city: Optional[str] = None
    _debug_state: Optional[str] = None
    _debug_lead_type: Optional[str] = None

    # If no URL provided, use AI to extract location + lead type and build Zillow URL
    if not scrape_url:
        city, state, lead_type = await _ai_extract_lead_params(prompt)
        if city:
            scrape_url = _build_zillow_url(city, state, lead_type)
            if scrape_url:
                _debug_city = city
                _debug_state = state
                _debug_lead_type = lead_type
                payload["lead_type"] = lead_type.replace("-", " ").title()
                logger.info("AI-generated Zillow URL for %s, %s (%s)", city, state, lead_type)
                logger.info("Scrape URL: %s", scrape_url)

    if scrape_url:
        logger.info("Starting Zillow scrape: %s", scrape_url)
        try:
            from services.lead_gen import get_properties
            filename = req.arguments.get("filename") or f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
            max_pages = _parse_positive_int(req.arguments.get("max_pages"), default=5, min_value=1, max_value=10)
            result = await get_properties(scrape_url, filename, max_pages=max_pages)
            payload["status"] = result.get("status", "error")
            payload["preview"] = result.get("preview")
            payload["excel_link"] = result.get("excel_link")
            payload["properties_count"] = result.get("properties_count", 0)
            payload["data_source"] = result.get("source", "scrape")
            payload["message"] = result.get("message", "")

            # URL suppression is always active — model must never expose source URLs
            url_suppression = (
                "\n\nCRITICAL: NEVER show the Zillow search URL or any internal source URL "
                "used to generate this list. "
                "\n\nURL FORMATTING: NEVER display raw Zillow URLs as plain text. "
                "Always format property links as markdown hyperlinks with friendly text, "
                'e.g. [View Property](https://www.zillow.com/...) or '
                '[Property Details](https://www.zillow.com/...). '
            )

            excel_link = result.get("excel_link", "")
            count = result.get("properties_count", 0)
            if excel_link and count:
                payload["route_system_prompt"] = (
                    payload.get("route_system_prompt", "") +
                    f"\n\nIMPORTANT — MANDATORY DOWNLOAD LINK: You MUST include this "
                    f"download link in your response. Display it prominently after "
                    f"the property list:\n"
                    f"📥 **[Download Full List ({count} properties)]({excel_link})**\n"
                    f"Do NOT omit this link. The user expects to download the Excel file."
                    + url_suppression +
                    f"The download link should also use markdown: "
                    f"[Download Full List ({count} properties)]({excel_link})"
                )
            else:
                payload["route_system_prompt"] = (
                    payload.get("route_system_prompt", "") + url_suppression
                )

            # Strip ALL source/debug fields — model must never see internal URLs
            payload.pop("detected_url", None)
            payload.pop("generated_url", None)
            payload.pop("lead_link_prompt", None)
            # Do NOT include _source_url / _city / _state / _lead_type in response
            logger.info(
                "[leads] scrape done: city=%r state=%r lead_type=%r count=%d",
                _debug_city, _debug_state, _debug_lead_type, count,
            )
        except Exception as exc:
            logger.error("Leads scraping failed: %s", exc)
            payload["status"] = "error"
            payload["message"] = f"Lead scraping failed: {str(exc)}"
    else:
        payload["status"] = "awaiting_url"
        payload["message"] = (
            "No location or Zillow URL detected. Please provide a city/state "
            "or a Zillow search URL to generate leads."
        )

    return _ok("leads", payload), 200


@app.post("/tools/attorneys")
async def tool_attorneys():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    payload = _attorneys_payload(prompt)

    scrape_url = req.arguments.get("url")
    if scrape_url:
        try:
            from services.lead_gen import get_attorneys
            filename = req.arguments.get("filename") or f"attorneys_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
            result = await get_attorneys(scrape_url, filename)
            payload["status"] = result.get("status", "error")
            payload["message"] = result.get("message", "")
            payload["preview"] = result.get("preview")
            payload["excel_link"] = result.get("excel_link")
            payload["attorneys_count"] = result.get("attorneys_count", 0)
            payload["data_source"] = result.get("source", "scrape")
        except Exception as exc:
            logger.error("Attorney scraping failed: %s", exc)
            payload["status"] = "error"
            payload["message"] = f"Attorney scraping failed: {str(exc)}"
    else:
        payload["status"] = "awaiting_url"
        payload["message"] = (
            "No attorney directory URL provided. Supply a URL argument to scrape "
            "attorney listings."
        )

    return _ok("attorneys", payload), 200


@app.post("/tools/strategy")
async def tool_strategy():
    req = await _read_tool_request()
    return _ok("strategy", _strategy_payload(_latest_user_prompt(req))), 200


@app.post("/tools/contracts")
async def tool_contracts():
    req = await _read_tool_request()
    return _ok("contracts", _contracts_payload(_latest_user_prompt(req))), 200


@app.post("/tools/buyers")
async def tool_buyers():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    return _ok("buyers", await _buyers_payload_with_data(prompt, req.arguments)), 200


@app.post("/tools/offtopic")
async def tool_offtopic():
    req = await _read_tool_request()
    return _ok("offtopic", _offtopic_payload(_latest_user_prompt(req))), 200


@app.post("/tools/build-retrieval-query")
async def tool_build_retrieval_query():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    return _ok(
        "build-retrieval-query",
        {"retrieval_query": build_retrieval_query(prompt), "prompt": prompt},
    ), 200


@app.post("/tools/infer-lead-type")
async def tool_infer_lead_type():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    incoming_url = req.arguments.get("url") if isinstance(req.arguments, dict) else None
    url = incoming_url or extract_first_url(prompt)
    return _ok(
        "infer-lead-type",
        {"url": url, "lead_type": infer_lead_type_from_url(url) if url else "Unknown"},
    ), 200


@app.post("/tools/extract-city-state")
async def tool_extract_city_state():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    city, state, source = _normalize_city_state(prompt, req.arguments)
    return _ok(
        "extract-city-state",
        {"city": city, "state": state, "location_source": source, "prompt": prompt},
    ), 200


@app.post("/tools/extract-address")
async def tool_extract_address():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    explicit_address = str(req.arguments.get("address") or "").strip()
    address = explicit_address or _extract_full_address(prompt)
    return _ok(
        "extract-address",
        {
            "address": address,
            "address_source": "arguments" if explicit_address else "prompt",
            "address_candidates": _extract_address_candidates(prompt),
        },
    ), 200


@app.post("/tools/buyers-search")
async def tool_buyers_search():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    payload = await _buyers_payload_with_data(prompt, req.arguments)
    return _ok("buyers-search", payload), 200


@app.post("/tools/bricked-comps")
async def tool_bricked_comps():
    req = await _read_tool_request()
    prompt = _latest_user_prompt(req)
    payload = await _comps_payload_with_data(prompt, req.arguments)
    return _ok("bricked-comps", payload), 200


@app.errorhandler(404)
async def not_found(_):
    return {"error": "Not found"}, 404


@app.errorhandler(500)
async def server_error(error):
    return {"error": "Internal server error", "detail": str(error)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8100, debug=False)
