// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Agreement } from '../api';
import { MemoryRouter } from 'react-router-dom';
import { AgreementCards, agreementFilterBucket } from './AgreementCards';

function agreement(id: string, milestoneStatus: string): Agreement {
  return {
    id,
    title: id,
    description: '',
    status: milestoneStatus === 'PROPOSED' ? 'PROPOSED' : 'ACTIVE',
    total_amount_cents: 10000,
    currency: 'USD',
    client_org_id: 'client',
    provider_org_id: 'provider',
    created_at: null,
    milestones: [{
      id: `${id}-milestone`,
      title: 'Design',
      description: '',
      order: 1,
      status: milestoneStatus as Agreement['milestones'][number]['status'],
      amount_cents: 10000,
      acceptance_criteria: [],
      evidence: [],
      invoices: [],
      payment_readiness: {} as Agreement['milestones'][number]['payment_readiness'],
    }],
  };
}

describe('AgreementCards filters', () => {
  afterEach(() => cleanup());

  it('classifies agreements by role and prioritizes action-needed agreements', () => {
    const proposed = agreement('proposal', 'PROPOSED');
    const inReview = agreement('review', 'IN_REVIEW');
    expect(agreementFilterBucket(proposed, 'provider')).toBe('needs-action');
    expect(agreementFilterBucket(proposed, 'client')).toBe('waiting');
    expect(agreementFilterBucket(inReview, 'client')).toBe('needs-action');

    render(
      <MemoryRouter>
        <AgreementCards agreements={[inReview, proposed]} role="provider" />
      </MemoryRouter>,
    );
    const cards = screen.getAllByRole('link');
    expect(cards[0]).toHaveTextContent('proposal');
    expect(screen.getByRole('button', { name: /Needs my action/ })).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByRole('button', { name: /Needs my action/ }));
    expect(screen.getByRole('link')).toHaveTextContent('proposal');
    expect(screen.queryByText('No agreements in this filter.')).not.toBeInTheDocument();
  });
});
