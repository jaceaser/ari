"""
Session endpoints: CRUD, messages, and streaming with MCP orchestration.

POST   /sessions                     — create session
GET    /sessions                     — list sessions
GET    /sessions/<id>                — get session detail
POST   /sessions/<id>/messages       — send message + stream response
GET    /sessions/<id>/messages       — get all messages (full history for UI replay)
"""

import asyncio
import json
import logging
import re
import time
import uuid

from quart import Response, jsonify, request

from . import sessions_bp

import httpx

logger = logging.getLogger("api.sessions")


async def _extract_document_texts(documents: list[dict]) -> list[str]:
    """Download document files and extract their text content."""
    results: list[str] = []
    for doc in documents:
        url = doc.get("url", "")
        media_type = doc.get("mediaType", "")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content

            if "pdf" in media_type:
                try:
                    import fitz  # PyMuPDF
                    pdf = fitz.open(stream=data, filetype="pdf")
                    text = "\n".join(page.get_text() for page in pdf)
                    pdf.close()
                    if text.strip():
                        results.append(text.strip()[:50000])
                except ImportError:
                    logger.warning("PyMuPDF not installed; cannot extract PDF text")
            elif "word" in media_type or "msword" in media_type:
                try:
                    import io
                    from docx import Document
                    doc_file = Document(io.BytesIO(data))
                    text = "\n".join(p.text for p in doc_file.paragraphs)
                    if text.strip():
                        results.append(text.strip()[:50000])
                except ImportError:
                    logger.warning("python-docx not installed; cannot extract Word text")
        except Exception as exc:
            logger.error("Failed to extract text from document %s: %s", url, exc)
    return results


# Fake document URL patterns the model generates instead of using tools
_FAKE_DOC_URL_RE = re.compile(
    r'\[([^\]]*)\]\(((?:sandbox:|https?://files\.openaiusercontent\.com|https?://(?:cdn\.)?openai\.com)[^\)]*\.docx?)\)',
    re.IGNORECASE,
)


async def _maybe_auto_generate_docx(response_text: str) -> str | None:
    """
    If the model's response contains fake document download links (sandbox:/, openaiusercontent.com),
    extract the document content, generate a real DOCX via Azure Blob, and return a markdown
    snippet with the real download link to append to the response.
    """
    logger.info("Auto DOCX check: response length=%d", len(response_text) if response_text else 0)

    if not response_text:
        logger.info("Auto DOCX: empty response, skipping")
        return None

    match = _FAKE_DOC_URL_RE.search(response_text)
    if not match:
        # Also check for bare fake URLs (not in markdown links)
        bare_fake = re.search(
            r'https?://files\.openaiusercontent\.com/[^\s\)]+\.docx?',
            response_text, re.IGNORECASE,
        )
        if not bare_fake:
            logger.info("Auto DOCX: no fake URL found, skipping")
            return None
        # Use bare URL match as a fallback
        logger.info("Auto DOCX: found bare fake URL: %s", bare_fake.group(0))
        title = "Document"
    else:
        title = match.group(1) or "Document"
        logger.info("Auto DOCX: found fake markdown link, title=%s", title)

    try:
        from app import _handle_generate_document

        # Use the full response as document content — strip commentary sections
        content = response_text
        for marker in ["### What's", "### How", "### File Details", "---\n\n###",
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


# Strict UUID v4/v5 format: 8-4-4-4-12 hex characters
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_MAX_TITLE_LEN = 200


def _sse_line(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_json(payload: dict) -> str:
    return _sse_line(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _is_valid_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _validate_path_session_id(session_id: str):
    """Return an error response tuple if session_id is not a valid UUID, else None."""
    if not _is_valid_uuid(session_id):
        return jsonify({"error": "Invalid session ID format"}), 400
    return None


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
    client_id = body.get("id")

    # Validate client-provided session ID format
    if client_id is not None:
        if not isinstance(client_id, str) or not _is_valid_uuid(client_id):
            return jsonify({"error": "Invalid session ID format", "detail": "id must be a valid UUID"}), 400

    # Validate title length
    if title is not None:
        if not isinstance(title, str) or len(title) > _MAX_TITLE_LEN:
            return jsonify({"error": "Title too long", "detail": f"max {_MAX_TITLE_LEN} characters"}), 400

    from cosmos import SessionConflictError

    try:
        session = await cosmos.create_session(user_id, title=title, session_id=client_id)
    except SessionConflictError:
        return jsonify({"error": "Session ID already exists"}), 409

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
            "userId": s.get("userId", user_id),
            "title": s.get("title"),
            "status": s.get("status", "active"),
            "created_at": s.get("createdAt", ""),
        }
        for s in sessions
    ])


@sessions_bp.get("/sessions/<session_id>")
async def get_session(session_id: str):
    """Get session detail."""
    err = _validate_path_session_id(session_id)
    if err:
        return err

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
        "userId": session.get("userId", user_id),
        "title": session.get("title"),
        "status": session.get("status", "active"),
        "created_at": session.get("createdAt", ""),
    })


