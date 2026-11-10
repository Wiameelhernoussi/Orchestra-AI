import { describe, expect, it } from 'vitest';
import type { Agreement, AuditEntry, Milestone, Role } from './api';
import {
  activityDescription,
  agreementAction,
  agreementNextStep,
  DESIGN_SAMPLE_PARTIAL,
  DESIGN_SAMPLE_SUFFICIENT,
} from './presentation';

function makeAgreement(
  status: Agreement['status'],
  milestoneStatus: Milestone['status'],
): Agreement {
  return {
    id: 'agreement-1',
    title: 'Portfolio site',
    description: '',
    status,
    total_amount_cents: 10000,
    currency: 'USD',
    client_org_id: 'client',
    provider_org_id: 'provider',
    created_at: null,
    milestones: [{
      id: 'milestone-1',
      title: 'Design',
      description: '',
      order: 1,
      status: milestoneStatus,
      amount_cents: 10000,
      acceptance_criteria: [],
      evidence: [],
      invoices: [],
      payment_readiness: {
        status: 'BLOCKED',
        score: 0,
        ready: false,
        paypal_invoice_allowed: false,
        client_approval_allowed: false,
        client_acknowledged_advisory: false,
        advisory_verdict: 'sufficient',
        blocking_reasons: [],
        completed_checks: [],
        checks: [],
        next_action: { actor: 'PROVIDER', action: 'Submit evidence.' },
        criteria_summary: { total: 0, verified: 0, unverified: 0, criteria: [] },
        approval_status: 'PENDING',
        approval_details: null,
        paypal_status: 'NOT_CREATED',
        webhook_payment_confirmed: false,
        scope_defined: true,
        next_milestone_title: null,
        next_milestone_unlocked: true,
        client_next_action: 'Review.',
        provider_next_action: 'Wait.',
      },
    }],
  };
}

describe('agreement presentation', () => {
  it('shows the completed message for both roles', () => {
    const agreement = makeAgreement('COMPLETED', 'PAID');
    for (const role of ['client', 'provider'] satisfies Role[]) {
      expect(agreementNextStep(agreement, role)).toBe(
        'All milestones are paid. Agreement completed.',
      );
    }
  });

  it('gives role-appropriate next steps for proposal, review, payment, and active work', () => {
    expect(agreementNextStep(makeAgreement('PROPOSED', 'PENDING'), 'provider'))
      .toContain('accept the proposal');
    expect(agreementNextStep(makeAgreement('PROPOSED', 'PENDING'), 'client'))
      .toContain('Waiting for the provider');
    expect(agreementNextStep(makeAgreement('ACTIVE', 'IN_REVIEW'), 'client'))
      .toContain('Review the submitted evidence');
    expect(agreementNextStep(makeAgreement('ACTIVE', 'IN_REVIEW'), 'provider'))
      .toContain('Waiting for the client');
    expect(agreementNextStep(makeAgreement('ACTIVE', 'PAYMENT_PENDING'), 'provider'))
      .toContain('PayPal payment confirmation');
    expect(agreementNextStep(makeAgreement('ACTIVE', 'IN_PROGRESS'), 'provider'))
      .toContain('Submit evidence');
  });

  it('shows actionable agreement card badges', () => {
    expect(agreementAction(makeAgreement('ACTIVE', 'IN_REVIEW'), 'client'))
      .toBe('Review evidence');
    expect(agreementAction(makeAgreement('ACTIVE', 'APPROVED'), 'client'))
      .toBe('Pay invoice');
    expect(agreementAction(makeAgreement('ACTIVE', 'IN_PROGRESS'), 'client'))
      .toBe('Waiting for provider');
  });

  it('labels activity with readable action text and the responsible actor', () => {
    const entry: AuditEntry = {
      id: 'event-1',
      user_id: null,
      action: 'paypal_invoice_status_updated',
      entity_type: 'invoice',
      entity_id: 'invoice-1',
      details: { status: 'PAID' },
      created_at: null,
    };
    expect(activityDescription(entry)).toEqual({
      message: 'Payment confirmed by PayPal webhook',
      actor: 'PayPal',
    });
  });

  it('provides partial and complete design evidence examples', () => {
    expect(DESIGN_SAMPLE_PARTIAL).not.toContain('Cart');
    expect(DESIGN_SAMPLE_SUFFICIENT).toContain('Cart');
  });
});
