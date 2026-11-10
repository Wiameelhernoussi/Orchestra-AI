// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Milestone } from '../api';
import { PaymentReadinessPanel } from './PaymentReadinessPanel';

const milestone: Milestone = {
  id: 'milestone-1',
  title: 'Design',
  description: 'Deliver the design files.',
  order: 1,
  status: 'IN_REVIEW',
  amount_cents: 15000,
  acceptance_criteria: ['Design files are provided.'],
  criteria: [{ id: 'criterion-1', description: 'Design files are provided.' }],
  evidence: [],
  invoices: [],
  payment_readiness: {
    status: 'BLOCKED',
    score: 40,
    ready: false,
    paypal_invoice_allowed: false,
    client_approval_allowed: false,
    client_acknowledged_advisory: false,
    advisory_verdict: 'unavailable',
    blocking_reasons: ['Evidence has not been submitted.'],
    completed_checks: [],
    checks: [],
    next_action: { actor: 'PROVIDER', action: 'Submit evidence.' },
    criteria_summary: {
      total: 1,
      verified: 0,
      unverified: 1,
      criteria: [{ criterion: 'Design files are provided.', status: 'missing' }],
    },
    approval_status: 'PENDING',
    approval_details: null,
    paypal_status: 'NOT_CREATED',
    webhook_payment_confirmed: false,
    scope_defined: true,
    next_milestone_title: 'Development',
    next_milestone_unlocked: false,
    client_next_action: 'Wait for evidence.',
    provider_next_action: 'Submit evidence for: Design files are provided.',
  },
};

describe('PaymentReadinessPanel', () => {
  it('explains blockers, checklist status, and provider-specific next action', () => {
    render(<PaymentReadinessPanel milestone={milestone} role="provider" />);

    expect(screen.getByText('BLOCKED')).toBeInTheDocument();
    expect(screen.getByText(/AI advisory: unavailable · 1 unverified criteria/)).toBeInTheDocument();
    expect(screen.getByText(/Next step for the provider/)).toBeInTheDocument();
    expect(screen.getByText(/Submit evidence for: Design files are provided/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Why is payment blocked?'));
    expect(screen.getByText('Evidence has not been submitted.')).toBeInTheDocument();
    expect(screen.getByText('Design files are provided. (missing)')).toBeInTheDocument();
  });
});
