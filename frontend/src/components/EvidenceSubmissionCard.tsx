import { useState } from 'react';
import { parseEvidenceContent, type Evidence } from '../api';
import { AdvisoryCard } from './AdvisoryCard';
import { EvidenceAttachments } from './EvidenceAttachments';

function evidenceSummary(text: string): string {
  const cleanText = text.replace(/\s+/g, ' ').trim();
  return cleanText.length > 110 ? `${cleanText.slice(0, 107)}…` : cleanText || 'Evidence submitted';
}

export function EvidenceSubmissionCard({
  userId,
  evidence,
  criteria,
}: {
  userId: string;
  evidence: Evidence;
  criteria: { id: string; description: string }[];
}) {
  const [expanded, setExpanded] = useState(false);
  const parsed = parseEvidenceContent(evidence.content);
  const relatedCriteria = criteria
    .filter((criterion) => parsed.criterion_ids.includes(criterion.id))
    .map((criterion) => criterion.description);
  const checkedLinks = evidence.link_checks.filter((fact) => fact.result === 'checked').length;
  const linkSummary = parsed.links.length === 0
    ? 'No links'
    : `${checkedLinks} of ${parsed.links.length} links reachable`;

  return (
    <article className="evidence-card">
      <details
        className="evidence-disclosure"
        onToggle={(event) => setExpanded(event.currentTarget.open)}
      >
        <summary onClick={() => setExpanded((current) => !current)}>
          <span className="evidence-summary-copy">
            <strong>{evidenceSummary(parsed.text)}</strong>
            <small>{parsed.attachments.length} files · {linkSummary}</small>
          </span>
          <span className="evidence-summary-date">
            {evidence.created_at ? new Date(evidence.created_at).toLocaleDateString() : 'Submitted'}
          </span>
        </summary>
        {expanded && (
          <div className="evidence-disclosure-content">
            {parsed.text && <p className="evidence-copy">{parsed.text}</p>}
            {parsed.links.map((link) => (
              <a className="evidence-link" href={link} target="_blank" rel="noreferrer" key={link}>
                {link} ↗
              </a>
            ))}
            {parsed.links.length > 0 && (
              <p className="evidence-source-note">
                Links are checked for reachability and limited metadata only.
              </p>
            )}
            {relatedCriteria.length > 0 && (
              <p className="evidence-related-criteria">
                Related criteria: {relatedCriteria.join(' · ')}
              </p>
            )}
            <EvidenceAttachments
              userId={userId}
              evidenceId={evidence.id}
              attachments={parsed.attachments}
            />
            {evidence.ai_report && (
              <AdvisoryCard report={evidence.ai_report} linkFacts={evidence.link_checks} />
            )}
          </div>
        )}
      </details>
      <p className="evidence-advisory-note">AI advises. You decide.</p>
    </article>
  );
}
