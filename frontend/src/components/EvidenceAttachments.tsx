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

  if (error) return <p className="attachment-error" role="alert">{error}</p>;
  if (!previewUrl) return <p className="attachment-preview-loading" role="status">Loading image preview…</p>;

  return (
    <figure className="evidence-image-preview-wrap">
      <img className="evidence-image-preview" src={previewUrl} alt={`Submitted evidence: ${attachment.name}`} />
      <figcaption>Image preview</figcaption>
    </figure>
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
      <h4>Attachments <span>stored securely · image previews shown below</span></h4>
      <ul>
        {attachments.map((attachment) => (
          <li key={attachment.id}>
            <span className="attachment-file-icon" aria-hidden="true">
              {attachment.content_type === 'application/pdf' ? 'PDF' : 'IMG'}
            </span>
            <span className="attachment-file-info">
              <strong>{attachment.name}</strong>
              <small>{formatBytes(attachment.size_bytes)}</small>
            </span>
            <button
              type="button"
              className="text-button"
              disabled={busyId !== ''}
              onClick={() => void download(attachment)}
            >
              {busyId === attachment.id ? 'Downloading…' : 'Download'}
            </button>
            {['image/png', 'image/jpeg', 'image/webp'].includes(attachment.content_type) && (
              <ImagePreview
                userId={userId}
                evidenceId={evidenceId}
                attachment={attachment}
              />
            )}
          </li>
        ))}
      </ul>
      {error && <p className="attachment-error" role="alert">{error}</p>}
    </div>
  );
}
