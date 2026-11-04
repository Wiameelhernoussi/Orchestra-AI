# Orchestra AI — Architecture

## System Overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React UI   │────▶│   FastAPI        │────▶│   PostgreSQL    │
│  (Client &   │◀────│   Backend        │◀────│   (or SQLite)   │
│   Provider)  │     │                  │     └─────────────────┘
└──────────────┘     │  ┌────────────┐  │
                     │  │ Workflow   │  │     ┌─────────────────┐
                     │  │ Engine     │  │────▶│   Groq LLM API  │
                     │  │ (FSM)      │  │     │  Intent Agent   │
                     │  └────────────┘  │     │  Evidence Agent  │
                     │                  │     └─────────────────┘
                     │  ┌────────────┐  │
                     │  │ PayPal     │  │     ┌─────────────────┐
                     │  │ Service    │◀─┼────▶│ PayPal Sandbox  │
                     │  └────────────┘  │     │ Invoicing API   │
                     └──────────────────┘     │ + Webhooks      │
                                              └─────────────────┘
```

## Data Model

- **users** — demo client/provider identities with organization membership
- **organizations** — client company & provider agency
- **agreements** — structured work agreements with FSM status
- **milestones** — sequential deliverable phases with amounts (cents)
- **acceptance_criteria** — verifiable criteria per milestone
- **evidence** — submitted proof (text, links, uploaded files)
- **approvals** — explicit human approval/rejection records
- **invoices** — PayPal invoice tracking with idempotency keys
- **webhook_events** — raw PayPal webhook payloads for audit
- **audit_logs** — append-only log of every action

## State Machines

### Agreement: DRAFT → PROPOSED → ACTIVE → COMPLETED
Provider refusal transitions PROPOSED → REJECTED. A milestone remains APPROVED
when invoice creation fails; a retryable invoice operation can return INVOICING
to APPROVED. Cancelled or expired invoices are recorded explicitly and may be
retried. Milestones are sequential: milestone N+1 cannot start until N is PAID.

### Milestone: PENDING → IN_PROGRESS → IN_REVIEW → APPROVED → INVOICING → PAYMENT_PENDING → PAID

See state machine source code in `backend/app/state_machine/` for all transitions,
guards, and role checks.

Amounts are stored as integer cents. Invoice creation uses a stable
`PayPal-Request-Id` (persisted on the invoice) and is separate from the human
approval action.

The demo role switcher is UI-only in this phase. Before workflow APIs are added,
the backend must resolve `X-User-Id` to a seeded user and verify that user's
organization is a member of the requested agreement; audit-log access follows
the same check.

## AI Agents

### Intent Agent
- Model: `meta-llama/llama-3.3-70b-versatile` (text, via Groq)
- Input: natural language business request
- Output: structured JSON (Pydantic-validated)
- Never invents: missing info listed under `missing_information`

### Evidence Agent
- Model: `meta-llama/llama-4-scout-17b-16e-instruct` (vision-capable, via Groq)
- Input: acceptance criteria + evidence (text, links, screenshots)
- Output: per-criterion verdict + overall assessment
- Advisory only — client makes final decision

## PayPal Integration
- Sandbox-only OAuth 2.0 client; production PayPal API hosts are rejected.
- `POST /api/v1/payments/milestones/{milestone_id}/invoice` requires a
  database-verified client user, agreement membership, and a recorded human
  approval. Invoice creation and sending are retryable and use persisted
  `PayPal-Request-Id` values.
- `POST /api/v1/webhooks/paypal` verifies the PayPal transmission signature with
  PayPal before processing `INVOICING.INVOICE.PAID` or
  `INVOICING.INVOICE.CANCELLED`. It extracts invoice IDs from supported
  resource shapes, persists all verified events (including ignored/unlinked
  events), and acknowledges those events with HTTP 200. Event IDs are persisted
  for idempotent replay; logs record event IDs, event types, verification and
  processing outcomes without logging headers or full payloads.
- `POST /api/v1/payments/invoices/{invoice_id}/sync` reads the invoice directly
  from PayPal for an agreement member; it does not trust a browser redirect.
- Amounts remain integer cents in the database and use `Decimal` for API values.

Configure the active tunnel as the Sandbox app's webhook URL:
`https://mutable-levitate-alkaline.ngrok-free.dev/api/v1/webhooks/paypal`.
Subscribe to the paid and cancelled invoice events and configure the generated
webhook ID as `PAYPAL_WEBHOOK_ID` in `backend/.env`. Use a sandbox Business
account as the invoicer and the sandbox Personal account as payer.

## Approved Phase Plan

1. **Scaffold and workflow core:** PostgreSQL, FastAPI health check, SQLAlchemy
   models and first migration, deterministic state machines with tests, and
   client/provider dashboard routing.
2. **PayPal Sandbox:** implement invoice creation with a stable
   `PayPal-Request-Id`, cancellation/expiry handling, signature-verified
   webhooks, and a PayPal API invoice-status sync endpoint. Validate a real
   sandbox payment by a sandbox buyer with the webhook delivered through a
   public tunnel; webhook replay is for automated tests only.
3. **AI agents:** keep the Intent Agent on a configurable text model and use a
   configurable vision-capable model for screenshot evidence. Re-check model
   availability in the official [Groq model catalog](https://console.groq.com/docs/models)
   before implementation. Missing details remain explicit; evidence output is
   advisory.
4. **Workflow API:** add DB-verified `X-User-Id` demo identity, seed client and
   provider accounts, enforce agreement organization membership on every
   operation (including audit logs), then connect the API to the state machine,
   agents, invoices, and audit log.
5. **Demo UI:** implement the request/review flow, local evidence uploads and
   sample screenshots, human approval, invoice retry, and payment status.
6. **Hackathon delivery:** publish the MIT-licensed repository, prepare a
   sub-three-minute demo video/script, and write the Devpost submission. Confirm
   the official submission deadline before scheduling this phase.

The Phase 2 payment demo uses PayPal Sandbox only. Automated tests replace the
HTTP transport with deterministic responses and never issue invoices. Approval
is persisted independently of invoice creation, and all monetary values use
integer cents.
