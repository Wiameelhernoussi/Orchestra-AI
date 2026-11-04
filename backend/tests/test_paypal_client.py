import json

import httpx
import pytest

from app.config import Settings
from app.services.paypal.client import PaypalClient, PaypalConfigurationError


def _settings(**overrides):
    values = {
        "PAYPAL_CLIENT_ID": "sandbox-client-id",
        "PAYPAL_CLIENT_SECRET": "sandbox-client-secret",
        "PAYPAL_WEBHOOK_ID": "sandbox-webhook-id",
    }
    values.update(overrides)
    return Settings(**values)


def test_invoice_request_uses_oauth_and_paypal_request_id():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-token", "expires_in": 300})
        return httpx.Response(201, json={"id": "PAYPAL-INVOICE-1"})

    http = httpx.Client(
        base_url="https://api-m.sandbox.paypal.com",
        transport=httpx.MockTransport(handler),
    )
    paypal = PaypalClient(_settings(), http)
    try:
        result = paypal.create_invoice({"items": []}, "stable-request-id")
    finally:
        http.close()

    assert result["id"] == "PAYPAL-INVOICE-1"
    assert requests[0].url.path == "/v1/oauth2/token"
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert requests[1].headers["authorization"] == "Bearer sandbox-token"
    assert requests[1].headers["paypal-request-id"] == "stable-request-id"


def test_webhook_verification_posts_signature_fields_to_paypal():
    captured = {}

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-token", "expires_in": 300})
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"verification_status": "SUCCESS"})

    http = httpx.Client(
        base_url="https://api-m.sandbox.paypal.com",
        transport=httpx.MockTransport(handler),
    )
    paypal = PaypalClient(_settings(), http)
    try:
        verified = paypal.verify_webhook(
            {
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://api-m.sandbox.paypal.com/cert",
                "paypal-transmission-id": "transmission-id",
                "paypal-transmission-sig": "signature",
                "paypal-transmission-time": "2026-11-03T22:00:00Z",
            },
            {"id": "event-1", "event_type": "INVOICING.INVOICE.PAID"},
        )
    finally:
        http.close()

    assert verified
    assert captured["webhook_id"] == "sandbox-webhook-id"
    assert captured["webhook_event"]["id"] == "event-1"


def test_invoice_search_posts_the_idempotency_number():
    captured = {}

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-token", "expires_in": 300})
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"items": []})

    http = httpx.Client(
        base_url="https://api-m.sandbox.paypal.com",
        transport=httpx.MockTransport(handler),
    )
    paypal = PaypalClient(_settings(), http)
    try:
        result = paypal.search_invoices("ORC-DESIGN-150-SMOKE")
    finally:
        http.close()

    assert result["items"] == []
    assert captured["path"] == "/v2/invoicing/search-invoices"
    assert captured["payload"]["invoice_number"] == "ORC-DESIGN-150-SMOKE"


def test_live_paypal_endpoint_is_rejected():
    with pytest.raises(PaypalConfigurationError, match="Sandbox"):
        PaypalClient(_settings(PAYPAL_BASE_URL="https://api-m.paypal.com"))


def test_only_sandbox_mode_is_supported():
    with pytest.raises(PaypalConfigurationError, match="Only PayPal Sandbox"):
        PaypalClient(_settings(PAYPAL_MODE="live"))
