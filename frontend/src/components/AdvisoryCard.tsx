import type { EvidenceReport, LinkCheckFact } from '../api';

const verdictLabels = {
  sufficient: 'Sufficient',
  partial: 'Partial',
  insufficient: 'Insufficient',
} as const;

export function AdvisoryCard({
  report,
  linkFacts = [],
}: {
  report: EvidenceReport;
  linkFacts?: LinkCheckFact[];
}) {
  const unverifiedCount = report.criteria_results.filter((item) => item.status !== 'verified').length;
  return (
    <section className="advisory-card" aria-label="Evidence Agent advisory">
      <div className="advisory-chip-row">
        <span className={`verdict-pill verdict-${report.overall_verdict}`}>
          AI · {verdictLabels[report.overall_verdict]}
        </span>
        <span className="advisory-unverified-count">{unverifiedCount} unverified</span>
      </div>
      <details className="advisory-details">
        <summary>View advisory details</summary>
        <div className="advisory-body">
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
          {report.image_analysis && (
            <details className="advisory-secondary-details">
              <summary>Image observations · advisory only</summary>
              <div className="image-analysis" aria-label="Image evidence analysis">
                <p className="muted small-copy">{report.image_analysis.message}</p>
                {report.image_analysis.status === 'not_analyzed'
                  && report.image_analysis.attachments.some((attachment) => (
                    attachment.content_type === 'image/png'
                    || attachment.content_type === 'image/jpeg'
                  )) && (
                  <p className="image-not-analyzed" role="status">Image not analyzed.</p>
                )}
                {report.image_analysis.attachments.length > 0 && (
                  <ul className="image-analysis-attachments">
                    {report.image_analysis.attachments.map((attachment) => (
                      <li key={attachment.id}>
                        <strong>{attachment.name}</strong>
                        <span>{attachment.status === 'analyzed'
                          ? 'Analyzed'
                          : attachment.status === 'mock_canned'
                            ? 'Mock canned response · pixels not analyzed'
                            : attachment.content_type === 'image/png' || attachment.content_type === 'image/jpeg'
                              ? 'Image not analyzed'
                              : 'Attachment contents not analyzed'}</span>
                        <small>{attachment.message}</small>
                      </li>
                    ))}
                  </ul>
                )}
                {report.image_analysis.criteria_results.length > 0 && (
                  <ul className="image-analysis-results">
                    {report.image_analysis.criteria_results.map((item) => (
                      <li key={item.criterion}>
                        <strong>{item.criterion} · {item.status.replace(/_/g, ' ')}</strong>
                        <p>{item.observation}</p>
                        {item.missing_element && <small>Missing element: {item.missing_element}</small>}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="small-copy">
                  Visual observations do not verify authenticity or functionality. Links are not inspected beyond reachability.
                </p>
              </div>
            </details>
          )}
          {report.report && <p className="advisory-report">{report.report}</p>}
          {linkFacts.length > 0 && (
            <details className="advisory-secondary-details">
              <summary>Link checks · {linkFacts.length}</summary>
              <div className="link-facts">
                {linkFacts.map((fact) => (
                  <article className="link-fact" key={fact.url}>
                    <a href={fact.https ? fact.url : undefined} target="_blank" rel="noreferrer">
                      {fact.url}
                    </a>
                    <span className={`fact-result fact-${fact.result}`}>
                      {fact.result === 'checked'
                        ? fact.http_status !== null && fact.http_status >= 200 && fact.http_status < 400
                          ? `Reachable · HTTP ${fact.http_status}`
                          : `Non-success response · HTTP ${fact.http_status ?? '—'}`
                        : fact.result === 'blocked'
                          ? 'Not checked · blocked by safety policy'
                          : 'Inaccessible to automated checker'}
                    </span>
                    {fact.result === 'checked' && fact.http_status !== null && fact.http_status >= 200 && fact.http_status < 400 && (
                      <p>Reachability and limited metadata only; linked contents and relevance to the criterion are not verified.</p>
                    )}
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
            </details>
          )}
        </div>
      </details>
    </section>
  );
}
