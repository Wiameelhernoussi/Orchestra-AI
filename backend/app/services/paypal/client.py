from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings


class PaypalConfigurationError(Exception):
    pass


class PaypalAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class PaypalClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ):
        base_url = settings.PAYPAL_BASE_URL.rstrip("/")
        if settings.PAYPAL_MODE != "sandbox":
            raise PaypalConfigurationError("Only PayPal Sandbox is supported.")
        if urlparse(base_url).hostname != "api-m.sandbox.paypal.com":
            raise PaypalConfigurationError("PAYPAL_BASE_URL must point to PayPal Sandbox.")
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            raise PaypalConfigurationError("PayPal Sandbox credentials are not configured.")

        self._settings = settings
        self._http = http_client or httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(20.0),
        )
        self._owns_client = http_client is None
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def create_invoice(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v2/invoicing/invoices",
            json=payload,
            request_id=request_id,
        )

    def send_invoice(self, invoice_id: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v2/invoicing/invoices/{invoice_id}/send",
            json={},
            request_id=request_id,
        )

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/invoicing/invoices/{invoice_id}")

    def search_invoices(self, invoice_number: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v2/invoicing/search-invoices",
            json={
                "invoice_number": invoice_number,
                "page": 1,
                "page_size": 100,
                "total_required": True,
            },
        )

    def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool:
        if not self._settings.PAYPAL_WEBHOOK_ID:
            raise PaypalConfigurationError("PAYPAL_WEBHOOK_ID is not configured.")

        result = self._request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json={
                "auth_algo": headers["paypal-auth-algo"],
                "cert_url": headers["paypal-cert-url"],
                "transmission_id": headers["paypal-transmission-id"],
                "transmission_sig": headers["paypal-transmission-sig"],
                "transmission_time": headers["paypal-transmission-time"],
                "webhook_id": self._settings.PAYPAL_WEBHOOK_ID,
                "webhook_event": event,
            },
        )
        return result.get("verification_status") == "SUCCESS"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        if json is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = self._http.request(method, path, headers=headers, json=json)
        except httpx.HTTPError as exc:
            raise PaypalAPIError("PayPal Sandbox request failed.") from exc

        if not response.is_success:
            raise PaypalAPIError(
                f"PayPal Sandbox returned HTTP {response.status_code}.",
                status_code=response.status_code,
            )
        if not response.content:
            return {}
        try:
            result = response.json()
        except ValueError as exc:
            raise PaypalAPIError("PayPal Sandbox returned an invalid JSON response.") from exc
        if not isinstance(result, dict):
            raise PaypalAPIError("PayPal Sandbox returned an unexpected response.")
        return result

    def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token

        try:
            response = self._http.post(
                "/v1/oauth2/token",
                auth=(self._settings.PAYPAL_CLIENT_ID, self._settings.PAYPAL_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise PaypalAPIError("PayPal Sandbox authentication request failed.") from exc

        if not response.is_success:
            raise PaypalAPIError(
                f"PayPal Sandbox authentication returned HTTP {response.status_code}.",
                status_code=response.status_code,
            )
        try:
            result = response.json()
            token = result["access_token"]
            expires_in = int(result["expires_in"])
        except (ValueError, KeyError, TypeError) as exc:
            raise PaypalAPIError("PayPal Sandbox returned an invalid access token response.") from exc
        if not isinstance(token, str) or not token or expires_in <= 0:
            raise PaypalAPIError("PayPal Sandbox returned an invalid access token response.")

        self._access_token = token
        self._token_expires_at = time.monotonic() + expires_in - 30
        return token
