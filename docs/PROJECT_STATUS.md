# Orchestra AI — Project Status

**Audit date:** 2026-11-04  
**Target submission:** 2026-11-11  
**Hackathon deadline supplied by the team:** Thursday, 2026-11-12 at 12:00 pm Pacific Time

This is a read-only audit of the repository and the running local Compose stack.
The only repository file added for this audit is this report. No raw values from
`backend/.env` were displayed, copied, logged, or included. One configuration
import from the backend directory caused the application settings loader to
read the file transiently; only boolean “configured” checks were printed. This
was outside the requested boundary, so no further access was made.

## Executive summary

The core prototype is implemented: agreement parsing, stateful client/provider
workflow, evidence review, explicit client approval, PayPal Sandbox invoices,
webhook processing, and client/provider dashboards are present. Docker is
currently running and the API health endpoint returns healthy.

At the time of this audit, the backend suite had one failing test;
screenshot/image evidence was not sent to Qwen; and no full browser journey
ending in a real Sandbox payment confirmed by the webhook (with no manual sync)
was verified. The frontend builds and its small unit suite passes. GitHub
reports the repository as public with an MIT license, but the YouTube video and
Devpost submission are not present in the repository.

## 1. Git state

- **Branch:** `main`, tracking `origin/main`.
- **Remote divergence:** 0 commits ahead, 0 behind at audit time.
- **Remote visibility:** GitHub reports `Wiameelhernoussi/Orchestra-AI` as
  public; the repository metadata reports MIT.
- **Last commits** (the repository has four commits, fewer than 15):
  1. `b50b66b` — 2026-11-04 — Phase 4: end-to-end workflow, demo identities, invoice-milestone link
  2. `17b9595` — 2026-11-04 — Phase 3: Groq Intent and Evidence agents, demo script with cache
  3. `7d83915` — 2026-11-04 — Phase 2: PayPal sandbox invoicing, webhooks, fix invoice id extraction
  4. `14a0123` — 2026-11-03 — Phase 1: scaffolding, models, state machines
- **Uncommitted at the start of this audit:** 29 modified tracked files and 14
  untracked paths. Changes span the README; backend workflow, payment, AI,
  configuration, and tests; Compose; and most frontend application surfaces.
  New paths include the evidence link checker and migration, mock integrations,
  their tests, and UI/API components (AG Grid, advisory, milestone, invoice,
  and status components). These changes predate this audit and were not altered.
  This report is an additional new file.
- `backend/.env` is ignored and not tracked.

## 2. Planned phase status

| Phase | Status | Evidence / remaining verification |
|---|---|---|
| 1. Scaffolding and state machines | **Done** | FastAPI app and health route in `backend/app/main.py`; SQLAlchemy models, Alembic migrations, and state machine tests in `backend/app/`, `backend/alembic/`, and `backend/tests/test_state_machines.py`. |
| 2. PayPal Sandbox | **Partial** | Invoice, retry, sync, signature verification, idempotent webhook processing, and simulated API tests exist in `backend/app/services/paypal/`, `backend/app/api/v1/payments.py`, `backend/app/api/v1/webhooks.py`, and `backend/tests/test_paypal_api.py`. A real payment delivered by PayPal's webhook has not been verified. |
| 3. Groq agents | **Partial** | Intent and advisory Evidence agents, criteria quality assessment, and model configuration exist in `backend/app/services/groq_agents.py` and `backend/app/config.py`. Image evidence is explicitly not attached to model requests, so screenshot analysis is absent. Live model behavior is not established by the automated suite. |
| 4. End-to-end workflow | **Partial** | Client/provider workflow, approval gate, audit trail, and invoice linkage are implemented in `backend/app/api/v1/workflow.py` and `backend/app/api/v1/payments.py`. `scripts/e2e_real.py` stops after creating the first invoice; the real payment-to-webhook journey remains unverified. |
| 5. Frontend | **Partial** | Client/provider flow and dashboards exist under `frontend/src/pages/`; reusable tables and workflow components are under `frontend/src/components/`. Build succeeds, but only three frontend unit tests exist and no full browser-flow test was found. Evidence input is text/links, not screenshot upload/analysis. |
| 6. Polish and submission | **Partial** | Public GitHub repository, tracked MIT `LICENSE`, English README, architecture document, and demo scripts exist. No hosted demo URL, YouTube video, or completed Devpost submission was found in the repository. Documentation still has stale plan details and a specific tunnel address that should be reviewed. |

## 3. What works now

### Tests and build

- **Backend:** `python -m pytest -q` — **97 passed, 1 failed** (98 total).
  Failing test: `backend/tests/test_paypal_api.py::test_invoice_creation_without_approval_is_rejected`.
  It expected HTTP 409 but received 503. That test does not install the fake
  PayPal dependency used by the other payment tests. With default `DEMO_MODE`
  set to `real`, PayPal dependency initialization can fail before the handler
  reaches its approval check. Isolate the test with the existing fake/mock
  dependency and rerun the suite.
