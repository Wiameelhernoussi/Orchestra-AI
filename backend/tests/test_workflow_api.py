from __future__ import annotations

from app.api.deps import get_completion_provider, get_paypal_client, get_settings
from app.config import Settings
from app.models import Agreement, Approval, Milestone
from app.services.groq_agents import MockProvider
from app.services.paypal.client import PaypalAPIError


INTENT = {
    "project_type": "E-commerce website",
    "requirements": ["Website for an e-commerce company"],
    "budget_cents": 60000,
    "currency": "USD",
    "deadline": "",
    "missing_information": ["Website feature scope", "Project deadline"],
    "milestones": [
        {
            "title": "Design",
            "amount_cents": 15000,
            "deliverables": ["Responsive designs"],
            "acceptance_criteria": ["Desktop and mobile layouts are provided"],
        },
        {
            "title": "Development",
            "amount_cents": 35000,
            "deliverables": ["Working website"],
            "acceptance_criteria": ["Agreed features work in staging"],
        },
        {
            "title": "Final Handover",
            "amount_cents": 10000,
            "deliverables": ["Source code and instructions"],
            "acceptance_criteria": ["Source code and deployment guide are delivered"],
        },
    ],
}

EVIDENCE_RESULT = {
    "criteria_results": [],
    "overall_verdict": "partial",
    "report": "Advisory test report.",
}


class FakePaypal:
    def __init__(self, fail_first_create: bool = False) -> None:
        self.fail_first_create = fail_first_create
        self.create_calls: list[tuple[str, str]] = []
        self.statuses: dict[str, str] = {}

    def create_invoice(self, payload, request_id):
        self.create_calls.append((payload["detail"]["invoice_number"], request_id))
        if self.fail_first_create and len(self.create_calls) == 1:
            raise PaypalAPIError("Simulated PayPal failure.")
        invoice_id = f"PAYPAL-{len(self.create_calls)}"
        self.statuses[invoice_id] = "SENT"
        return {"id": invoice_id}

    def send_invoice(self, invoice_id, _request_id):
        assert _request_id
        return {
            "links": [
                {"rel": "payer-view", "href": f"https://sandbox.example/{invoice_id}"}
            ]
        }

    def get_invoice(self, invoice_id):
        return {"id": invoice_id, "status": self.statuses[invoice_id]}


def _setup_demo(api_client, provider, paypal):
    settings = Settings(
        DEMO_SEED_TOKEN="test-seed-token",
        DEMO_CLIENT_PAYPAL_EMAIL="sandbox-client@example.test",
    )
    api_client.app.dependency_overrides[get_settings] = lambda: settings
    api_client.app.dependency_overrides[get_completion_provider] = lambda: provider
    api_client.app.dependency_overrides[get_paypal_client] = lambda: paypal
    response = api_client.post(
        "/api/v1/demo/seed",
        headers={"X-Demo-Seed-Token": "test-seed-token"},
    )
    assert response.status_code == 200
    return response.json()


def _headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def test_demo_seed_protects_reset_endpoint(api_client):
    api_client.app.dependency_overrides[get_settings] = lambda: Settings(
        DEMO_SEED_TOKEN="",
    )
    response = api_client.post("/api/v1/demo/seed")
    assert response.status_code == 503

    api_client.app.dependency_overrides[get_settings] = lambda: Settings(
        DEMO_SEED_TOKEN="test-seed-token",
        DEMO_CLIENT_PAYPAL_EMAIL="sandbox-client@example.test",
    )
    response = api_client.post(
        "/api/v1/demo/seed",
        headers={"X-Demo-Seed-Token": "wrong"},
    )
    assert response.status_code == 401


