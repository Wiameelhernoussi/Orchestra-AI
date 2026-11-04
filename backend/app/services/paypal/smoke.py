from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from typing import Any, TextIO
from uuid import NAMESPACE_URL, uuid5

from app.config import settings
from app.services.paypal.client import PaypalAPIError, PaypalClient

INVOICE_NUMBER = "ORC-DESIGN-150-SMOKE"
CREATE_REQUEST_ID = str(uuid5(NAMESPACE_URL, f"orchestra-smoke:{INVOICE_NUMBER}:create"))
SEND_REQUEST_ID = str(uuid5(NAMESPACE_URL, f"orchestra-smoke:{INVOICE_NUMBER}:send"))
AMOUNT = Decimal("150.00")


def build_payload(recipient_email: str) -> dict[str, Any]:
    return {
        "detail": {
            "invoice_number": INVOICE_NUMBER,
            "currency_code": "USD",
            "note": "Payment for the approved Design milestone.",
        },
        "primary_recipients": [
            {"billing_info": {"email_address": recipient_email}}
        ],
        "items": [
            {
                "name": "Design",
                "description": "Design milestone",
                "quantity": "1",
                "unit_amount": {"currency_code": "USD", "value": "150.00"},
            }
        ],
    }


def run_smoke(paypal: PaypalClient, recipient_email: str, output: TextIO = sys.stdout) -> None:
    email = recipient_email.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("A valid Personal Sandbox account email is required.")

    matches = paypal.search_invoices(INVOICE_NUMBER).get("items", [])
    if not isinstance(matches, list):
        raise PaypalAPIError("PayPal Sandbox returned an invalid invoice search result.")
    if len(matches) > 1:
        raise PaypalAPIError("More than one matching smoke invoice exists; refusing to send.")

    if matches:
        summary = matches[0]
        if not isinstance(summary, dict) or not isinstance(summary.get("id"), str):
            raise PaypalAPIError("PayPal Sandbox returned an invalid matching invoice.")
        invoice = paypal.get_invoice(summary["id"])
        _verify_invoice(invoice, email)
        status = invoice.get("status")
        if status == "DRAFT":
            paypal.send_invoice(summary["id"], SEND_REQUEST_ID)
            invoice = paypal.get_invoice(summary["id"])
        elif status not in {"SENT", "PAID"}:
            raise PaypalAPIError(
                "A matching smoke invoice exists in a non-sendable state; refusing to create another."
            )
    else:
        created = paypal.create_invoice(build_payload(email), CREATE_REQUEST_ID)
        invoice_id = created.get("id")
        if not isinstance(invoice_id, str) or not invoice_id:
            raise PaypalAPIError("PayPal Sandbox did not return an invoice ID.")
        paypal.send_invoice(invoice_id, SEND_REQUEST_ID)
        invoice = paypal.get_invoice(invoice_id)

    _verify_invoice(invoice, email)
    invoice_id = invoice.get("id")
    status = invoice.get("status")
    payer_view_link = _payer_view_url(invoice)
    if not isinstance(invoice_id, str) or status not in {"SENT", "PAID"} or not payer_view_link:
        raise PaypalAPIError("PayPal Sandbox invoice is not send-confirmed or has no payer-view link.")

    print(f"invoice_id: {invoice_id}", file=output)
    print(f"invoice_status: {status}", file=output)
    print(f"payer_view_link: {payer_view_link}", file=output)


def _verify_invoice(invoice: dict[str, Any], recipient_email: str) -> None:
    detail = invoice.get("detail")
    recipients = invoice.get("primary_recipients")
    items = invoice.get("items")
    if not isinstance(detail, dict) or detail.get("invoice_number") != INVOICE_NUMBER:
        raise PaypalAPIError("Matching PayPal invoice number has unexpected details.")
    if detail.get("currency_code") != "USD":
        raise PaypalAPIError("Matching PayPal invoice has an unexpected currency.")
    if not isinstance(recipients, list) or not any(
        isinstance(entry, dict)
        and isinstance(entry.get("billing_info"), dict)
        and isinstance(entry["billing_info"].get("email_address"), str)
        and entry["billing_info"]["email_address"].casefold() == recipient_email.casefold()
        for entry in recipients
    ):
        raise PaypalAPIError("Matching PayPal invoice recipient does not match.")
    if not isinstance(items, list) or not items:
        raise PaypalAPIError("Matching PayPal invoice has no line items.")

    total = Decimal("0")
    for item in items:
        if not isinstance(item, dict):
            raise PaypalAPIError("Matching PayPal invoice has an invalid line item.")
        amount = item.get("unit_amount")
        if (
            item.get("name") != "Design"
            or item.get("quantity") != "1"
            or not isinstance(amount, dict)
            or amount.get("currency_code") != "USD"
        ):
            raise PaypalAPIError("Matching PayPal invoice line item does not match the smoke request.")
        try:
            total += Decimal(amount["value"]) * Decimal(item["quantity"])
        except (KeyError, ArithmeticError, TypeError, ValueError) as exc:
            raise PaypalAPIError("Matching PayPal invoice has an invalid amount.") from exc
    if total != AMOUNT:
        raise PaypalAPIError("Matching PayPal invoice amount is not $150.00.")


def _payer_view_url(invoice: dict[str, Any]) -> str | None:
    links = invoice.get("links", [])
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "payer-view":
            href = link.get("href")
            if isinstance(href, str) and href.startswith("https://"):
                return href
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and send one idempotent $150 PayPal Sandbox Design invoice."
    )
    parser.add_argument("--recipient", required=True, help="Personal Sandbox recipient email.")
    args = parser.parse_args()

    paypal = PaypalClient(settings)
    try:
        run_smoke(paypal, args.recipient)
    except (PaypalAPIError, ValueError) as exc:
        print(f"PayPal Sandbox smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        paypal.close()
    return 0
