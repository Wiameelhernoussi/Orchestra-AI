# Orchestra AI

**From intent to agreement. From evidence to approval. From approval to payment.**

Orchestra AI turns a business request into a structured work agreement with
milestones, measurable acceptance criteria, evidence review, and traceable
PayPal payments. This prototype was built for the PayPal AI Hackathon 2026.

## The problem

Freelance and agency projects often begin with vague requests and end with
unclear deliverables, difficult approval conversations, and payment follow-up
spread across email and payment portals.

## The solution

Orchestra AI structures the request into milestones and acceptance criteria,
collects provider evidence, and gives the client an advisory evidence report.
The client—not the AI—decides whether to approve. Only after that explicit
approval can the system create a standard PayPal invoice. Verified PayPal
webhooks update payment state; an invoice-sync endpoint is available as a
fallback.

Provider evidence requires a written description and can optionally include
URLs and private PNG/JPEG/WebP/PDF attachments. Link checks are bounded and
SSRF-protected; they report limited observations such as reachability and page
title (and public GitHub repository/root-file metadata), not proof of deliverable
contents or criterion relevance. Uploaded files are available to agreement
members for download, but this prototype does not inspect image or PDF contents.
The AI labels its results advisory, and client approval remains required.

## Architecture

- **Frontend:** React, TypeScript, Vite, and AG Grid Community dashboards.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, and Alembic.
- **Database:** PostgreSQL in Docker Compose; SQLite is available for local
  backend tests.
