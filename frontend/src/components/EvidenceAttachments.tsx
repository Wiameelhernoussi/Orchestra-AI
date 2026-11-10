import { useState } from 'react';
import { api, type EvidenceAttachment } from '../api';

function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
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
      <h4>Attachments <span>stored securely · not inspected by AI</span></h4>
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
          </li>
        ))}
      </ul>
      {error && <p className="attachment-error" role="alert">{error}</p>}
    </div>
  );
}
