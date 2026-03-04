"""
ARI Backend API
OpenAI-compatible Chat Completions endpoint with SSE streaming.
Uses Azure OpenAI GPT-5.2 with model-driven MCP tool orchestration.
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, List

import httpx
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from pydantic import BaseModel, Field, ValidationError
from quart import Quart, Response, request

from middleware.auth import auth_middleware, jwt_auth_middleware
from middleware.rate_limit import rate_limit_middleware


# ============================================================================
# Structured JSON Logging
# ============================================================================


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        for key in ("correlation_id", "method", "path", "status", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(_JSONFormatter())
logging.root.handlers = [_handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger("ari.api")


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

# Precedence: process env > apps/api/.env
if LOCAL_ENV_PATH.exists():
    load_dotenv(LOCAL_ENV_PATH, override=False)
_load_env_file(LOCAL_ENV_PATH)

app = Quart(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "dev-secret-change-me")

# Register Phase 2 blueprints
from routes import auth_bp, sessions_bp, lead_runs_bp, documents_bp  # noqa: E402
from routes.frontend_data import frontend_data_bp  # noqa: E402
from routes.magic_link import magic_link_bp  # noqa: E402
from routes.stripe_webhook import stripe_webhook_bp  # noqa: E402
from routes.billing import billing_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(sessions_bp)
app.register_blueprint(lead_runs_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(frontend_data_bp)
app.register_blueprint(magic_link_bp)
app.register_blueprint(stripe_webhook_bp)
app.register_blueprint(billing_bp)

# ============================================================================
# Configuration
# ============================================================================

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# CORS / security
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS: set[str] = (
    {o.strip() for o in _raw_origins.split(",") if o.strip()} if _raw_origins else {FRONTEND_URL}
)

# Request validation limits
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "32000"))
MAX_MESSAGES_COUNT = int(os.getenv("MAX_MESSAGES_COUNT", "100"))

# Azure OpenAI Configuration
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv(
    "AZURE_OPENAI_MODEL", "gpt-5.2-chat"
)
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_TIMEOUT_SECONDS = float(os.getenv("AZURE_OPENAI_TIMEOUT_SECONDS", "120"))

# Security
FORCE_HTTPS = os.getenv("FORCE_HTTPS", "False").lower() == "true"

GLOBAL_SYSTEM_PROMPT = os.getenv("ARI_SYSTEM_PROMPT") or os.getenv(
    "AZURE_OPENAI_SYSTEM_MESSAGE", ""
)

# MCP orchestration configuration
MCP_ENABLED = os.getenv("MCP_ENABLED", "True").lower() == "true"
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8100").rstrip("/")
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "60"))
MCP_TOOL_MAX_ROUNDS = int(os.getenv("MCP_TOOL_MAX_ROUNDS", "4"))
MCP_TOOL_MAX_CALLS_PER_ROUND = int(os.getenv("MCP_TOOL_MAX_CALLS_PER_ROUND", "4"))

# Context window management
# GPT-5.2: 400K input context, 128K max output.
# Budget = 400K - 128K output headroom = 272K usable input.  We use 260K to
# leave an additional buffer for system prompts injected at call time.
_CONTEXT_TOKEN_BUDGET = int(os.getenv("CONTEXT_TOKEN_BUDGET", "260000"))
# Tool results (Zillow previews, buyer lists) are capped in-place before dropping messages.
_MAX_TOOL_RESULT_CHARS = int(os.getenv("MAX_TOOL_RESULT_CHARS", "12000"))  # ≈ 3K tokens

_azure_client: AsyncAzureOpenAI | None = None

# System prompt injected into the planning/orchestration phase so the model
# knows which tools to call for which request types.
_ORCHESTRATION_SYSTEM_PROMPT = (
    "You are ARI, an AI assistant for real estate investors. You have access to live data tools.\n\n"
    "TOOL ROUTING — follow exactly:\n\n"
    "1. User asks for a LIST of properties, leads, sellers, landlords, or contacts in a city/county:\n"
    "   → IMMEDIATELY call mcp_leads_context. NEVER answer from training knowledge.\n"
    "   Triggers: 'tired landlords', 'agent owned', 'agent listed', 'fsbo', 'for sale by owner',\n"
    "   'foreclosures', 'pre-foreclosures', 'reo', 'bank owned', 'motivated sellers',\n"
    "   'absentee owners', 'vacant', 'tax delinquent', 'high equity', 'free and clear',\n"
    "   'probate', 'code violations', 'lis pendens', 'distressed', 'inherited', 'divorce leads',\n"
    "   'hud homes', or ANY phrase like 'get me a list of X in [city]'.\n\n"
    "2. User asks for cash buyers or investor contacts in a city:\n"
    "   → Call mcp_buyers_search.\n\n"
    "3. User asks for comps, ARV, or after-repair value:\n"
    "   → Call mcp_bricked_comps or mcp_comps_context.\n\n"
    "4. User asks about attorneys or title:\n"
    "   → Call mcp_attorneys_context.\n\n"
    "5. Educational question about real estate (no live data needed):\n"
    "   → Call mcp_education_context or mcp_strategy_context or mcp_contracts_context.\n\n"
    "CRITICAL: For rules 1 and 2, you MUST call the live data tool. "
    "Do not answer lead or buyer list requests from training knowledge."
)

MCP_TOOL_ENDPOINTS: dict[str, str] = {
    "mcp_integration_config": "/tools/integration-config",
    "mcp_classify_route": "/tools/classify",
    "mcp_education_context": "/tools/education",
    "mcp_comps_context": "/tools/comps",
    "mcp_bricked_comps": "/tools/bricked-comps",
    "mcp_leads_context": "/tools/leads",
    "mcp_attorneys_context": "/tools/attorneys",
    "mcp_strategy_context": "/tools/strategy",
    "mcp_contracts_context": "/tools/contracts",
    "mcp_buyers_context": "/tools/buyers",
    "mcp_buyers_search": "/tools/buyers-search",
    "mcp_extract_city_state": "/tools/extract-city-state",
    "mcp_extract_address": "/tools/extract-address",
    "mcp_offtopic_context": "/tools/offtopic",
    "mcp_build_retrieval_query": "/tools/build-retrieval-query",
    "mcp_infer_lead_type": "/tools/infer-lead-type",
}

MCP_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "mcp_integration_config",
            "description": "Read availability flags for configured backends (Azure Search, CosmosDB, Stripe, Azure OpenAI).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_classify_route",
            "description": "Classify request into ARI route (Leads, Comps, Education, Strategy, Contracts, Buyers, Attorneys, Offtopic).",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "User prompt to classify."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_education_context",
            "description": "Get educational context and topic hints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "User educational prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_comps_context",
            "description": "Get comps-focused context, address candidates, and workflow hints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Comparable analysis prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_bricked_comps",
            "description": "Run Bricked comps lookup for a subject property address and return ARV/CMV/comps payload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Comparable analysis prompt."},
                    "address": {"type": "string", "description": "Full property address (preferred)."},
                    "max_comps": {"type": "integer", "description": "Maximum comps to return."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_leads_context",
            "description": (
                "REQUIRED for ANY request for a list of properties, leads, sellers, or real estate contacts in a city or county. "
                "This tool retrieves LIVE data from Zillow and returns a downloadable Excel file. "
                "You MUST call this tool — NEVER answer lead requests from training knowledge. "
                "Call this for: 'tired landlords', 'agent owned', 'agent listed', 'fsbo', 'for sale by owner', "
                "'foreclosures', 'pre-foreclosures', 'reo', 'bank owned', 'motivated sellers', 'absentee owners', "
                "'vacant properties', 'tax delinquent', 'high equity', 'free and clear', 'probate', 'code violations', "
                "'lis pendens', 'distressed properties', 'inherited properties', 'divorce leads', 'hud homes', "
                "or ANY phrase like 'get me a list of [property type] in [city]'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Lead generation prompt."},
                    "url": {"type": "string", "description": "Zillow search URL to scrape for leads."},
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_attorneys_context",
            "description": "Get attorneys route context and city/state extraction hints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Attorney lookup prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_strategy_context",
            "description": "Get strategy route context and phased planning hints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Strategy planning prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_contracts_context",
            "description": "Get contract route context and expanded contract-analysis prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Contract-related prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_buyers_context",
            "description": "Get buyer route hints when you need general guidance about the buyers feature. Do NOT use this to retrieve actual buyer data — use mcp_buyers_search instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Buyers prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_buyers_search",
            "description": "Search the database for actual cash buyers by city and state. USE THIS TOOL when the user asks for a list of buyers, cash buyers, or investor buyers in a specific location. Returns real buyer names, phone numbers, and emails from the nationwide buyers database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Buyers prompt (optional if city/state provided)."},
                    "city": {"type": "string", "description": "Target city."},
                    "state": {"type": "string", "description": "Target state abbreviation or full state name."},
                    "max_results": {"type": "integer", "description": "Maximum buyer rows to return. Defaults to 50. Always use 50 unless the user explicitly asks for fewer."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_extract_city_state",
            "description": "Extract and normalize city/state from prompt or explicit arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "User prompt text."},
                    "city": {"type": "string", "description": "Optional explicit city override."},
                    "state": {"type": "string", "description": "Optional explicit state override."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_extract_address",
            "description": "Extract a property address from prompt or explicit argument.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "User prompt text."},
                    "address": {"type": "string", "description": "Optional explicit address override."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_offtopic_context",
            "description": "Get off-topic handling hint and redirect strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Off-topic prompt."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_build_retrieval_query",
            "description": "Build short keyword retrieval query from verbose user text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "User prompt to compress into retrieval query."}
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_infer_lead_type",
            "description": "Infer lead type from a URL or prompt context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Lead-related prompt."},
                    "url": {"type": "string", "description": "URL to infer lead type from."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_document",
            "description": "Convert markdown content to a downloadable Word document (.docx). You MUST call this tool whenever you create a document, contract, agreement, lease, report, or any long-form content. NEVER generate fake download links like 'sandbox:/' or placeholder URLs — ALWAYS use this tool to get a real download URL. Pass ONLY the document body content (the contract/agreement/report text itself) — do NOT include conversational commentary. The tool returns a real Azure download URL that you must include in your response as a markdown link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full markdown content to convert to DOCX."},
                    "title": {"type": "string", "description": "Document title (e.g. 'Lease Agreement', 'Market Report')."},
                },
                "required": ["content", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_stack_lists",
            "description": (
                "Combine multiple uploaded property lists (Excel/CSV files) and return only the "
                "properties that appear on 2 or more lists. Use this when the user has attached "
                "multiple spreadsheets (e.g. lis pendens + code violations + tax delinquent) and "
                "wants to find the overlap — properties with multiple distress signals are the most "
                "motivated sellers. The files must already be attached/uploaded in the current chat "
                "message. Returns a download link for the consolidated Excel workbook."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Brief description of what the user wants (e.g. 'combine lis pendens and code violations lists').",
                    },
                },
                "required": [],
            },
        },
    },
]

# ============================================================================
# CORS & Security Middleware
# ============================================================================


def _get_allowed_origin() -> str | None:
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        return origin
    return None


def _add_cors_headers(response: Response) -> Response:
    origin = _get_allowed_origin()
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-Requested-With, X-Request-ID"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def _add_security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# Paths that use JWT auth instead of API key auth
_JWT_AUTH_PREFIXES = ("/sessions", "/lead-runs", "/auth/", "/documents", "/data", "/billing")


@app.before_request
async def before_request():
    """Handle preflight, auth (dual scheme), rate limiting, and request correlation."""
    request.correlation_id = uuid.uuid4().hex
    request.start_time = time.monotonic()

    if request.method == "OPTIONS":
        response = Response()
        return _add_cors_headers(response)

    # Enforce HTTPS in production via X-Forwarded-Proto (Azure App Service / reverse proxy)
    if FORCE_HTTPS:
        proto = request.headers.get("X-Forwarded-Proto", "https")
        if proto.lower() != "https":
            https_url = request.url.replace("http://", "https://", 1)
            from quart import redirect
            return redirect(https_url, code=301)

    path = request.path
    if any(path.startswith(prefix) for prefix in _JWT_AUTH_PREFIXES):
        # Phase 2 endpoints — JWT required
        jwt_response = await jwt_auth_middleware()
        if jwt_response is not None:
            return jwt_response
    elif path.startswith("/v1/"):
        # Chat endpoint — try JWT (web users) first, fall back to API key
        # (server-to-server / internal clients).  No anonymous access.
        jwt_response = await jwt_auth_middleware()
        if jwt_response is not None:
            # JWT failed or absent — try API key
            api_key_response = await auth_middleware()
            if api_key_response is not None:
                # Both failed — return JWT's 401 (more descriptive)
                return jwt_response
            # API key valid — flag so tier lookup can skip Cosmos
            request.api_key_auth = True  # type: ignore[attr-defined]
    else:
        auth_response = await auth_middleware()
        if auth_response is not None:
            return auth_response

    rl_response = await rate_limit_middleware()
    if rl_response is not None:
        return rl_response


@app.after_request
async def after_request(response: Response) -> Response:
    _add_cors_headers(response)
    _add_security_headers(response)

    correlation_id = getattr(request, "correlation_id", None)
    if correlation_id:
        response.headers["X-Request-ID"] = correlation_id

    start_time = getattr(request, "start_time", None)
    duration_ms = round((time.monotonic() - start_time) * 1000, 2) if start_time else None

    logger.info(
        "request completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    return response


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatMessage(BaseModel):
    """OpenAI-compatible message."""

    role: str  # "user", "assistant", "system"
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: List[ChatMessage]
    stream: bool = Field(default=False)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=65536, ge=1)  # GPT-5.2 supports 128K output


# ============================================================================
# Azure + MCP helpers
# ============================================================================


def _require_azure_config() -> None:
    missing = []
    if not AZURE_OPENAI_KEY:
        missing.append("AZURE_OPENAI_KEY")
    if not AZURE_OPENAI_ENDPOINT:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _is_gpt5_deployment() -> bool:
    return "gpt-5" in AZURE_OPENAI_DEPLOYMENT.lower()


def get_azure_client() -> AsyncAzureOpenAI:
    """Initialize Azure OpenAI client."""
    global _azure_client
    _require_azure_config()

    if _azure_client is None:
        _azure_client = AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            timeout=AZURE_OPENAI_TIMEOUT_SECONDS,
        )

    return _azure_client


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue

            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
                continue

            nested = item.get("content")
            if isinstance(nested, str):
                parts.append(nested)

        return "\n".join(p for p in parts if p)

    return ""


def _normalize_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for message in messages:
        role = str(message.get("role", "")).strip().lower()
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        content = message.get("content")

        # Preserve array content (vision format with image_url parts) as-is
        if role == "user" and isinstance(content, list):
            normalized.append({"role": role, "content": content})
            continue

        text_content = _extract_text_content(content)

        if role == "tool":
            normalized.append({"role": role, "content": text_content or "{}"})
            continue

        if text_content:
            normalized.append({"role": role, "content": text_content})

    return normalized


def _last_user_prompt(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        # Handle vision-format content (array with text + image_url parts)
        if isinstance(content, list):
            texts = [
                p["text"] for p in content
                if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str)
            ]
            result = "\n".join(texts)
            if result:
                return result
            continue
        text = _extract_text_content(content)
        if text:
            return text
    return ""


def _messages_for_tool_payload(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    slim: list[dict[str, str]] = []
    for message in messages[-10:]:
        role = str(message.get("role", "")).strip().lower()
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        slim.append(
            {
                "role": role,
                "content": _extract_text_content(message.get("content")) or "",
            }
        )

    return slim


# ============================================================================
# Context Token Management
# ============================================================================


def _count_message_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Estimate token count for a list of messages.

    Uses tiktoken with the gpt-4o encoding (o200k_base) for accuracy, falling
    back to cl100k_base, then to a rough char/4 heuristic if tiktoken is not
    installed.  The per-message overhead (+4 tokens) follows the OpenAI
    cookbook formula for chat completions.
    """
    try:
        import tiktoken

        # Use o200k_base directly — the encoding used by GPT-4o and the GPT-5
        # family.  Avoids model-name lookups that fail for Azure deployment
        # names like "gpt-5.2-chat" which aren't in tiktoken's registry.
        try:
            enc = tiktoken.get_encoding("o200k_base")
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")

        total = 3  # reply-priming overhead
        for msg in messages:
            total += 4  # per-message framing
            total += len(enc.encode(msg.get("role") or ""))
            content = msg.get("content")
            if isinstance(content, str):
                total += len(enc.encode(content))
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += len(enc.encode(str(part.get("text") or "")))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                total += len(enc.encode(fn.get("name") or ""))
                total += len(enc.encode(fn.get("arguments") or ""))
        return total

    except ImportError:
        # Fallback: ~4 chars per token
        total = 3
        for msg in messages:
            total += 4
            content = msg.get("content") or ""
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total += len(str(part.get("text") or "")) // 4
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                total += len(fn.get("arguments") or "") // 4
        return total


