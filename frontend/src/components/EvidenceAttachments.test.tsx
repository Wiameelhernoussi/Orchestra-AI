// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('loads a fixed thumbnail and opens the full image in an accessible lightbox', async () => {
    vi.spyOn(api, 'downloadEvidenceAttachment').mockResolvedValue(new Blob(['image']));
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:design-preview');

    render(
      <EvidenceAttachments
        userId="client-user"
        evidenceId="evidence-1"
        attachments={[imageAttachment]}
      />,
    );

    const previewButton = await screen.findByRole('button', { name: 'Open image preview: design.png' });
    expect(previewButton.querySelector('img')).toHaveAttribute('src', 'blob:design-preview');
    expect(api.downloadEvidenceAttachment).toHaveBeenCalledWith(
      'client-user',
      'evidence-1',
      'image-1',
    );
    fireEvent.click(previewButton);
    expect(screen.getByRole('dialog', { name: 'Image preview: design.png' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Submitted evidence: design.png' })).toHaveAttribute(
      'src',
      'blob:design-preview',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Close image preview' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
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
