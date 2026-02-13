"""Shared test constants."""

import uuid

TEST_JWT_SECRET = "test-jwt-secret-for-testing"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{TEST_USER_EMAIL}"))

# Second user for cross-user isolation tests
TEST_USER_EMAIL_B = "attacker@example.com"
TEST_USER_ID_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{TEST_USER_EMAIL_B}"))

# Valid UUIDs for test sessions/messages
TEST_SESSION_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
TEST_LEAD_RUN_ID = "d4c3b2a1-6f5e-4b7a-9d8c-1f0e3a2b5c4d"
