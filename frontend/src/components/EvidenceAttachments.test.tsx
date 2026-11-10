// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type EvidenceAttachment } from '../api';
import { EvidenceAttachments } from './EvidenceAttachments';

const imageAttachment: EvidenceAttachment = {
  id: 'image-1',
  name: 'design.png',
  content_type: 'image/png',
  size_bytes: 1024,
  inspection_status: 'analyzed',
};

describe('EvidenceAttachments', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads and displays an inline preview for uploaded images', async () => {
    vi.spyOn(api, 'downloadEvidenceAttachment').mockResolvedValue(new Blob(['image']));
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:design-preview');

    render(
      <EvidenceAttachments
        userId="client-user"
        evidenceId="evidence-1"
        attachments={[imageAttachment]}
      />,
    );

    const preview = await screen.findByRole('img', { name: 'Submitted evidence: design.png' });
    expect(preview).toHaveAttribute('src', 'blob:design-preview');
    expect(api.downloadEvidenceAttachment).toHaveBeenCalledWith(
      'client-user',
      'evidence-1',
      'image-1',
    );
    expect(screen.getByText('Image preview')).toBeInTheDocument();
  });

  it('reports an image preview download error and does not attempt to preview PDFs', async () => {
    vi.spyOn(api, 'downloadEvidenceAttachment').mockRejectedValue(new Error('Attachment not found.'));
    render(
      <EvidenceAttachments
        userId="client-user"
        evidenceId="evidence-1"
        attachments={[
          imageAttachment,
          {
            ...imageAttachment,
            id: 'pdf-1',
            name: 'specification.pdf',
            content_type: 'application/pdf',
          },
        ]}
      />,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Attachment not found.');
    await waitFor(() => {
      expect(api.downloadEvidenceAttachment).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByRole('img', { name: 'Submitted evidence: specification.pdf' })).toBeNull();
  });
});
