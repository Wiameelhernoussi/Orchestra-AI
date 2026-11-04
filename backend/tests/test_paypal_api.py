import logging

from app.api.deps import get_paypal_client
from app.models.invoice import Invoice
from app.models.webhook import WebhookEvent


class FakePaypal:
    def __init__(self, verified=True):
        self.verified = verified
        self.created = []

    def create_invoice(self, payload, request_id):
        self.created.append((payload, request_id))
        return {"id": "PAYPAL-INVOICE-API"}

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


def test_invoice_creation_without_approval_is_rejected(api_client, db, demo_records):
    db.delete(demo_records["approval"])
    db.commit()

    response = api_client.post(
        "/api/v1/payments/milestones/milestone-1/invoice",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409


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
