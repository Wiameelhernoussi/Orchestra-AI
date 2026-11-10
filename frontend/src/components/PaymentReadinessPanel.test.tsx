// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
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
  afterEach(() => cleanup());

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

  it('shows paid milestones as complete and next milestone unlocked without blocker details', () => {
    const paidMilestone: Milestone = {
      ...milestone,
      status: 'PAID',
      payment_readiness: {
        ...milestone.payment_readiness,
        status: 'PAID',
        score: 75,
        next_milestone_title: 'Development',
        next_milestone_unlocked: true,
        paypal_status: 'PAID',
      },
    };

    render(<PaymentReadinessPanel milestone={paidMilestone} role="client" />);

    expect(screen.getByText('100% complete')).toBeInTheDocument();
    const nextMilestone = screen.getByText('Next milestone: unlocked · Development');
    expect(nextMilestone.closest('li')).toHaveClass('complete');
    expect(screen.queryByText('Why is payment blocked?')).not.toBeInTheDocument();
    expect(screen.queryByText(/75% complete/)).not.toBeInTheDocument();
  });
});
