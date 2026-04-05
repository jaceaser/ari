"""
Phase 1C tests — core metering service.

All tests mock the database layer (get_db_session) so no live DB is needed.
Covers:
  - start_event: happy path, DB failure isolation, missing URL
  - complete_event: happy path, cost calculation, idempotency guard, None no-op
  - fail_event: happy path, error metadata, None no-op
  - track() context manager: clean exit, exception path, re-raise guarantee
  - Failure isolation: DB errors in metering must never crash the caller
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_mock_session(event=None):
    """Return a mock async session context manager that yields a session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # .execute() returns a result whose .scalar_one_or_none() returns `event`
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=event)
    session.execute = AsyncMock(return_value=execute_result)

    # Make the session work as an async context manager
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


def _patch_db(event=None):
    """Patch get_db_session to return a mock session holding `event`."""
    cm, session = _make_mock_session(event)
    return patch("billing.database.get_db_session", return_value=cm), session


# ── start_event ────────────────────────────────────────────────────────────────


class TestStartEvent:
    @pytest.mark.asyncio
    async def test_returns_uuid_on_success(self):
        p, session = _patch_db()
        with p:
            from billing.metering_service import start_event
            result = await start_event("user-1", "chat", "gpt-5.2-chat")
        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    async def test_adds_event_to_session(self):
        p, session = _patch_db()
        with p:
            from billing.metering_service import start_event
            await start_event("user-1", "chat", "gpt-5.2-chat", session_id="sess-1")
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.user_id == "user-1"
        assert added.action_type == "chat"
        assert added.action_name == "gpt-5.2-chat"
        assert added.session_id == "sess-1"
        assert added.status == "started"

    @pytest.mark.asyncio
    async def test_passes_execution_id(self):
        p, session = _patch_db()
        with p:
            from billing.metering_service import start_event
            await start_event("u", "tool", "mcp_leads_context", execution_id="exec-42")
        added = session.add.call_args[0][0]
        assert added.execution_id == "exec-42"

    @pytest.mark.asyncio
    async def test_passes_metadata(self):
        p, session = _patch_db()
        with p:
            from billing.metering_service import start_event
            await start_event("u", "chat", "gpt-5.2-chat", metadata={"round": 1})
        added = session.add.call_args[0][0]
        assert added.metadata_json == {"round": 1}

    @pytest.mark.asyncio
    async def test_returns_none_on_db_failure(self):
        """DB errors must not propagate — start_event returns None."""
        with patch("billing.database.get_db_session", side_effect=RuntimeError("no db")):
            from billing.metering_service import start_event
            result = await start_event("u", "chat", "gpt-5.2-chat")
        assert result is None

    @pytest.mark.asyncio
    async def test_logs_error_on_db_failure(self, caplog):
        import logging
        with patch("billing.database.get_db_session", side_effect=RuntimeError("conn refused")):
            from billing.metering_service import start_event
            with caplog.at_level(logging.ERROR, logger="ari.billing.metering"):
                await start_event("u", "chat", "gpt-5.2-chat")
        assert "start_event failed" in caplog.text


# ── complete_event ─────────────────────────────────────────────────────────────


