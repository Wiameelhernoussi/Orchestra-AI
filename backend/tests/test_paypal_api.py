import logging
import base64

from app.api.deps import get_paypal_client
from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.models.webhook import WebhookEvent
from app.services.paypal.client import PaypalAPIError


class FakePaypal:
    def __init__(self, verified=True):
        self.verified = verified
        self.created = []
        self.qr_calls = []
        self.reminder_calls = []

    def create_invoice(self, payload, request_id):
        self.created.append((payload, request_id))
        return {"id": "PAYPAL-INVOICE-API"}

    def search_invoices(self, invoice_number):
        return {"items": []}

    def send_invoice(self, invoice_id, request_id):
        return {
            "links": [
                {"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/payer"}
            ]
        }

    def get_invoice(self, invoice_id):
        return {"id": invoice_id, "status": "PAID"}

    def verify_webhook(self, headers, event):
        return self.verified

    def generate_invoice_qr_code(self, invoice_id):
        self.qr_calls.append(invoice_id)
        return {"image": base64.b64encode(b"\x89PNG\r\n\x1a\nfake-image").decode()}

    def send_invoice_reminder(self, invoice_id):
        self.reminder_calls.append(invoice_id)
        return {}


def _install_paypal(api_client, paypal):
    api_client.app.dependency_overrides[get_paypal_client] = lambda: paypal


