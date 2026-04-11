"""
Demo endpoint — unauthenticated 3-question teaser for reilabs.ai/getari.

POST /demo/token  — issue a fresh signed demo JWT (questionsUsed=0)
POST /demo/chat   — validate token, enforce 3-question limit, stream SSE response

Security:
- Token is a signed JWT (same JWT_SECRET as the rest of the API); HS256
- Origin validated against allowlist on every chat request
- Reuses existing prompt injection + content guardrails
- No MCP tool calls — direct Azure OpenAI only
- Max 300 tokens per response
"""

import json
import logging
import os
import time

import jwt as pyjwt
from quart import Blueprint, Response, jsonify, request

logger = logging.getLogger("api.demo")

demo_bp = Blueprint("demo", __name__)

DEMO_MAX_QUESTIONS = 3
DEMO_MAX_INPUT_CHARS = 500
DEMO_MAX_RESPONSE_TOKENS = 1024
DEMO_TOKEN_TTL = 86400  # 24 hours

_DEMO_SYSTEM_PROMPT = (
    "You are ARI, an AI-powered real estate investment assistant by REI Labs. "
    "Answer real estate questions thoroughly with practical, actionable insights. "
    "Use bullet points or structured formatting when it makes the answer clearer. "
    "If the user asks for live data (leads, buyer lists, comps for a specific address), "
    "explain what ARI can do with that data and encourage them to sign up for full access at https://reilabs.ai/getari. "
    "Never answer questions unrelated to real estate."
)

_ALLOWED_ORIGINS = {
    "https://reilabs.ai",
    "https://www.reilabs.ai",
    "https://ari-web.azurewebsites.net",
    "https://ari-web-dev.azurewebsites.net",
}


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "").strip()


def _issue_demo_token(questions_used: int = 0, email: str = "") -> str:
    secret = _get_jwt_secret()
    now = int(time.time())
    payload = {
        "sub": "demo",
        "q": questions_used,
        "iat": now,
        "exp": now + DEMO_TOKEN_TTL,
    }
    if email:
        payload["email"] = email
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _verify_demo_token(token: str) -> dict | None:
    """Verify and decode a demo token. Returns payload or None on failure."""
    secret = _get_jwt_secret()
    if not secret:
        return None
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("sub") != "demo":
            return None
        return payload
    except pyjwt.InvalidTokenError:
        return None


