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
    ai_report: {
      criteria_results: [],
      overall_verdict: 'partial',
      report: 'Advisory only',
    },
    link_checks: [],
    created_at: null,
  }],
  invoices: [],
};

describe('ProofToPay', () => {
  it('shows all six steps, their actors, and highlights the current step', () => {
    render(<ProofToPay milestone={milestone} />);

    const list = screen.getByRole('list');
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
  });

  it('moves the current step to payment confirmation after invoice creation', () => {
    expect(proofToPayProgress({ ...milestone, status: 'PAYMENT_PENDING' })).toBe(5);
  });
});
