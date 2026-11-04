import type { EvidenceReport, LinkCheckFact } from '../api';

const verdictLabels = {
  sufficient: 'Evidence looks complete',
  partial: 'Some evidence is available',
  insufficient: 'More evidence may be needed',
} as const;

export function AdvisoryCard({
  report,
  linkFacts = [],
}: {
  report: EvidenceReport;
  linkFacts?: LinkCheckFact[];
}) {
  return (
    <section className="advisory-card" aria-label="Evidence Agent advisory">
      <div className="advisory-banner">
        <span aria-hidden="true">✦</span>
        <strong>AI advisory only. Human approval required.</strong>
      </div>
      <div className="advisory-body">
        <div className="advisory-heading">
          <div>
            <p className="eyebrow">Evidence Agent</p>
            <h3>{verdictLabels[report.overall_verdict]}</h3>
          </div>
          <span className={`verdict-pill verdict-${report.overall_verdict}`}>
            {report.overall_verdict}
          </span>
        </div>
        {report.criteria_results.length > 0 && (
          <ul className="criteria-list">
            {report.criteria_results.map((item) => (
              <li key={item.criterion} className="criterion-row">
                <span className={`criterion-status criterion-${item.status}`}>
                  {item.status === 'verified'
                    ? '✓ Verified'
                    : item.status === 'missing'
                      ? '○ Missing'
                      : '– Not verifiable'}
                </span>
                <div>
                  <strong>{item.criterion}</strong>
                  <p>{item.explanation}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {report.report && <p className="advisory-report">{report.report}</p>}
        {linkFacts.length > 0 && (
          <div className="link-facts">
            <h4>Deterministic link checks</h4>
            <p className="muted small-copy">These checks confirm reachability and public metadata, not that a deliverable meets its criteria.</p>
            {linkFacts.map((fact) => (
              <article className="link-fact" key={fact.url}>
                <a href={fact.https ? fact.url : undefined} target="_blank" rel="noreferrer">
                  {fact.url}
                </a>
                <span className={`fact-result fact-${fact.result}`}>
                  {fact.result === 'checked'
                    ? `HTTP ${fact.http_status ?? '—'}`
                    : fact.result === 'blocked'
                      ? 'Blocked'
                      : 'Unavailable'}
                </span>
                {fact.title && <p>Page title: {fact.title}</p>}
                <small>{fact.reason}</small>
                {fact.github_repo_exists !== null && (
                  <div className="github-facts">
                    <strong>Public GitHub repository: {fact.github_repo_exists ? 'found' : 'not found'}</strong>
                    <ul>
                      {fact.github_expected_files.map((file) => (
                        <li key={file.name}>{file.present ? '✓' : '○'} {file.name}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
