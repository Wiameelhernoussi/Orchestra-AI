export type Role = 'client' | 'provider';
export type MilestoneStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'IN_REVIEW'
  | 'REVISION_REQUESTED'
  | 'APPROVED'
  | 'INVOICING'
  | 'PAYMENT_PENDING'
  | 'PAID'
  | 'INVOICE_CANCELLED'
  | 'INVOICE_EXPIRED';
export type AgreementStatus =
  | 'DRAFT'
  | 'PROPOSED'
  | 'ACTIVE'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'REJECTED';

export interface EvidenceReport {
  criteria_results: {
    criterion: string;
    status: 'verified' | 'not_verifiable' | 'missing';
    explanation: string;
  }[];
  overall_verdict: 'sufficient' | 'partial' | 'insufficient';
  report: string;
  revision_request_draft?: string;
}

export interface CriterionQuality {
  criterion: string;
  objectively_verifiable: boolean;
  reason: string;
  rewritten_criterion: string;
}

export interface LinkCheckFact {
  url: string;
  https: boolean;
  http_status: number | null;
  title: string | null;
  result: 'checked' | 'blocked' | 'unavailable';
  reason: string;
  github_repo_exists: boolean | null;
  github_expected_files: { name: string; present: boolean }[];
}

export interface Evidence {
  id: string;
  type: string;
  content: string;
  ai_report: EvidenceReport | null;
  link_checks: LinkCheckFact[];
  created_at: string | null;
}

export interface Invoice {
  id: string;
  paypal_invoice_id: string | null;
  status: string;
  amount_cents: number;
  currency: string;
  payer_view_url: string | null;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  order: number;
  status: MilestoneStatus;
  amount_cents: number;
  acceptance_criteria: string[];
  evidence: Evidence[];
  invoices: Invoice[];
}

export interface Agreement {
  id: string;
  title: string;
  description: string;
  status: AgreementStatus;
  total_amount_cents: number;
  currency: string;
  client_org_id: string;
  provider_org_id: string;
  created_at: string | null;
  milestones: Milestone[];
}

export interface IntentMilestone {
  title: string;
  amount_cents: number;
  deliverables: string[];
  acceptance_criteria: string[];
  criteria_quality: CriterionQuality[];
}

export interface Intent {
  project_type: string;
  requirements: string[];
  budget_cents: number;
  currency: string;
  deadline: string;
  missing_information: string[];
  milestones: IntentMilestone[];
}

export interface AuditEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  userId?: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (userId) headers.set('X-User-Id', userId);

  let response: Response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch {
    throw new ApiError('Cannot reach the Orchestra API. Is the backend running?', 0);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (response.status === 429) {
        message = 'The AI is busy right now. Please try again in a moment.';
      } else if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = 'Some fields need attention. Please review the form and try again.';
      }
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const api = {
  health: () =>
    request<{ demo_mode: 'mock' | 'real' }>('/api/v1/health'),
  listAgreements: (role: Role, userId: string) =>
    request<Agreement[]>(`/api/v1/${role}/agreements`, userId),
  getAgreement: (role: Role, id: string, userId: string) =>
    request<Agreement>(`/api/v1/${role}/agreements/${id}`, userId),
  parseIntent: (userId: string, text: string) =>
    request<Intent>(
      '/api/v1/client/intents/parse',
      userId,
      json('POST', { request: text }),
    ),
  createAgreement: (userId: string, intent: Intent) =>
    request<Agreement>(
      '/api/v1/client/agreements',
      userId,
      json('POST', {
        intent: {
          ...intent,
          milestones: intent.milestones.map((milestone) => ({
            title: milestone.title,
            amount_cents: milestone.amount_cents,
            deliverables: milestone.deliverables,
            acceptance_criteria: milestone.acceptance_criteria,
          })),
        },
      }),
    ),
  publishAgreement: (userId: string, agreementId: string) =>
    request<Agreement>(
      `/api/v1/client/agreements/${agreementId}/publish`,
      userId,
      json('POST'),
    ),
  approveMilestone: (userId: string, agreementId: string, milestoneId: string) =>
    request<Milestone>(
      `/api/v1/client/agreements/${agreementId}/milestones/${milestoneId}/approve`,
      userId,
      json('POST'),
    ),
  requestRevision: (
    userId: string,
    agreementId: string,
    milestoneId: string,
    notes: string,
  ) =>
    request<Milestone>(
      `/api/v1/client/agreements/${agreementId}/milestones/${milestoneId}/revision`,
      userId,
      json('POST', { notes }),
    ),
  acceptAgreement: (userId: string, agreementId: string) =>
    request<Agreement>(
      `/api/v1/provider/agreements/${agreementId}/accept`,
      userId,
      json('POST'),
    ),
  refuseAgreement: (userId: string, agreementId: string, notes: string) =>
    request<Agreement>(
      `/api/v1/provider/agreements/${agreementId}/refuse`,
      userId,
      json('POST', { notes }),
    ),
  startMilestone: (userId: string, agreementId: string, milestoneId: string) =>
    request<Milestone>(
      `/api/v1/provider/agreements/${agreementId}/milestones/${milestoneId}/start`,
      userId,
      json('POST'),
    ),
  submitEvidence: (
    userId: string,
    agreementId: string,
    milestoneId: string,
    text: string,
    links: string[],
  ) =>
    request<{
      ai_report: EvidenceReport;
      link_checks: LinkCheckFact[];
      milestone_status: MilestoneStatus;
    }>(
      `/api/v1/provider/agreements/${agreementId}/milestones/${milestoneId}/evidence`,
      userId,
      json('POST', { text, links: links.filter(Boolean) }),
    ),
  submitForReview: (userId: string, agreementId: string, milestoneId: string) =>
    request<Milestone>(
      `/api/v1/provider/agreements/${agreementId}/milestones/${milestoneId}/submit`,
      userId,
      json('POST'),
    ),
  createInvoice: (userId: string, milestoneId: string) =>
    request<{
      id: string;
      paypal_invoice_id: string | null;
      status: string;
      amount_cents: number;
      paypal_invoice_url: string | null;
    }>(
      `/api/v1/payments/milestones/${milestoneId}/invoice`,
      userId,
      json('POST'),
    ),
  syncInvoice: (userId: string, invoiceId: string) =>
    request<{ status: string }>(
      `/api/v1/payments/invoices/${invoiceId}/sync`,
      userId,
      json('POST'),
    ),
  auditLogs: (userId: string, agreementId: string) =>
    request<AuditEntry[]>(`/api/v1/agreements/${agreementId}/audit-logs`, userId),
  resetDemo: () =>
    request<{ status: string }>(
      '/api/v1/demo/seed',
      'demo-client',
      json('POST'),
    ),
};

export function formatMoney(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}