def _cap_tool_result_content(msg: dict[str, Any]) -> dict[str, Any]:
    """
    Return a (possibly new) tool-role message with content capped at
    _MAX_TOOL_RESULT_CHARS.  Prefers trimming verbose fields inside the JSON
    payload (preview, data, results) over blind string truncation so the
    structure stays valid.
    """
    content = msg.get("content")
    if not isinstance(content, str) or len(content) <= _MAX_TOOL_RESULT_CHARS:
        return msg

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            half = _MAX_TOOL_RESULT_CHARS // 2
            for key in ("preview", "data", "results", "body", "raw"):
                val = parsed.get(key)
                if isinstance(val, str) and len(val) > half:
                    parsed[key] = val[:half] + "... [truncated]"
                elif isinstance(val, list) and len(val) > 20:
                    parsed[key] = val[:20]
                    parsed["_truncated"] = True
        capped = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        capped = content[:_MAX_TOOL_RESULT_CHARS] + "... [truncated]"

    return {**msg, "content": capped}


def _truncate_to_token_budget(
    messages: list[dict[str, Any]],
    budget: int = _CONTEXT_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    """
    Reduce the message list to fit within ``budget`` tokens while preserving
    conversational coherence.

    Truncation order (least-lossy first):

    1. Cap individual tool-result content in-place (preserves all messages).
    2. Drop the oldest assistant-tool-call group (the assistant message that
       requested tool calls plus all the tool-response messages that follow it)
       from the front of the list.  Tool-call pairs are always removed as a
       unit to keep the conversation structurally valid.
    3. Drop the oldest non-system message from the front (user/assistant
       exchanges from early in the conversation).

    Invariants:
    - System messages are never dropped.
    - The last user message is never dropped.
    """
    # Step 1: cap individual tool results — often enough on its own
    capped = [
        _cap_tool_result_content(m) if m.get("role") == "tool" else m
        for m in messages
    ]

    if _count_message_tokens(capped) <= budget:
        return capped

    system_msgs = [m for m in capped if m.get("role") == "system"]
    other_msgs = [m for m in capped if m.get("role") != "system"]

    # Index of the last user message — must always be kept
    last_user_idx = next(
        (i for i in reversed(range(len(other_msgs))) if other_msgs[i].get("role") == "user"),
        None,
    )

    def _over_budget() -> bool:
        return _count_message_tokens(system_msgs + other_msgs) > budget

    # Step 2: drop oldest tool-call group (assistant + all its tool responses)
    while _over_budget() and len(other_msgs) > 1:
        removed = False
        for i, msg in enumerate(other_msgs):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Collect all consecutive tool responses that follow
                j = i + 1
                while j < len(other_msgs) and other_msgs[j].get("role") == "tool":
                    j += 1
                dropped = j - i
                other_msgs = other_msgs[:i] + other_msgs[j:]
                if last_user_idx is not None and last_user_idx > i:
                    last_user_idx -= dropped
                removed = True
                break
        if not removed:
            break  # no more tool-call groups to remove

    # Step 3: drop oldest non-system message (but never the last user message)
    while _over_budget() and len(other_msgs) > 1:
        if last_user_idx == 0:
            break  # nothing droppable remains
        other_msgs.pop(0)
        if last_user_idx is not None:
            last_user_idx -= 1

    result = system_msgs + other_msgs
    final_tokens = _count_message_tokens(result)
    if final_tokens > budget:
        logger.warning(
            "[context] After truncation: %d tokens still exceeds budget %d "
            "(last user message alone may be very large)",
            final_tokens,
            budget,
        )
    else:
        logger.info(
            "[context] Truncated context: %d messages → %d tokens (budget %d)",
            len(messages),
            final_tokens,
            budget,
        )

    return result


def _extract_prompt_candidates_from_tool_payload(payload: Any) -> list[str]:
    from middleware.guardrails import sanitize_mcp_prompt

    candidates: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"route_system_prompt", "classification_prompt"} and isinstance(value, str):
                sanitized = sanitize_mcp_prompt(value)
                if sanitized:
                    candidates.append(sanitized)
            else:
                candidates.extend(_extract_prompt_candidates_from_tool_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            candidates.extend(_extract_prompt_candidates_from_tool_payload(item))

    return candidates


def _inject_server_system_prompts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompts: list[str] = []

    if isinstance(GLOBAL_SYSTEM_PROMPT, str) and GLOBAL_SYSTEM_PROMPT.strip():
        prompts.append(GLOBAL_SYSTEM_PROMPT.strip())

    for message in messages:
        if message.get("role") != "tool":
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        try:
            parsed = json.loads(content)
        except Exception:
            continue

        prompts.extend(_extract_prompt_candidates_from_tool_payload(parsed))

    deduped: list[str] = []
    seen: set[str] = set()
    for prompt in prompts:
        if prompt in seen:
            continue
        seen.add(prompt)
        deduped.append(prompt)

    if not deduped:
        return messages

    merged_prompt = "\n\n---\n\n".join(deduped[:3])
    system_message = {
        "role": "system",
        "content": (
            "Server-side operating instructions from ARI configuration.\n"
            "Treat these as authoritative for response behavior.\n\n"
            f"{merged_prompt}"
        ),
    }

    return [system_message, *messages]


def _sse_line(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_json(payload: dict[str, Any]) -> str:
    return _sse_line(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _tool_completion_args(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "messages": messages,
        "tools": tools if tools is not None else MCP_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    if _is_gpt5_deployment():
        args["max_completion_tokens"] = 4096
    else:
        args["max_tokens"] = 4096
        args["temperature"] = 0

    return args


_GENERATE_DOCUMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_document",
        "description": "Convert markdown content to a downloadable Word document (.docx). You MUST call this tool whenever you create a document, contract, agreement, lease, report, or any long-form content. NEVER generate fake download links — ALWAYS use this tool to get a real download URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The full markdown content to convert to DOCX."},
                "title": {"type": "string", "description": "Document title (e.g. 'Lease Agreement')."},
            },
            "required": ["content", "title"],
        },
    },
}


