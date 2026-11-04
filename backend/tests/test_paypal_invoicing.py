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

    def search_invoices(self, invoice_number):
        return {"items": []}

    def send_invoice(self, invoice_id, request_id):
        self.send_calls.append((invoice_id, request_id))
        return {
            "links": [
                {"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/payer-view"}
            ]
        }

    def get_invoice(self, invoice_id):
        return {"id": invoice_id, "status": "SENT"}


class DuplicateInvoicePaypal(FakePaypal):
    def __init__(self):
        super().__init__()
        self.invoice_number = ""
        self.search_calls = []
        self.get_calls = []
        self.payload = None

    def create_invoice(self, payload, request_id):
        self.create_calls.append((payload, request_id))
        self.payload = payload
        self.invoice_number = payload["detail"]["invoice_number"]
        raise PaypalAPIError(
            "Duplicate invoice number.",
            status_code=422,
            error_name="UNPROCESSABLE_ENTITY",
            issues=("DUPLICATE_INVOICE_NUMBER",),
        )

    def search_invoices(self, invoice_number):
        self.search_calls.append(invoice_number)
        if len(self.search_calls) == 1:
            return {"items": []}
        return {
            "items": [
                {
                    "id": "PAYPAL-EXISTING-DRAFT",
                    "detail": {"invoice_number": self.invoice_number},
                }
            ]
        }

    def get_invoice(self, invoice_id):
        self.get_calls.append(invoice_id)
        return {
            "id": invoice_id,
            "status": "DRAFT",
            "detail": self.payload["detail"],
            "primary_recipients": [
                {"billing_info": {"email_address": "alice@example.test"}}
            ],
            "items": self.payload["items"],
        }


class ExistingDraftInvoicePaypal(FakePaypal):
    def __init__(
        self,
        *,
        recipient_email="alice@example.test",
        amount="150.00",
    ):
        super().__init__()
        self.recipient_email = recipient_email
        self.amount = amount
        self.invoice_number = ""

    def search_invoices(self, invoice_number):
        self.invoice_number = invoice_number
        return {
            "items": [
                {
                    "id": "PAYPAL-EXISTING-DRAFT",
                    "detail": {"invoice_number": invoice_number},
                }
            ]
        }

    def get_invoice(self, invoice_id):
        return {
            "id": invoice_id,
            "status": "DRAFT",
            "detail": {
                "invoice_number": self.invoice_number,
                "currency_code": "USD",
            },
            "primary_recipients": [
                {"billing_info": {"email_address": self.recipient_email}}
            ],
            "items": [
                {
                    "name": "Design",
                    "quantity": "1",
                    "unit_amount": {
                        "currency_code": "USD",
                        "value": self.amount,
                    },
                }
            ],
        }


class EmptyBodySearchPaypal(FakePaypal):
    def search_invoices(self, invoice_number):
        return {}


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


def test_empty_paypal_search_response_is_treated_as_no_existing_invoice(
    db, demo_records
):
    paypal = EmptyBodySearchPaypal()

    invoice = create_or_retry_invoice(
        db, demo_records["milestone"], "alice@example.test", paypal
    )

    assert invoice.status == "SENT"
    assert invoice.paypal_invoice_id == "PAYPAL-INVOICE-1"
    assert demo_records["milestone"].status == "PAYMENT_PENDING"
    assert len(paypal.create_calls) == 1
    assert paypal.create_calls[0][1] == invoice.paypal_request_id
    assert len(paypal.send_calls) == 1


def test_repeated_invoice_request_does_not_create_a_duplicate(db, demo_records):
    paypal = FakePaypal()
    milestone = demo_records["milestone"]

    first = create_or_retry_invoice(db, milestone, "alice@example.test", paypal)
    second = create_or_retry_invoice(db, milestone, "alice@example.test", paypal)

    assert first.id == second.id
    assert len(paypal.create_calls) == 1
    assert len(paypal.send_calls) == 1


def test_payer_view_link_falls_back_to_sandbox_invoice_view_route():
    from app.services.paypal.invoicing import _payer_view_url

    assert _payer_view_url({}, "INV2-EXISTING-123") == (
        "https://www.sandbox.paypal.com/invoice/payerView/details/INV2-EXISTING-123"
    )


def test_duplicate_invoice_number_recovers_existing_sandbox_draft(db, demo_records):
    paypal = DuplicateInvoicePaypal()

    invoice = create_or_retry_invoice(
        db,
        demo_records["milestone"],
        "alice@example.test",
        paypal,
    )

    assert invoice.paypal_invoice_id == "PAYPAL-EXISTING-DRAFT"
    assert invoice.status == "SENT"
    assert demo_records["milestone"].status == "PAYMENT_PENDING"
    assert paypal.search_calls == [paypal.invoice_number, paypal.invoice_number]
    assert paypal.get_calls == ["PAYPAL-EXISTING-DRAFT"]
    assert len(paypal.create_calls) == 1
    assert len(paypal.send_calls) == 1


def test_existing_sandbox_draft_is_reused_before_create(db, demo_records):
    paypal = ExistingDraftInvoicePaypal()

    invoice = create_or_retry_invoice(
        db,
        demo_records["milestone"],
        "alice@example.test",
        paypal,
    )

    assert invoice.paypal_invoice_id == "PAYPAL-EXISTING-DRAFT"
    assert invoice.status == "SENT"
    assert demo_records["milestone"].status == "PAYMENT_PENDING"
    assert paypal.create_calls == []
    assert len(paypal.send_calls) == 1


def test_existing_invoice_for_another_recipient_is_not_reused(db, demo_records):
    paypal = ExistingDraftInvoicePaypal(recipient_email="other@example.test")

    with pytest.raises(PaypalAPIError, match="unexpected recipient"):
        create_or_retry_invoice(
            db,
            demo_records["milestone"],
            "alice@example.test",
            paypal,
        )

    invoice = db.query(Invoice).one()
    assert invoice.paypal_invoice_id is None
    assert invoice.status == "DRAFT"
    assert demo_records["milestone"].status == "APPROVED"
    assert paypal.create_calls == []
    assert paypal.send_calls == []


def test_existing_invoice_with_another_amount_is_not_reused(db, demo_records):
    paypal = ExistingDraftInvoicePaypal(amount="1.00")

    with pytest.raises(PaypalAPIError, match="does not match the milestone amount"):
        create_or_retry_invoice(
            db,
            demo_records["milestone"],
            "alice@example.test",
            paypal,
        )

    invoice = db.query(Invoice).one()
    assert invoice.paypal_invoice_id is None
    assert demo_records["milestone"].status == "APPROVED"
    assert paypal.send_calls == []


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