def _sse_line(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_json(payload: dict) -> str:
    return _sse_line(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True  # non-browser clients (curl, server-side) — allow
    if os.getenv("DEBUG", "False").lower() == "true" and origin.startswith("http://localhost"):
        return True
    return origin in _ALLOWED_ORIGINS


@demo_bp.post("/demo/lead")
async def capture_lead():
    """Store a demo lead (name + email) for marketing. Unauthenticated."""
    origin = request.headers.get("Origin", "")
    if not _is_origin_allowed(origin):
        return jsonify({"error": "Forbidden"}), 403

    body = await request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body required"}), 400

    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()

    if not name or len(name) > 100:
        return jsonify({"error": "name is required (max 100 chars)"}), 400
    if not email or "@" not in email or "." not in email.split("@")[-1] or len(email) > 200:
        return jsonify({"error": "valid email is required"}), 400

    from cosmos import SessionsCosmosClient
    from datetime import datetime, timezone

    import hashlib
    doc_id = "demo_lead:" + hashlib.sha256(email.encode()).hexdigest()[:16]
    questions_used = 0

    cosmos = SessionsCosmosClient.get_instance()
    if cosmos:
        try:
            now = datetime.now(timezone.utc).isoformat()
            async with cosmos._client() as client:
                container = await cosmos._container(client)
                # Check for existing lead doc (returning user)
                try:
                    existing = await container.read_item(item=doc_id, partition_key="demo")
                    questions_used = int(existing.get("questionsUsed", 0))
                    # Update name/consent but preserve questionsUsed and createdAt
                    existing["name"] = name
                    existing["consentGiven"] = True
                    existing["consentAt"] = now
                    await container.upsert_item(existing)
                except Exception:
                    # New lead
                    doc = {
                        "id": doc_id,
                        "type": "demo_lead",
                        "userId": "demo",
                        "name": name,
                        "email": email,
                        "questionsUsed": 0,
                        "consentGiven": True,
                        "consentAt": now,
                        "source": origin or "direct",
                        "createdAt": now,
                    }
                    await container.upsert_item(doc)
            logger.info("Demo lead captured: %s (questionsUsed=%d)", email, questions_used)
        except Exception:
            logger.exception("Failed to store demo lead for %s", email)
            # Don't fail the request — storage is best-effort

    # Issue a token seeded with their actual server-side usage count
    token = _issue_demo_token(questions_used=questions_used, email=email)
    return jsonify({
        "ok": True,
        "token": token,
        "questionsUsed": questions_used,
        "questionsRemaining": max(0, DEMO_MAX_QUESTIONS - questions_used),
    })


@demo_bp.post("/demo/token")
async def issue_token():
    """Issue a fresh demo JWT with questionsUsed=0."""
    token = _issue_demo_token(questions_used=0)
    return jsonify({"token": token, "questionsRemaining": DEMO_MAX_QUESTIONS})


@demo_bp.post("/demo/chat")
async def demo_chat():
    """Validate demo token, enforce question limit, stream ARI response."""
    origin = request.headers.get("Origin", "")
    if not _is_origin_allowed(origin):
        logger.warning("Demo chat rejected: unauthorized origin=%s", origin)
        return jsonify({"error": "Forbidden"}), 403

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing demo token"}), 401

    raw_token = auth_header[7:].strip()
    payload = _verify_demo_token(raw_token)
    if payload is None:
        return jsonify({"error": "Invalid or expired demo token"}), 401

    questions_used = int(payload.get("q", 0))
    if questions_used >= DEMO_MAX_QUESTIONS:
        return jsonify({
            "error": "limit_reached",
            "detail": "You've used all 3 demo questions. Sign up for full access!",
        }), 429

    body = await request.get_json(silent=True)
    if not body or not isinstance(body.get("content"), str) or not body["content"].strip():
        return jsonify({"error": "content is required"}), 400

    content = body["content"].strip()
    if len(content) > DEMO_MAX_INPUT_CHARS:
        return jsonify({"error": "Message too long", "detail": f"max {DEMO_MAX_INPUT_CHARS} characters"}), 400

    from middleware.guardrails import check_content, check_prompt_injection

    if check_prompt_injection(content):
        return jsonify({"error": "blocked", "detail": "Message flagged as potential injection attempt"}), 400
    if check_content(content):
        return jsonify({"error": "blocked", "detail": "Message flagged for inappropriate content"}), 400

    new_questions_used = questions_used + 1
    new_token = _issue_demo_token(new_questions_used, email=payload.get("email", ""))
    questions_remaining = DEMO_MAX_QUESTIONS - new_questions_used

    # Best-effort: increment questionsUsed in Cosmos by email (from token sub claim)
    # The token email is stashed in the "email" claim if present
    _email_claim = payload.get("email")
    if _email_claim:
        import asyncio, hashlib as _hl
        async def _increment_cosmos():
            try:
                from cosmos import SessionsCosmosClient
                cosmos = SessionsCosmosClient.get_instance()
                if not cosmos:
                    return
                doc_id = "demo_lead:" + _hl.sha256(_email_claim.encode()).hexdigest()[:16]
                async with cosmos._client() as client:
                    container = await cosmos._container(client)
                    try:
                        doc = await container.read_item(item=doc_id, partition_key="demo")
                        doc["questionsUsed"] = new_questions_used
                        await container.upsert_item(doc)
                    except Exception:
                        pass  # Lead doc may not exist for legacy sessions
            except Exception:
                pass
        asyncio.ensure_future(_increment_cosmos())

    async def generate():
        from app import AZURE_OPENAI_DEPLOYMENT, get_azure_client

        client = get_azure_client()
        messages = [
            {"role": "system", "content": _DEMO_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]
        try:
            response = await client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                stream=True,
                max_completion_tokens=DEMO_MAX_RESPONSE_TOKENS,
            )
            async for chunk in response:
                chunk_payload = chunk.model_dump(exclude_none=True)
                has_text = any(
                    c.get("delta", {}).get("content")
                    for c in chunk_payload.get("choices", [])
                )
                if has_text:
                    yield _sse_json(chunk_payload)
        except Exception as exc:
            logger.exception("Demo streaming error")
            yield _sse_json({"error": {"type": "api_error", "message": str(exc)}})
        finally:
            yield _sse_line("[DONE]")

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Demo-Token": new_token,
            "X-Questions-Remaining": str(questions_remaining),
            # Expose custom headers to the browser (CORS)
            "Access-Control-Expose-Headers": "X-Demo-Token, X-Questions-Remaining",
        },
    )