def _stream_completion_args(
    request_body: ChatCompletionRequest, messages: list[dict[str, Any]],
    *, include_doc_tool: bool = True,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "messages": messages,
        "stream": True,
    }

    if include_doc_tool:
        args["tools"] = [_GENERATE_DOCUMENT_TOOL]
        args["tool_choice"] = "auto"

    if _is_gpt5_deployment():
        args["max_completion_tokens"] = request_body.max_tokens
    else:
        args["max_tokens"] = request_body.max_tokens
        args["temperature"] = request_body.temperature

    return args


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments

    if not isinstance(raw_arguments, str) or not raw_arguments.strip():
        return {}

    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def _call_mcp_tool_endpoint(
    tool_name: str,
    arguments: dict[str, Any],
    messages: list[dict[str, Any]],
    fallback_prompt: str,
) -> dict[str, Any]:
    endpoint = MCP_TOOL_ENDPOINTS.get(tool_name)
    if not endpoint:
        return {
            "ok": False,
            "tool": tool_name,
            "error": f"Unknown MCP tool name: {tool_name}",
        }

    payload = {
        "prompt": str(arguments.get("prompt") or fallback_prompt or ""),
        "messages": _messages_for_tool_payload(messages),
        "arguments": arguments,
    }

    try:
        async with httpx.AsyncClient(timeout=MCP_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{MCP_BASE_URL}{endpoint}", json=payload)

        if response.status_code >= 400:
            return {
                "ok": False,
                "tool": tool_name,
                "error": f"MCP tool HTTP {response.status_code}",
                "body": response.text[:2000],
            }

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:2000]}

        return {
            "ok": True,
            "tool": tool_name,
            "data": data,
        }
    except Exception as exc:
        return {
            "ok": False,
            "tool": tool_name,
            "error": str(exc),
        }


