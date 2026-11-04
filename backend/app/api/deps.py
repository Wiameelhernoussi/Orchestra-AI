from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import get_db
from app.models.user import User
from app.services.paypal.client import PaypalClient, PaypalConfigurationError


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
) -> Generator[PaypalClient, None, None]:
    try:
        client = PaypalClient(config)
    except PaypalConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        yield client
    finally:
        client.close()
