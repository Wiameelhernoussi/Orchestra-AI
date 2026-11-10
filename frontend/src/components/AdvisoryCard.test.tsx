// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AdvisoryCard } from './AdvisoryCard';

describe('AdvisoryCard', () => {
  it('shows the human approval gate and criterion-level evidence states', () => {
    render(
      <AdvisoryCard
        linkFacts={[
          {
            url: 'https://example.test/unavailable',
            https: true,
            http_status: null,
            title: null,
            result: 'unavailable',
            reason: 'Connection timed out.',
            github_repo_exists: null,
            github_expected_files: [],
          },
          {
            url: 'https://example.test/design',
            https: true,
            http_status: 200,
            title: 'Design Preview',
            result: 'checked',
            reason: 'HTTP response received.',
            github_repo_exists: null,
            github_expected_files: [],
          },
        ]}
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
    expect(screen.getByText('Inaccessible to automated checker')).toBeInTheDocument();
    expect(screen.getByText('Reachable · HTTP 200')).toBeInTheDocument();
    expect(screen.getByText(/linked contents and relevance to the criterion are not verified/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://example.test/design' })).toHaveAttribute(
      'href',
      'https://example.test/design',
    );
  });
});
