// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Agreement } from '../api';
import { AgreementSummaryStrip, MilestoneRail } from './AgreementWorkspaceNavigation';

const agreement: Agreement = {
  id: 'agreement-1',
  title: 'Project',
  description: '',
  status: 'ACTIVE',
  total_amount_cents: 50000,
  currency: 'USD',
  client_org_id: 'client',
  provider_org_id: 'provider',
  created_at: null,
  milestones: [
    {
      id: 'milestone-1',
      title: 'Design',
      description: '',
      order: 1,
      status: 'PAID',
      amount_cents: 15000,
      acceptance_criteria: [],
      evidence: [],
      invoices: [],
      payment_readiness: {} as Agreement['milestones'][number]['payment_readiness'],
    },
    {
      id: 'milestone-2',
      title: 'Development',
      description: '',
      order: 2,
      status: 'IN_PROGRESS',
      amount_cents: 35000,
      acceptance_criteria: [],
      evidence: [],
      invoices: [],
      payment_readiness: {} as Agreement['milestones'][number]['payment_readiness'],
    },
  ],
};

describe('Agreement workspace navigation', () => {
  afterEach(() => cleanup());

  it('shows next action and amount-paid progress', () => {
    render(
      <AgreementSummaryStrip
        agreement={agreement}
        role="client"
        nextAction="Review the Development milestone."
      />,
    );

    expect(screen.getByText('YOUR NEXT ACTION')).toBeInTheDocument();
    expect(screen.getByText('Review the Development milestone.')).toBeInTheDocument();
    expect(screen.getByText('Progress · 30%')).toBeInTheDocument();
    expect(screen.getByText('$150.00 paid / $500.00')).toBeInTheDocument();
  });

  it('selects the active milestone from the rail', () => {
    const onSelect = vi.fn();
    render(<MilestoneRail agreement={agreement} selectedId="milestone-1" onSelect={onSelect} />);

    expect(screen.getByRole('button', { name: /Design/ })).toHaveAttribute('aria-current', 'step');
    fireEvent.click(screen.getByRole('button', { name: /Development/ }));
    expect(onSelect).toHaveBeenCalledWith('milestone-2');
  });
});
