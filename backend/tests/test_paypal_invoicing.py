import pytest

from app.models.approval import Approval
from app.models.invoice import Invoice
from app.services.paypal.client import PaypalAPIError
from app.services.paypal.invoicing import (
    apply_paypal_invoice_status,
    build_invoice_payload,
    create_or_retry_invoice,
)


class FakePaypal:
    def __init__(self, fail_on_create=False):
        self.fail_on_create = fail_on_create
        self.create_calls = []
        self.send_calls = []

    def create_invoice(self, payload, request_id):
        self.create_calls.append((payload, request_id))
        if self.fail_on_create:
            raise PaypalAPIError("temporary sandbox error", status_code=503)
        return {"id": "PAYPAL-INVOICE-1"}

    def send_invoice(self, invoice_id, request_id):
        self.send_calls.append((invoice_id, request_id))
        return {
            "links": [
                {"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/payer-view"}
            ]
        }

    def get_invoice(self, invoice_id):
        return {"id": invoice_id, "status": "SENT"}


def test_invoice_payload_uses_cents_and_the_approved_client_email(demo_records):
    payload = build_invoice_payload(
        demo_records["milestone"],
        "internal-invoice-id",
        "alice@example.test",
    )

    assert payload["items"][0]["unit_amount"]["value"] == "150.00"
    assert payload["items"][0]["unit_amount"]["currency_code"] == "USD"
    assert payload["primary_recipients"][0]["billing_info"]["email_address"] == "alice@example.test"


def test_paypal_failure_preserves_approval_and_retry_reuses_request_id(db, demo_records):
    failed_paypal = FakePaypal(fail_on_create=True)
    milestone = demo_records["milestone"]

    with pytest.raises(PaypalAPIError):
        create_or_retry_invoice(db, milestone, "alice@example.test", failed_paypal)

    assert milestone.status == "APPROVED"
    assert db.query(Approval).count() == 1
    assert db.query(Invoice).count() == 1
    original_request_id = db.query(Invoice).one().paypal_request_id

    working_paypal = FakePaypal()
    invoice = create_or_retry_invoice(db, milestone, "alice@example.test", working_paypal)

    assert invoice.paypal_request_id == original_request_id
    assert invoice.paypal_invoice_id == "PAYPAL-INVOICE-1"
    assert invoice.status == "SENT"
    assert invoice.paypal_invoice_url == "https://www.sandbox.paypal.com/invoice/payer-view"
    assert milestone.status == "PAYMENT_PENDING"
    assert len(working_paypal.create_calls) == 1
    assert len(working_paypal.send_calls) == 1


def test_repeated_invoice_request_does_not_create_a_duplicate(db, demo_records):
    paypal = FakePaypal()
    milestone = demo_records["milestone"]

    first = create_or_retry_invoice(db, milestone, "alice@example.test", paypal)
    second = create_or_retry_invoice(db, milestone, "alice@example.test", paypal)

    assert first.id == second.id
    assert len(paypal.create_calls) == 1
    assert len(paypal.send_calls) == 1


def test_verified_paypal_status_updates_invoice_and_milestone(db, demo_records):
    milestone = demo_records["milestone"]
    milestone.status = "PAYMENT_PENDING"
    invoice = Invoice(
        id="local-invoice",
        milestone=milestone,
        paypal_invoice_id="PAYPAL-INVOICE-1",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    db.commit()

    apply_paypal_invoice_status(db, invoice, "PAID")
    db.commit()

    assert invoice.status == "PAID"
    assert milestone.status == "PAID"


def test_cancellation_and_expiry_statuses_are_recorded(db, demo_records):
    milestone = demo_records["milestone"]
    milestone.status = "PAYMENT_PENDING"
    invoice = Invoice(
        id="local-invoice",
        milestone=milestone,
        paypal_invoice_id="PAYPAL-INVOICE-1",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    db.commit()

    apply_paypal_invoice_status(db, invoice, "CANCELLED")
    db.commit()

    assert invoice.status == "CANCELLED"
    assert milestone.status == "INVOICE_CANCELLED"


def test_paypal_expiry_status_is_recorded(db, demo_records):
    milestone = demo_records["milestone"]
    milestone.status = "PAYMENT_PENDING"
    invoice = Invoice(
        id="local-invoice",
        milestone=milestone,
        paypal_invoice_id="PAYPAL-INVOICE-1",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    db.commit()

    apply_paypal_invoice_status(db, invoice, "EXPIRED")
    db.commit()

    assert invoice.status == "EXPIRED"
    assert milestone.status == "INVOICE_EXPIRED"
