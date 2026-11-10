import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Milestone } from '../api';
import { MilestoneTracker } from './MilestoneTracker';

const milestones: Milestone[] = [
  {
    id: 'milestone-1',
    title: 'Design',
    description: 'Deliver page mockups.',
    order: 1,
    status: 'IN_REVIEW',
    amount_cents: 15000,
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
      advisory_verdict: 'insufficient',
      blocking_reasons: ['Evidence has not been submitted.'],
      completed_checks: [],
      checks: [],
      next_action: { actor: 'PROVIDER', action: 'Submit evidence for this milestone.' },
      criteria_summary: { total: 0, verified: 0, unverified: 0, criteria: [] },
      approval_status: 'PENDING',
      paypal_status: 'NOT_CREATED',
    },
  },
  {
    id: 'milestone-2',
    title: 'Development',
    description: 'Build the site.',
    order: 2,
    status: 'PAID',
    amount_cents: 35000,
    acceptance_criteria: [],
    evidence: [],
    invoices: [],
    payment_readiness: {
      status: 'PAID',
      score: 100,
      ready: true,
      paypal_invoice_allowed: false,
      client_approval_allowed: false,
      client_acknowledged_advisory: false,
      advisory_verdict: 'sufficient',
      blocking_reasons: [],
      completed_checks: [],
      checks: [],
      next_action: { actor: 'SYSTEM', action: 'No action required.' },
      criteria_summary: { total: 0, verified: 0, unverified: 0, criteria: [] },
      approval_status: 'APPROVED',
      paypal_status: 'PAID',
    },
  },
];

describe('MilestoneTracker', () => {
  it('renders milestone status badges and the Proof-to-Pay stepper', () => {
    render(<MilestoneTracker milestones={milestones} />);

    expect(screen.getByRole('list', { name: 'Milestone progress' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: /Design/ })).toBeTruthy();
    expect(screen.getByRole('heading', { name: /Development/ })).toBeTruthy();
    expect(screen.getByText('In review')).toBeTruthy();
    expect(screen.getAllByText('Paid').length).toBeGreaterThan(0);
    expect(screen.getByText('1 of 2 paid')).toBeTruthy();
  });
});
