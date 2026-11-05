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
