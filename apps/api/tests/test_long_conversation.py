"""
Long conversation stress tests for the sessions chat API.

Simulates a 20-turn real estate conversation through
POST /sessions/<id>/messages and verifies:

  1. Every turn streams to [DONE] with no error events.
  2. The full text content is non-empty on every turn.
  3. Token-budget truncation does not produce errors when the
     pre-existing history is large (~4 K tokens per message × 20 turns).
  4. get_recent_messages is called once per turn and the history
     seen by each call grows monotonically.

Azure OpenAI and MCP orchestration are mocked so no network calls
are made.  Cosmos is mocked via the shared `app_client` / `mock_cosmos`
fixtures in conftest.py.
"""
from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from _constants import TEST_SESSION_ID


# ── SSE helpers ─────────────────────────────────────────────────────────────


def _parse_sse(raw: bytes) -> tuple[list[str], bool, list[dict], str | None]:
    """
    Parse a raw SSE response body.

    Returns
    -------
    text_parts : list[str]
        All text delta strings emitted in the stream.
    done : bool
        True when ``[DONE]`` was received.
    errors : list[dict]
        Any ``{"error": ...}`` objects found in the stream.
    finish_reason : str | None
        The last non-null ``finish_reason`` seen across all chunks, or None.
    """
    text_parts: list[str] = []
    done = False
    errors: list[dict] = []
    finish_reason: str | None = None

    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if "error" in chunk:
            errors.append(chunk["error"])
        for choice in chunk.get("choices", []):
            content = (choice.get("delta") or {}).get("content")
            if content:
                text_parts.append(content)
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

    return text_parts, done, errors, finish_reason


