"""Tests for send_welcome_email and its integration with the Stripe checkout webhook."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from _constants import TEST_USER_EMAIL, TEST_USER_ID


_EMAIL_CLIENT_PATH = "azure.communication.email.EmailClient"


class TestSendWelcomeEmail:
    @pytest.mark.asyncio
    async def test_sends_email_with_correct_links(self, monkeypatch):
        """Welcome email includes all three resource links."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")
        monkeypatch.setenv("AZURE_COMMUNICATION_SENDER", "DoNotReply@reilabs.ai")

        mock_poller = MagicMock()
        mock_client = MagicMock()
        mock_client.begin_send.return_value = mock_poller

        with patch(_EMAIL_CLIENT_PATH) as MockEmailClient:
            MockEmailClient.from_connection_string.return_value = mock_client
            from routes.magic_link import send_welcome_email
            await send_welcome_email("test@example.com")

        mock_client.begin_send.assert_called_once()
        message = mock_client.begin_send.call_args[0][0]

        assert message["recipients"]["to"][0]["address"] == "test@example.com"
        assert message["senderAddress"] == "DoNotReply@reilabs.ai"
        assert message["content"]["subject"] == "Welcome to ARI — let's get you started"

        # All three links must appear in both plain text and HTML
        for url in ("https://reilabs.ai/guides", "https://reilabs.ai/prompts", "https://reilabs.ai/usage"):
            assert url in message["content"]["plainText"], f"Missing {url} in plainText"
            assert url in message["content"]["html"], f"Missing {url} in html"

        mock_poller.result.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_endpoint_logs_warning_and_returns(self, monkeypatch):
        """No-op (with warning) when AZURE_COMMUNICATION_ENDPOINT is not set."""
        monkeypatch.delenv("AZURE_COMMUNICATION_ENDPOINT", raising=False)

        with patch(_EMAIL_CLIENT_PATH) as MockEmailClient:
            from routes.magic_link import send_welcome_email
            await send_welcome_email("test@example.com")
            MockEmailClient.from_connection_string.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_client_import_error(self, monkeypatch):
        """Gracefully handles missing azure-communication-email package."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")

        import sys
        with patch.dict(sys.modules, {"azure.communication.email": None}):
            from routes.magic_link import send_welcome_email
            # Should not raise
            await send_welcome_email("test@example.com")

    @pytest.mark.asyncio
    async def test_send_failure_is_logged_and_not_raised(self, monkeypatch):
        """Email client exceptions are logged but not propagated — welcome email must never break checkout."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")

        mock_client = MagicMock()
        mock_client.begin_send.side_effect = RuntimeError("network error")

        with patch(_EMAIL_CLIENT_PATH) as MockEmailClient:
            MockEmailClient.from_connection_string.return_value = mock_client
            from routes.magic_link import send_welcome_email
            # Should not raise
            await send_welcome_email("test@example.com")

    @pytest.mark.asyncio
    async def test_uses_custom_sender_env(self, monkeypatch):
        """Respects AZURE_COMMUNICATION_SENDER env var."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")
        monkeypatch.setenv("AZURE_COMMUNICATION_SENDER", "ari@custom-domain.com")

        mock_poller = MagicMock()
        mock_client = MagicMock()
        mock_client.begin_send.return_value = mock_poller

        with patch(_EMAIL_CLIENT_PATH) as MockEmailClient:
            MockEmailClient.from_connection_string.return_value = mock_client
            from routes.magic_link import send_welcome_email
            await send_welcome_email("test@example.com")

        message = mock_client.begin_send.call_args[0][0]
        assert message["senderAddress"] == "ari@custom-domain.com"


class TestCheckoutCompletedSendsWelcomeEmail:
    """Integration: checkout.session.completed triggers a welcome email."""

    def _make_stripe_event(self, event_type: str, data: dict) -> dict:
        return {"id": "evt_test", "type": event_type, "data": {"object": data}}

    @pytest.mark.asyncio
    async def test_welcome_email_sent_on_checkout_completed(self, mock_cosmos, monkeypatch):
        """Welcome email is sent when checkout.session.completed fires with a customer email."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")

        mock_cosmos.find_user_by_email = AsyncMock(return_value={
            "userId": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
        })
        mock_cosmos.update_user_subscription = AsyncMock()

        session_obj = {
            "customer": "cus_123",
            "customer_email": TEST_USER_EMAIL,
            "subscription": "sub_123",
        }

        with patch("routes.magic_link.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
            from routes.stripe_webhook import _handle_checkout_completed
            await _handle_checkout_completed(mock_cosmos, session_obj)

        mock_welcome.assert_called_once_with(TEST_USER_EMAIL)

    @pytest.mark.asyncio
    async def test_welcome_email_not_sent_when_no_customer_email(self, mock_cosmos):
        """No welcome email when checkout session has no customer_email."""
        mock_cosmos.find_user_by_stripe_customer = AsyncMock(return_value={
            "userId": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
        })
        mock_cosmos.update_user_subscription = AsyncMock()

        session_obj = {
            "customer": "cus_123",
            "customer_email": None,
            "subscription": "sub_123",
        }

        with patch("routes.magic_link.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
            from routes.stripe_webhook import _handle_checkout_completed
            await _handle_checkout_completed(mock_cosmos, session_obj)

        mock_welcome.assert_not_called()

    @pytest.mark.asyncio
    async def test_welcome_email_failure_does_not_break_checkout(self, mock_cosmos, monkeypatch):
        """A welcome email send failure is caught and does not raise from _handle_checkout_completed."""
        monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "endpoint://fake")

        mock_cosmos.find_user_by_email = AsyncMock(return_value={
            "userId": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
        })
        mock_cosmos.update_user_subscription = AsyncMock()

        session_obj = {
            "customer": "cus_123",
            "customer_email": TEST_USER_EMAIL,
            "subscription": "sub_123",
        }

        with patch("routes.magic_link.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
            mock_welcome.side_effect = RuntimeError("email service down")
            from routes.stripe_webhook import _handle_checkout_completed
            # Should not raise — failure is caught and logged
            await _handle_checkout_completed(mock_cosmos, session_obj)

        mock_cosmos.update_user_subscription.assert_called_once()
