"""Route blueprints for Phase 2 API endpoints."""

from quart import Blueprint

auth_bp = Blueprint("auth", __name__)
sessions_bp = Blueprint("sessions", __name__)
lead_runs_bp = Blueprint("lead_runs", __name__)
documents_bp = Blueprint("documents", __name__)

# Import route handlers to register them on blueprints
from . import auth  # noqa: F401, E402
from . import sessions  # noqa: F401, E402
from . import lead_runs  # noqa: F401, E402
from . import documents  # noqa: F401, E402

# Frontend data persistence (documents, suggestions, votes, messages)
from .frontend_data import frontend_data_bp  # noqa: F401, E402

# Magic link authentication
from .magic_link import magic_link_bp  # noqa: F401, E402

# Stripe + billing
from .stripe_webhook import stripe_webhook_bp  # noqa: F401, E402
from .billing import billing_bp  # noqa: F401, E402

# Unauthenticated demo (sales funnel teaser)
from .demo import demo_bp  # noqa: F401, E402