async def _handle_generate_document(arguments: dict[str, Any]) -> dict[str, Any]:
    """Local tool: convert markdown to DOCX, upload to Azure Blob, return download URL."""
    import re as _re
    import time as _time

    from services.azure_blob import AzureBlobService
    from services.docx_export import markdown_to_docx

    content = arguments.get("content", "")
    title = arguments.get("title", "Document")

    if not isinstance(content, str) or not content.strip():
        return {"ok": False, "tool": "generate_document", "error": "content is required"}

    if not isinstance(title, str) or not title.strip():
        title = "Document"
    title = title.strip()[:200]

    blob = AzureBlobService.get_instance()
    if not blob:
        return {"ok": False, "tool": "generate_document", "error": "Document export not configured (blob storage unavailable)"}

    try:
        buffer = markdown_to_docx(content, title)
    except Exception:
        logger.exception("DOCX generation failed in tool call")
        return {"ok": False, "tool": "generate_document", "error": "Failed to generate document"}

    # Slugify title for filename
    slug = title.lower().strip()
    slug = _re.sub(r"[^\w\s-]", "", slug)
    slug = _re.sub(r"[\s_]+", "-", slug)
    slug = _re.sub(r"-+", "-", slug).strip("-")[:60] or "document"
    filename = f"{slug}_{int(_time.time())}.docx"

    try:
        url = blob.upload_bytes(
            container_name="documents",
            file_name=filename,
            data=buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            expiry_minutes=30,
        )
    except Exception:
        logger.exception("Blob upload failed in tool call")
        return {"ok": False, "tool": "generate_document", "error": "Failed to upload document"}

    return {
        "ok": True,
        "tool": "generate_document",
        "data": {
            "url": url,
            "filename": filename,
            "message": f"Document ready for download. Include this link in your response: {url}",
        },
    }


