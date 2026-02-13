"""Tests for lead run endpoints."""

import pytest

from _constants import TEST_LEAD_RUN_ID, TEST_USER_ID


class TestLeadRuns:
    @pytest.mark.asyncio
    async def test_list_lead_runs(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get("/lead-runs", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == TEST_LEAD_RUN_ID
        assert data[0]["result_count"] == 25
        assert data[0]["location"] == "Miami, FL"
        mock_cosmos.get_lead_runs.assert_called_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_list_lead_runs_requires_auth(self, app_client):
        resp = await app_client.get("/lead-runs")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_lead_run_detail(self, app_client, auth_headers, mock_cosmos):
        resp = await app_client.get(f"/lead-runs/{TEST_LEAD_RUN_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = await resp.get_json()
        assert data["id"] == TEST_LEAD_RUN_ID
        assert data["file_url"] == f"https://storage.example.com/leads/{TEST_LEAD_RUN_ID}.csv"
        assert data["filters"] == {"min_equity": 50}
        mock_cosmos.get_lead_run.assert_called_once_with(TEST_USER_ID, TEST_LEAD_RUN_ID)

    @pytest.mark.asyncio
    async def test_get_lead_run_not_found(self, app_client, auth_headers, mock_cosmos):
        mock_cosmos.get_lead_run.return_value = None
        resp = await app_client.get("/lead-runs/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_lead_run_requires_auth(self, app_client):
        resp = await app_client.get(f"/lead-runs/{TEST_LEAD_RUN_ID}")
        assert resp.status_code == 401