def test_full_demo_flow_uses_human_approval_and_sequential_payments(
    api_client, db
):
    provider = MockProvider([INTENT, EVIDENCE_RESULT, EVIDENCE_RESULT, EVIDENCE_RESULT])
    paypal = FakePaypal()
    seeded = _setup_demo(api_client, provider, paypal)
    client_headers = _headers(seeded["client_user_id"])
    provider_headers = _headers(seeded["provider_user_id"])
    agreement_id = seeded["agreement_id"]

    parsed = api_client.post(
        "/api/v1/client/intents/parse",
        headers=client_headers,
        json={"request": "Build an e-commerce website for $600."},
    )
    assert parsed.status_code == 200
    assert parsed.json()["budget_cents"] == 60000
    created = api_client.post(
        "/api/v1/client/agreements",
        headers=client_headers,
        json={"intent": parsed.json()},
    )
    assert created.status_code == 201
    agreement_id = created.json()["id"]
    assert api_client.post(
        f"/api/v1/client/agreements/{agreement_id}/publish",
        headers=client_headers,
    ).status_code == 200
    assert api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/accept",
        headers=provider_headers,
    ).status_code == 200

    blocked = api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/milestones/{created.json()['milestones'][1]['id']}/start",
        headers=provider_headers,
    )
    assert blocked.status_code == 409

    for index, milestone in enumerate(created.json()["milestones"]):
        path = f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone['id']}"
        started = api_client.post(f"{path}/start", headers=provider_headers)
        assert started.status_code == 200
        wrong_role_submit = api_client.post(
            f"{path}/evidence",
            headers=client_headers,
            json={"text": "The client cannot submit provider evidence."},
        )
        assert wrong_role_submit.status_code == 403
        evidence = api_client.post(
            f"{path}/evidence",
            headers=provider_headers,
            json={"text": "Completed the agreed deliverable."},
        )
        assert evidence.status_code == 200
        assert evidence.json()["milestone_status"] == "IN_PROGRESS"
        submitted = api_client.post(f"{path}/submit", headers=provider_headers)
        assert submitted.status_code == 200
        wrong_role_approval = api_client.post(
            f"/api/v1/client/agreements/{agreement_id}/milestones/{milestone['id']}/approve",
            headers=provider_headers,
        )
        assert wrong_role_approval.status_code == 403
        approved = api_client.post(
            f"/api/v1/client/agreements/{agreement_id}/milestones/{milestone['id']}/approve",
            headers=client_headers,
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"
        invoice_response = api_client.post(
            f"/api/v1/payments/milestones/{milestone['id']}/invoice",
            headers=client_headers,
        )
        assert invoice_response.status_code == 200
        assert invoice_response.json()["status"] == "SENT"
        assert invoice_response.json()["amount_cents"] == milestone["amount_cents"]
        assert api_client.get(
            f"/api/v1/client/agreements/{agreement_id}",
            headers=client_headers,
        ).json()["milestones"][index]["status"] == "PAYMENT_PENDING"
        paypal.statuses[invoice_response.json()["paypal_invoice_id"]] = "PAID"
        synced = api_client.post(
            f"/api/v1/payments/invoices/{invoice_response.json()['id']}/sync",
            headers=provider_headers,
        )
        assert synced.status_code == 200
        assert synced.json()["status"] == "PAID"

    agreement = db.get(Agreement, agreement_id)
    assert agreement.status == "COMPLETED"
    assert [item.status for item in agreement.milestones] == ["PAID", "PAID", "PAID"]
    assert all(
        item["ai_report"]["overall_verdict"] == "insufficient"
        for item in api_client.get(
            f"/api/v1/client/agreements/{agreement_id}",
            headers=client_headers,
        ).json()["milestones"]
        for item in item["evidence"]
    )
    assert provider.calls[0]["schema_name"] == "business_intent"
    assert len(provider.calls) == 4
    logs = api_client.get(
        f"/api/v1/agreements/{agreement_id}/audit-logs",
        headers=client_headers,
    )
    assert logs.status_code == 200
    assert any(item["action"] == "agreement_completed" for item in logs.json())


def test_invoice_failure_can_be_retried_without_losing_approval(
    api_client, db
):
    provider = MockProvider([EVIDENCE_RESULT])
    paypal = FakePaypal(fail_first_create=True)
    seeded = _setup_demo(api_client, provider, paypal)
    client_headers = _headers(seeded["client_user_id"])
    provider_headers = _headers(seeded["provider_user_id"])
    agreement_id = seeded["agreement_id"]
    milestone_id = seeded["milestone_ids"][0]

    assert api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/accept",
        headers=provider_headers,
    ).status_code == 200
    assert api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/start",
        headers=provider_headers,
    ).status_code == 200
    assert api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/evidence",
        headers=provider_headers,
        json={"text": "Design mockups are ready."},
    ).status_code == 200
    assert api_client.post(
        f"/api/v1/provider/agreements/{agreement_id}/milestones/{milestone_id}/submit",
        headers=provider_headers,
    ).status_code == 200
    assert api_client.post(
        f"/api/v1/client/agreements/{agreement_id}/milestones/{milestone_id}/approve",
        headers=client_headers,
    ).status_code == 200

    failed = api_client.post(
        f"/api/v1/payments/milestones/{milestone_id}/invoice",
        headers=client_headers,
    )
    assert failed.status_code == 502
    milestone = db.get(Milestone, milestone_id)
    assert milestone.status == "APPROVED"
    assert db.query(Approval).filter_by(
        milestone_id=milestone_id,
        decision="approved",
    ).count() == 1

    retried = api_client.post(
        f"/api/v1/payments/milestones/{milestone_id}/invoice",
        headers=client_headers,
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "SENT"
    assert len(paypal.create_calls) == 2
    assert paypal.create_calls[0][1] == paypal.create_calls[1][1]
