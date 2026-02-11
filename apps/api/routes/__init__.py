"""Route blueprints for Phase 2 API endpoints."""

from quart import Blueprint

auth_bp = Blueprint("auth", __name__)
sessions_bp = Blueprint("sessions", __name__)
lead_runs_bp = Blueprint("lead_runs", __name__)

# Import route handlers to register them on blueprints
from . import auth  # noqa: F401, E402
from . import sessions  # noqa: F401, E402
from . import lead_runs  # noqa: F401, E402