class TestCompleteEvent:
    def _make_started_event(self, event_id=None):
        from billing.models import UsageEvent
        e = MagicMock(spec=UsageEvent)
        e.id = event_id or uuid.uuid4()
        e.status = "started"
        e.metadata_json = {}
        return e

    @pytest.mark.asyncio
    async def test_none_event_id_is_noop(self):
        """complete_event(None, ...) must not touch the DB at all."""
        with patch("billing.database.get_db_session") as mock_db:
            from billing.metering_service import complete_event
            await complete_event(None, model_name="gpt-5.2-chat", input_tokens=100, output_tokens=50)
        mock_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_status_completed(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, model_name="gpt-5.2-chat", input_tokens=1000, output_tokens=500)
        assert event.status == "completed"

    @pytest.mark.asyncio
    async def test_sets_token_counts(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, input_tokens=200, output_tokens=100, model_name="gpt-5.2-chat")
        assert event.input_tokens == 200
        assert event.output_tokens == 100
        assert event.model_name == "gpt-5.2-chat"

    @pytest.mark.asyncio
    async def test_computes_token_cost(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, model_name="gpt-5.2-chat", input_tokens=1000, output_tokens=1000)
        assert event.token_cost_estimate is not None
        assert event.token_cost_estimate > 0

    @pytest.mark.asyncio
    async def test_computes_tool_cost(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, tool_name="mcp_leads_context")
        assert event.tool_cost_estimate == float(Decimal("0.100000"))

    @pytest.mark.asyncio
    async def test_total_cost_is_sum(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(
                event.id,
                model_name="gpt-5.2-chat",
                input_tokens=1000,
                output_tokens=1000,
                tool_name="mcp_leads_context",
            )
        expected_token = float(Decimal("0.005000") + Decimal("0.015000"))  # 1k+1k at gpt-5.2-chat rates
        expected_tool = float(Decimal("0.100000"))
        assert abs(event.total_cost_estimate - (expected_token + expected_tool)) < 0.000001

    @pytest.mark.asyncio
    async def test_idempotency_guard_skips_already_completed(self):
        """Calling complete_event on an already-completed event must be a no-op."""
        event = self._make_started_event()
        event.status = "completed"
        event.input_tokens = 999  # sentinel — must not be overwritten

        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, input_tokens=1, output_tokens=1, model_name="gpt-5.2-chat")

        assert event.input_tokens == 999  # unchanged

    @pytest.mark.asyncio
    async def test_idempotency_guard_logs_info(self, caplog):
        import logging
        event = self._make_started_event()
        event.status = "completed"
        p, _ = _patch_db(event=event)
        with p, caplog.at_level(logging.INFO, logger="ari.billing.metering"):
            from billing.metering_service import complete_event
            await complete_event(event.id)
        assert "idempotency" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_missing_event_logs_warning(self, caplog):
        import logging
        p, _ = _patch_db(event=None)  # DB returns no row
        with p, caplog.at_level(logging.WARNING, logger="ari.billing.metering"):
            from billing.metering_service import complete_event
            await complete_event(uuid.uuid4())
        assert "not found" in caplog.text

    @pytest.mark.asyncio
    async def test_merges_metadata(self):
        event = self._make_started_event()
        event.metadata_json = {"existing": "value"}
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import complete_event
            await complete_event(event.id, metadata={"new_key": "new_value"})
        assert event.metadata_json["existing"] == "value"
        assert event.metadata_json["new_key"] == "new_value"

    @pytest.mark.asyncio
    async def test_db_failure_does_not_propagate(self):
        """DB errors in complete_event must never crash the caller."""
        with patch("billing.database.get_db_session", side_effect=RuntimeError("db down")):
            from billing.metering_service import complete_event
            # Must not raise
            await complete_event(uuid.uuid4(), model_name="gpt-5.2-chat")


# ── fail_event ─────────────────────────────────────────────────────────────────


