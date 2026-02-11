"""Shared test constants."""

import uuid

TEST_JWT_SECRET = "test-jwt-secret-for-testing"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ari:user:{TEST_USER_EMAIL}"))
