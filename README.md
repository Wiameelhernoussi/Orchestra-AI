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
http://localhost:8000/api/v1/health. Client/provider workflow endpoints and the
real Groq + PayPal Sandbox demo runner are available in the backend. The UI
workflow is not yet implemented.

### Environment Variables
Copy `backend/.env.example` to `backend/.env`. Add credentials only when
you are ready to use the corresponding integration:
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` — from [developer.paypal.com](https://developer.paypal.com)
- `PAYPAL_WEBHOOK_ID` — webhook ID configured in your PayPal sandbox app
- `DATABASE_URL` — PostgreSQL or SQLite connection string
- `DEMO_CLIENT_PAYPAL_EMAIL` — Sandbox Personal account email that receives invoices
- `DEMO_SEED_TOKEN` — private random token required to reset and seed demo data

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
Sandbox credentials, seeded users, and a client-approved milestone are required
for an end-to-end invoice. `X-User-Id` is checked against the database, and every
agreement route verifies organization membership. The demo seed endpoint deletes
the current application records before creating the sample agreement, so use it
only with demo data.

### Phase 4 end-to-end demo

Set `DEMO_CLIENT_PAYPAL_EMAIL` and `DEMO_SEED_TOKEN` in `backend/.env`, along
with the Groq and PayPal Sandbox credentials. Generate a seed token locally
without displaying it:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$seedToken = [Convert]::ToBase64String($bytes)
$envPath = '.\backend\.env'
$tokenEntry = "DEMO_SEED_TOKEN=$seedToken"
$envLines = Get-Content $envPath
if ($envLines -match '^DEMO_SEED_TOKEN=') {
  $envLines = $envLines | ForEach-Object {
    if ($_ -match '^DEMO_SEED_TOKEN=') { $tokenEntry } else { $_ }
  }
} else {
  $envLines += $tokenEntry
}
Set-Content -Path $envPath -Value $envLines
$rng.Dispose()
Remove-Variable seedToken, tokenEntry, envLines, bytes, rng
```

Start the services, then seed the demo explicitly (the script below can also
seed automatically; do not seed separately if running it without `--no-seed`):

```powershell
docker compose up -d --build
$seedToken = ((Get-Content .\backend\.env | Where-Object { $_ -match '^DEMO_SEED_TOKEN=' } | Select-Object -First 1) -replace '^DEMO_SEED_TOKEN=', '')
$seed = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/demo/seed `
  -Headers @{ 'X-Demo-Seed-Token' = $seedToken }
Remove-Variable seedToken
$seed | Select-Object status, client_user_id, provider_user_id, agreement_id
```

Run the real Groq → review → approval → PayPal Sandbox invoice flow. `--no-seed`
uses the users created above and avoids clearing database records:

```powershell
python .\scripts\e2e_real.py --no-seed
```

The runner stops after invoice creation and prints only the milestone ID,
PayPal invoice ID, and payer-view link. Open that link and sign in with the
Sandbox **Personal** account to review and pay the $150 Design invoice. Never
use a real PayPal account for this Sandbox invoice.

After payment, retrieve the local invoice ID for synchronization and check its
status. Replace the placeholder with the milestone ID printed by the runner:

```powershell
$milestoneId = '<milestone id from e2e_real.py>'
$agreements = Invoke-RestMethod -Uri http://localhost:8000/api/v1/client/agreements `
  -Headers @{ 'X-User-Id' = 'demo-client' }
$agreement = $agreements | Where-Object { $_.milestones.id -contains $milestoneId } | Select-Object -First 1
$milestone = $agreement.milestones | Where-Object { $_.id -eq $milestoneId }
$localInvoiceId = $milestone.invoices[0].id
$sync = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/payments/invoices/$localInvoiceId/sync" `
  -Headers @{ 'X-User-Id' = 'demo-client' }
$sync | Select-Object status, milestone_id
$agreements = Invoke-RestMethod -Uri http://localhost:8000/api/v1/client/agreements `
  -Headers @{ 'X-User-Id' = 'demo-client' }
$agreement = $agreements | Where-Object { $_.milestones.id -contains $milestoneId } | Select-Object -First 1
$paidMilestone = $agreement.milestones | Where-Object { $_.id -eq $milestoneId }
$paidMilestone | Select-Object id, status
```

Expect invoice `PAID` and milestone `PAID`. A verified PayPal webhook can update
the same state automatically; `/sync` is the fallback when the webhook is not
delivered. The following milestone cannot start until this one is paid.

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
- **AI:** Groq (GPT-OSS 120B for intent; Qwen 3.8 27B for evidence with GPT-OSS 20B fallback)
- **Payments:** PayPal Invoicing API + Webhooks (Sandbox)

### Groq agent demo

Set `GROQ_API_KEY` and the model settings in `backend/.env` (see
`backend/.env.example`), then run from the repository root:

```powershell
python scripts/agents_demo.py --cache
```

The demo compares the configured intent/evidence models with
`GROQ_COMPARE_MODEL` (GPT-OSS 20B by default). `--cache` stores outputs in an
ignored local JSON file; use `--cache path\to\cache.json` for a custom path.
Cached runs do not call Groq. Each live request uses strict JSON Schema, low
reasoning effort, compact fixed demo prompts and a bounded output-token cap.
429 retries honor `Retry-After` up to `GROQ_MAX_RETRY_WAIT_SECONDS`; longer
waits fail explicitly so the script does not retry too early. Logs contain only
per-call token counts. An uncached run makes two intent and two evidence
requests (configured model plus comparison model); an additional evidence
request is made only if the primary model fails and the fallback is needed.
A repeated run with the same cache uses none.

If you change model settings while the backend container is running, recreate
it to refresh its environment:

```powershell
docker compose up -d --force-recreate backend
```

Qwen is the Evidence Agent's primary model and GPT-OSS 20B is used if Qwen
returns an API error or rate limit. The current agent interface does not send
image bytes to Groq; if image evidence is flagged, the corresponding assessment
is conservatively marked `not_verifiable`. The supported JSON Schema,
reasoning, and retry parameters were checked against Groq's official
[Structured Outputs](https://console.groq.com/docs/structured-outputs),
[Reasoning](https://console.groq.com/docs/reasoning), and
[Rate Limits](https://console.groq.com/docs/rate-limits) documentation.

## License

MIT — see [LICENSE](LICENSE).
