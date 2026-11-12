from app.api.deps import get_paypal_client, get_settings
from app.api.v1.paywall import get_paywall_recommendation_provider
from app.config import Settings
from app.models.paywall_purchase import PaywallPurchase
from app.services.groq_agents import AgentResult, TokenUsage
from app.services.mock_integrations import MockPaypalClient


class FakePayPal:
    def __init__(self):
        self.order_calls = []
        self.capture_calls = []
        self.capture_result = None

    def create_order(self, payload, request_id):
        self.order_calls.append((payload, request_id))
        return {
            "id": "SANDBOX-ORDER-1",
            "status": "CREATED",
            "links": [
                {
                    "rel": "payer-action",
                    "href": "https://www.sandbox.paypal.com/checkoutnow?token=SANDBOX-ORDER-1",
                }
            ],
        }

    def capture_order(self, order_id, request_id):
        self.capture_calls.append((order_id, request_id))
        return self.capture_result or {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "SANDBOX-CAPTURE-1",
                                "status": "COMPLETED",
                                "amount": {"currency_code": "USD", "value": "1.99"},
                            }
                        ]
                    }
                }
            ],
        }

    def get_order(self, order_id):
        return self.capture_result or {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "SANDBOX-CAPTURE-1",
                                "status": "COMPLETED",
                                "amount": {"currency_code": "USD", "value": "1.99"},
                            }
                        ]
                    }
                }
            ],
        }


class FakeRecommendationProvider:
    def __init__(self, response=None):
        self.response = response or {
            "recommendations": [
                {
                    "id": "focus-workflows",
                    "reason": "It matches the selected productivity topic and budget.",
                },
                {
                    "id": "safe-ai",
                    "reason": "It fits the budget and may also interest you.",
                },
            ]
        }
        self.calls = []

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        return AgentResult(self.response, TokenUsage(0, 0, 0))


def _install(api_client, paypal, provider=None):
    api_client.app.dependency_overrides[get_settings] = lambda: Settings(
        PAYWALL_ASSISTANT_ENABLED=True,
    )
    api_client.app.dependency_overrides[get_paypal_client] = lambda: paypal
    if provider is not None:
        api_client.app.dependency_overrides[get_paywall_recommendation_provider] = lambda: provider


def test_paywall_endpoints_are_not_found_when_feature_flag_is_disabled(api_client, demo_records):
    assert Settings().PAYWALL_ASSISTANT_ENABLED is False
    for mode in ("mock", "real"):
        api_client.app.dependency_overrides[get_settings] = lambda mode=mode: Settings(
            DEMO_MODE=mode,
        )
        responses = [
            api_client.post(
                "/api/v1/paywall/recommendations",
                headers={"X-User-Id": "client-user"},
                json={"topics": ["productivity"], "max_budget_cents": 500},
            ),
            api_client.post(
                "/api/v1/paywall/purchases",
                headers={"X-User-Id": "client-user"},
                json={
                    "offer_id": "focus-workflows",
                    "max_budget_cents": 500,
                    "user_confirmed_purchase": True,
                },
            ),
            api_client.post(
                "/api/v1/paywall/purchases/not-a-real-purchase/capture",
                headers={"X-User-Id": "client-user"},
            ),
        ]
        assert [response.status_code for response in responses] == [404, 404, 404]


def _recommend(api_client, user_id="client-user"):
    return api_client.post(
        "/api/v1/paywall/recommendations",
        headers={"X-User-Id": user_id},
        json={"topics": ["productivity"], "max_budget_cents": 500},
    )


def _start_purchase(api_client):
    return api_client.post(
        "/api/v1/paywall/purchases",
        headers={"X-User-Id": "client-user", "Origin": "http://localhost:5173"},
        json={
            "offer_id": "focus-workflows",
            "max_budget_cents": 500,
            "user_confirmed_purchase": True,
        },
    )


def test_recommendations_use_groq_but_never_purchase(api_client, demo_records):
    paypal = FakePayPal()
    provider = FakeRecommendationProvider()
    _install(api_client, paypal, provider)

    response = api_client.post(
        "/api/v1/paywall/recommendations",
        headers={"X-User-Id": "client-user"},
        json={"topics": ["productivity"], "max_budget_cents": 500},
    )

    assert response.status_code == 200
    assert response.json()["assistant_mode"] == "groq_ai"
    assert response.json()["recommendations"][0]["id"] == "focus-workflows"
    assert response.json()["recommendations"][1]["id"] == "safe-ai"
    assert provider.calls[0]["schema_name"] == "paywall_recommendations"
    assert paypal.order_calls == []


def test_recommendations_discard_ai_offers_outside_budget(api_client, demo_records):
    provider = FakeRecommendationProvider(
        {
            "recommendations": [
                {"id": "safe-ai", "reason": "Try this more expensive content."},
                {"id": "focus-workflows", "reason": "Fits."},
            ]
        }
    )
    _install(api_client, FakePayPal(), provider)

    response = api_client.post(
        "/api/v1/paywall/recommendations",
        headers={"X-User-Id": "client-user"},
        json={"topics": ["productivity"], "max_budget_cents": 300},
    )

    assert response.status_code == 200
    assert [offer["id"] for offer in response.json()["recommendations"]] == [
        "focus-workflows"
    ]


def test_recommendations_are_client_only(api_client, demo_records):
    _install(api_client, FakePayPal(), FakeRecommendationProvider())

    response = _recommend(api_client, user_id="provider-user")

    assert response.status_code == 403


