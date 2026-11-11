import { useEffect, useState } from 'react';
import { api, type EvidenceAttachment } from '../api';

function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function ImagePreview({
  userId,
  evidenceId,
  attachment,
}: {
  userId: string;
  evidenceId: string;
  attachment: EvidenceAttachment;
}) {
  const [previewUrl, setPreviewUrl] = useState('');
  const [error, setError] = useState('');
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = '';

    void api.downloadEvidenceAttachment(userId, evidenceId, attachment.id)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'Image preview could not be loaded.');
        }
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment.id, evidenceId, userId]);

  useEffect(() => {
    if (!lightboxOpen) return undefined;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setLightboxOpen(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [lightboxOpen]);

  if (error) return <p className="attachment-error" role="alert">{error}</p>;
  if (!previewUrl) return <p className="attachment-preview-loading" role="status">Loading image…</p>;

  return (
    <>
      <button
        type="button"
        className="evidence-thumbnail"
        aria-label={`Open image preview: ${attachment.name}`}
        onClick={() => setLightboxOpen(true)}
      >
        <img src={previewUrl} alt="" />
        <span>View image</span>
      </button>
      {lightboxOpen && (
        <div
          className="evidence-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={`Image preview: ${attachment.name}`}
          onClick={() => setLightboxOpen(false)}
        >
          <button
            type="button"
            className="evidence-lightbox-close"
            aria-label="Close image preview"
            onClick={() => setLightboxOpen(false)}
          >
            Close
          </button>
          <img
            src={previewUrl}
            alt={`Submitted evidence: ${attachment.name}`}
            onClick={(event) => event.stopPropagation()}
          />
          <p>{attachment.name}</p>
        </div>
      )}
    </>
  );
}

export function EvidenceAttachments({
  userId,
  evidenceId,
  attachments,
}: {
  userId: string;
  evidenceId: string;
  attachments: EvidenceAttachment[];
}) {
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');

  async function download(attachment: EvidenceAttachment) {
    setBusyId(attachment.id);
    setError('');
    try {
      const blob = await api.downloadEvidenceAttachment(
        userId,
        evidenceId,
        attachment.id,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = attachment.name;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Attachment could not be downloaded.');
    } finally {
      setBusyId('');
    }
  }

  if (attachments.length === 0) return null;
  return (
    <div className="evidence-attachments">
      <h4>Submitted files <span>{attachments.length}</span></h4>
      <ul>
        {attachments.map((attachment) => (
          <li key={attachment.id}>
            {['image/png', 'image/jpeg', 'image/webp'].includes(attachment.content_type) ? (
              <ImagePreview
                userId={userId}
                evidenceId={evidenceId}
                attachment={attachment}
              />
            ) : (
              <span className="attachment-file-icon" aria-hidden="true">PDF</span>
            )}
            <div className="attachment-file-info">
              <strong title={attachment.name}>{attachment.name}</strong>
              <small>{formatBytes(attachment.size_bytes)}</small>
            </div>
            <button
              type="button"
              className="attachment-download"
              disabled={busyId !== ''}
              onClick={() => void download(attachment)}
            >
              {busyId === attachment.id ? 'Downloading…' : 'Download'}
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="attachment-error" role="alert">{error}</p>}
    </div>
  );
}