- **Frontend:** `npm test -- --run` in `frontend/` — **3 passed** in 2 test
  files.
- **Frontend production build:** `npm run build` — TypeScript check and Vite
  build succeeded. Vite warns that the main minified JS chunk exceeds 500 kB.
- Backend test output also had pytest/pytest-asyncio deprecation warnings.

### Local services and health

`docker compose ps` showed the PostgreSQL and backend services healthy and the
frontend service running. `GET http://localhost:8000/api/v1/health` returned
`healthy`; the running stack reports `DEMO_MODE=real`. This confirms the
currently running stack, not a clean, zero-key mock-mode startup.

### API endpoint inventory

All paths below are under `/api/v1`.

**Client**

- `POST /client/intents/parse`
- `POST /client/agreements`
- `POST /client/agreements/{agreement_id}/publish`
- `GET /client/agreements`
- `GET /client/agreements/{agreement_id}`
- `POST /client/agreements/{agreement_id}/milestones/{milestone_id}/approve`
- `POST /client/agreements/{agreement_id}/milestones/{milestone_id}/revision`

**Provider**

- `GET /provider/agreements`
- `GET /provider/agreements/{agreement_id}`
- `POST /provider/agreements/{agreement_id}/accept`
- `POST /provider/agreements/{agreement_id}/refuse`
- `POST /provider/agreements/{agreement_id}/milestones/{milestone_id}/start`
- `POST /provider/agreements/{agreement_id}/milestones/{milestone_id}/evidence`
- `POST /provider/agreements/{agreement_id}/milestones/{milestone_id}/submit`

**Payments**

- `POST /payments/milestones/{milestone_id}/invoice`
- `POST /payments/invoices/{invoice_id}/sync`

**Webhooks**

- `POST /webhooks/paypal`

**Demo and shared**

- `POST /demo/seed`
- `GET /agreements/{agreement_id}/audit-logs`
- `GET /health`

## 4. Checklist: present versus missing

| Requirement | Finding |
|---|---|
| Judge/mock mode with zero AI/payment API keys | **Implemented and documented.** `backend/app/api/deps.py` selects `DemoMockProvider` and `MockPaypalClient` when `DEMO_MODE=mock`; the README's mock setup selects that mode. The Compose default is `real`, so a zero-key launch must explicitly select mock mode. A clean zero-key startup was not run during this audit. |
| AG Grid tables | **Present.** `frontend/package.json` includes AG Grid; `frontend/src/components/DataGrid.tsx` is used by client/provider dashboards and milestone/invoice-related views. |
| Criteria quality check in Intent Agent | **Present.** `backend/app/services/groq_agents.py` adds/validates criteria quality; `frontend/src/pages/client/NewAgreementWizard.tsx` surfaces rewrite suggestions. |
| Evidence link facts with SSRF protection | **Present.** `backend/app/services/evidence_facts.py` checks HTTPS, rejects non-public DNS answers, pins the checked IP, revalidates redirects, and bounds response size/time. `backend/tests/test_evidence_facts.py` covers private/mixed DNS, redirect-to-private, size limits, and pinned connections using mocked transports. |
| Screenshot analysis with Qwen | **Missing.** Qwen is configured for evidence assessment, but `groq_agents.py` says image evidence is not attached and normalizes image-dependent criteria to `not_verifiable`. No upload route or frontend screenshot flow was found. |
| English README and setup in under five minutes | **Present with qualification.** `README.md` is English and says setup takes under five minutes once Docker images are cached; first image downloads can take longer. A fresh setup was not timed. |
| Architecture document | **Present, needs refresh.** `docs/architecture.md` describes the system, but its phase plan does not match the implementation and it contains a specific tunnel URL. |
| Public repo and visible open-source license | **Present.** GitHub reports the repository as public and MIT-licensed; root `LICENSE` is tracked. |
| `.env.example` uses placeholders | **Present.** Credential/token entries use placeholders; other entries are non-secret local or Sandbox defaults. This report does not disclose any example values. |
| Demo-flow scripts | **Present, incomplete coverage.** `scripts/agents_demo.py`, `scripts/paypal_smoke.py`, and `scripts/e2e_real.py` exist. The real workflow runner ends after the first invoice, not after webhook-confirmed payment. |

## 5. Known issues, risks, and TODOs

1. **Backend suite is not green.** Fix the one payment test's dependency setup;
   verify that it asserts the approval guard rather than depending on real
   PayPal configuration.
2. **No verified real Sandbox end-to-end payment.** Webhook tests use a fake
   PayPal verifier and synthetic events. There is no recorded browser journey
   in which a Sandbox payer pays and the verified webhook marks the milestone
   `PAID` without using the manual invoice-sync button.
3. **Screenshot evidence is not analyzed.** The intended vision model is
   configured, but the Evidence Agent receives text and trusted link facts, not
   image bytes. File storage is not equivalent to model-based screenshot
   inspection.
