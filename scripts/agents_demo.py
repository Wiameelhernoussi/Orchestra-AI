from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.services.groq_agents import (  # noqa: E402
    AgentOutputCache,
    EvidenceAgent,
    GroqAgentClient,
    IntentAgent,
)

REQUEST = (
    "Build an e-commerce website for $600: Design $150, Development $350, "
    "Final Handover $100. No deadline was provided."
)
CRITERIA = [
    "The design is responsive on mobile and desktop.",
    "A customer can add a product to the cart and complete a test checkout.",
    "The provider hands over source code and deployment instructions.",
]
EVIDENCE = (
    "Submitted: a Figma design link showing desktop and mobile layouts; a staging "
    "URL where adding a product to the cart and test checkout succeeds; a source "
    "repository link and deployment README."
)


class CachedAgentRunner:
    def __init__(
        self,
        client: GroqAgentClient,
        cache: AgentOutputCache,
    ) -> None:
        self.client = client
        self.cache = cache

    def intent(self, model: str, settings: Settings) -> dict[str, Any]:
        task = {
            "request": REQUEST,
            "max_completion_tokens": settings.GROQ_INTENT_MAX_COMPLETION_TOKENS,
            "reasoning_effort": settings.GROQ_REASONING_EFFORT,
            "prompt_version": 3,
        }
        cached = self.cache.get(model, "intent", task)
        if cached is not None:
            return cached
        result = IntentAgent(
            self.client,
            model=model,
            max_completion_tokens=settings.GROQ_INTENT_MAX_COMPLETION_TOKENS,
            reasoning_effort=settings.GROQ_REASONING_EFFORT,
        ).parse(REQUEST)
        self.cache.put(model, "intent", task, result.data)
        return result.data

    def evidence(
        self,
        model: str,
        settings: Settings,
        *,
        fallback_model: str | None = None,
    ) -> dict[str, Any]:
        task = {
            "criteria": CRITERIA,
            "evidence": EVIDENCE,
            "max_completion_tokens": settings.GROQ_EVIDENCE_MAX_COMPLETION_TOKENS,
            "reasoning_effort": settings.GROQ_REASONING_EFFORT,
            "fallback_model": fallback_model,
            "prompt_version": 2,
        }
        cached = self.cache.get(model, "evidence", task)
        if cached is not None:
            return cached
        result = EvidenceAgent(
            self.client,
            model=model,
            fallback_model=fallback_model,
            max_completion_tokens=settings.GROQ_EVIDENCE_MAX_COMPLETION_TOKENS,
            reasoning_effort=settings.GROQ_REASONING_EFFORT,
        ).assess(CRITERIA, EVIDENCE)
        self.cache.put(model, "evidence", task, result.data)
        return result.data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run and compare Groq agents on the Orchestra e-commerce demo."
    )
    parser.add_argument(
        "--cache",
        nargs="?",
        const=str(ROOT / "scripts" / ".agents_demo_cache.json"),
        metavar="PATH",
        help="read/write agent outputs to this JSON cache (default path if omitted)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings(_env_file=BACKEND_DIR / ".env")
    if not settings.GROQ_API_KEY:
        print(
            "GROQ_API_KEY is missing. Set it in backend/.env or the environment.",
            file=sys.stderr,
        )
        return 2

    cache_path = Path(args.cache).resolve() if args.cache else None
    client = GroqAgentClient(
        settings.GROQ_API_KEY,
        max_retries=settings.GROQ_MAX_RETRIES,
        max_retry_wait_seconds=settings.GROQ_MAX_RETRY_WAIT_SECONDS,
    )
    try:
        cache = AgentOutputCache(str(cache_path) if cache_path else None)
        runner = CachedAgentRunner(client, cache)
        comparison_model = settings.GROQ_COMPARE_MODEL
        results = {
            "configured_models": {
                "intent": settings.GROQ_INTENT_MODEL,
                "evidence": settings.GROQ_EVIDENCE_MODEL,
            },
            "comparison_model": comparison_model,
            "intent": {
                settings.GROQ_INTENT_MODEL: runner.intent(
                    settings.GROQ_INTENT_MODEL, settings
                ),
                comparison_model: runner.intent(comparison_model, settings),
            },
            "evidence": {
                settings.GROQ_EVIDENCE_MODEL: runner.evidence(
                    settings.GROQ_EVIDENCE_MODEL,
                    settings,
                    fallback_model=settings.GROQ_EVIDENCE_FALLBACK_MODEL,
                ),
                comparison_model: runner.evidence(
                    comparison_model,
                    settings,
                ),
            },
        }
        print(json.dumps(results, indent=2, ensure_ascii=True))
        if cache_path:
            print(f"\nCached outputs: {cache_path}")
        return 0
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
