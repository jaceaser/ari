"""
Phase 1E tests — admin reporting service and admin API endpoints.

Reporting service tests mock get_db_session to verify query structure
and aggregation logic without a live DB.

Admin endpoint tests use the Quart test client to verify auth enforcement,
date parsing, and response shapes.
"""
import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_db_returning(rows):
    """
    Patch get_db_session to return a mock session whose .execute() result
    has .one() returning `rows[0]` and .all() returning `rows`.
    """
    result = MagicMock()
    result.one = MagicMock(return_value=rows[0] if rows else MagicMock())
    result.all = MagicMock(return_value=rows)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    return patch("billing.database.get_db_session", return_value=cm)


def _summary_row(
    total_events=10, total_cost=1.5, total_input=5000,
    total_output=2000, unique_users=3
):
    r = MagicMock()
    r.total_events = total_events
    r.total_cost = total_cost
    r.total_input_tokens = total_input
    r.total_output_tokens = total_output
    r.unique_users = unique_users
    return r


# ── Reporting service ──────────────────────────────────────────────────────────


class TestGetUsageSummary:
    @pytest.mark.asyncio
    async def test_returns_expected_shape(self):
        with _mock_db_returning([_summary_row()]):
            from billing.reporting_service import get_usage_summary
            result = await get_usage_summary(date(2026, 1, 1), date(2026, 1, 31))

        assert "total_events" in result
        assert "total_cost_usd" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result
        assert "unique_users" in result
        assert "start_date" in result
        assert "end_date" in result

    @pytest.mark.asyncio
    async def test_maps_row_values(self):
        with _mock_db_returning([_summary_row(total_events=42, total_cost=9.99)]):
            from billing.reporting_service import get_usage_summary
            result = await get_usage_summary(date(2026, 1, 1), date(2026, 1, 31))

        assert result["total_events"] == 42
        assert abs(result["total_cost_usd"] - 9.99) < 0.0001

    @pytest.mark.asyncio
    async def test_includes_date_range(self):
        with _mock_db_returning([_summary_row()]):
            from billing.reporting_service import get_usage_summary
            result = await get_usage_summary(date(2026, 2, 1), date(2026, 2, 28))

        assert result["start_date"] == "2026-02-01"
        assert result["end_date"] == "2026-02-28"

    @pytest.mark.asyncio
    async def test_db_failure_returns_zeroed_summary(self):
        with patch("billing.database.get_db_session", side_effect=RuntimeError("db down")):
            from billing.reporting_service import get_usage_summary
            result = await get_usage_summary(date(2026, 1, 1), date(2026, 1, 31))

        assert result["total_events"] == 0
        assert result["total_cost_usd"] == 0.0


