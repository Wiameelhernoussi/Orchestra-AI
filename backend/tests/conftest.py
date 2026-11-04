import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Agreement, Approval, Milestone, Organization, User


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api_client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def demo_records(db):
    client_org = Organization(id="client-org", name="ShopFlow Inc")
    provider_org = Organization(id="provider-org", name="DevStudio Agency")
    client_user = User(
        id="client-user",
        name="Alice Chen",
        email="alice@example.test",
        role="client",
        organization=client_org,
    )
    provider_user = User(
        id="provider-user",
        name="Bob Martinez",
        email="bob@example.test",
        role="provider",
        organization=provider_org,
    )
    agreement = Agreement(
        id="agreement-1",
        title="E-commerce website",
        total_amount_cents=60000,
        currency="USD",
        client_org_id=client_org.id,
        provider_org_id=provider_org.id,
        created_by=client_user.id,
    )
    milestone = Milestone(
        id="milestone-1",
        agreement=agreement,
        title="Design",
        order=1,
        status="APPROVED",
        amount_cents=15000,
    )
    approval = Approval(
        id="approval-1",
        milestone=milestone,
        approved_by=client_user.id,
        decision="approved",
    )
    db.add_all(
        [
            client_org,
            provider_org,
            client_user,
            provider_user,
            agreement,
            milestone,
            approval,
        ]
    )
    db.commit()
    return {
        "db": db,
        "client": client_user,
        "provider": provider_user,
        "agreement": agreement,
        "milestone": milestone,
        "approval": approval,
    }
