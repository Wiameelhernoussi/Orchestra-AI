import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Milestone } from '../api';
import { ProofToPay, proofToPayProgress } from './ProofToPay';

const milestone: Milestone = {
  id: 'milestone-1',
  title: 'Design',
  description: 'Deliver page mockups.',
  order: 1,
  status: 'IN_REVIEW',
  amount_cents: 15000,
  acceptance_criteria: [],
  evidence: [{
    id: 'evidence-1',
    type: 'submission',
    content: 'Evidence content',
    submission_status: 'SUBMITTED',
    verification_status: 'ADVISORY',
    ai_report: {
      criteria_results: [],
      overall_verdict: 'partial',
      report: 'Advisory only',
    },
    link_checks: [],
    created_at: null,
  }],
  invoices: [],
  payment_readiness: {
    status: 'BLOCKED',
    score: 71,
    ready: false,
    paypal_invoice_allowed: false,
    client_approval_allowed: true,
    client_acknowledged_advisory: false,
    advisory_verdict: 'partial',
    blocking_reasons: ['Client approval is required.'],
    completed_checks: ['Active work agreement'],
    checks: [
      { key: 'agreement_valid', label: 'Active work agreement', complete: true, required: true },
      { key: 'paypal_invoice_allowed', label: 'PayPal invoice can be created', complete: false, required: false },
    ],
    next_action: { actor: 'CLIENT', action: 'Review the evidence and approve the milestone.' },
    criteria_summary: { total: 1, verified: 1, unverified: 0, criteria: [] },
    approval_status: 'PENDING',
    paypal_status: 'NOT_CREATED',
  },
};

describe('ProofToPay', () => {
  it('shows all six steps, their actors, and highlights the current step', () => {
    render(<ProofToPay milestone={milestone} />);

    const list = screen.getByRole('list', { name: 'Proof-to-Pay workflow steps' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(6);
    expect(within(list).getByText('Started')).toBeTruthy();
    expect(within(list).getByText('Evidence submitted')).toBeTruthy();
    expect(within(list).getByText('AI advisory')).toBeTruthy();
    expect(within(list).getByText('Client approval')).toBeTruthy();
    expect(within(list).getByText('Invoice sent')).toBeTruthy();
    expect(within(list).getByText('Paid')).toBeTruthy();
    expect(within(list).getAllByText('Provider')).toHaveLength(2);
    expect(within(list).getAllByText('AI')).toHaveLength(2);
    expect(within(list).getByText('Client')).toBeTruthy();
    expect(within(list).getAllByText('PayPal')).toHaveLength(2);
    expect(within(list).getByRole('listitem', { current: 'step' })).toHaveTextContent('Client approval');
    expect(screen.getByText('PAYMENT READINESS')).toBeTruthy();
    expect(screen.getByText('71%')).toBeTruthy();
    expect(screen.getByText('Client approval is required.')).toBeTruthy();
    expect(screen.getByText(/Next action · CLIENT/)).toBeTruthy();
  });

  it('moves the current step to payment confirmation after invoice creation', () => {
    expect(proofToPayProgress({ ...milestone, status: 'PAYMENT_PENDING' })).toBe(5);
  });
});