@sessions_bp.delete("/sessions/<session_id>")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    err = _validate_path_session_id(session_id)
    if err:
        return err

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

    await cosmos.delete_session(user_id, session_id)
    return jsonify({"id": session_id, "deleted": True}), 200


@sessions_bp.patch("/sessions/<session_id>")
async def update_session(session_id: str):
    """Update session metadata (currently: title only)."""
    err = _validate_path_session_id(session_id)
    if err:
        return err

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

    body = await request.get_json(silent=True) or {}
    title = body.get("title")
    if title is not None:
        if not isinstance(title, str) or len(title) > _MAX_TITLE_LEN:
            return jsonify({"error": "Title too long", "detail": f"max {_MAX_TITLE_LEN} characters"}), 400
        session["title"] = title.strip() or None

    updated = await cosmos.update_session(user_id, session)
    return jsonify({
        "id": updated["id"],
        "title": updated.get("title"),
        "status": updated.get("status", "active"),
    })


# ── Messages ──


@sessions_bp.get("/sessions/<session_id>/messages")
async def list_messages(session_id: str):
    """Get full message history for a session (UI replay)."""
    err = _validate_path_session_id(session_id)
    if err:
        return err

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
    err = _validate_path_session_id(session_id)
    if err:
        return err

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
    # Parse request body
    body = await request.get_json(silent=True)
    if not body or not isinstance(body.get("content"), str) or not body["content"].strip():
        return jsonify({"error": "Invalid request", "detail": "content is required"}), 400

    content = body["content"].strip()
    if len(content) > 32000:
        return jsonify({"error": "Message too long"}), 400

    # Guardrails — check user message before processing
    from middleware.guardrails import check_prompt_injection, check_content, check_off_topic

    injection = check_prompt_injection(content)
    if injection:
        return jsonify({"error": "blocked", "detail": injection}), 400

    moderation = check_content(content)
    if moderation:
        return jsonify({"error": "blocked", "detail": moderation}), 400

    offtopic = check_off_topic(content)
    if offtopic:
        return jsonify({"error": "off_topic", "detail": offtopic}), 422

    # Extract optional image URLs (uploaded to Azure Blob by the frontend)
    raw_images = body.get("images") or []
    images: list[str] = [
        url for url in raw_images[:5]
        if isinstance(url, str) and url.startswith("https://")
    ]

    # Extract optional document attachments (PDFs, Word docs)
    raw_docs = body.get("documents") or []
    documents: list[dict] = [
        doc for doc in raw_docs[:3]
        if isinstance(doc, dict) and isinstance(doc.get("url"), str) and doc["url"].startswith("https://")
    ]

    # Extract text from uploaded documents and prepend to user content
    doc_text_parts: list[str] = []
    if documents:
        doc_text_parts = await _extract_document_texts(documents)

    effective_content = content
    if doc_text_parts:
        doc_context = "\n\n".join(doc_text_parts)
        effective_content = f"{content}\n\n---\nAttached document content:\n{doc_context}"

    # Persist user message (text only — images are referenced by URL)
    await cosmos.create_message(user_id, session_id, "user", content)

    # Auto-generate title from first message if session has none
    if not session.get("title"):
        raw = content.strip().replace("\n", " ")
        auto_title = raw[:60].rsplit(" ", 1)[0] if len(raw) > 60 else raw
        try:
            session["title"] = auto_title
            await cosmos.update_session(user_id, session)
        except Exception:
            pass  # Non-fatal — title stays blank

    # Build context: bounded window of recent messages for LLM
    recent = await cosmos.get_recent_messages(user_id, session_id, limit=60)
    context_messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in recent
    ]

    # For the current user message, build multimodal content if files are present
    if (images or doc_text_parts) and context_messages and context_messages[-1].get("role") == "user":
        vision_content: list[dict] = [{"type": "text", "text": effective_content}]
        for img_url in images:
            vision_content.append({
                "type": "image_url",
                "image_url": {"url": img_url, "detail": "auto"},
            })
        context_messages[-1]["content"] = vision_content
    elif doc_text_parts and context_messages and context_messages[-1].get("role") == "user":
        # Documents only (no images) — just inject the extracted text
        context_messages[-1]["content"] = effective_content

    # Run MCP orchestration + stream response
    async def generate():
        # Lazy imports to avoid circular deps with app.py
        from app import (
            _inject_server_system_prompts,
            _normalize_openai_messages,
            _run_mcp_tool_orchestration,
            _stream_completion_args,
            _handle_generate_document,
            _parse_tool_arguments,
            _auto_generate_docx_if_needed,
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
                completion_messages = await _run_mcp_tool_orchestration(normalized, user_id=user_id)
                # Collect tool results for lead run detection
                for msg in completion_messages:
                    if msg.get("role") == "tool":
                        mcp_tool_results.append(msg)
            except Exception:
                logger.exception("MCP orchestration failed; continuing without tools")
                completion_messages = normalized

            completion_messages = _inject_server_system_prompts(completion_messages)

            from app import _truncate_to_token_budget
            completion_messages = _truncate_to_token_budget(completion_messages)

            # Build a minimal request body for _stream_completion_args
            dummy_request = ChatCompletionRequest(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[],
                stream=True,
                max_tokens=128000,
                temperature=0.3,
            )

            client = get_azure_client()

            # Stream with up to 2 rounds of tool calls (generate_document)
            for _round in range(2):
                response = await client.chat.completions.create(
                    **_stream_completion_args(dummy_request, completion_messages,
                                              include_doc_tool=(_round == 0))
                )

                round_text = ""
                tool_call_id = None
                tool_name = None
                tool_args_str = ""
                last_chunk_time = time.time()
                finish_reason: str | None = None

                async for chunk in response:
                    # Send SSE keepalive comment if no text has been forwarded
                    # for >15 s (prevents Azure App Service idle-connection close).
                    now = time.time()
                    if now - last_chunk_time > 15:
                        yield ": keepalive\n\n"
                        last_chunk_time = now
                    payload = chunk.model_dump(exclude_none=True)
                    payload.setdefault("id", stream_id)
                    payload.setdefault("object", "chat.completion.chunk")
                    payload.setdefault("created", created)
                    payload.setdefault("model", AZURE_OPENAI_DEPLOYMENT)

                    for choice in payload.get("choices", []):
                        delta = choice.get("delta", {})

                        # Capture finish_reason from any choice
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]

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

                    # Only forward text-content chunks to the client
                    has_text = any(
                        c.get("delta", {}).get("content")
                        for c in payload.get("choices", [])
                    )
                    if has_text:
                        yield _sse_json(payload)
                        last_chunk_time = time.time()

                # Detect token-limit truncation and surface it to the user
                if finish_reason == "length":
                    logger.warning(
                        "Response truncated by token limit in session %s "
                        "(finish_reason=length, response_chars=%d)",
                        session_id,
                        len(full_response_text),
                    )
                    notice = (
                        "\n\n---\n*Response was cut off because it reached the length limit. "
                        "Try asking a more specific question or breaking your request into smaller parts.*"
                    )
                    notice_chunk = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": AZURE_OPENAI_DEPLOYMENT,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": notice},
                            "finish_reason": None,
                        }],
                    }
                    yield _sse_json(notice_chunk)
                    full_response_text += notice

                # If model called generate_document, execute it and loop
                if tool_name == "generate_document" and tool_call_id:
                    logger.info("Model called generate_document tool during streaming")
                    tool_args = _parse_tool_arguments(tool_args_str)
                    tool_result = await _handle_generate_document(tool_args)

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
                        "model": AZURE_OPENAI_DEPLOYMENT,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": docx_extra},
                            "finish_reason": None,
                        }],
                    }
                    yield _sse_json(extra_chunk)
                    full_response_text += docx_extra
            except Exception:
                logger.exception("Auto DOCX fallback failed")

        except Exception as exc:
            logger.exception("Streaming error in session %s", session_id)
            yield _sse_json({"error": {"type": "api_error", "message": str(exc)}})
        finally:
            yield _sse_line("[DONE]")

            # Persist assistant response + detect lead runs in the background
            # so the SSE stream closes immediately after [DONE].
            async def _persist():
                if full_response_text.strip():
                    try:
                        await cosmos.create_message(
                            user_id, session_id, "assistant", full_response_text.strip()
                        )
                    except Exception:
                        logger.exception("Failed to persist assistant message")
                await _detect_and_save_lead_runs(
                    cosmos, user_id, session_id, mcp_tool_results
                )

            asyncio.ensure_future(_persist())

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
        # MCP tool returns {"ok": True, "tool": "leads", "result": {...}}
        inner = data.get("result", data.get("data", {}))

        if tool_name not in ("leads", "mcp_leads_context"):
            continue

        # Look for lead run indicators in the response
        excel_link = inner.get("excel_link") or inner.get("file_url") or inner.get("fileUrl") or ""
        result_count = (
            inner.get("properties_count")
            or inner.get("result_count")
            or inner.get("resultCount")
            or 0
        )
        if not excel_link or not result_count:
            continue

        city = inner.get("_city") or inner.get("city") or ""
        state = inner.get("_state") or inner.get("state") or ""
        location = f"{city}, {state}".strip(", ") if (city or state) else inner.get("location", "")
        source_url = inner.get("_source_url") or ""

        try:
            await cosmos.create_lead_run(
                user_id=user_id,
                session_id=session_id,
                summary=inner.get("summary", "Lead generation run"),
                location=location,
                strategy=inner.get("_lead_type") or inner.get("strategy", ""),
                result_count=int(result_count),
                file_url=excel_link,
                filters=inner.get("filters"),
                source_url=source_url,
            )
        except Exception:
            logger.exception("Failed to persist lead run")
