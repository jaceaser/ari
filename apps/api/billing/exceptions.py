"""
Metering-specific exceptions.

These are raised internally within the billing package.
They must NEVER propagate to user-facing code — all metering call sites
in metering_service.py catch MeteringError and log rather than re-raising.
"""


class MeteringError(Exception):
    """Base class for all metering errors."""


class MeteringDatabaseError(MeteringError):
    """Raised when a database operation in the metering pipeline fails."""


class MeteringNotConfiguredError(MeteringError):
    """
    Raised when metering is invoked but METERING_DATABASE_URL is not set.
    The app treats this the same as a DB error — log and continue.
    """
