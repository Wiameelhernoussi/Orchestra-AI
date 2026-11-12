from typing import Any


OFFERS: tuple[dict[str, Any], ...] = (
    {
        "id": "focus-workflows",
        "title": "A practical guide to focused work",
        "topic": "productivity",
        "price_cents": 199,
        "currency": "USD",
        "preview": "A concise guide to planning a small project without losing momentum.",
        "content": (
            "Start with one outcome. Break it into steps that can be reviewed "
            "independently, and agree on what evidence will demonstrate completion. "
            "Protect focused time by grouping similar tasks and keeping the next "
            "action visible. At the end of each work session, record what changed, "
            "what remains uncertain, and the smallest useful next step."
        ),
    },
    {
        "id": "clear-briefs",
        "title": "Writing a clear project brief",
        "topic": "freelancing",
        "price_cents": 299,
        "currency": "USD",
        "preview": "Turn a broad request into milestones, acceptance checks, and useful evidence.",
        "content": (
            "A useful brief names the audience, intended outcome, constraints, and "
            "decision maker. Divide work into milestones that produce observable "
            "outputs. For each output, write a check that another person can apply "
            "without guessing. Agree on review timing, revision limits, and how "
            "changes to scope will be handled before work begins."
        ),
    },
    {
        "id": "safe-ai",
        "title": "A short introduction to safer AI workflows",
        "topic": "artificial-intelligence",
        "price_cents": 399,
        "currency": "USD",
        "preview": "Keep people in control when AI helps inspect or summarize work.",
        "content": (
            "Treat model output as a suggestion, not authority. Keep untrusted "
            "documents and images separate from system instructions, minimize "
            "sensitive data sent to external services, and make uncertainty visible. "
            "Require a person to review consequential decisions. Log the evidence "
            "and decision path so errors can be understood and corrected."
        ),
    },
)


def recommend_offers(
    topics: list[str],
    max_budget_cents: int,
) -> list[dict[str, Any]]:
    normalized_topics = {topic.strip().lower() for topic in topics if topic.strip()}
    eligible = [
        offer for offer in OFFERS
        if offer["price_cents"] <= max_budget_cents
    ]
    ranked = sorted(
        eligible,
        key=lambda offer: (
            offer["topic"] not in normalized_topics,
            offer["price_cents"],
            offer["id"],
        ),
    )
    return [
        {
            "id": offer["id"],
            "title": offer["title"],
            "topic": offer["topic"],
            "price_cents": offer["price_cents"],
            "currency": offer["currency"],
            "preview": offer["preview"],
            "reason": (
                f"Matches your interest in {offer['topic']} and fits your budget."
                if offer["topic"] in normalized_topics
                else "Fits your budget; choose topics above to personalize the order."
            ),
        }
        for offer in ranked
    ]


def get_offer(offer_id: str) -> dict[str, Any] | None:
    return next((offer for offer in OFFERS if offer["id"] == offer_id), None)
