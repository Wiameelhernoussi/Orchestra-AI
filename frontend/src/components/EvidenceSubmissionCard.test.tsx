// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Evidence } from '../api';
import { api } from '../api';
import { EvidenceSubmissionCard } from './EvidenceSubmissionCard';

const evidence: Evidence = {
  id: 'evidence-1',
  type: 'submission',
  content: JSON.stringify({
    text: 'The detailed evidence description for this deliverable.',
    links: ['https://example.test/preview'],
    criterion_ids: ['criterion-1'],
    attachments: [{
      id: 'attachment-1',
      name: 'home-page.png',
      content_type: 'image/png',
      size_bytes: 2048,
      inspection_status: 'analyzed',
    }],
  }),
  submission_status: 'SUBMITTED',
  verification_status: 'ADVISORY',
  ai_report: null,
  link_checks: [{
    url: 'https://example.test/preview',
    https: true,
    http_status: 200,
    title: null,
    result: 'checked',
    reason: 'HTTP response received.',
    github_repo_exists: null,
    github_expected_files: [],
  }],
  created_at: null,
};

describe('EvidenceSubmissionCard', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('starts collapsed and only loads attachments when evidence is expanded', () => {
    const download = vi.spyOn(api, 'downloadEvidenceAttachment').mockResolvedValue(new Blob(['image']));
    render(
      <EvidenceSubmissionCard
        userId="client-user"
        evidence={evidence}
        criteria={[{ id: 'criterion-1', description: 'Homepage design is included.' }]}
      />,
    );

    expect(screen.getByText('The detailed evidence description for this deliverable.')).toBeInTheDocument();
    expect(screen.getByText('1 files · 1 of 1 links reachable')).toBeInTheDocument();
    expect(screen.getByText('AI advises. You decide.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /example.test/ })).not.toBeInTheDocument();
    expect(screen.queryByText('home-page.png')).not.toBeInTheDocument();
    expect(download).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('The detailed evidence description for this deliverable.').closest('summary')!);

    expect(screen.getByRole('link', { name: /example.test/ })).toHaveAttribute(
      'href',
      'https://example.test/preview',
    );
    expect(screen.getByText(/Related criteria:.*Homepage design is included/)).toBeInTheDocument();
    expect(download).toHaveBeenCalledOnce();
  });
});
