// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { AdvisoryCard } from './AdvisoryCard';

describe('AdvisoryCard', () => {
  afterEach(() => cleanup());

  it('renders analyzed attachment names and per-criterion visual observations', () => {
    render(
      <AdvisoryCard
        report={{
          overall_verdict: 'partial',
          report: 'AI assessment only; client approval is required.',
          criteria_results: [],
          image_analysis: {
            status: 'analyzed',
            message: 'Visual observations are advisory only.',
            attachments: [{
              id: 'attachment-1',
              name: 'home-page.png',
              content_type: 'image/png',
              status: 'analyzed',
              message: 'Image pixels were visually analyzed.',
            }],
            criteria_results: [{
              criterion: 'Home page mockup is included',
              status: 'visible_in_image',
              observation: 'A desktop home page mockup is visible.',
              missing_element: 'Mobile layout is not shown.',
            }],
          },
        }}
      />,
    );

    expect(screen.getByText('home-page.png')).toBeInTheDocument();
    expect(screen.getByText('Analyzed')).toBeInTheDocument();
    expect(screen.getByText(/Home page mockup is included · visible in image/i)).toBeInTheDocument();
    expect(screen.getByText('A desktop home page mockup is visible.')).toBeInTheDocument();
    expect(screen.getByText('Missing element: Mobile layout is not shown.')).toBeInTheDocument();
  });

  it('shows visual observations and clearly labels failed image analysis', () => {
    render(
      <AdvisoryCard
        report={{
          overall_verdict: 'partial',
          report: 'Text advisory only.',
          criteria_results: [],
          image_analysis: {
            status: 'not_analyzed',
            message: 'Vision request was rate limited. Image not analyzed.',
            attachments: [{
              id: 'attachment-1',
              name: 'design.png',
              content_type: 'image/png',
              status: 'not_analyzed',
              message: 'The image could not be analyzed.',
            }],
            criteria_results: [{
              criterion: 'Mobile design is included',
              status: 'cannot_tell',
              observation: 'No visual assessment is available.',
              missing_element: 'Image analysis unavailable.',
            }],
          },
        }}
      />,
    );

    expect(screen.getByText('Image not analyzed.')).toBeInTheDocument();
    expect(screen.getByText('design.png')).toBeInTheDocument();
    expect(screen.getByText(/Mobile design is included · cannot tell/i)).toBeInTheDocument();
    expect(screen.getByText(/Links are not inspected beyond reachability/)).toBeInTheDocument();
    expect(screen.getByText('Missing element: Image analysis unavailable.')).toBeInTheDocument();
  });

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
