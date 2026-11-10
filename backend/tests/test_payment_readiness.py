import json

from app.models import Approval, Evidence, Invoice
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
