# Orchestra AI

> **From intent to agreement. From evidence to approval. From approval to payment.**
> *Proof-to-Pay Intelligence*

Orchestra AI turns a natural-language business request into a structured work
agreement with milestones, verifiable deliverables, and traceable PayPal
payments.

Built for the **PayPal AI Hackathon 2026**.

## Core Principles

1. **AI never decides alone.** The client always approves deliverables. No payment
   is triggered without explicit human approval.
2. **Deterministic workflow engine.** Status transitions, role checks, and invoicing
   triggers are plain code (state machine), not LLM decisions.
3. **AI doesn't invent.** Missing information is flagged and asked for — never fabricated.
4. **Honest framing.** This is NOT escrow. We use standard PayPal invoicing. The
   agreement is a structured work agreement, not a legally binding contract.
5. **Verified payments.** Payment status comes from PayPal webhooks, never from
   the user returning to our site.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker Desktop (recommended), or PostgreSQL for a local backend
- Groq credentials are needed in the AI phase. PayPal Sandbox credentials are
  needed only to create/pay a real Sandbox invoice; tests use mocked responses.

### Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/orchestra-ai.git
cd orchestra-ai

# Configure the backend (placeholders work for Phase 1)
cp backend/.env.example backend/.env

# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### With Docker
```bash
cp backend/.env.example backend/.env
docker-compose up --build
```

The frontend is available at http://localhost:5173, the API at
http://localhost:8000, and the API health check at
http://localhost:8000/api/v1/health. Phase 1 does not yet include agreement
management APIs or AI agents. The PayPal Sandbox integration is available for
persisted, client-approved milestones.

### Environment Variables
Copy `backend/.env.example` to `backend/.env`. Add credentials only when
you are ready to use the corresponding integration:
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` — from [developer.paypal.com](https://developer.paypal.com)
- `PAYPAL_WEBHOOK_ID` — webhook ID configured in your PayPal sandbox app
- `DATABASE_URL` — PostgreSQL or SQLite connection string

### PayPal Sandbox (Phase 2)

The backend must be publicly reachable over HTTPS for PayPal webhooks. Register
this URL in the Sandbox app under **Webhooks**:

```text
https://mutable-levitate-alkaline.ngrok-free.dev/api/v1/webhooks/paypal
```

Subscribe to `INVOICING.INVOICE.PAID` and
`INVOICING.INVOICE.CANCELLED`, then put the webhook ID shown by PayPal in
`backend/.env` as `PAYPAL_WEBHOOK_ID` and recreate the backend container:

```powershell
docker compose up -d --force-recreate backend
```

`POST /api/v1/payments/milestones/{milestone_id}/invoice` requires `X-User-Id`
for a client user in the agreement and a recorded client approval. It creates
and sends a real Sandbox invoice; do not call it until you intend to issue one.
If creation or sending fails, approval remains recorded and the same request can
be retried without duplicating the invoice.

`POST /api/v1/payments/invoices/{invoice_id}/sync` reads the invoice from PayPal
and is available to an agreement member. `POST /api/v1/webhooks/paypal` is
public, but every event's signature is verified through PayPal before the
database is updated. Replayed/forged test payloads do not confirm payment.
`X-User-Id` is a database-checked demo identity header, not production
authentication.
Sandbox credentials, an existing agreement, seeded users, and an approved
milestone are required for an end-to-end invoice; seed/workflow APIs are planned
for a later phase.

An OAuth `401` means PayPal rejected the configured client ID/secret. Ensure
they are a matching pair from the Sandbox REST API app (not the Sandbox
account's login password); do not share them in chat or commit them.

Run the integration tests without using real credentials or creating invoices:

```powershell
cd backend
python -m pytest -q
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system design.

## Stack
- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI + SQLAlchemy + Alembic
- **Database:** PostgreSQL (SQLite for local dev)
- **AI:** Groq LLM (Llama 3.3 for intent, Llama 4 Scout for vision)
- **Payments:** PayPal Invoicing API + Webhooks (Sandbox)

## License

MIT — see [LICENSE](LICENSE).
