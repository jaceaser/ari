"""
Session endpoints: CRUD, messages, and streaming with MCP orchestration.

POST   /sessions                     — create session
GET    /sessions                     — list sessions
GET    /sessions/<id>                — get session detail
POST   /sessions/<id>/seal           — seal session
POST   /sessions/<id>/messages       — send message + stream response
GET    /sessions/<id>/messages       — get all messages (full history for UI replay)
"""

import json
import logging
import time
import uuid

from quart import Response, jsonify, request

from . import sessions_bp

logger = logging.getLogger("api.sessions")


def _sse_line(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_json(payload: dict) -> str:
    return _sse_line(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


# ── Session CRUD ──


@sessions_bp.post("/sessions")
async def create_session():
    """Create a new chat session."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    body = await request.get_json(silent=True) or {}
    title = body.get("title")

    session = await cosmos.create_session(user_id, title=title)
    return jsonify({"id": session["id"], "created_at": session["createdAt"]}), 201


@sessions_bp.get("/sessions")
async def list_sessions():
    """List sessions for the authenticated user."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    sessions = await cosmos.get_sessions(user_id)
    return jsonify([
        {
            "id": s["id"],
            "title": s.get("title"),
            "status": s.get("status", "active"),
            "created_at": s.get("createdAt", ""),
            "sealed_at": s.get("sealedAt"),
        }
        for s in sessions
    ])


@sessions_bp.get("/sessions/<session_id>")
async def get_session(session_id: str):
    """Get session detail."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    session = await cosmos.get_session(user_id, session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": session["id"],
        "title": session.get("title"),
        "status": session.get("status", "active"),
        "created_at": session.get("createdAt", ""),
        "sealed_at": session.get("sealedAt"),
    })


@sessions_bp.post("/sessions/<session_id>/seal")
async def seal_session(session_id: str):
    """Seal a session (no more messages allowed)."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    session = await cosmos.seal_session(user_id, session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": session["id"],
        "status": session["status"],
        "sealed_at": session.get("sealedAt"),
    })


# ── Messages ──


@sessions_bp.get("/sessions/<session_id>/messages")
async def list_messages(session_id: str):
    """Get full message history for a session (UI replay)."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    # Verify session belongs to user
    session = await cosmos.get_session(user_id, session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404

    messages = await cosmos.get_messages(user_id, session_id)
    return jsonify([
        {
            "id": m["id"],
            "role": m.get("role", ""),
            "content": m.get("content", ""),
            "created_at": m.get("createdAt", ""),
        }
        for m in messages
    ])


@sessions_bp.post("/sessions/<session_id>/messages")
async def send_message(session_id: str):
    """
    Send a user message, run MCP orchestration, stream assistant response.

    Persists both user and assistant messages. Detects lead runs from
    MCP tool results and creates lead_run documents.
    """
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    # Verify session exists and is active
    session = await cosmos.get_session(user_id, session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    if session.get("status") == "sealed":
        return jsonify({"error": "Session is sealed"}), 409

    # Parse request body
    body = await request.get_json(silent=True)
    if not body or not isinstance(body.get("content"), str) or not body["content"].strip():
        return jsonify({"error": "Invalid request", "detail": "content is required"}), 400

    content = body["content"].strip()
    if len(content) > 32000:
        return jsonify({"error": "Message too long"}), 400

    # Persist user message
    await cosmos.create_message(user_id, session_id, "user", content)

    # Build context: bounded window of recent messages for LLM
    recent = await cosmos.get_recent_messages(user_id, session_id, limit=40)
    context_messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in recent
    ]

    # Run MCP orchestration + stream response
    async def generate():
        # Lazy imports to avoid circular deps with app.py
        from app import (
            _inject_server_system_prompts,
            _normalize_openai_messages,
            _run_mcp_tool_orchestration,
            _stream_completion_args,
            get_azure_client,
            AZURE_OPENAI_DEPLOYMENT,
            ChatCompletionRequest,
        )

        stream_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        full_response_text = ""
        mcp_tool_results = []

        try:
            normalized = _normalize_openai_messages(context_messages)

            # MCP tool orchestration
            try:
                completion_messages = await _run_mcp_tool_orchestration(normalized)
                # Collect tool results for lead run detection
                for msg in completion_messages:
                    if msg.get("role") == "tool":
                        mcp_tool_results.append(msg)
            except Exception:
                logger.exception("MCP orchestration failed; continuing without tools")
                completion_messages = normalized

            completion_messages = _inject_server_system_prompts(completion_messages)

            # Build a minimal request body for _stream_completion_args
            dummy_request = ChatCompletionRequest(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[],
                stream=True,
                max_tokens=2048,
            )

            client = get_azure_client()
            response = await client.chat.completions.create(
                **_stream_completion_args(dummy_request, completion_messages)
            )

            async for chunk in response:
                payload = chunk.model_dump(exclude_none=True)
                payload.setdefault("id", stream_id)
                payload.setdefault("object", "chat.completion.chunk")
                payload.setdefault("created", created)
                payload.setdefault("model", AZURE_OPENAI_DEPLOYMENT)

                # Accumulate response text
                for choice in payload.get("choices", []):
                    delta = choice.get("delta", {})
                    if "content" in delta and delta["content"]:
                        full_response_text += delta["content"]

                yield _sse_json(payload)

        except Exception as exc:
            logger.exception("Streaming error in session %s", session_id)
            yield _sse_json({"error": {"type": "api_error", "message": str(exc)}})
        finally:
            yield _sse_line("[DONE]")

            # Persist assistant response
            if full_response_text.strip():
                try:
                    await cosmos.create_message(
                        user_id, session_id, "assistant", full_response_text.strip()
                    )
                except Exception:
                    logger.exception("Failed to persist assistant message")

            # Detect and persist lead runs from MCP tool results
            await _detect_and_save_lead_runs(
                cosmos, user_id, session_id, mcp_tool_results
            )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _detect_and_save_lead_runs(
    cosmos, user_id: str, session_id: str, tool_results: list[dict]
) -> None:
    """
    Scan MCP tool results for lead run data and persist once per successful run.

    Looks for tool results from mcp_leads_context that contain result data
    with file URLs and result counts.
    """
    for msg in tool_results:
        content = msg.get("content", "")
        if not content:
            continue

        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue

        # Check if this is a successful tool result with lead data
        if not isinstance(data, dict) or not data.get("ok"):
            continue

        tool_name = data.get("tool", "")
        inner = data.get("data", {})

        if tool_name != "mcp_leads_context":
            continue

        # Look for lead run indicators in the response
        file_url = inner.get("file_url") or inner.get("fileUrl") or ""
        result_count = inner.get("result_count") or inner.get("resultCount") or 0
        if not file_url or not result_count:
            continue

        try:
            await cosmos.create_lead_run(
                user_id=user_id,
                session_id=session_id,
                summary=inner.get("summary", "Lead generation run"),
                location=inner.get("location", ""),
                strategy=inner.get("strategy", ""),
                result_count=int(result_count),
                file_url=file_url,
                filters=inner.get("filters"),
            )
        except Exception:
            logger.exception("Failed to persist lead run")
