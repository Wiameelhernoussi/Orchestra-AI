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
  image_analysis?: {
    status: 'analyzed' | 'not_analyzed' | 'mock' | 'disabled';
    message: string;
    attachments: {
      id: string;
      name: string;
      content_type: string;
      status: 'analyzed' | 'not_analyzed' | 'mock_canned';
      message: string;
    }[];
    criteria_results: {
      criterion: string;
      status: 'visible_in_image' | 'not_visible' | 'cannot_tell';
      observation: string;
      missing_element: string;
    }[];
  };
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

export interface EvidenceAttachment {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number;
  inspection_status: 'not_inspected_by_ai' | 'analyzed' | 'not_analyzed' | 'mock_canned';
}

export interface EvidenceContent {
  text: string;
  links: string[];
  criterion_ids: string[];
  attachments: EvidenceAttachment[];
}

export interface Evidence {
  id: string;
  type: string;
  content: string;
  submission_status: 'SUBMITTED';
  verification_status: 'ADVISORY';
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
  created_at?: string | null;
  sent_at?: string | null;
  paid_at?: string | null;
  payment_confirmation?: 'verified_webhook' | 'manual_sync' | null;
  last_reminder_at?: string | null;
  last_reminder_status?: 'pending' | 'sent' | 'failed' | null;
  webhook_events?: {
    event_type: string;
    signature_verified: boolean;
    processed: string;
    created_at: string | null;
    duplicate_deliveries: number;
  }[];
}

export interface PaymentTotals {
  total_invoiced_cents: number;
  paid_cents: number;
  pending_cents: number;
}

export interface PaymentReadinessCheck {
  key: string;
  label: string;
  complete: boolean;
  required: boolean;
}