def _extract_file_attachments(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract base64-encoded file attachments from message content arrays.

    The web frontend sends files as FileUIPart objects:
        {"type": "file", "url": "data:<mime>;base64,<data>", "filename": "...", "mediaType": "..."}

    Returns a list of {"filename": str, "data": bytes, "media_type": str}.
    """
    import base64

    attachments: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "file":
                continue
            url = part.get("url", "")
            filename = (part.get("filename") or part.get("name") or "upload").strip()
            media_type = (part.get("mediaType") or part.get("mimeType") or "").strip()

            if not url.startswith("data:"):
                continue

            try:
                header, encoded = url.split(",", 1)
                if ";base64" not in header:
                    continue
                data = base64.b64decode(encoded)
                attachments.append({"filename": filename, "data": data, "media_type": media_type})
            except Exception:
                logger.warning("Failed to decode file attachment '%s'", filename)

    return attachments


async def _handle_stack_lists(
    arguments: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Local tool: process uploaded property lists, find overlap, return Excel download URL."""
    import time as _time

    from services.azure_blob import AzureBlobService
    from services.stack_lists import process_stack_lists

    _SPREADSHEET_EXTS = {".xlsx", ".xls", ".csv"}

    all_files = _extract_file_attachments(messages)
    spreadsheet_files = [
        f for f in all_files
        if any(f["filename"].lower().endswith(ext) for ext in _SPREADSHEET_EXTS)
    ]

    if len(spreadsheet_files) < 2:
        found = len(spreadsheet_files)
        total = len(all_files)
        return {
            "ok": False,
            "tool": "mcp_stack_lists",
            "error": (
                f"Stack lists requires at least 2 Excel/CSV files. "
                f"Found {found} spreadsheet(s) out of {total} total attachment(s). "
                "Please upload your property list files directly in the chat message."
            ),
        }

    try:
        result_buf, summary = process_stack_lists(spreadsheet_files)
    except ValueError as exc:
        return {"ok": False, "tool": "mcp_stack_lists", "error": str(exc)}
    except Exception:
        logger.exception("Stack lists processing failed")
        return {"ok": False, "tool": "mcp_stack_lists", "error": "Failed to process the uploaded files"}

    blob = AzureBlobService.get_instance()
    if not blob:
        return {
            "ok": False,
            "tool": "mcp_stack_lists",
            "error": "Document export not configured (Azure Blob Storage unavailable)",
        }

    filename = f"stacked_properties_{int(_time.time())}.xlsx"
    try:
        url = blob.upload_bytes(
            container_name="documents",
            file_name=filename,
            data=result_buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            expiry_minutes=30,
        )
    except Exception:
        logger.exception("Blob upload failed for stack lists")
        return {"ok": False, "tool": "mcp_stack_lists", "error": "Failed to upload the results file"}

    overlap = summary["overlap_count"]
    lists = summary["lists_processed"]
    list_names = ", ".join(l["filename"] for l in lists)

    if overlap == 0:
        message = (
            f"No overlapping properties found across the {len(lists)} uploaded lists ({list_names}). "
            f"A summary file is available: {url}"
        )
    else:
        message = (
            f"Found {overlap} {'property' if overlap == 1 else 'properties'} appearing on "
            f"multiple lists out of {len(lists)} files ({list_names}). "
            f"Download the consolidated Excel file: {url}"
        )

    return {
        "ok": True,
        "tool": "mcp_stack_lists",
        "data": {
            "url": url,
            "filename": filename,
            "overlap_count": overlap,
            "total_rows": summary["total_rows"],
            "lists_processed": lists,
            "message": message,
        },
    }


# Fake document URLs the model hallucinates instead of using the generate_document tool.
_FAKE_DOC_URL_RE = re.compile(
    r'\[([^\]]*)\]\(((?:sandbox:|https?://files\.openaiusercontent\.com|https?://(?:cdn\.)?openai\.com|https?://(?:www\.)?reilabs\.ai/)[^\)]*)\)',
    re.IGNORECASE,
)

# Hallucinated blob URLs: data.reilabs.ai/documents/...docx WITHOUT a SAS token (?sv=).
# Real URLs from _handle_generate_document always have ?sv=...&sig=... query params.
_HALLUCINATED_BLOB_RE = re.compile(
    r'https?://data\.reilabs\.ai/documents/[a-zA-Z0-9_\-]+\.docx(?!\?)',
    re.IGNORECASE,
)


async def _auto_generate_docx_if_needed(response_text: str) -> str | None:
    """
    If the model generated fake document links (sandbox:/, openaiusercontent.com),
    extract the document content, generate a real DOCX, and return a markdown
    snippet with the real download link.
    """
    logger.info("Auto DOCX check (v1): response length=%d", len(response_text) if response_text else 0)

    if not response_text:
        return None

    match = _FAKE_DOC_URL_RE.search(response_text)
    if not match:
        # Also check for bare fake URLs (not in markdown links)
        bare_fake = re.search(
            r'https?://files\.openaiusercontent\.com/[^\s\)]+\.docx?',
            response_text, re.IGNORECASE,
        )
        bare_sandbox = re.search(r'sandbox:/[^\s\)]+\.docx?', response_text, re.IGNORECASE)
        bare_blob = _HALLUCINATED_BLOB_RE.search(response_text)
        if not bare_fake and not bare_sandbox and not bare_blob:
            logger.info("Auto DOCX: no fake URL found, skipping")
            return None
        found = bare_fake or bare_sandbox or bare_blob
        logger.info("Auto DOCX: found bare fake URL: %s", found.group(0))
        # Extract a readable title from hallucinated blob filename (e.g. "single-family-home-lease-option-agreement")
        title = "Document"
        if bare_blob:
            slug = bare_blob.group(0).rsplit("/", 1)[-1].rsplit(".", 1)[0]
            slug = re.sub(r'_\d+$', '', slug)  # strip trailing timestamp
            title = slug.replace("-", " ").replace("_", " ").strip().title() or "Document"
    else:
        title = match.group(1) or "Document"
        logger.info("Auto DOCX: found fake markdown link, title=%s", title)

    try:
        # Strip commentary after the document content
        content = response_text
        for marker in ["## How Investors", "## Critical Investor", "## Next Steps",
                        "### What's", "### How", "### File Details", "---\n\n###",
                        "If you want", "If for any reason", "### If you",
                        "### Next", "### ✅ What this", "### ✅ What's"]:
            idx = content.find(marker)
            if idx > 0:
                content = content[:idx].strip()
                break

        # Remove fake URL lines (markdown links and bare URLs)
        content = _FAKE_DOC_URL_RE.sub("", content)
        content = re.sub(r'https?://files\.openaiusercontent\.com/[^\s\)]+', '', content)
        content = re.sub(r'sandbox:/[^\s\)]+', '', content)
        content = _HALLUCINATED_BLOB_RE.sub('', content)
        # Remove emoji-heavy intro lines
        content = re.sub(r'^.*(?:👉|✅|📄).*$', '', content, flags=re.MULTILINE)
        content = content.strip()

        logger.info("Auto DOCX: cleaned content length=%d", len(content))

        if len(content) < 200:
            logger.info("Auto DOCX: content too short (%d), skipping", len(content))
            return None

        result = await _handle_generate_document({"content": content, "title": title})
        logger.info("Auto DOCX: generate result ok=%s", result.get("ok"))

        if result.get("ok") and result.get("data", {}).get("url"):
            url = result["data"]["url"]
            return f"\n\n📄 **[Download {title} (.docx)]({url})**"
        else:
            logger.error("Auto DOCX: generation failed: %s", result.get("error"))
    except Exception:
        logger.exception("Auto DOCX generation failed")

    return None


# ---------------------------------------------------------------------------
# Tier-based tool access
# ---------------------------------------------------------------------------

_ALL_TOOL_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in MCP_TOOL_DEFINITIONS
)

