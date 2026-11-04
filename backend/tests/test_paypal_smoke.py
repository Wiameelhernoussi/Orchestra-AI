from io import StringIO

import pytest

from app.services.paypal.client import PaypalAPIError
from app.services.paypal.smoke import (
    CREATE_REQUEST_ID,
    INVOICE_NUMBER,
    SEND_REQUEST_ID,
    run_smoke,
)

RECIPIENT = "sb-personal@example.test"
PAYER_VIEW_LINK = "https://www.sandbox.paypal.com/invoice/payer-view"


def _invoice(status="SENT", recipient=RECIPIENT):
    return {
        "id": "PAYPAL-SMOKE-INVOICE",
        "status": status,
        "detail": {"invoice_number": INVOICE_NUMBER, "currency_code": "USD"},
        "primary_recipients": [
            {"billing_info": {"email_address": recipient}}
        ],
        "items": [
            {
                "name": "Design",
                "quantity": "1",
                "unit_amount": {"currency_code": "USD", "value": "150.00"},
            }
        ],
        "links": [{"rel": "payer-view", "href": PAYER_VIEW_LINK}],
    }


class FakePaypal:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.created = []
        self.sent = []

    def search_invoices(self, invoice_number):
        assert invoice_number == INVOICE_NUMBER
        return {"items": self.matches}

    def get_invoice(self, invoice_id):
        assert invoice_id == "PAYPAL-SMOKE-INVOICE"
        return _invoice()

    def create_invoice(self, payload, request_id):
        self.created.append((payload, request_id))
        return {"id": "PAYPAL-SMOKE-INVOICE"}

    def send_invoice(self, invoice_id, request_id):
        self.sent.append((invoice_id, request_id))
        return {}


def test_smoke_creates_and_sends_one_fixed_amount_invoice():
    paypal = FakePaypal()
    output = StringIO()

    run_smoke(paypal, RECIPIENT, output)

    assert len(paypal.created) == 1
    assert paypal.created[0][1] == CREATE_REQUEST_ID
    assert paypal.created[0][0]["items"][0]["unit_amount"]["value"] == "150.00"
    assert paypal.created[0][0]["primary_recipients"][0]["billing_info"]["email_address"] == RECIPIENT
    assert paypal.sent == [("PAYPAL-SMOKE-INVOICE", SEND_REQUEST_ID)]
    assert output.getvalue().splitlines() == [
        "invoice_id: PAYPAL-SMOKE-INVOICE",
        "invoice_status: SENT",
        f"payer_view_link: {PAYER_VIEW_LINK}",
    ]


def test_smoke_reuses_existing_matching_invoice_without_resending():
    paypal = FakePaypal(matches=[{"id": "PAYPAL-SMOKE-INVOICE"}])
    output = StringIO()

    run_smoke(paypal, RECIPIENT, output)

    assert paypal.created == []
    assert paypal.sent == []
    assert "invoice_id: PAYPAL-SMOKE-INVOICE" in output.getvalue()


def test_smoke_refuses_to_create_when_search_returns_duplicate_matches():
    paypal = FakePaypal(matches=[{"id": "one"}, {"id": "two"}])

    with pytest.raises(PaypalAPIError, match="More than one"):
        run_smoke(paypal, RECIPIENT, StringIO())

    assert paypal.created == []
    assert paypal.sent == []


def test_smoke_refuses_to_send_an_existing_invoice_to_another_recipient():
    paypal = FakePaypal(matches=[{"id": "PAYPAL-SMOKE-INVOICE"}])

    with pytest.raises(PaypalAPIError, match="recipient does not match"):
        run_smoke(paypal, "other@example.test", StringIO())

    assert paypal.created == []
    assert paypal.sent == []
