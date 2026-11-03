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
- Groq and PayPal Sandbox credentials are only needed for later agent/payment phases

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
APIs, authentication, AI agents, or PayPal operations.

### Environment Variables
Copy `backend/.env.example` to `backend/.env`. Add credentials only when
implementing the corresponding later phase:
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` — from [developer.paypal.com](https://developer.paypal.com)
- `PAYPAL_WEBHOOK_ID` — webhook ID configured in your PayPal sandbox app
- `DATABASE_URL` — PostgreSQL or SQLite connection string

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
