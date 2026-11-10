import json

from app.models import Approval, AuditLog, Evidence, Invoice, Milestone, User
from app.services.payment_readiness import calculate_payment_readiness


def test_complete_milestone_and_client_approval_are_payment_ready(demo_records):
    readiness = calculate_payment_readiness(
        demo_records["db"], demo_records["milestone"]
    )

    assert readiness["status"] == "READY_FOR_PAYMENT"
    assert readiness["ready"] is True
    assert readiness["score"] == 100
    assert readiness["checks"][8]["complete"] is True


def test_missing_evidence_blocks_payment(demo_records):
    db = demo_records["db"]
    db.query(Evidence).filter_by(
        milestone_id=demo_records["milestone"].id
    ).delete()

    readiness = calculate_payment_readiness(db, demo_records["milestone"])

    assert readiness["status"] == "BLOCKED"
    assert readiness["ready"] is False
    assert "Evidence has not been submitted." in readiness["blocking_reasons"]


def test_incomplete_evidence_blocks_payment(demo_records):
    db = demo_records["db"]
    evidence = db.query(Evidence).filter_by(
        milestone_id=demo_records["milestone"].id
    ).one()
    report = json.loads(evidence.ai_report)
    report["criteria_results"][0]["status"] = "missing"
    evidence.ai_report = json.dumps(report)

    readiness = calculate_payment_readiness(db, demo_records["milestone"])

    assert readiness["status"] == "BLOCKED"
    assert readiness["criteria_summary"]["unverified"] == 1
    assert "1 acceptance criteria remain unverified." in readiness["blocking_reasons"]


def test_ai_verification_without_client_approval_is_not_payment_ready(demo_records):
    db = demo_records["db"]
    db.query(Approval).filter_by(
        milestone_id=demo_records["milestone"].id
    ).delete()

    readiness = calculate_payment_readiness(db, demo_records["milestone"])

    assert readiness["status"] == "READY_FOR_APPROVAL"
    assert readiness["ready"] is False
    assert readiness["checks"][8]["complete"] is False


def test_client_must_acknowledge_unverified_evidence_before_approval(api_client, demo_records):
    db = demo_records["db"]
    evidence = db.query(Evidence).filter_by(
        milestone_id=demo_records["milestone"].id
    ).one()
    report = json.loads(evidence.ai_report)
    report["criteria_results"][0]["status"] = "missing"
    evidence.ai_report = json.dumps(report)
    db.query(Approval).filter_by(
        milestone_id=demo_records["milestone"].id
    ).delete()
    demo_records["milestone"].status = "IN_REVIEW"
    db.commit()

    response = api_client.post(
        "/api/v1/client/agreements/agreement-1/milestones/milestone-1/approve",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["acknowledge_unverified_required"] is True
    assert response.json()["detail"]["unverified_criteria"] == [
        {"criterion": "Design files are provided.", "status": "missing"}
    ]
    assert db.query(Approval).filter_by(
        milestone_id=demo_records["milestone"].id
    ).count() == 0


def test_invoice_endpoint_rejects_direct_request_when_readiness_is_false(
    api_client, demo_records
):
    db = demo_records["db"]
    evidence = db.query(Evidence).filter_by(
        milestone_id=demo_records["milestone"].id
    ).one()
    report = json.loads(evidence.ai_report)
    report["criteria_results"][0]["status"] = "missing"
    evidence.ai_report = json.dumps(report)
    db.commit()

    response = api_client.post(
        "/api/v1/payments/milestones/milestone-1/invoice",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409
    assert "acceptance criteria remain unverified" in response.json()["detail"]
    assert db.query(Invoice).count() == 0


def test_readiness_endpoint_returns_authoritative_state(api_client, demo_records):
    response = api_client.get(
        "/api/v1/milestones/milestone-1/payment-readiness",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "READY_FOR_PAYMENT"
    assert response.json()["approval_status"] == "APPROVED"
    assert response.json()["approval_details"]["approver_name"] == "Alice Chen"
    assert response.json()["approval_details"]["advisory_overridden"] is False
    assert response.json()["webhook_payment_confirmed"] is False
    assert response.json()["next_milestone_unlocked"] is True
    assert isinstance(response.json()["client_next_action"], str)
    assert isinstance(response.json()["provider_next_action"], str)


def test_paid_milestone_is_fully_complete_and_unlocks_next_milestone(demo_records):
    db = demo_records["db"]
    milestone = demo_records["milestone"]
    milestone.status = "PAID"
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

    readiness = calculate_payment_readiness(db, milestone)

    assert readiness["status"] == "PAID"
    assert readiness["score"] == 100
    assert readiness["next_milestone_title"] == "Development"
    assert readiness["next_milestone_unlocked"] is True


def test_readiness_marks_only_paid_webhook_as_webhook_confirmation(db, demo_records):
    invoice = Invoice(
        id="readiness-invoice",
        milestone_id=demo_records["milestone"].id,
        paypal_invoice_id="PAYPAL-INVOICE-1",
        paypal_request_id="request-id",
        amount_cents=15000,
        currency="USD",
        status="PAID",
    )
    sync_event = AuditLog(
        agreement_id=demo_records["agreement"].id,
        action="invoice_status_synchronized",
        entity_type="invoice",
        entity_id=invoice.id,
        details='{"source":"paypal_api"}',
    )
    db.add_all([invoice, sync_event])
    db.commit()

    readiness = calculate_payment_readiness(db, demo_records["milestone"])
    assert readiness["webhook_payment_confirmed"] is False

    sync_event.action = "paypal_invoice_status_updated"
    sync_event.details = '{"status":"PAID"}'
    db.commit()
    readiness = calculate_payment_readiness(db, demo_records["milestone"])
    assert readiness["webhook_payment_confirmed"] is True


def test_ai_role_cannot_approve_milestone(api_client, db, demo_records):
    ai_user = User(
        id="ai-user",
        name="Evidence Agent",
        email="evidence-agent@example.test",
        role="ai",
        organization_id=demo_records["agreement"].client_org_id,
    )
    db.add(ai_user)
    db.commit()
    demo_records["milestone"].status = "IN_REVIEW"
    db.commit()

    response = api_client.post(
        "/api/v1/client/agreements/agreement-1/milestones/milestone-1/approve",
        headers={"X-User-Id": "ai-user"},
        json={"acknowledge_unverified": True},
    )

    assert response.status_code == 403
    assert db.query(Approval).filter_by(
        milestone_id=demo_records["milestone"].id,
        approved_by=ai_user.id,
    ).count() == 0


def test_provider_role_cannot_approve_milestone(api_client, db, demo_records):
    demo_records["milestone"].status = "IN_REVIEW"
    db.commit()

    response = api_client.post(
        "/api/v1/client/agreements/agreement-1/milestones/milestone-1/approve",
        headers={"X-User-Id": "provider-user"},
        json={"acknowledge_unverified": True},
    )

    assert response.status_code == 403
    assert db.query(Approval).filter_by(
        milestone_id=demo_records["milestone"].id,
        approved_by=demo_records["provider"].id,
    ).count() == 0