def test_client_can_create_invoice_only_after_recorded_approval(api_client, demo_records):
    paypal = FakePaypal()
    _install_paypal(api_client, paypal)

    response = api_client.post(
        "/api/v1/payments/milestones/milestone-1/invoice",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "SENT"
    assert response.json()["amount_cents"] == 15000
    assert demo_records["milestone"].status == "PAYMENT_PENDING"


def test_provider_cannot_trigger_invoice_creation(api_client, demo_records):
    _install_paypal(api_client, FakePaypal())

    response = api_client.post(
        "/api/v1/payments/milestones/milestone-1/invoice",
        headers={"X-User-Id": "provider-user"},
    )

    assert response.status_code == 403


def test_invoice_failure_logs_redacted_details_and_returns_safe_reason(
    api_client, demo_records, caplog
):
    class FailingPaypal(FakePaypal):
        def create_invoice(self, payload, request_id):
            raise PaypalAPIError(
                "Request for payer@example.test failed at "
                "https://sandbox.invalid/?access_token=do-not-log"
            )

    _install_paypal(api_client, FailingPaypal())

    with caplog.at_level(logging.ERROR, logger="app.services.paypal.invoicing"):
        response = api_client.post(
            "/api/v1/payments/milestones/milestone-1/invoice",
            headers={"X-User-Id": "client-user"},
        )

    assert response.status_code == 502
    assert "during create_draft" in response.json()["detail"]
    assert "[redacted email]" in response.json()["detail"]
    assert "[redacted URL]" in response.json()["detail"]
    assert "payer@example.test" not in response.json()["detail"]
    assert "do-not-log" not in response.json()["detail"]
    assert "step=create_draft" in caplog.text
    assert "exception_class=PaypalAPIError" in caplog.text
    assert "status_code=none" in caplog.text
    assert "error_name=none" in caplog.text
    assert "debug_id=none" in caplog.text
    assert "payer@example.test" not in caplog.text
    assert "do-not-log" not in caplog.text


def test_invoice_failure_logs_paypal_http_diagnostics(
    api_client, demo_records, caplog
):
    class HttpFailingPaypal(FakePaypal):
        def create_invoice(self, payload, request_id):
            raise PaypalAPIError(
                "PayPal Sandbox returned HTTP 422.",
                status_code=422,
                error_name="UNPROCESSABLE_ENTITY",
                issues=("INVOICE_FIELD_INVALID",),
                debug_id="DEBUG-123",
            )

    _install_paypal(api_client, HttpFailingPaypal())

    with caplog.at_level(logging.ERROR, logger="app.services.paypal.invoicing"):
        response = api_client.post(
            "/api/v1/payments/milestones/milestone-1/invoice",
            headers={"X-User-Id": "client-user"},
        )

    assert response.status_code == 502
    assert "status_code=422" in caplog.text
    assert "error_name=UNPROCESSABLE_ENTITY" in caplog.text
    assert "issues=INVOICE_FIELD_INVALID" in caplog.text
    assert "debug_id=DEBUG-123" in caplog.text


def test_invoice_creation_without_approval_is_rejected(api_client, db, demo_records):
    db.delete(demo_records["approval"])
    db.commit()
    _install_paypal(api_client, FakePaypal())

    response = api_client.post(
        "/api/v1/payments/milestones/milestone-1/invoice",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409


def test_next_milestone_stays_locked_until_previous_is_paid(api_client, db, demo_records):
    next_milestone = Milestone(
        id="milestone-2",
        agreement_id=demo_records["agreement"].id,
        title="Development",
        order=2,
        status="PENDING",
        amount_cents=35000,
    )
    db.add(next_milestone)
    db.commit()

    response = api_client.post(
        "/api/v1/provider/agreements/agreement-1/milestones/milestone-2/start",
        headers={"X-User-Id": "provider-user"},
    )

    assert response.status_code == 409
    db.refresh(next_milestone)
    assert next_milestone.status == "PENDING"


def test_invalid_webhook_signature_does_not_change_payment_state(
    api_client, db, demo_records, caplog
):
    caplog.set_level(logging.INFO, logger="app.api.v1.webhooks")
    paypal = FakePaypal(verified=False)
    _install_paypal(api_client, paypal)
    invoice = Invoice(
        id="local-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-WEBHOOK",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    demo_records["milestone"].status = "PAYMENT_PENDING"
    db.commit()

    response = api_client.post(
        "/api/v1/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.test/cert",
            "paypal-transmission-id": "transmission-id",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-11-03T22:00:00Z",
        },
        json={
            "id": "event-invalid",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"id": "PAYPAL-INVOICE-WEBHOOK"},
        },
    )

    assert response.status_code == 400
    assert invoice.status == "SENT"
    assert demo_records["milestone"].status == "PAYMENT_PENDING"
    assert db.query(WebhookEvent).count() == 0
    delivery_log = next(
        line for line in caplog.text.splitlines()
        if "paypal_webhook_delivery" in line
    )
    assert "event_id=event-invalid" in delivery_log
    assert "event_type=INVOICING.INVOICE.PAID" in delivery_log
    assert "signature_verified=false" in delivery_log
    assert "linked_milestone=none" in delivery_log
    assert "response_code=400" in delivery_log
    assert "paypal-transmission-sig" not in delivery_log


def test_valid_paid_webhook_is_verified_processed_and_idempotent(
    api_client, db, demo_records, caplog
):
    caplog.set_level(logging.INFO, logger="app.api.v1.webhooks")
    paypal = FakePaypal()
    _install_paypal(api_client, paypal)
    invoice = Invoice(
        id="local-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-WEBHOOK",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    demo_records["milestone"].status = "PAYMENT_PENDING"
    db.commit()
    request = {
        "id": "event-paid",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {"id": "PAYPAL-INVOICE-WEBHOOK"},
    }
    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://example.test/cert",
        "paypal-transmission-id": "transmission-id",
        "paypal-transmission-sig": "signature",
        "paypal-transmission-time": "2026-11-03T22:00:00Z",
    }

    first = api_client.post("/api/v1/webhooks/paypal", headers=headers, json=request)
    duplicate = api_client.post("/api/v1/webhooks/paypal", headers=headers, json=request)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert duplicate.json()["status"] == "duplicate"
    assert invoice.status == "PAID"
    assert demo_records["milestone"].status == "PAID"
    assert db.query(WebhookEvent).count() == 1
    stored = db.query(WebhookEvent).one()
    assert stored.signature_verified is True
    assert stored.duplicate_deliveries == 1
    delivery_logs = [
        line for line in caplog.text.splitlines()
        if "paypal_webhook_delivery" in line
    ]
    assert any(
        "event_id=event-paid" in line
        and "signature_verified=true" in line
        and "linked_milestone=milestone-1" in line
        and "response_code=200" in line
        for line in delivery_logs
    )
    assert any("outcome=duplicate" in line for line in delivery_logs)
    agreement_response = api_client.get(
        "/api/v1/client/agreements/agreement-1",
        headers={"X-User-Id": "client-user"},
    )
    serialized_invoice = agreement_response.json()["milestones"][0]["invoices"][0]
    assert serialized_invoice["payment_confirmation"] == "verified_webhook"
    assert serialized_invoice["paid_at"] is not None
    assert serialized_invoice["webhook_events"] == [
        {
            "event_type": "INVOICING.INVOICE.PAID",
            "signature_verified": True,
            "processed": "processed",
            "created_at": serialized_invoice["paid_at"],
            "duplicate_deliveries": 1,
        }
    ]


def _sent_invoice(db, demo_records):
    invoice = Invoice(
        id="local-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-SENT",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    demo_records["milestone"].status = "PAYMENT_PENDING"
    db.add(invoice)
    db.commit()
    return invoice


def test_payment_totals_are_scoped_and_computed_from_invoices(api_client, db, demo_records):
    paid = Invoice(
        id="paid-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-PAID",
        paypal_request_id="paid-request",
        amount_cents=15000,
        currency="USD",
        status="PAID",
    )
    pending = Invoice(
        id="pending-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-PENDING",
        paypal_request_id="pending-request",
        amount_cents=5000,
        currency="USD",
        status="SENT",
    )
    db.add_all([paid, pending])
    db.commit()

    client_totals = api_client.get(
        "/api/v1/payments/summary", headers={"X-User-Id": "client-user"}
    )
    provider_totals = api_client.get(
        "/api/v1/payments/summary", headers={"X-User-Id": "provider-user"}
    )

    assert client_totals.status_code == 200
    assert client_totals.json() == {
        "total_invoiced_cents": 20000,
        "paid_cents": 15000,
        "pending_cents": 5000,
    }
    assert provider_totals.json() == client_totals.json()


def test_client_can_request_paypal_qr_code_only_for_sent_invoice(
    api_client, db, demo_records
):
    paypal = FakePaypal()
    invoice = _sent_invoice(db, demo_records)
    _install_paypal(api_client, paypal)

    response = api_client.post(
        f"/api/v1/payments/invoices/{invoice.id}/qr-code",
        headers={"X-User-Id": "client-user"},
    )
    denied = api_client.post(
        f"/api/v1/payments/invoices/{invoice.id}/qr-code",
        headers={"X-User-Id": "provider-user"},
    )

    assert response.status_code == 200
    assert response.json()["content_type"] == "image/png"
    assert response.json()["qr_code_base64"] == base64.b64encode(
        b"\x89PNG\r\n\x1a\nfake-image"
    ).decode()
    assert paypal.qr_calls == ["PAYPAL-INVOICE-SENT"]
    assert denied.status_code == 404


def test_qr_code_paypal_failure_returns_safe_error(api_client, db, demo_records):
    class FailingPaypal(FakePaypal):
        def generate_invoice_qr_code(self, invoice_id):
            raise PaypalAPIError(
                "PayPal Sandbox returned HTTP 422.",
                status_code=422,
                error_name="UNPROCESSABLE_ENTITY",
                debug_id="DEBUG-QR",
            )

    invoice = _sent_invoice(db, demo_records)
    _install_paypal(api_client, FailingPaypal())

    response = api_client.post(
        f"/api/v1/payments/invoices/{invoice.id}/qr-code",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "PayPal Sandbox could not generate a payment QR code."


def test_provider_reminder_is_audited_and_idempotent(api_client, db, demo_records):
    paypal = FakePaypal()
    invoice = _sent_invoice(db, demo_records)
    _install_paypal(api_client, paypal)
    request_path = f"/api/v1/payments/invoices/{invoice.id}/reminder"

    first = api_client.post(request_path, headers={"X-User-Id": "provider-user"})
    second = api_client.post(request_path, headers={"X-User-Id": "provider-user"})
    denied = api_client.post(request_path, headers={"X-User-Id": "client-user"})

    assert first.status_code == 200
    assert first.json()["status"] == "sent"
    assert second.status_code == 200
    assert second.json()["status"] == "already_sent"
    assert denied.status_code == 404
    assert paypal.reminder_calls == ["PAYPAL-INVOICE-SENT"]
    assert invoice.last_reminder_status == "sent"
    assert db.query(AuditLog).filter_by(
        action="invoice_payment_reminder_requested", entity_id=invoice.id
    ).count() == 1
    assert db.query(AuditLog).filter_by(
        action="invoice_payment_reminder_sent", entity_id=invoice.id
    ).count() == 1


def test_failed_reminder_is_not_resent_to_avoid_duplicates(api_client, db, demo_records):
    class FailingPaypal(FakePaypal):
        def send_invoice_reminder(self, invoice_id):
            self.reminder_calls.append(invoice_id)
            raise PaypalAPIError(
                "PayPal Sandbox returned HTTP 503.",
                status_code=503,
                error_name="SERVICE_UNAVAILABLE",
            )

    invoice = _sent_invoice(db, demo_records)
    paypal = FailingPaypal()
    _install_paypal(api_client, paypal)
    request_path = f"/api/v1/payments/invoices/{invoice.id}/reminder"

    failed = api_client.post(request_path, headers={"X-User-Id": "provider-user"})
    retry = api_client.post(request_path, headers={"X-User-Id": "provider-user"})

    assert failed.status_code == 502
    assert retry.status_code == 409
    assert paypal.reminder_calls == ["PAYPAL-INVOICE-SENT"]
    assert invoice.last_reminder_status == "failed"


def test_paid_webhook_extracts_invoice_id_from_nested_invoice(api_client, db, demo_records):
    paypal = FakePaypal()
    _install_paypal(api_client, paypal)
    invoice = Invoice(
        id="local-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-NESTED",
        paypal_request_id="request-nested",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    demo_records["milestone"].status = "PAYMENT_PENDING"
    db.commit()

    response = api_client.post(
        "/api/v1/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.test/cert",
            "paypal-transmission-id": "transmission-id",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-11-03T22:00:00Z",
        },
        json={
            "id": "event-paid-nested",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"invoice": {"id": "PAYPAL-INVOICE-NESTED"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert invoice.status == "PAID"
    assert demo_records["milestone"].status == "PAID"
    stored = db.query(WebhookEvent).filter_by(paypal_event_id="event-paid-nested").one()
    assert stored.resource_id == "PAYPAL-INVOICE-NESTED"


def test_verified_non_invoice_event_is_stored_and_acknowledged(api_client, db):
    _install_paypal(api_client, FakePaypal())

    response = api_client.post(
        "/api/v1/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.test/cert",
            "paypal-transmission-id": "transmission-id",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-11-03T22:00:00Z",
        },
        json={
            "id": "event-non-invoice",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {"id": "CAPTURE-123"},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    stored = db.query(WebhookEvent).filter_by(paypal_event_id="event-non-invoice").one()
    assert stored.processed == "ignored"
    assert stored.resource_id == "CAPTURE-123"


def test_verified_paid_event_for_unlinked_invoice_is_stored_and_acknowledged(
    api_client, db
):
    _install_paypal(api_client, FakePaypal())

    response = api_client.post(
        "/api/v1/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.test/cert",
            "paypal-transmission-id": "transmission-id",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-11-03T22:00:00Z",
        },
        json={
            "id": "event-unlinked-invoice",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"invoice": {"id": "PAYPAL-NOT-LINKED"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    stored = db.query(WebhookEvent).filter_by(paypal_event_id="event-unlinked-invoice").one()
    assert stored.processed == "ignored"
    assert stored.resource_id == "PAYPAL-NOT-LINKED"


def test_verified_paid_event_without_invoice_id_is_stored_and_acknowledged(api_client, db):
    _install_paypal(api_client, FakePaypal())

    response = api_client.post(
        "/api/v1/webhooks/paypal",
        headers={
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://example.test/cert",
            "paypal-transmission-id": "transmission-id",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-11-03T22:00:00Z",
        },
        json={
            "id": "event-missing-invoice-id",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"invoice": {"status": "PAID"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    stored = db.query(WebhookEvent).filter_by(
        paypal_event_id="event-missing-invoice-id"
    ).one()
    assert stored.processed == "ignored"
    assert stored.resource_id is None


def test_sync_endpoint_uses_paypal_status_and_requires_agreement_member(api_client, db, demo_records):
    paypal = FakePaypal()
    _install_paypal(api_client, paypal)
    invoice = Invoice(
        id="local-invoice",
        milestone=demo_records["milestone"],
        paypal_invoice_id="PAYPAL-INVOICE-SYNC",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="SENT",
    )
    db.add(invoice)
    demo_records["milestone"].status = "PAYMENT_PENDING"
    db.commit()

    denied = api_client.post(
        "/api/v1/payments/invoices/local-invoice/sync",
        headers={"X-User-Id": "unknown-user"},
    )
    synchronized = api_client.post(
        "/api/v1/payments/invoices/local-invoice/sync",
        headers={"X-User-Id": "client-user"},
    )

    assert denied.status_code == 401
    assert synchronized.status_code == 200
    assert synchronized.json()["status"] == "PAID"
    assert demo_records["milestone"].status == "PAID"
    agreement_response = api_client.get(
        "/api/v1/client/agreements/agreement-1",
        headers={"X-User-Id": "client-user"},
    )
    serialized_invoice = agreement_response.json()["milestones"][0]["invoices"][0]
    assert serialized_invoice["payment_confirmation"] == "manual_sync"
    assert serialized_invoice["paid_at"] is not None
    assert serialized_invoice["webhook_events"] == []