# elite / admin  — unrestricted access to every tool
# pro            — all data tools (leads, buyers, comps, attorneys, documents)
# basic          — education, strategy, comps, contracts, documents only
#                  (no lead scraping, no buyers DB, no attorneys)
# (no tier)      — new / unverified accounts: classification + education only
_TIER_TOOLS: dict[str, frozenset[str]] = {
    "admin": _ALL_TOOL_NAMES,
    "elite": _ALL_TOOL_NAMES,
    "pro": frozenset({
        "mcp_integration_config",
        "mcp_classify_route",
        "mcp_education_context",
        "mcp_comps_context",
        "mcp_bricked_comps",
        "mcp_leads_context",
        "mcp_attorneys_context",
        "mcp_strategy_context",
        "mcp_contracts_context",
        "mcp_buyers_context",
        "mcp_buyers_search",
        "mcp_extract_city_state",
        "mcp_extract_address",
        "mcp_offtopic_context",
        "mcp_build_retrieval_query",
        "mcp_infer_lead_type",
        "generate_document",
        "mcp_stack_lists",
    }),
    "basic": frozenset({
        "mcp_integration_config",
        "mcp_classify_route",
        "mcp_education_context",
        "mcp_comps_context",
        "mcp_strategy_context",
        "mcp_contracts_context",
        "mcp_extract_address",
        "mcp_offtopic_context",
        "mcp_build_retrieval_query",
        "generate_document",
    }),
}

# Authenticated users with no tier (signed up but not subscribed yet)
_NO_TIER_TOOLS: frozenset[str] = frozenset({
    "mcp_integration_config",
    "mcp_classify_route",
    "mcp_education_context",
    "mcp_offtopic_context",
})

# Simple TTL cache: user_id → (tier_str, fetched_at_monotonic)
_tier_cache: dict[str, tuple[str, float]] = {}
_TIER_CACHE_TTL: float = float(os.getenv("TIER_CACHE_TTL_SECONDS", "300"))


async def _get_user_tier(user_id: str) -> str:
    """
    Return the user's tier string from Cosmos DB (cached for _TIER_CACHE_TTL seconds).

    Returns "elite" when Cosmos is not configured (dev / local mode).
    Returns "" (empty string) when the user has no tier assigned.
    """
    now = time.monotonic()
    cached = _tier_cache.get(user_id)
    if cached is not None and (now - cached[1]) < _TIER_CACHE_TTL:
        return cached[0]

    from cosmos import SessionsCosmosClient

    cosmos = SessionsCosmosClient.get_instance()
    if cosmos is None:
        # Dev mode: no Cosmos configured — grant full access
        return "elite"

    try:
        sub = await cosmos.get_user_subscription(user_id)
        tier = ((sub or {}).get("tier") or "").strip().lower()
        # Normalize ari_* prefixed values (from metadata or legacy plan field)
        _plan_map = {"ari_elite": "elite", "ari_pro": "pro", "ari_lite": "basic"}
        tier = _plan_map.get(tier, tier)
        # Fall back to deriving tier from plan for migrated users that have plan but no tier
        if not tier:
            plan = ((sub or {}).get("plan") or "").strip().lower()
            tier = _plan_map.get(plan, "")
    except Exception:
        logger.warning("[tier] Cosmos lookup failed for user %s; defaulting to no-tier", user_id)
        tier = ""

    _tier_cache[user_id] = (tier, now)
    logger.info("[tier] user=%s tier=%r", user_id, tier or "(none)")
    return tier