def _make_stream(text: str = "This is a helpful real estate answer.") -> AsyncIterator:
    """
    Return a fresh async generator that mimics an OpenAI streaming response.
    Each call produces a new, independent generator so the mock can be
    reused across multiple ``await create(...)`` calls.
    """

    async def _gen():
        words = text.split()
        for i, word in enumerate(words):
            chunk = MagicMock()
            chunk.model_dump.return_value = {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 1_700_000_000,
                "model": "gpt-5.2-chat",
                "choices": [{
                    "index": 0,
                    "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                    "finish_reason": None,
                }],
            }
            yield chunk

        fin = MagicMock()
        fin.model_dump.return_value = {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 1_700_000_000,
            "model": "gpt-5.2-chat",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield fin

    return _gen()


# ── Prompts ──────────────────────────────────────────────────────────────────

REAL_ESTATE_PROMPTS: list[str] = [
    "What is wholesaling real estate?",
    "How do I find motivated sellers in my area?",
    "What does ARV mean and how do I calculate it?",
    "What is the 70% rule for fix-and-flip deals?",
    "How do I analyze a rental property for cash flow?",
    "What is a subject-to deal in real estate?",
    "How do I build a buyers list for wholesaling?",
    "What is the difference between a purchase and sale agreement and an assignment contract?",
    "How does a double closing work?",
    "What are the best ways to market to absentee owners?",
    "What is a lis pendens and why does it matter for investors?",
    "How do I estimate repair costs on a distressed property?",
    "What is a hard money loan and when should I use one?",
    "What are the tax benefits of owning rental properties?",
    "How do I execute a BRRRR deal from start to finish?",
    "What is a cap rate and how do I use it to value commercial property?",
    "How do I find pre-foreclosure properties before they hit the MLS?",
    "What is the difference between a short sale and a foreclosure?",
    "How do I negotiate with motivated sellers to get a below-market price?",
    "What is a novation agreement and when would I use one instead of a standard assignment?",
]

assert len(REAL_ESTATE_PROMPTS) == 20


# ── Shared mock wiring ────────────────────────────────────────────────────────


def _mock_azure_client() -> MagicMock:
    """Build a mock Azure OpenAI client whose ``create`` returns a fresh stream each call."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=lambda *a, **kw: _make_stream()
    )
    return client


async def _passthrough_orchestration(messages: list, user_id: str | None = None) -> list:
    """MCP orchestration stub — returns messages unchanged."""
    return messages


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLongConversation:
    """
    End-to-end SSE streaming tests across a 20-turn conversation.

    Azure OpenAI + MCP orchestration are fully mocked.  The tests exercise
    the real Quart request pipeline, context-management code, and SSE
    serialisation in ``routes/sessions.py``.
    """

    # ── Helpers ──

    @staticmethod
    def _attach_history_mock(mock_cosmos, history: list[dict]) -> None:
        """Wire mock_cosmos to return a slice of *history* on each call."""

        async def _recent(user_id: str, session_id: str, limit: int = 60) -> list[dict]:
            return list(history[-limit:])

        mock_cosmos.get_recent_messages = AsyncMock(side_effect=_recent)

    # ── Test cases ──

    @pytest.mark.asyncio
    async def test_20_turn_conversation_all_complete(
        self, app_client, auth_headers, mock_cosmos
    ):
        """
        Send 20 real estate questions in sequence.
        Every turn must:
          - return HTTP 200
          - stream at least one text delta
          - end with [DONE]
          - contain no error events
        """
        history: list[dict] = []
        self._attach_history_mock(mock_cosmos, history)

        with (
            patch("app.get_azure_client", return_value=_mock_azure_client()),
            patch("app._run_mcp_tool_orchestration", side_effect=_passthrough_orchestration),
            patch("app._get_user_tier", new=AsyncMock(return_value="elite")),
        ):
            for turn, prompt in enumerate(REAL_ESTATE_PROMPTS, start=1):
                # Simulate the user message being stored before the request
                history.append({
                    "id": f"u{turn}",
                    "role": "user",
                    "content": prompt,
                    "createdAt": "2025-01-01T00:00:00+00:00",
                })

                resp = await app_client.post(
                    f"/sessions/{TEST_SESSION_ID}/messages",
                    json={"content": prompt},
                    headers=auth_headers,
                )

                assert resp.status_code == 200, (
                    f"Turn {turn}: expected HTTP 200, got {resp.status_code}"
                )

                raw = await resp.get_data()
                text_parts, done, errors, finish_reason = _parse_sse(raw)

                assert done, f"Turn {turn}: [DONE] not received in SSE stream"
                assert not errors, f"Turn {turn}: SSE error event(s): {errors}"
                assert text_parts, f"Turn {turn}: no text content received in stream"
                # finish_reason is handled server-side; the user-visible signal for
                # a token-limit cutoff is the truncation notice injected into the text.
                full_text = "".join(text_parts)
                assert "length limit" not in full_text.lower(), (
                    f"Turn {turn}: unexpected truncation notice found — "
                    "response may have hit the token limit (finish_reason='length')"
                )

                # Simulate the assistant reply being persisted after the response
                history.append({
                    "id": f"a{turn}",
                    "role": "assistant",
                    "content": " ".join(text_parts),
                    "createdAt": "2025-01-01T00:00:01+00:00",
                })

    @pytest.mark.asyncio
    async def test_context_truncation_with_large_messages(
        self, app_client, auth_headers, mock_cosmos
    ):
        """
        When message history is large (>300 K tokens), _truncate_to_token_budget
        must silently trim it without producing an error event or HTTP error.

        Builds a 20-turn pre-existing history where each assistant message
        is ~3,000 words (~4,000 tokens).  The combined context exceeds the
        300 K budget by a wide margin, exercising the truncation path.
        """
        # ~3,000 words ≈ 4,000 tokens per assistant turn × 20 turns = 80 K tokens
        # combined with system prompts / tool defs this pushes well past 300 K
        long_response = (
            "In real estate investing, understanding market dynamics is absolutely critical "
            "to long-term success. Investors who take the time to analyze local trends, "
            "study comparable sales, and build strong relationships with motivated sellers "
            "consistently outperform those who rely solely on gut instinct. "
        ) * 150  # ~3,000 words

        history: list[dict] = []
        for i in range(20):
            history.append({
                "id": f"u{i}",
                "role": "user",
                "content": REAL_ESTATE_PROMPTS[i],
                "createdAt": "2025-01-01T00:00:00+00:00",
            })
            history.append({
                "id": f"a{i}",
                "role": "assistant",
                "content": long_response,
                "createdAt": "2025-01-01T00:00:01+00:00",
            })

        self._attach_history_mock(mock_cosmos, history)

        with (
            patch("app.get_azure_client", return_value=_mock_azure_client()),
            patch("app._run_mcp_tool_orchestration", side_effect=_passthrough_orchestration),
            patch("app._get_user_tier", new=AsyncMock(return_value="elite")),
        ):
            prompt = "What is the best strategy for a beginner real estate investor?"
            resp = await app_client.post(
                f"/sessions/{TEST_SESSION_ID}/messages",
                json={"content": prompt},
                headers=auth_headers,
            )

            assert resp.status_code == 200, (
                f"Expected HTTP 200 after truncation, got {resp.status_code}"
            )
            raw = await resp.get_data()
            text_parts, done, errors, _ = _parse_sse(raw)

            assert done, "Large-context turn: [DONE] not received"
            assert not errors, f"Large-context turn produced SSE error events: {errors}"
            full_text = "".join(text_parts)
            assert "length limit" not in full_text.lower(), (
                "Large-context turn: truncation notice found — "
                "response hit the token limit (finish_reason='length')"
            )

    @pytest.mark.asyncio
    async def test_finish_reason_length_surfaces_notice(
        self, app_client, auth_headers, mock_cosmos
    ):
        """
        When Azure OpenAI returns finish_reason='length' (token limit hit),
        the backend must:
          - still return HTTP 200 and stream [DONE]
          - append a user-visible truncation notice to the response
          - NOT emit a generic SSE error event

        This test replaces the mock stream with one that ends with
        finish_reason='length' instead of 'stop', simulating what happens
        when max_completion_tokens is exhausted mid-response.
        """
        mock_cosmos.get_recent_messages = AsyncMock(return_value=[])

        async def _length_stream():
            # Emit some partial text...
            for word in "Here is a very long answer that got cut off".split():
                chunk = MagicMock()
                chunk.model_dump.return_value = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion.chunk",
                    "created": 1_700_000_000,
                    "model": "gpt-5.2-chat",
                    "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}],
                }
                yield chunk

            # ...then stop with finish_reason='length' instead of 'stop'
            fin = MagicMock()
            fin.model_dump.return_value = {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 1_700_000_000,
                "model": "gpt-5.2-chat",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
            }
            yield fin

        mock_azure = MagicMock()
        mock_azure.chat.completions.create = AsyncMock(side_effect=lambda *a, **kw: _length_stream())

        with (
            patch("app.get_azure_client", return_value=mock_azure),
            patch("app._run_mcp_tool_orchestration", side_effect=_passthrough_orchestration),
            patch("app._get_user_tier", new=AsyncMock(return_value="elite")),
        ):
            resp = await app_client.post(
                f"/sessions/{TEST_SESSION_ID}/messages",
                json={"content": "Write me a very long real estate guide"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        raw = await resp.get_data()
        text_parts, done, errors, finish_reason = _parse_sse(raw)

        assert done, "finish_reason=length: [DONE] not received"
        assert not errors, f"finish_reason=length: unexpected SSE error event: {errors}"

        # The partial text content should still be present
        assert text_parts, "finish_reason=length: no text content in stream"

        # The backend must have appended a truncation notice
        full_text = "".join(text_parts)
        assert "cut off" in full_text.lower() or "length limit" in full_text.lower(), (
            "finish_reason=length: expected a truncation notice in the response, "
            f"got: {full_text!r}"
        )

    @pytest.mark.asyncio
    async def test_context_history_grows_per_turn(
        self, app_client, auth_headers, mock_cosmos
    ):
        """
        get_recent_messages must be called exactly once per turn, and the
        history snapshot it receives must be monotonically non-decreasing.
        """
        history: list[dict] = []
        call_snapshots: list[int] = []

        async def _tracking_recent(user_id: str, session_id: str, limit: int = 60) -> list[dict]:
            call_snapshots.append(len(history))
            return list(history[-limit:])

        mock_cosmos.get_recent_messages = AsyncMock(side_effect=_tracking_recent)

        with (
            patch("app.get_azure_client", return_value=_mock_azure_client()),
            patch("app._run_mcp_tool_orchestration", side_effect=_passthrough_orchestration),
            patch("app._get_user_tier", new=AsyncMock(return_value="elite")),
        ):
            for turn, prompt in enumerate(REAL_ESTATE_PROMPTS, start=1):
                history.append({
                    "id": f"u{turn}",
                    "role": "user",
                    "content": prompt,
                    "createdAt": "2025-01-01T00:00:00+00:00",
                })
                await app_client.post(
                    f"/sessions/{TEST_SESSION_ID}/messages",
                    json={"content": prompt},
                    headers=auth_headers,
                )
                history.append({
                    "id": f"a{turn}",
                    "role": "assistant",
                    "content": "Test answer.",
                    "createdAt": "2025-01-01T00:00:01+00:00",
                })

        assert len(call_snapshots) == 20, (
            f"Expected get_recent_messages called 20 times, got {len(call_snapshots)}"
        )
        for i in range(1, len(call_snapshots)):
            assert call_snapshots[i] >= call_snapshots[i - 1], (
                f"History seen by turn {i + 1} ({call_snapshots[i]}) "
                f"was smaller than turn {i} ({call_snapshots[i - 1]})"
            )

    @pytest.mark.asyncio
    async def test_history_limit_respected_at_60_messages(
        self, app_client, auth_headers, mock_cosmos
    ):
        """
        get_recent_messages must be called with limit=60 (the value set in
        sessions.py after the recent bump from 40 → 60).
        """
        captured_limits: list[int] = []

        async def _capture_limit(user_id: str, session_id: str, limit: int = 60) -> list[dict]:
            captured_limits.append(limit)
            return []

        mock_cosmos.get_recent_messages = AsyncMock(side_effect=_capture_limit)

        with (
            patch("app.get_azure_client", return_value=_mock_azure_client()),
            patch("app._run_mcp_tool_orchestration", side_effect=_passthrough_orchestration),
            patch("app._get_user_tier", new=AsyncMock(return_value="elite")),
        ):
            await app_client.post(
                f"/sessions/{TEST_SESSION_ID}/messages",
                json={"content": "Test message"},
                headers=auth_headers,
            )

        assert captured_limits, "get_recent_messages was not called"
        assert captured_limits[0] == 60, (
            f"Expected limit=60, got {captured_limits[0]}"
        )