export interface PaymentReadiness {
  status:
    | 'NOT_READY'
    | 'IN_REVIEW'
    | 'READY_FOR_APPROVAL'
    | 'READY_FOR_PAYMENT'
    | 'INVOICE_CREATED'
    | 'INVOICE_SENT'
    | 'PAID'
    | 'BLOCKED';
  score: number;
  ready: boolean;
  paypal_invoice_allowed: boolean;
  client_approval_allowed: boolean;
  client_acknowledged_advisory: boolean;
  advisory_verdict: 'sufficient' | 'partial' | 'insufficient' | 'unavailable';
  blocking_reasons: string[];
  completed_checks: string[];
  checks: PaymentReadinessCheck[];
  next_action: { actor: 'CLIENT' | 'PROVIDER' | 'AI' | 'PAYPAL' | 'SYSTEM'; action: string };
  criteria_summary: {
    total: number;
    verified: number;
    unverified: number;
    criteria: { criterion: string; status: 'verified' | 'not_verifiable' | 'missing' }[];
  };
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  approval_details: {
    approver_name: string;
    approved_at: string | null;
    advisory_overridden: boolean;
  } | null;
  paypal_status: string;
  webhook_payment_confirmed: boolean;
  scope_defined: boolean;
  next_milestone_title: string | null;
  next_milestone_unlocked: boolean;
  client_next_action: string;
  provider_next_action: string;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  order: number;
  status: MilestoneStatus;
  amount_cents: number;
  acceptance_criteria: string[];
  criteria?: { id: string; description: string }[];
  evidence: Evidence[];
  invoices: Invoice[];
  payment_readiness: PaymentReadiness;
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
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
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
      } else if (
        typeof body.detail === 'object'
        && body.detail !== null
        && 'message' in body.detail
        && typeof body.detail.message === 'string'
      ) {
        message = body.detail.message;
        const criteria = 'unverified_criteria' in body.detail
          && Array.isArray(body.detail.unverified_criteria)
          ? body.detail.unverified_criteria
              .filter(
                (item): item is { criterion: string } =>
                  typeof item === 'object'
                  && item !== null
                  && 'criterion' in item
                  && typeof item.criterion === 'string',
              )
              .map((item) => item.criterion)
          : [];
        if (criteria.length > 0) {
          message += ` Unverified criteria: ${criteria.join('; ')}`;
        }
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
  paymentTotals: (userId: string) =>
    request<PaymentTotals>('/api/v1/payments/summary', userId),
  getAgreement: (role: Role, id: string, userId: string) =>
    request<Agreement>(`/api/v1/${role}/agreements/${id}`, userId),
  paymentReadiness: (userId: string, milestoneId: string) =>
    request<PaymentReadiness>(
      `/api/v1/milestones/${milestoneId}/payment-readiness`,
      userId,
    ),
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
  approveMilestone: (
    userId: string,
    agreementId: string,
    milestoneId: string,
    acknowledgeUnverified = false,
  ) =>
    request<Milestone>(
      `/api/v1/client/agreements/${agreementId}/milestones/${milestoneId}/approve`,
      userId,
      json('POST', { acknowledge_unverified: acknowledgeUnverified }),
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
    files: File[] = [],
    criterionIds: string[] = [],
  ) =>
    {
      const body = new FormData();
      body.append('text', text);
      links.filter(Boolean).forEach((link) => body.append('links', link));
      criterionIds.forEach((criterionId) => body.append('criterion_ids', criterionId));
      files.forEach((file) => body.append('files', file, file.name));
      return request<{
        evidence_id: string;
        submission_status: 'SUBMITTED';
        verification_status: 'ADVISORY';
        attachments: EvidenceAttachment[];
        ai_report: EvidenceReport;
        link_checks: LinkCheckFact[];
        milestone_status: MilestoneStatus;
      }>(
        `/api/v1/provider/agreements/${agreementId}/milestones/${milestoneId}/evidence`,
        userId,
        { method: 'POST', body },
      );
    },
  downloadEvidenceAttachment: async (
    userId: string,
    evidenceId: string,
    attachmentId: string,
  ): Promise<Blob> => {
    let response: Response;
    try {
      response = await fetch(
        `/api/v1/evidence/${encodeURIComponent(evidenceId)}/attachments/${encodeURIComponent(attachmentId)}`,
        {
          headers: {
            Accept: 'application/octet-stream',
            'X-User-Id': userId,
          },
        },
      );
    } catch {
      throw new ApiError('Cannot reach the Orchestra API. Is the backend running?', 0);
    }
    if (!response.ok) {
      let message = `Request failed (${response.status}).`;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') message = body.detail;
      } catch {
        // Keep the status-based message for non-JSON responses.
      }
      throw new ApiError(message, response.status);
    }
    return response.blob();
  },
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
  invoiceQrCode: (userId: string, invoiceId: string) =>
    request<{ qr_code_base64: string; content_type: 'image/png' }>(
      `/api/v1/payments/invoices/${invoiceId}/qr-code`,
      userId,
      json('POST'),
    ),
  sendInvoiceReminder: (userId: string, invoiceId: string) =>
    request<{ status: 'sent' | 'already_sent'; sent_at: string | null }>(
      `/api/v1/payments/invoices/${invoiceId}/reminder`,
      userId,
      json('POST'),
    ),
  simulateMockPayment: (userId: string, invoiceId: string) =>
    request<{ status: string }>(
      `/api/v1/payments/invoices/${invoiceId}/simulate-mock-payment`,
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

export function parseEvidenceContent(content: string): EvidenceContent {
  try {
    const parsed: unknown = JSON.parse(content);
    if (typeof parsed === 'object' && parsed !== null && 'text' in parsed) {
      const value = parsed as Record<string, unknown>;
      return {
        text: typeof value.text === 'string' ? value.text : '',
        links: Array.isArray(value.links)
          ? value.links.filter((item): item is string => typeof item === 'string')
          : [],
        criterion_ids: Array.isArray(value.criterion_ids)
          ? value.criterion_ids.filter((item): item is string => typeof item === 'string')
          : [],
        attachments: Array.isArray(value.attachments)
          ? value.attachments.filter(
            (item): item is EvidenceAttachment =>
              typeof item === 'object'
              && item !== null
              && 'id' in item
              && 'name' in item
              && 'content_type' in item
              && 'size_bytes' in item
              && 'inspection_status' in item,
          )
          : [],
      };
    }
  } catch {
    // Older evidence records store plain text.
  }
  return { text: content, links: [], criterion_ids: [], attachments: [] };
}

export function formatMoney(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}