async def _get_tools_for_user(user_id: str | None = None) -> list[dict[str, Any]]:
    """
    Return the MCP tool definitions the caller is permitted to use.

    Priority:
    1. API-key-authenticated requests (server-to-server) → full admin access
    2. JWT user with a recognised tier → _TIER_TOOLS[tier]
    3. JWT user with no tier assigned  → _NO_TIER_TOOLS (classification/education only)
    4. No identity (should be blocked by auth, but defensive fallback) → _NO_TIER_TOOLS
    """
    if user_id is None:
        try:
            user_id = getattr(request, "user_id", None)
        except RuntimeError:
            pass

    # API-key calls (internal/server-to-server) get unrestricted access
    try:
        if getattr(request, "api_key_auth", False):
            return MCP_TOOL_DEFINITIONS
    except RuntimeError:
        pass

    # No identity — should have been blocked by auth middleware, but be defensive
    if not user_id:
        logger.warning("[tier] No user_id in tool lookup; returning minimal tools")
        return [t for t in MCP_TOOL_DEFINITIONS if t["function"]["name"] in _NO_TIER_TOOLS]

    tier = await _get_user_tier(user_id)
    allowed = _TIER_TOOLS.get(tier, _NO_TIER_TOOLS)
    tools = [t for t in MCP_TOOL_DEFINITIONS if t["function"]["name"] in allowed]
    logger.info("[tier] user=%s tier=%r → %d/%d tools", user_id, tier or "(none)", len(tools), len(MCP_TOOL_DEFINITIONS))
    return tools


