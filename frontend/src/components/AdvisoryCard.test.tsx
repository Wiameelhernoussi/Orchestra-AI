// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AdvisoryCard } from './AdvisoryCard';

describe('AdvisoryCard', () => {
  it('shows the human approval gate and criterion-level evidence states', () => {
    render(
      <AdvisoryCard
        report={{
          overall_verdict: 'partial',
          report: 'One item needs more evidence.',
          criteria_results: [
            {
              criterion: 'Mobile layout is responsive',
              status: 'verified',
              explanation: 'A preview link was submitted.',
            },
            {
              criterion: 'Checkout completes',
              status: 'not_verifiable',
              explanation: 'No checkout evidence was supplied.',
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('AI advisory only. Human approval required.')).toBeInTheDocument();
    expect(screen.getByText('partial')).toBeInTheDocument();
    expect(screen.getByText('✓ Verified')).toBeInTheDocument();
    expect(screen.getByText('– Not verifiable')).toBeInTheDocument();
    expect(screen.getByText('One item needs more evidence.')).toBeInTheDocument();
  });
});