4. **No browser-level regression suite was found.** Current frontend tests
   cover only a small number of components; there is no automated full client
   to provider to client journey.
5. **Demo identity is not production authentication.** The README documents
   `X-User-Id` as demo-only. Do not present this prototype as production
   authorization.
6. **Docs drift.** `docs/architecture.md` has a stale phase plan, a specific
   tunnel URL, and a phase description that does not reflect the existing UI.
   The README's five-minute setup claim is conditional on cached Docker images.
7. **Frontend bundle size warning.** The production build succeeds, but its
   main JS chunk is over Vite's 500 kB warning threshold.
8. **Submission assets remain unverified.** No YouTube video link or completed
   Devpost submission was found. The README contains a walkthrough, not the
   required under-three-minute hosted demo video.
9. **Live integrations were not exercised in this audit.** Current Compose
   health verifies API/database reachability only; it does not prove Groq,
   PayPal invoice creation, PayPal signature verification against a live
   Sandbox delivery, or the public webhook tunnel.

## 6. Prioritized next steps through November 11

Estimates are relative effort: **S** = a few hours or less, **M** = about a
day, **L** = multi-step integration/testing effort.

| Order | Target | Size | Next step |
|---:|---|:---:|---|
| 1 | Nov 5 | S | Fix the failing backend payment test by overriding `get_paypal_client` with the test fake; rerun all backend tests. |
| 2 | Nov 5 | S | Run the documented mock-mode Compose setup from a clean terminal with no Groq/PayPal keys; execute the README walkthrough and record any setup friction. |
| 3 | Nov 5 | S | Update `docs/architecture.md`: remove/replace the stale tunnel URL, align phase statuses with reality, and state plainly that screenshot bytes are not analyzed. |
| 4 | Nov 6 | M | Add or execute a browser-level mock workflow check covering parse, proposal, provider evidence, human approval, invoice creation, and simulated payment. |
| 5 | Nov 6–7 | M | Decide whether screenshot analysis is essential for judging. If yes, implement and test safe image upload/validation and actual image input to the selected vision model; otherwise make the limitation clear in the demo narrative. |
| 6 | Nov 7–8 | L | Run a real Sandbox buyer payment through the browser; verify the public HTTPS webhook, signature validation, event linkage, and `PAID` transition without manual sync. Capture non-secret test evidence. |
| 7 | Nov 9 | S | Re-run backend tests, frontend tests/build, mock startup, and README steps; resolve release-blocking failures and warnings where feasible. |
| 8 | Nov 10 | M | Record and publish an English YouTube walkthrough under three minutes; verify it is accessible to judges and matches the currently working demo. |
| 9 | Nov 11 | M | Complete and verify the Devpost submission, public repository/license visibility, demo link, and final English submission materials before the planned submission date. |

## Audit boundaries

The initial read-only audit did not directly open or print `backend/.env`,
change application code or configuration, issue PayPal transactions, contact
Groq, or trigger a real webhook. The settings-loader access noted at the top
was transient and produced no raw values. Its runtime integration observations
were limited to the local health response and Compose service status.

## Follow-up — invoice failure fix

On November 4, the invoice failure was reproduced through the API on the
specified milestone. The first failing step was `find_existing_invoice`: the
successful PayPal search response had no body, which the client represented as
an empty object and the workflow incorrectly rejected. Treating an empty
successful search response as no matches allowed the flow to reach draft
creation.

PayPal's Invoicing API creates a draft with HTTP 201 but returns the invoice
representation only when the request includes `Prefer: return=representation`.
The client omitted that header, returned an empty object, and the workflow
could not obtain the created invoice ID. The header is now sent on draft
creation. The same persisted `PayPal-Request-Id` is reused for retries, and
invoice sending keeps its deterministic request ID. The exact API retry
completed successfully; a subsequent retry returned successfully and the
database still had one `SENT` invoice row for the milestone. No payment was
made.

- **Reproduced failure:** step `create_draft`; exception `PaypalAPIError`;
  redacted message `PayPal Sandbox did not return an invoice ID.`; no HTTP
  error status, PayPal error name, or debug ID was available.
- **Backend tests after fix:** 103 passed. One existing pytest deprecation
  warning remains.
- **Groq fallback diagnostics:** now include HTTP status, exception type, and
  classified failure kind. Tests cover rate limit (429), model error (503),
  and format error (HTTP 200 with invalid response content). Recent runtime
  logs contained a legacy `GroqAPIError` fallback entry without an HTTP status;
  that rules out the explicit 429 and response-format exception types, but does
  not distinguish an HTTP/model error from a transport failure. No live Qwen
  failure was induced during this follow-up.
- **Changed implementation/tests:** `backend/app/services/paypal/client.py`,
  `backend/app/services/paypal/invoicing.py`,
  `backend/app/api/v1/payments.py`, `backend/app/services/groq_agents.py`,
  and their corresponding backend tests.