class TestFailEvent:
    def _make_started_event(self):
        from billing.models import UsageEvent
        e = MagicMock(spec=UsageEvent)
        e.id = uuid.uuid4()
        e.status = "started"
        e.metadata_json = {}
        return e

    @pytest.mark.asyncio
    async def test_none_event_id_is_noop(self):
        with patch("billing.database.get_db_session") as mock_db:
            from billing.metering_service import fail_event
            await fail_event(None, error="something went wrong")
        mock_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_status_failed(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import fail_event
            await fail_event(event.id, error="timeout")
        assert event.status == "failed"

    @pytest.mark.asyncio
    async def test_stores_error_in_metadata(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import fail_event
            await fail_event(event.id, error="connection reset")
        assert event.metadata_json.get("error") == "connection reset"

    @pytest.mark.asyncio
    async def test_sets_duration(self):
        event = self._make_started_event()
        p, _ = _patch_db(event=event)
        with p:
            from billing.metering_service import fail_event
            await fail_event(event.id, duration_ms=1234)
        assert event.duration_ms == 1234

    @pytest.mark.asyncio
    async def test_db_failure_does_not_propagate(self):
        with patch("billing.database.get_db_session", side_effect=RuntimeError("db down")):
            from billing.metering_service import fail_event
            await fail_event(uuid.uuid4(), error="original error")
            # Must not raise


# ── track() context manager ────────────────────────────────────────────────────


class TestTrackContextManager:
    @pytest.mark.asyncio
    async def test_clean_exit_calls_complete(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock) as mock_complete, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock) as mock_fail:

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            async with track("u", "chat", "gpt-5.2-chat"):
                pass

        mock_complete.assert_awaited_once()
        mock_fail.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exception_calls_fail_and_reraises(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock) as mock_complete, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock) as mock_fail:

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            with pytest.raises(ValueError, match="downstream error"):
                async with track("u", "tool", "mcp_leads_context"):
                    raise ValueError("downstream error")

        mock_fail.assert_awaited_once()
        mock_complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exception_is_always_reraised(self):
        """Metering must NEVER swallow exceptions from the primary call path."""
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock):

            mock_start.return_value = None  # simulate metering unavailable

            from billing.metering_service import track
            with pytest.raises(RuntimeError, match="critical error"):
                async with track("u", "chat", "gpt-5.2-chat"):
                    raise RuntimeError("critical error")

    @pytest.mark.asyncio
    async def test_record_tokens_forwarded_to_complete(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock) as mock_complete, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock):

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            async with track("u", "chat", "gpt-5.2-chat") as t:
                t.record_tokens(1000, 500, "gpt-5.2-chat", metadata={"finish_reason": "stop"})

        call_kwargs = mock_complete.call_args.kwargs
        assert call_kwargs["input_tokens"] == 1000
        assert call_kwargs["output_tokens"] == 500
        assert call_kwargs["model_name"] == "gpt-5.2-chat"
        assert call_kwargs["metadata"]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_record_tool_forwarded_to_complete(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock) as mock_complete, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock):

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            async with track("u", "tool", "mcp_leads_context") as t:
                t.record_tool("mcp_leads_context")

        assert mock_complete.call_args.kwargs["tool_name"] == "mcp_leads_context"

    @pytest.mark.asyncio
    async def test_duration_ms_is_set(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock) as mock_complete, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock):

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            async with track("u", "chat", "gpt-5.2-chat"):
                pass

        duration = mock_complete.call_args.kwargs.get("duration_ms")
        assert duration is not None
        assert duration >= 0

    @pytest.mark.asyncio
    async def test_error_string_forwarded_to_fail(self):
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.complete_event", new_callable=AsyncMock), \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock) as mock_fail:

            mock_start.return_value = uuid.uuid4()

            from billing.metering_service import track
            with pytest.raises(RuntimeError):
                async with track("u", "chat", "gpt-5.2-chat"):
                    raise RuntimeError("azure timeout")

        assert mock_fail.call_args.kwargs["error"] == "azure timeout"

    @pytest.mark.asyncio
    async def test_fail_event_db_error_still_reraises_original(self):
        """If fail_event itself errors, the original exception must still propagate."""
        with patch("billing.metering_service.start_event", new_callable=AsyncMock) as mock_start, \
             patch("billing.metering_service.fail_event", new_callable=AsyncMock) as mock_fail:

            mock_start.return_value = uuid.uuid4()
            mock_fail.side_effect = RuntimeError("metering db exploded")

            from billing.metering_service import track
            with pytest.raises(ValueError, match="original error"):
                async with track("u", "chat", "gpt-5.2-chat"):
                    raise ValueError("original error")


# ── EventTracker ───────────────────────────────────────────────────────────────


class TestEventTracker:
    def _make_tracker(self):
        from billing.metering_service import EventTracker
        return EventTracker(event_id=uuid.uuid4())

    def test_record_tokens_sets_fields(self):
        t = self._make_tracker()
        t.record_tokens(100, 50, "gpt-5.2-chat")
        assert t._input_tokens == 100
        assert t._output_tokens == 50
        assert t._model_name == "gpt-5.2-chat"

    def test_record_tool_sets_field(self):
        t = self._make_tracker()
        t.record_tool("mcp_leads_context")
        assert t._tool_name == "mcp_leads_context"

    def test_add_metadata_merges(self):
        t = self._make_tracker()
        t.add_metadata(key1="v1")
        t.add_metadata(key2="v2")
        assert t._extra_metadata == {"key1": "v1", "key2": "v2"}

    def test_record_tokens_with_metadata(self):
        t = self._make_tracker()
        t.record_tokens(1, 1, "gpt-5-mini", metadata={"finish_reason": "stop"})
        assert t._extra_metadata["finish_reason"] == "stop"
