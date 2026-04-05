"""
Phase 1A tests — database schema and connection setup.

These tests run without a live database. They verify:
  - URL scheme normalisation in database.py
  - Graceful no-op when METERING_DATABASE_URL is unset
  - RuntimeError from get_db_session() when not configured
  - SQLAlchemy model structure (columns, nullability, indexes)
  - Exception class hierarchy
"""
import importlib
import pytest


# ── URL normalisation ──────────────────────────────────────────────────────────


class TestGetDatabaseUrl:
    """billing.database._get_database_url normalises URL schemes for asyncpg."""

    def _call(self, url: str, monkeypatch) -> str | None:
        # Reset cached engine/factory between tests
        import billing.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None

        monkeypatch.setenv("METERING_DATABASE_URL", url)
        # Re-import to pick up fresh env
        importlib.reload(db_mod)
        return db_mod._get_database_url()

    def test_postgres_scheme_rewritten(self, monkeypatch):
        import billing.database as db_mod
        monkeypatch.setenv("METERING_DATABASE_URL", "postgres://u:p@host:5432/db")
        result = db_mod._get_database_url()
        assert result.startswith("postgresql+asyncpg://")

    def test_postgresql_scheme_rewritten(self, monkeypatch):
        import billing.database as db_mod
        monkeypatch.setenv("METERING_DATABASE_URL", "postgresql://u:p@host:5432/db")
        result = db_mod._get_database_url()
        assert result.startswith("postgresql+asyncpg://")

    def test_already_asyncpg_scheme_unchanged(self, monkeypatch):
        import billing.database as db_mod
        url = "postgresql+asyncpg://u:p@host:5432/db"
        monkeypatch.setenv("METERING_DATABASE_URL", url)
        assert db_mod._get_database_url() == url

    def test_empty_env_returns_none(self, monkeypatch):
        import billing.database as db_mod
        monkeypatch.delenv("METERING_DATABASE_URL", raising=False)
        assert db_mod._get_database_url() is None

    def test_whitespace_only_returns_none(self, monkeypatch):
        import billing.database as db_mod
        monkeypatch.setenv("METERING_DATABASE_URL", "   ")
        assert db_mod._get_database_url() is None

    def test_query_params_preserved(self, monkeypatch):
        import billing.database as db_mod
        monkeypatch.setenv(
            "METERING_DATABASE_URL",
            "postgresql://u:p@host:5432/ari_metering?sslmode=require",
        )
        result = db_mod._get_database_url()
        assert "ssl" in result or "sslmode" in result
        assert "ari_metering" in result


# ── Unconfigured behaviour ─────────────────────────────────────────────────────


class TestUnconfiguredDatabase:
    """When METERING_DATABASE_URL is not set everything degrades gracefully."""

    @pytest.fixture(autouse=True)
    def _clear_url(self, monkeypatch):
        monkeypatch.delenv("METERING_DATABASE_URL", raising=False)
        # Reset cached singletons
        import billing.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None

    def test_get_engine_returns_none(self):
        from billing.database import get_engine
        assert get_engine() is None

    def test_get_session_factory_returns_none(self):
        from billing.database import get_session_factory
        assert get_session_factory() is None

    @pytest.mark.asyncio
    async def test_get_db_session_raises_runtime_error(self):
        from billing.database import get_db_session
        with pytest.raises(RuntimeError, match="METERING_DATABASE_URL"):
            async with get_db_session():
                pass  # should not reach here


# ── Model structure ────────────────────────────────────────────────────────────


class TestUsageEventModel:
    """Verify the SQLAlchemy model matches the spec — no live DB needed."""

    @pytest.fixture
    def table(self):
        from billing.models import UsageEvent
        return UsageEvent.__table__

    def test_table_name(self, table):
        assert table.name == "usage_events"

    def test_primary_key_is_id(self, table):
        pk_cols = [c.name for c in table.primary_key.columns]
        assert pk_cols == ["id"]

    @pytest.mark.parametrize("col_name", [
        "id", "user_id", "session_id", "request_id", "execution_id",
        "action_type", "action_name", "model_name",
        "input_tokens", "output_tokens", "token_cost_estimate",
        "tool_name", "tool_cost_estimate", "total_cost_estimate",
        "status", "duration_ms", "metadata_json",
        "created_at", "updated_at",
    ])
    def test_column_exists(self, table, col_name):
        assert col_name in table.c, f"Column '{col_name}' missing from usage_events"

    @pytest.mark.parametrize("col_name", [
        "user_id", "action_type", "action_name", "status",
        "total_cost_estimate", "created_at", "updated_at",
    ])
    def test_required_columns_not_nullable(self, table, col_name):
        assert not table.c[col_name].nullable, f"Column '{col_name}' should be NOT NULL"

    @pytest.mark.parametrize("col_name", [
        "session_id", "request_id", "execution_id", "model_name",
        "input_tokens", "output_tokens", "token_cost_estimate",
        "tool_name", "tool_cost_estimate", "duration_ms", "metadata_json",
    ])
    def test_optional_columns_are_nullable(self, table, col_name):
        assert table.c[col_name].nullable, f"Column '{col_name}' should be nullable"

    def test_request_id_is_unique(self, table):
        unique_cols = {
            col.name
            for constraint in table.constraints
            if hasattr(constraint, "columns")
            for col in constraint.columns
            if getattr(constraint, "unique", False) or constraint.__class__.__name__ == "UniqueConstraint"
        }
        # request_id has unique=True on the Column itself
        assert table.c["request_id"].unique

    def test_expected_indexes_exist(self, table):
        index_names = {idx.name for idx in table.indexes}
        expected = {
            "ix_usage_events_user_id_created_at",
            "ix_usage_events_action_type_created_at",
            "ix_usage_events_execution_id",
            "ix_usage_events_created_at",
            "ix_usage_events_status",
        }
        assert expected <= index_names, f"Missing indexes: {expected - index_names}"

    def test_cost_columns_use_numeric_type(self, table):
        from sqlalchemy import Numeric
        for col_name in ("token_cost_estimate", "tool_cost_estimate", "total_cost_estimate"):
            col_type = type(table.c[col_name].type)
            assert issubclass(col_type, Numeric), (
                f"Column '{col_name}' should use Numeric type, got {col_type}"
            )

    def test_numeric_precision_and_scale(self, table):
        col = table.c["total_cost_estimate"]
        assert col.type.precision == 12
        assert col.type.scale == 6


# ── Exception hierarchy ────────────────────────────────────────────────────────


class TestExceptionHierarchy:
    def test_metering_database_error_is_metering_error(self):
        from billing.exceptions import MeteringDatabaseError, MeteringError
        assert issubclass(MeteringDatabaseError, MeteringError)

    def test_metering_not_configured_error_is_metering_error(self):
        from billing.exceptions import MeteringError, MeteringNotConfiguredError
        assert issubclass(MeteringNotConfiguredError, MeteringError)

    def test_metering_error_is_exception(self):
        from billing.exceptions import MeteringError
        assert issubclass(MeteringError, Exception)

    def test_exceptions_are_catchable_as_base(self):
        from billing.exceptions import MeteringDatabaseError, MeteringError
        with pytest.raises(MeteringError):
            raise MeteringDatabaseError("db write failed")
