from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import get_db
from app.models.user import User
from app.services.groq_agents import DemoMockProvider, GroqAgentClient
from app.services.evidence_facts import EvidenceFactChecker
from app.services.paypal.client import PaypalClient, PaypalConfigurationError
from app.services.mock_integrations import MockPaypalClient


def get_settings() -> Settings:
    return settings


def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id is required.")
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo user.")
    return user


def get_paypal_client(
    config: Settings = Depends(get_settings),
) -> Generator[PaypalClient | MockPaypalClient, None, None]:
    if config.DEMO_MODE == "mock":
        yield MockPaypalClient()
        return
    try:
        client = PaypalClient(config)
    except PaypalConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        yield client
    finally:
        client.close()


def get_completion_provider(
    config: Settings = Depends(get_settings),
) -> Generator[GroqAgentClient | DemoMockProvider, None, None]:
    if config.DEMO_MODE == "mock":
        yield DemoMockProvider()
        return
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Groq is not configured.")
    client = GroqAgentClient(
        config.GROQ_API_KEY,
        max_retries=config.GROQ_MAX_RETRIES,
        max_retry_wait_seconds=config.GROQ_MAX_RETRY_WAIT_SECONDS,
    )
    try:
        yield client
    finally:
        client.close()


def get_evidence_fact_checker():
    checker = EvidenceFactChecker()
    try:
        yield checker
    finally:
        checker.close()
