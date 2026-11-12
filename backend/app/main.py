from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.payments import router as payments_router
from app.api.v1.paywall import router as paywall_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workflow import client_router, provider_router, router as workflow_router
from app.database import engine
from app.config import settings

app = FastAPI(
    title="Orchestra AI",
    description="From intent to agreement. From evidence to approval. From approval to payment.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router, prefix="/api/v1")
app.include_router(paywall_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(client_router, prefix="/api/v1")
app.include_router(provider_router, prefix="/api/v1")
app.include_router(workflow_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {
        "status": "healthy",
        "service": "orchestra-ai",
        "demo_mode": settings.DEMO_MODE,
    }