async def _run_mcp_tool_orchestration(
    messages: list[dict[str, Any]],
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Model-driven tool loop:
    1) Ask model to call MCP tools
    2) Execute tool calls over HTTP
    3) Feed tool outputs back to model context

    ``user_id`` is forwarded to ``_get_tools_for_user`` so that tier-based
    filtering works even when called outside the Quart request context.
    """
    if not MCP_ENABLED:
        logger.info("[MCP] Orchestration skipped — MCP_ENABLED is False")
        return messages

    prompt = _last_user_prompt(messages)
    if not prompt:
        logger.info("[MCP] Orchestration skipped — no user prompt found")
        return messages

    client = get_azure_client()
    # Prepend orchestration system prompt so the planning model knows routing rules.
    # This is separate from the GLOBAL_SYSTEM_PROMPT which is injected for the
    # streaming response phase.
    orchestration_system = {"role": "system", "content": _ORCHESTRATION_SYSTEM_PROMPT}
    working_messages: list[dict[str, Any]] = [orchestration_system, *messages]
    allowed_tools = await _get_tools_for_user(user_id)
    tool_names = [t.get("function", {}).get("name") for t in allowed_tools]
    logger.info("[MCP] Orchestration start — user_id=%s, %d tools available: %s",
                user_id, len(allowed_tools), tool_names)

    for round_idx in range(MCP_TOOL_MAX_ROUNDS):
        # Truncate before each planning call — working_messages grows each round
        # as tool results are appended and can overflow the context window.
        budget_messages = _truncate_to_token_budget(working_messages)
        planning = await client.chat.completions.create(
            **_tool_completion_args(budget_messages, tools=allowed_tools)
        )

        if not planning.choices:
            logger.info("[MCP] Round %d — no choices from model", round_idx)
            break

        assistant_message = planning.choices[0].message
        tool_calls = [
            tc
            for tc in (assistant_message.tool_calls or [])
            if getattr(tc, "type", None) == "function"
        ][:MCP_TOOL_MAX_CALLS_PER_ROUND]

        if not tool_calls:
            logger.info("[MCP] Round %d — model chose no tool calls", round_idx)
            break

        logger.info("[MCP] Round %d — model requested tools: %s", round_idx,
                    [tc.function.name for tc in tool_calls])

        assistant_tool_message = {
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ],
        }
        working_messages.append(assistant_tool_message)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = _parse_tool_arguments(tool_call.function.arguments)

            # Local tool handlers (no MCP proxy needed)
            if tool_name == "generate_document":
                tool_result = await _handle_generate_document(tool_args)
            elif tool_name == "mcp_stack_lists":
                # Pass original messages so file attachments are accessible
                tool_result = await _handle_stack_lists(tool_args, messages)
            else:
                tool_result = await _call_mcp_tool_endpoint(
                    tool_name=tool_name,
                    arguments=tool_args,
                    messages=working_messages,
                    fallback_prompt=prompt,
                )

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    return working_messages


# ============================================================================
# Azure OpenAI Streaming Response Generator
# ============================================================================


async def generate_azure_response(
    request_body: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """
    Stream response from Azure OpenAI GPT-5.2 using SSE format.
    Maintains OpenAI-compatible API contract.

    If the model calls generate_document mid-stream, the tool is executed
    and a follow-up streaming completion feeds the result back so the model
    can include the real download URL in its response.
    """
    stream_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    full_response_text = ""

    try:
        client = get_azure_client()

        base_messages = [
            {"role": message.role, "content": message.content}
            for message in request_body.messages
        ]
        normalized_messages = _normalize_openai_messages(base_messages)

        try:
            completion_messages = await _run_mcp_tool_orchestration(normalized_messages)
        except Exception:
            logger.exception("MCP orchestration failed; continuing without MCP tool context")
            completion_messages = normalized_messages

        completion_messages = _inject_server_system_prompts(completion_messages)
        completion_messages = _truncate_to_token_budget(completion_messages)

        # Stream with up to 2 rounds of tool calls (generate_document)
        for _round in range(2):
            response = await client.chat.completions.create(
                **_stream_completion_args(request_body, completion_messages,
                                          include_doc_tool=(_round == 0))
            )

            round_text = ""
            tool_call_id = None
            tool_name = None
            tool_args_str = ""

            async for chunk in response:
                payload = chunk.model_dump(exclude_none=True)
                payload.setdefault("id", stream_id)
                payload.setdefault("object", "chat.completion.chunk")
                payload.setdefault("created", created)
                payload.setdefault("model", request_body.model)

                for choice in payload.get("choices", []):
                    delta = choice.get("delta", {})

                    # Accumulate text content
                    if "content" in delta and delta["content"]:
                        round_text += delta["content"]
                        full_response_text += delta["content"]

                    # Accumulate tool call arguments (streamed incrementally)
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            if tc.get("id"):
                                tool_call_id = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                tool_name = fn["name"]
                            if fn.get("arguments"):
                                tool_args_str += fn["arguments"]

                # Only forward text-content chunks to the client (skip tool_call deltas)
                has_text = any(
                    c.get("delta", {}).get("content")
                    for c in payload.get("choices", [])
                )
                if has_text:
                    yield _sse_json(payload)

            # If model called generate_document, execute it and loop for follow-up
            if tool_name == "generate_document" and tool_call_id:
                logger.info("Model called generate_document tool during streaming")
                tool_args = _parse_tool_arguments(tool_args_str)
                tool_result = await _handle_generate_document(tool_args)

                # Add assistant tool_call message + tool result to context
                completion_messages.append({
                    "role": "assistant",
                    "content": round_text or "",
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "generate_document",
                            "arguments": tool_args_str or "{}",
                        },
                    }],
                })
                completion_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })
                # Continue loop — next round streams the follow-up with tool result
                continue

            # No tool call — done streaming
            break

        # Fallback: auto-generate DOCX if model still used fake URLs
        try:
            docx_extra = await _auto_generate_docx_if_needed(full_response_text)
            if docx_extra:
                extra_chunk = {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": request_body.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": docx_extra},
                        "finish_reason": None,
                    }],
                }
                yield _sse_json(extra_chunk)
        except Exception:
            logger.exception("Auto DOCX generation failed in streaming response")

    except Exception as exc:
        logger.exception("Azure OpenAI streaming error")
        yield _sse_json(
            {
                "error": {
                    "type": "api_error",
                    "message": str(exc),
                }
            }
        )
    finally:
        yield _sse_line("[DONE]")


# ============================================================================
# Routes
# ============================================================================


@app.post("/v1/chat/completions")
async def chat_completions():
    """
    OpenAI-compatible chat completions endpoint.

    Accepts:
    {
        "model": "gpt-5.2-chat",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "stream": true
    }

    Returns SSE stream with delta tokens.
    """
    try:
        json_data = await request.get_json()
        if not isinstance(json_data, dict):
            raise ValueError("Expected JSON object body")
        request_body = ChatCompletionRequest(**json_data)
    except (ValidationError, ValueError, TypeError) as exc:
        return {"error": "Invalid request body", "detail": str(exc)}, 400

    if not request_body.stream:
        return {
            "error": "Streaming is required for this endpoint",
            "detail": "stream=true must be set",
        }, 400

    # Server uses AZURE_OPENAI_DEPLOYMENT — ignore client-sent model field
    request_body.model = AZURE_OPENAI_DEPLOYMENT

    if len(request_body.messages) > MAX_MESSAGES_COUNT:
        return {
            "error": "Too many messages",
            "detail": f"Maximum {MAX_MESSAGES_COUNT} messages allowed per request",
        }, 400

    for i, msg in enumerate(request_body.messages):
        # For array content (vision/file format) only measure text parts,
        # not base64 file data which can be legitimately large.
        if isinstance(msg.content, str):
            content_len = len(msg.content)
        elif isinstance(msg.content, list):
            content_len = sum(
                len(p.get("text", ""))
                for p in msg.content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        else:
            content_len = 0
        if content_len > MAX_MESSAGE_LENGTH:
            return {
                "error": "Message too long",
                "detail": f"Message at index {i} exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
            }, 400

    # Guardrails — check last user message before processing
    from middleware.guardrails import check_prompt_injection, check_content, check_off_topic

    last_user_content = ""
    for msg in reversed(request_body.messages):
        if msg.role == "user":
            if isinstance(msg.content, str):
                last_user_content = msg.content
            elif isinstance(msg.content, list):
                # Extract text parts only — skip base64 file attachments
                texts = [
                    p.get("text", "")
                    for p in msg.content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                last_user_content = " ".join(texts)
            break

    if last_user_content:
        injection = check_prompt_injection(last_user_content)
        if injection:
            return {"error": "blocked", "detail": injection}, 400

        moderation = check_content(last_user_content)
        if moderation:
            return {"error": "blocked", "detail": moderation}, 400

        offtopic = check_off_topic(last_user_content)
        if offtopic:
            return {"error": "off_topic", "detail": offtopic}, 422

    try:
        _require_azure_config()
    except RuntimeError as exc:
        return {"error": "Azure OpenAI is not configured", "detail": str(exc)}, 500

    return Response(
        generate_azure_response(request_body),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
        "mcp_enabled": MCP_ENABLED,
        "mcp_base_url": MCP_BASE_URL,
    }, 200


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ARI Backend API",
        "version": "0.2.0",
        "endpoints": [
            "POST /v1/chat/completions",
            "POST /auth/exchange",
            "POST /sessions",
            "GET /sessions",
            "GET /sessions/<id>",
            "POST /sessions/<id>/messages",
            "GET /sessions/<id>/messages",
            "GET /lead-runs",
            "GET /lead-runs/<id>",
            "POST /auth/magic-link/send",
            "POST /auth/magic-link/verify",
            "GET /billing/status",
            "POST /billing/create-checkout",
            "POST /webhook/stripe",
            "GET /health",
        ],
    }, 200


@app.errorhandler(404)
async def not_found(_):
    """404 handler."""
    return {"error": "Not found"}, 404


@app.errorhandler(500)
async def server_error(err):
    """500 handler."""
    logger.exception("Unhandled 500 error: %s", err)
    return {"error": "Internal server error"}, 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=DEBUG,
    )