def test_purchase_requires_explicit_confirmation_and_budget(api_client, demo_records):
    paypal = FakePayPal()
    _install(api_client, paypal)
    declined = api_client.post(
        "/api/v1/paywall/purchases",
        headers={"X-User-Id": "client-user"},
        json={
            "offer_id": "focus-workflows",
            "max_budget_cents": 500,
            "user_confirmed_purchase": False,
        },
    )
    over_budget = api_client.post(
        "/api/v1/paywall/purchases",
        headers={"X-User-Id": "client-user"},
        json={
            "offer_id": "safe-ai",
            "max_budget_cents": 300,
            "user_confirmed_purchase": True,
        },
    )

    assert declined.status_code == 409
    assert over_budget.status_code == 409
    assert paypal.order_calls == []


def test_purchase_create_is_idempotent_and_returns_sandbox_approval(api_client, demo_records):
    paypal = FakePayPal()
    _install(api_client, paypal)

    first = _start_purchase(api_client)
    retry = _start_purchase(api_client)

    assert first.status_code == 200
    assert first.json()["status"] == "PENDING"
    assert first.json()["approval_url"].startswith("https://www.sandbox.paypal.com/")
    assert retry.json() == first.json()
    assert len(paypal.order_calls) == 1
    purchase = demo_records["db"].query(PaywallPurchase).one()
    assert paypal.order_calls[0][1] == purchase.create_request_id
    assert paypal.order_calls[0][0]["intent"] == "CAPTURE"
    assert paypal.order_calls[0][0]["purchase_units"][0]["amount"]["value"] == "1.99"


def test_demo_reset_removes_paywall_purchases_before_reseeding(api_client, demo_records):
    api_client.app.dependency_overrides[get_settings] = lambda: Settings(
        DEMO_MODE="mock",
        DEMO_SEED_TOKEN="",
    )
    seeded = api_client.post(
        "/api/v1/demo/seed",
        headers={"X-User-Id": "demo-client"},
    ).json()
    purchase = PaywallPurchase(
        user_id=seeded["client_user_id"],
        offer_id="focus-workflows",
        create_request_id="demo-reset-create",
        capture_request_id="demo-reset-capture",
        amount_cents=199,
    )
    demo_records["db"].add(purchase)
    demo_records["db"].commit()

    reset = api_client.post(
        "/api/v1/demo/seed",
        headers={"X-User-Id": seeded["client_user_id"]},
    )

    assert reset.status_code == 200
    assert (
        demo_records["db"]
        .query(PaywallPurchase)
        .filter(PaywallPurchase.user_id == seeded["client_user_id"])
        .count()
        == 0
    )


def test_provider_cannot_create_content_purchase(api_client, demo_records):
    paypal = FakePayPal()
    _install(api_client, paypal)

    response = api_client.post(
        "/api/v1/paywall/purchases",
        headers={"X-User-Id": "provider-user"},
        json={
            "offer_id": "focus-workflows",
            "max_budget_cents": 500,
            "user_confirmed_purchase": True,
        },
    )

    assert response.status_code == 403
    assert paypal.order_calls == []


def test_content_unlocks_only_after_matching_paypal_capture_and_is_idempotent(
    api_client, demo_records
):
    paypal = FakePayPal()
    _install(api_client, paypal)
    purchase_response = _start_purchase(api_client)
    purchase_id = purchase_response.json()["purchase_id"]

    unlocked = api_client.post(
        f"/api/v1/paywall/purchases/{purchase_id}/capture",
        headers={"X-User-Id": "client-user"},
    )
    retry = api_client.post(
        f"/api/v1/paywall/purchases/{purchase_id}/capture",
        headers={"X-User-Id": "client-user"},
    )

    assert unlocked.status_code == 200
    assert unlocked.json()["status"] == "CAPTURED"
    assert unlocked.json()["content"]
    assert retry.json() == unlocked.json()
    assert len(paypal.capture_calls) == 1
    assert paypal.capture_calls[0][1] == (
        demo_records["db"].query(PaywallPurchase).one().capture_request_id
    )


def test_content_does_not_unlock_for_unconfirmed_payment(api_client, demo_records):
    paypal = FakePayPal()
    paypal.capture_result = {
        "id": "SANDBOX-ORDER-1",
        "status": "APPROVED",
        "purchase_units": [],
    }
    _install(api_client, paypal)
    purchase_id = _start_purchase(api_client).json()["purchase_id"]

    response = api_client.post(
        f"/api/v1/paywall/purchases/{purchase_id}/capture",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409
    assert "content" not in response.json()
    purchase = demo_records["db"].query(PaywallPurchase).one()
    assert purchase.status == "PENDING"


def test_purchase_cannot_be_captured_by_another_user(api_client, demo_records):
    _install(api_client, FakePayPal())
    purchase_id = _start_purchase(api_client).json()["purchase_id"]

    response = api_client.post(
        f"/api/v1/paywall/purchases/{purchase_id}/capture",
        headers={"X-User-Id": "provider-user"},
    )

    assert response.status_code == 403


def test_mock_mode_does_not_simulate_paywall_purchase(api_client, demo_records):
    _install(api_client, MockPaypalClient())

    response = _start_purchase(api_client)

    assert response.status_code == 409
    assert "real PayPal Sandbox mode" in response.json()["detail"]


def test_capture_response_must_match_expected_amount(api_client, demo_records):
    paypal = FakePayPal()
    _install(api_client, paypal)
    purchase_id = _start_purchase(api_client).json()["purchase_id"]
    paypal.capture_result = {
        "id": "SANDBOX-ORDER-1",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "SANDBOX-CAPTURE-1",
                            "status": "COMPLETED",
                            "amount": {"currency_code": "USD", "value": "9.99"},
                        }
                    ]
                }
            }
        ],
    }

    response = api_client.post(
        f"/api/v1/paywall/purchases/{purchase_id}/capture",
        headers={"X-User-Id": "client-user"},
    )

    assert response.status_code == 409
    assert demo_records["db"].query(PaywallPurchase).one().status == "PENDING"
