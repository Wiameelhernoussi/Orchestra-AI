from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def _environment() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    values.update(os.environ)
    return values


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    user_id: str | None = None,
    seed_token: str | None = None,
) -> dict:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if user_id:
        headers["X-User-Id"] = user_id
    if seed_token:
        headers["X-Demo-Seed-Token"] = seed_token
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read())
    except HTTPError as exc:
        message = f"{method} {path} failed with HTTP {exc.code}"
        if exc.code == 422:
            try:
                error = json.loads(exc.read())
            except (OSError, json.JSONDecodeError):
                error = None
            details = error.get("detail") if isinstance(error, dict) else None
            if isinstance(details, list):
                fields = []
                for item in details:
                    if not isinstance(item, dict):
                        continue
                    location = item.get("loc")
                    error_type = item.get("type")
                    if isinstance(location, list) and isinstance(error_type, str):
                        fields.append(
                            ".".join(str(part) for part in location)
                            + f" ({error_type})"
                        )
                if fields:
                    message += "; invalid fields: " + ", ".join(fields)
            elif isinstance(details, str):
                message += "; request rejected by workflow validation"
        raise RuntimeError(message + ".") from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError(f"{method} {path} failed.") from None
    if not isinstance(result, dict):
        raise RuntimeError("API returned an unexpected response.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the real PayPal Sandbox demo flow.")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Use the already seeded demo users instead of resetting demo data.",
    )
    args = parser.parse_args()
    env = _environment()
    base_url = env.get("ORCHESTRA_API_URL", "http://localhost:8000")
    seed_token = env.get("DEMO_SEED_TOKEN", "")
    if not args.no_seed and not seed_token:
        print("DEMO_SEED_TOKEN is not configured in backend/.env.", file=sys.stderr)
        return 1

    try:
        if args.no_seed:
            client_id = "demo-client"
            provider_id = "demo-provider"
        else:
            seeded = _request(
                base_url,
                "POST",
                "/api/v1/demo/seed",
                seed_token=seed_token,
            )
            client_id = seeded["client_user_id"]
            provider_id = seeded["provider_user_id"]
            agreement_id = seeded["agreement_id"]

        intent = _request(
            base_url,
            "POST",
            "/api/v1/client/intents/parse",
            payload={
                "request": (
                    "Create an e-commerce website for a $600 total budget. "
                    "Use three milestones: Design $150, Development $350, "
                    "and Final Handover $100. Use exactly those milestone "
                    "amounts. Do not invent missing product features or a deadline."
                )
            },
            user_id=client_id,
        )
        if not isinstance(intent, dict):
            raise RuntimeError("Intent Agent returned an unexpected response.")
        # This demo explicitly specifies dollar amounts and supports USD only.
        intent["currency"] = "USD"
        if intent.get("budget_cents") != 60000 or [
            item.get("amount_cents") for item in intent.get("milestones", [])
        ] != [15000, 35000, 10000]:
            raise RuntimeError("Groq intent did not preserve the demo budget and milestone amounts.")

        agreement = _request(
            base_url,
            "POST",
            "/api/v1/client/agreements",
            payload={"intent": intent},
            user_id=client_id,
        )
        agreement_id = agreement["id"]
        _request(
            base_url,
            "POST",
            f"/api/v1/client/agreements/{agreement_id}/publish",
            user_id=client_id,
        )
        _request(
            base_url,
            "POST",
            f"/api/v1/provider/agreements/{agreement_id}/accept",
            user_id=provider_id,
        )
        milestone_id = agreement["milestones"][0]["id"]
        _request(
            base_url,
            "POST",
            f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/start",
            user_id=provider_id,
        )
        _request(
            base_url,
            "POST",
            f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/evidence",
            payload={
                "text": (
                    "The design milestone deliverables are ready for review. "
                    "A responsive layout for desktop and mobile has been prepared."
                )
            },
            user_id=provider_id,
        )
        _request(
            base_url,
            "POST",
            f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/submit",
            user_id=provider_id,
        )
        _request(
            base_url,
            "POST",
            f"/api/v1/client/agreements/{agreement_id}/milestones/{milestone_id}/approve",
            user_id=client_id,
        )
        invoice = _request(
            base_url,
            "POST",
            f"/api/v1/payments/milestones/{milestone_id}/invoice",
            user_id=client_id,
        )
    except (KeyError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"milestone_id: {milestone_id}")
    print(f"invoice_id: {invoice.get('paypal_invoice_id')}")
    print(f"payer_view_link: {invoice.get('paypal_invoice_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
