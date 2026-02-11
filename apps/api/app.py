"""
ARI Backend API
OpenAI-compatible Chat Completions endpoint with SSE streaming.
Uses Azure OpenAI GPT-5.2 with model-driven MCP tool orchestration.
"""

import json
import logging
import os
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
from routes import auth_bp, sessions_bp, lead_runs_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(sessions_bp)
app.register_blueprint(lead_runs_bp)

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

GLOBAL_SYSTEM_PROMPT = os.getenv("ARI_SYSTEM_PROMPT") or os.getenv(
    "AZURE_OPENAI_SYSTEM_MESSAGE", ""
)

# MCP orchestration configuration
MCP_ENABLED = os.getenv("MCP_ENABLED", "True").lower() == "true"
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8100").rstrip("/")
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))
MCP_TOOL_MAX_ROUNDS = int(os.getenv("MCP_TOOL_MAX_ROUNDS", "2"))
MCP_TOOL_MAX_CALLS_PER_ROUND = int(os.getenv("MCP_TOOL_MAX_CALLS_PER_ROUND", "4"))

_azure_client: AsyncAzureOpenAI | None = None

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
            "description": "Get lead-generation context, lead type inference, and retrieval hint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Lead generation prompt."}
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
            "description": "Get buyer route context and location hints.",
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
            "description": "Query Cosmos buyers list by city/state and return preview rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Buyers prompt (optional if city/state provided)."},
                    "city": {"type": "string", "description": "Target city."},
                    "state": {"type": "string", "description": "Target state abbreviation or full state name."},
                    "max_results": {"type": "integer", "description": "Maximum buyer rows to return."},
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
    return response


# Paths that use JWT auth instead of API key auth
_JWT_AUTH_PREFIXES = ("/sessions", "/lead-runs", "/auth/")


@app.before_request
async def before_request():
    """Handle preflight, auth (dual scheme), rate limiting, and request correlation."""
    request.correlation_id = uuid.uuid4().hex
    request.start_time = time.monotonic()

    if request.method == "OPTIONS":
        response = Response()
        return _add_cors_headers(response)

    # Dual auth routing: JWT for Phase 2 endpoints, API key for /v1/*
    path = request.path
    if any(path.startswith(prefix) for prefix in _JWT_AUTH_PREFIXES):
        jwt_response = await jwt_auth_middleware()
        if jwt_response is not None:
            return jwt_response
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
    max_tokens: int = Field(default=2048, ge=1)


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


def _normalize_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    for message in messages:
        role = str(message.get("role", "")).strip().lower()
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        content = _extract_text_content(message.get("content"))

        if role == "tool":
            normalized.append({"role": role, "content": content or "{}"})
            continue

        if content:
            normalized.append({"role": role, "content": content})

    return normalized


def _last_user_prompt(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = _extract_text_content(message.get("content"))
        if content:
            return content
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


def _extract_prompt_candidates_from_tool_payload(payload: Any) -> list[str]:
    candidates: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"route_system_prompt", "classification_prompt"} and isinstance(value, str):
                text = value.strip()
                if text:
                    candidates.append(text)
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


def _tool_completion_args(messages: list[dict[str, Any]]) -> dict[str, Any]:
    args: dict[str, Any] = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "messages": messages,
        "tools": MCP_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    if _is_gpt5_deployment():
        args["max_completion_tokens"] = 900
    else:
        args["max_tokens"] = 900
        args["temperature"] = 0

    return args


def _stream_completion_args(
    request_body: ChatCompletionRequest, messages: list[dict[str, Any]]
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "model": AZURE_OPENAI_DEPLOYMENT,
        "messages": messages,
        "stream": True,
    }

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


async def _run_mcp_tool_orchestration(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Model-driven tool loop:
    1) Ask model to call MCP tools
    2) Execute tool calls over HTTP
    3) Feed tool outputs back to model context
    """
    if not MCP_ENABLED:
        return messages

    prompt = _last_user_prompt(messages)
    if not prompt:
        return messages

    client = get_azure_client()
    working_messages: list[dict[str, Any]] = list(messages)

    for _ in range(MCP_TOOL_MAX_ROUNDS):
        planning = await client.chat.completions.create(
            **_tool_completion_args(working_messages)
        )

        if not planning.choices:
            break

        assistant_message = planning.choices[0].message
        tool_calls = [
            tc
            for tc in (assistant_message.tool_calls or [])
            if getattr(tc, "type", None) == "function"
        ][:MCP_TOOL_MAX_CALLS_PER_ROUND]

        if not tool_calls:
            break

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
    """
    stream_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

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

        response = await client.chat.completions.create(
            **_stream_completion_args(request_body, completion_messages)
        )

        async for chunk in response:
            payload = chunk.model_dump(exclude_none=True)
            payload.setdefault("id", stream_id)
            payload.setdefault("object", "chat.completion.chunk")
            payload.setdefault("created", created)
            payload.setdefault("model", request_body.model)
            yield _sse_json(payload)
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
        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
        if len(content) > MAX_MESSAGE_LENGTH:
            return {
                "error": "Message too long",
                "detail": f"Message at index {i} exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
            }, 400

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
            "POST /sessions/<id>/seal",
            "POST /sessions/<id>/messages",
            "GET /sessions/<id>/messages",
            "GET /lead-runs",
            "GET /lead-runs/<id>",
            "GET /health",
        ],
    }, 200


@app.errorhandler(404)
async def not_found(_):
    """404 handler."""
    return {"error": "Not found"}, 404


@app.errorhandler(500)
async def server_error(error):
    """500 handler."""
    return {"error": "Internal server error", "detail": str(error)}, 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=DEBUG,
    )