- **AI:** Groq behind an injectable provider interface. The demo has a
  deterministic mock provider; the real Intent Agent uses GPT-OSS 120B and the
  Evidence Agent uses Qwen 3.8 27B with GPT-OSS 20B fallback.
  Real-mode PNG/JPEG attachments can receive separate advisory image analysis
  with Qwen 3.8 27B; images are re-encoded as JPEG at up to 768 px and at most
  two are sent per request. Image contents are treated as untrusted data.
  The request uses Groq's documented
  [`image_url` data-URL format](https://console.groq.com/docs/vision).
  `EVIDENCE_IMAGE_ANALYSIS` defaults on in real mode and off in mock mode;
  mock mode returns an explicitly labeled canned result without sending images.
- **Payments:** Standard PayPal Invoicing API and verified webhooks in Sandbox.
  Mock mode uses a fake payment client and never contacts PayPal.
- **Workflow:** Plain-code state machines enforce roles, client approval, and
  sequential milestones. A deterministic Payment Readiness Engine derives
  blockers from persisted agreement, evidence, approval, and invoice records;
  invoice creation rechecks eligibility on the backend.

## Permission matrix

| Action | AI | Provider | Client | System | PayPal |
|---|---|---|---|---|---|
| Structure the request | Structures intent | — | Supplies request | Runs agent | — |
| Create agreement proposal | — | — | Submits proposal | Stores proposal | — |
| Submit evidence | — | Submits | — | Stores submission | — |
| Analyze evidence | Advisory only | — | — | Runs and stores advisory | — |
| Request revision | — | — | Requests | Records request | — |
| Approve work | — | — | Human decision | Records approval | — |
| Create invoice | — | — | Requests | Creates after recorded client approval | — |
| Authorize payment | — | — | Pays invoice | — | Processes payment |
| Confirm payment | — | — | — | Records verified status | Reports status / webhook |

Invoice creation is server-side and requires a recorded client approval. The AI
never approves work, creates invoices, or confirms payment. Payment state is
updated from a verified PayPal webhook or a status read from PayPal.

## Quick setup: mock mode

Requirements: Docker Desktop with Docker Compose. No Groq or PayPal credentials
are needed. Once Docker's base images are cached, these steps take under five
minutes; the first build may take longer while Docker downloads images and
dependencies.

```powershell
git clone <repository-url>
cd Orchestra-AI
$env:DEMO_MODE = 'mock'
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). The first run creates the
database and applies migrations. Choose **Reset demo** to seed the sample
$600 e-commerce agreement. The top bar marks **Mock mode · simulated
payments**. Mock payment status changes to `PAID` when you select the sync
action; it does not represent a PayPal transaction.
The frontend container runs `npm ci` on startup so its persistent dependency
volume stays synchronized with `frontend/package-lock.json`.

To stop the app, press `Ctrl+C` or run `docker compose down`. The database
volume is retained unless explicitly removed.

## Run with real Groq and PayPal Sandbox

1. Copy `backend/.env.example` to `backend/.env`.
2. Replace the placeholder values for `GROQ_API_KEY`,
   `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`,
   `DEMO_CLIENT_PAYPAL_EMAIL`, and `DEMO_SEED_TOKEN` with your own local
   credentials and values. Use a PayPal **Sandbox** REST app and a Sandbox
   Personal account. Never commit `backend/.env`.
3. In PowerShell, select real mode and start the services:

   ```powershell
   $env:DEMO_MODE = 'real'
   docker compose up --build
   ```

4. Seed the demo with the local seed token configured in `backend/.env`:

   ```powershell
   $seedToken = ((Get-Content .\backend\.env | Where-Object { $_ -match '^DEMO_SEED_TOKEN=' } | Select-Object -First 1) -replace '^DEMO_SEED_TOKEN=', '')
   Invoke-RestMethod -Method Post `
     -Uri http://localhost:8000/api/v1/demo/seed `
     -Headers @{ 'X-Demo-Seed-Token' = $seedToken } | Select-Object status, agreement_id
   Remove-Variable seedToken
   ```

The UI is at `http://localhost:5173`; API health is at
`http://localhost:8000/api/v1/health`. To run Docker on alternate host ports,
set `UI_PORT`, `API_PORT`, or `POSTGRES_PORT` before `docker compose up`.
Agreement members can inspect a milestone's derived readiness at
`GET /api/v1/milestones/{milestone_id}/payment-readiness`. A client must review
the submitted evidence and explicitly approve before invoicing. If the AI
advisory is not sufficient or criteria remain unverified, the client must
acknowledge that limitation; the AI never approves or unlocks payment.

For webhooks, configure the PayPal Sandbox app's webhook URL to the publicly
reachable HTTPS endpoint `https://<your-public-host>/api/v1/webhooks/paypal`
and subscribe to the invoice events supported by this application. Use a
temporary HTTPS tunnel only for development. Payment status is based on
verified webhook events or the explicit PayPal invoice-sync fallback.

## Three-minute demo walkthrough

1. In **Client**, choose **New agreement**, review the prefilled e-commerce
   request, analyze it, check missing information and proposed milestone
   criteria, then propose the agreement.
2. Switch to **Provider**, accept the proposal, start **Design**, submit a
   description and any evidence links, then submit it for review. The seeded
   Design milestone includes visual file criteria and a public HTTPS preview
   reachability criterion; link checks confirm reachability only, not visual
   quality or criterion compliance.
3. Switch to **Client**. Review the deterministic link facts and the Evidence
   Agent's advisory report. Edit the revision-request draft if needed. Approve
   the deliverable explicitly.
4. In mock mode, use **Simulate mock payment** and observe the milestone update.
   In real mode, create the Sandbox invoice, pay it using the Sandbox Personal
   account, and return to the agreement. The page polls while payment is
   pending; **Refresh status** syncs if the webhook has not arrived.
5. Continue with the next milestone only after the prior milestone is paid.
   Agreement, milestone, invoice, and audit tables support sorting and
   filtering.

## Environment variables

The complete variable list and safe placeholders are in
[`backend/.env.example`](backend/.env.example). The primary settings are:

| Variable | Purpose |
|---|---|
| `DEMO_MODE` | `mock` for zero-key judge mode; `real` for Groq and PayPal Sandbox |
| `DATABASE_URL` | Database connection; Docker Compose supplies PostgreSQL |
| `GROQ_API_KEY` | Groq API key, required only in real mode |
| `GROQ_INTENT_MODEL` | Intent model (default `openai/gpt-oss-120b`) |
| `GROQ_EVIDENCE_MODEL` | Evidence model (default `qwen/qwen3.8-27b`) |
| `GROQ_EVIDENCE_FALLBACK_MODEL` | Evidence fallback (default `openai/gpt-oss-20b`) |
| `EVIDENCE_IMAGE_ANALYSIS` | Enable real-mode PNG/JPEG image analysis (defaults on in real mode; no external image call in mock mode) |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | PayPal Sandbox REST app credentials |
| `PAYPAL_WEBHOOK_ID` | Sandbox webhook identifier for signature verification |
| `DEMO_CLIENT_PAYPAL_EMAIL` | Sandbox Personal payer email used for invoices |
| `DEMO_SEED_TOKEN` | Locally generated token that protects initial demo seeding |
| `PAYPAL_MODE` / `PAYPAL_BASE_URL` | Keep set to `sandbox` and PayPal's Sandbox API URL |

Compose's `DEMO_MODE` is selected from the host environment. For local
development in PowerShell, set `$env:DEMO_MODE = 'mock'` or
`$env:DEMO_MODE = 'real'` in the same terminal before starting Compose.

## Local checks

```powershell
Set-Location backend
python -m pip install -e ".[dev]"
python -m pytest -q

Set-Location ..\frontend
npm ci
npm run build
npm test
```

## Limitations

- **Not escrow:** this application creates ordinary PayPal invoices and does
  not hold funds.
- **Image analysis is advisory:** PNG/JPEG observations do not prove
  authenticity or functionality. Other file contents are not analyzed, and
  links are not inspected beyond reachability and limited metadata.
- **Not a legal contract:** agreements are structured project records, not
  legally binding documents or e-signatures.
- **Demo authentication only:** `X-User-Id` identifies seeded demo users; it
  is not production authentication or authorization.
- **AI is advisory:** model and link-check outputs do not establish that work
  meets a criterion. The client must review evidence and approve explicitly.
- **Mock payments are simulated:** mock mode has no PayPal connection and
  should not be presented as a real payment.
- **Sandbox only:** real integration is intended for PayPal Sandbox, not
  production payments. This MVP has no disputes, escrow, or autonomous
  financial actions.
- **Link checks are limited observations:** HTTPS links are checked with
  bounded requests and public-IP validation. HTTP status, page title, and
  selected GitHub repository metadata do not prove authorship, correctness,
  safety of page content, or acceptance-criteria compliance. GitHub root-file
  checks are informational only.

## License

MIT — see [`LICENSE`](LICENSE).