class TestGetSpendByUser:
    def _user_row(self, user_id="u1", event_count=5, total_cost=2.0, inp=1000, out=500):
        r = MagicMock()
        r.user_id = user_id
        r.event_count = event_count
        r.total_cost = total_cost
        r.total_input_tokens = inp
        r.total_output_tokens = out
        return r

    @pytest.mark.asyncio
    async def test_returns_list_of_users(self):
        rows = [self._user_row("u1", total_cost=5.0), self._user_row("u2", total_cost=2.0)]
        with _mock_db_returning(rows):
            from billing.reporting_service import get_spend_by_user
            result = await get_spend_by_user(date(2026, 1, 1), date(2026, 1, 31))

        assert len(result) == 2
        assert result[0]["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_each_entry_has_required_keys(self):
        with _mock_db_returning([self._user_row()]):
            from billing.reporting_service import get_spend_by_user
            result = await get_spend_by_user(date(2026, 1, 1), date(2026, 1, 31))

        entry = result[0]
        for key in ("user_id", "event_count", "total_cost_usd", "total_input_tokens", "total_output_tokens"):
            assert key in entry, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_db_failure_returns_empty_list(self):
        with patch("billing.database.get_db_session", side_effect=RuntimeError("db down")):
            from billing.reporting_service import get_spend_by_user
            result = await get_spend_by_user(date(2026, 1, 1), date(2026, 1, 31))

        assert result == []


class TestGetTopUsers:
    @pytest.mark.asyncio
    async def test_delegates_to_spend_by_user_with_limit(self):
        with patch("billing.reporting_service.get_spend_by_user", new_callable=AsyncMock) as mock:
            mock.return_value = []
            from billing.reporting_service import get_top_users
            await get_top_users(date(2026, 1, 1), date(2026, 1, 31), limit=5)

        mock.assert_awaited_once()
        assert mock.call_args.kwargs["limit"] == 5


class TestGetTopActions:
    @pytest.mark.asyncio
    async def test_slices_to_limit(self):
        all_actions = [{"action_name": f"action-{i}"} for i in range(20)]
        with patch("billing.reporting_service.get_spend_by_action_name", new_callable=AsyncMock) as mock:
            mock.return_value = all_actions
            from billing.reporting_service import get_top_actions
            result = await get_top_actions(date(2026, 1, 1), date(2026, 1, 31), limit=5)

        assert len(result) == 5


class TestGetUsageTimeseries:
    def _ts_row(self, period, count=10, cost=1.0, users=3):
        from datetime import datetime, timezone
        r = MagicMock()
        r.period = datetime(2026, 1, int(period[-2:]), tzinfo=timezone.utc)
        r.event_count = count
        r.total_cost = cost
        r.unique_users = users
        return r

    @pytest.mark.asyncio
    async def test_returns_list_with_period_key(self):
        with _mock_db_returning([self._ts_row("2026-01-01")]):
            from billing.reporting_service import get_usage_timeseries
            result = await get_usage_timeseries(date(2026, 1, 1), date(2026, 1, 31))

        assert isinstance(result, list)
        assert "period" in result[0]
        assert "event_count" in result[0]
        assert "total_cost_usd" in result[0]
        assert "unique_users" in result[0]

    @pytest.mark.asyncio
    async def test_db_failure_returns_empty_list(self):
        with patch("billing.database.get_db_session", side_effect=RuntimeError("db down")):
            from billing.reporting_service import get_usage_timeseries
            result = await get_usage_timeseries(date(2026, 1, 1), date(2026, 1, 31))

        assert result == []


# ── Admin endpoint auth ────────────────────────────────────────────────────────


class TestRequireAdmin:
    """Auth behaviour — no DB needed, mock reporting_service."""

    @pytest.fixture
    def client(self, mock_cosmos):
        from unittest.mock import patch
        with patch("cosmos.SessionsCosmosClient.get_instance", return_value=mock_cosmos):
            from app import app
            yield app.test_client()

    @pytest.mark.asyncio
    async def test_missing_admin_key_env_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        resp = await client.get("/admin/usage/summary")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_wrong_key_returns_401(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "correct-secret")
        resp = await client.get(
            "/admin/usage/summary",
            headers={"X-Admin-Key": "wrong-secret"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_key_header_returns_401(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "correct-secret")
        resp = await client.get("/admin/usage/summary")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_correct_key_via_x_admin_key_header(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "correct-secret")
        with patch("billing.reporting_service.get_usage_summary", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "total_events": 0, "total_cost_usd": 0.0,
                "total_input_tokens": 0, "total_output_tokens": 0,
                "unique_users": 0, "start_date": "2026-01-01", "end_date": "2026-01-31",
            }
            resp = await client.get(
                "/admin/usage/summary",
                headers={"X-Admin-Key": "correct-secret"},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_correct_key_via_bearer_token(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "correct-secret")
        with patch("billing.reporting_service.get_usage_summary", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "total_events": 0, "total_cost_usd": 0.0,
                "total_input_tokens": 0, "total_output_tokens": 0,
                "unique_users": 0, "start_date": "2026-01-01", "end_date": "2026-01-31",
            }
            resp = await client.get(
                "/admin/usage/summary",
                headers={"Authorization": "Bearer correct-secret"},
            )
        assert resp.status_code == 200


# ── Admin endpoint date validation ─────────────────────────────────────────────


class TestAdminDateParsing:
    @pytest.fixture
    def authed_client(self, mock_cosmos, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
        with patch("cosmos.SessionsCosmosClient.get_instance", return_value=mock_cosmos):
            from app import app
            yield app.test_client(), {"X-Admin-Key": "test-admin-key"}

    @pytest.mark.asyncio
    async def test_invalid_date_returns_400(self, authed_client):
        client, headers = authed_client
        resp = await client.get(
            "/admin/usage/summary?start_date=not-a-date",
            headers=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_granularity_returns_400(self, authed_client):
        client, headers = authed_client
        resp = await client.get(
            "/admin/usage/timeseries?granularity=hourly",
            headers=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_granularity_values_accepted(self, authed_client):
        client, headers = authed_client
        for gran in ("daily", "weekly", "monthly"):
            with patch("billing.reporting_service.get_usage_timeseries", new_callable=AsyncMock) as mock:
                mock.return_value = []
                resp = await client.get(
                    f"/admin/usage/timeseries?granularity={gran}",
                    headers=headers,
                )
            assert resp.status_code == 200, f"granularity={gran} should be accepted"
