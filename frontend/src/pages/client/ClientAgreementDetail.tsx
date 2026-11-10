import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, formatMoney, parseEvidenceContent, type Agreement, type AuditEntry } from '../../api';
import { AdvisoryCard } from '../../components/AdvisoryCard';
import { AgreementSummaryStrip, MilestoneRail } from '../../components/AgreementWorkspaceNavigation';
import { EvidenceAttachments } from '../../components/EvidenceAttachments';
import { StatusBadge } from '../../components/StatusBadge';
import { useRole } from '../../context/RoleContext';
import { InvoiceTable } from '../../components/InvoiceTable';
import { PaymentReadinessPanel } from '../../components/PaymentReadinessPanel';
import { activityDescription, agreementNextStep } from '../../presentation';

function ClientAgreementDetail() {
  const { id = '' } = useParams();
  const { user, demoMode } = useRole();
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});
  const [approvalConfirmation, setApprovalConfirmation] = useState<string | null>(null);
  const [approvalAcknowledged, setApprovalAcknowledged] = useState(false);
  const [selectedMilestoneId, setSelectedMilestoneId] = useState('');

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [nextAgreement, nextAudit] = await Promise.all([
        api.getAgreement('client', id, user.id),
        api.auditLogs(user.id, id),
      ]);
      setAgreement(nextAgreement);
      setAudit(nextAudit);
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Agreement could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [id, user.id]);

  useEffect(() => { void load(); }, [load]);
  const hasPendingPayment = useMemo(
    () => agreement?.milestones.some((item) => item.status === 'PAYMENT_PENDING') ?? false,
    [agreement],
  );
  useEffect(() => {
    if (!hasPendingPayment) return;
    const timer = window.setInterval(() => { void load(true); }, 3000);
    return () => window.clearInterval(timer);
  }, [hasPendingPayment, load]);

  async function act(key: string, operation: () => Promise<unknown>) {
    setBusy(key);
    setError('');
    try {
      await operation();
      await load(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The action could not be completed.');
    } finally {
      setBusy('');
    }
  }

  async function createInvoice(milestoneId: string) {
    setBusy(`invoice-${milestoneId}`);
    setError('');
    try {
      await api.createInvoice(user.id, milestoneId);
      await load(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The invoice could not be created.');
    } finally {
      setBusy('');
    }
  }

  async function approveMilestone(milestoneId: string, acknowledgeUnverified: boolean) {
    await act(`approve-${milestoneId}`, async () => {
      await api.approveMilestone(user.id, agreement!.id, milestoneId, acknowledgeUnverified);
      setApprovalConfirmation(null);
      setApprovalAcknowledged(false);
    });
  }

  function beginApproval(milestone: Agreement['milestones'][number]) {
    const unverified = milestone.payment_readiness.criteria_summary.criteria.some(
      (item) => item.status !== 'verified',
    );
    if (milestone.payment_readiness.advisory_verdict !== 'sufficient' || unverified) {
      setApprovalConfirmation(milestone.id);
      setApprovalAcknowledged(false);
      return;
    }
    void approveMilestone(milestone.id, false);
  }

  if (loading) return <div className="loading-panel"><span className="spinner" /> Loading agreement…</div>;
  if (!agreement) {
    return <div className="alert alert-error" role="alert">{error || 'Agreement not found.'} <Link to="/client">Back to agreements</Link></div>;
  }
  const activeMilestone = agreement.milestones.find((item) => item.id === selectedMilestoneId)
    ?? agreement.milestones.find((item) => item.status === 'IN_REVIEW')
    ?? agreement.milestones.find((item) => item.status !== 'PAID')
    ?? agreement.milestones[0];
  return (
    <>
      <div className="breadcrumb"><Link to="/client">Agreements</Link><span>/</span><span>{agreement.title}</span></div>
      <div className="page-heading detail-heading">
        <div>
          <p className="eyebrow">CLIENT AGREEMENT</p>
          <h1>{agreement.title}</h1>
          <p className="page-subtitle">{agreement.milestones.length} milestones</p>
        </div>
        <StatusBadge status={agreement.status} />
      </div>
      <AgreementSummaryStrip agreement={agreement} role="client" nextAction={agreementNextStep(agreement, 'client')} />
      {error && <div className="alert alert-error" role="alert">{error} <button type="button" className="text-button" onClick={() => void load()}>Retry</button></div>}

      <div className="agreement-detail-workspace">
        <MilestoneRail agreement={agreement} selectedId={activeMilestone?.id ?? ''} onSelect={setSelectedMilestoneId} />
        <section className="agreement-detail-content">
          {agreement.milestones.filter((item) => item.id === activeMilestone?.id).map((milestone) => (
            <section className="card section-card" key={milestone.id}>
              <div className="section-heading">
                <div><p className="eyebrow">MILESTONE {String(milestone.order).padStart(2, '0')}</p><h2>{milestone.title}</h2></div>
                <div className="milestone-status-group">
                  {milestone.payment_readiness.client_acknowledged_advisory && (
                    <span className="approval-advisory-badge">Approved by client (AI advisory was not sufficient)</span>
                  )}
                  <StatusBadge status={milestone.status} />
                </div>
              </div>
              <h3 className="subsection-title">Acceptance criteria</h3>
              <ul className="plain-list criteria-plain-list">
                {milestone.acceptance_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}
              </ul>
              <PaymentReadinessPanel milestone={milestone} role="client" />

              {milestone.evidence.length > 0 && (
                <div className="evidence-stack">
                  <h3 className="subsection-title">Provider evidence</h3>
                  {milestone.evidence.map((item) => {
                    const parsed = parseEvidenceContent(item.content);
                    const relatedCriteria = milestone.criteria?.filter(
                      (criterion) => parsed.criterion_ids.includes(criterion.id),
                    ) ?? [];
                    return (
                      <article className="evidence-card" key={item.id}>
                        <div className="evidence-meta">
                          <span>Evidence submitted · AI advisory only</span>
                          <span>{item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span>
                        </div>
                        {parsed.text && <p className="evidence-copy">{parsed.text}</p>}
                        {parsed.links.map((link) => <a className="evidence-link" href={link} target="_blank" rel="noreferrer" key={link}>{link} ↗</a>)}
                        {parsed.links.length === 0 && parsed.attachments.length === 0 && (
                          <p className="evidence-source-note">
                            Description only — no URL or attachment was submitted, so no external deliverable was available to check.
                          </p>
                        )}
                        {parsed.links.length > 0 && (
                          <p className="evidence-source-note">
                            Submitted URL(s) are shown above. Automated checks only report limited reachability and metadata; they do not verify page contents or criterion relevance.
                          </p>
                        )}
                        {relatedCriteria.length > 0 && (
                          <p className="evidence-related-criteria">
                            Related to: {relatedCriteria.map((criterion) => criterion.description).join(' · ')}
                          </p>
                        )}
                        <EvidenceAttachments userId={user.id} evidenceId={item.id} attachments={parsed.attachments} />
                        <p className="evidence-verification-note">
                          Submitted evidence is not the same as verified evidence. AI criterion results are advisory; your review and approval remain the human gate.
                        </p>
                        {item.ai_report && <AdvisoryCard report={item.ai_report} linkFacts={item.link_checks} />}
                      </article>
                    );
                  })}
                </div>
              )}

              {milestone.status === 'IN_REVIEW' && (
                <div className="decision-panel">
                  <label className="field">
                    <span>Revision notes <small>only needed if requesting changes</small></span>
                    <textarea className="text-area compact-area" rows={3} value={revisionNotes[milestone.id] ?? milestone.evidence[milestone.evidence.length - 1]?.ai_report?.revision_request_draft ?? ''} onChange={(event) => setRevisionNotes((current) => ({ ...current, [milestone.id]: event.target.value }))} placeholder="What should be revised?" />
                  </label>
                  {milestone.payment_readiness.criteria_summary.unverified > 0 && (() => {
                    const unverifiedCriteria = milestone.payment_readiness.criteria_summary.criteria
                      .filter((item) => item.status !== 'verified');
                    return (
                      <div
                        id={`approval-blocker-${milestone.id}`}
                        className="approval-guidance"
                        role="status"
                      >
                        <strong>AI advice does not decide approval.</strong>
                        <p>You may approve after reviewing the submitted evidence yourself. To proceed when the advisory is not sufficient or criteria are unverified, you must confirm your review.</p>
                        <ul>
                          {unverifiedCriteria.map((item) => (
                            <li key={item.criterion}>{item.criterion} <span>({item.status.replace('_', ' ')})</span></li>
                          ))}
                        </ul>
                      </div>
                    );
                  })()}
                  <div className="form-actions sticky-action-bar">
                    <button className="button button-secondary" disabled={busy !== ''} onClick={() => void act(`revision-${milestone.id}`, () => api.requestRevision(user.id, agreement.id, milestone.id, revisionNotes[milestone.id] ?? milestone.evidence[milestone.evidence.length - 1]?.ai_report?.revision_request_draft ?? ''))}>
                      {busy === `revision-${milestone.id}` ? 'Requesting…' : 'Request revision'}
                    </button>
                    <button className="button button-primary" aria-describedby={milestone.payment_readiness.criteria_summary.unverified > 0 ? `approval-blocker-${milestone.id}` : undefined} disabled={busy !== '' || !milestone.payment_readiness.client_approval_allowed || milestone.evidence.length === 0} onClick={() => beginApproval(milestone)}>
                      {busy === `approve-${milestone.id}` ? 'Approving…' : 'Approve deliverable'}
                    </button>
                  </div>
                  {approvalConfirmation === milestone.id && (
                    <div className="approval-confirmation" role="dialog" aria-modal="true" aria-labelledby={`approval-confirmation-title-${milestone.id}`}>
                      <h3 id={`approval-confirmation-title-${milestone.id}`}>Confirm your approval</h3>
                      <p>
                        The Evidence Agent advisory is <strong>{milestone.payment_readiness.advisory_verdict}</strong>.
                        It is advisory only; you are responsible for reviewing the evidence before approving.
                      </p>
                      {milestone.payment_readiness.criteria_summary.criteria.some((item) => item.status !== 'verified') ? (
                        <>
                          <p>These criteria were not verified by the AI:</p>
                          <ul>
                            {milestone.payment_readiness.criteria_summary.criteria
                              .filter((item) => item.status !== 'verified')
                              .map((item) => (
                                <li key={item.criterion}>{item.criterion} <span>({item.status.replace('_', ' ')})</span></li>
                              ))}
                          </ul>
                        </>
                      ) : (
                        <p>No criteria are marked unverified, but the AI advisory was not sufficient.</p>
                      )}
                      <label className="approval-acknowledgement">
                        <input
                          type="checkbox"
                          checked={approvalAcknowledged}
                          onChange={(event) => setApprovalAcknowledged(event.target.checked)}
                        />
                        <span>I reviewed the submitted evidence and attachments myself and accept this decision.</span>
                      </label>
                      <div className="form-actions">
                        <button type="button" className="button button-secondary" onClick={() => {
                          setApprovalConfirmation(null);
                          setApprovalAcknowledged(false);
                        }}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="button button-primary"
                          disabled={!approvalAcknowledged || busy !== ''}
                          onClick={() => void approveMilestone(milestone.id, true)}
                        >
                          {busy === `approve-${milestone.id}` ? 'Approving…' : 'Confirm approval'}
                        </button>
                      </div>
                    </div>
                  )}
                  <p className="human-gate-note">Your approval is recorded before any invoice can be created.</p>
                </div>
              )}

              <div className="payment-panel">
                <div className="payment-heading">
                  <div><p className="eyebrow">PAYMENT</p><h3>{formatMoney(milestone.amount_cents)}</h3></div>
                  {milestone.invoices[0] ? <StatusBadge status={milestone.invoices[0].status} /> : <StatusBadge status={milestone.status} />}
                </div>
                {milestone.invoices[0] ? (
                  <>
                    <div className="invoice-meta">
                      <span>Invoice ID</span><code>{milestone.invoices[0].paypal_invoice_id ?? 'Preparing invoice'}</code>
                    </div>
                    {milestone.invoices[0].status === 'PAID' ? (
                      audit.some((entry) => entry.action === 'paypal_invoice_status_updated' && entry.entity_id === milestone.invoices[0].id && entry.details.status === 'PAID')
                            ? <div className="webhook-confirmed" role="status" aria-live="polite"><span aria-hidden="true">✓</span><span><strong>Payment confirmed by PayPal webhook</strong><small>Milestone marked paid · event traced in activity</small></span></div>
                            : <div className="webhook-confirmed" role="status"><span aria-hidden="true">✓</span><span><strong>Payment confirmed by PayPal</strong><small>Milestone marked paid</small></span></div>
                    ) : milestone.invoices[0].status === 'SENT' && demoMode === 'mock' ? (
                      <button type="button" className="button button-secondary" disabled={busy !== ''} onClick={() => void act(`sync-${milestone.id}`, () => api.simulateMockPayment(user.id, milestone.invoices[0].id))}>
                        Simulate mock payment
                      </button>
                    ) : milestone.invoices[0].status === 'SENT' ? (
                      <a className="button button-paypal" href={milestone.invoices[0].payer_view_url ?? undefined} target="_blank" rel="noreferrer">
                        Pay with PayPal Sandbox <span aria-hidden="true">↗</span>
                      </a>
                    ) : milestone.payment_readiness.paypal_invoice_allowed ? (
                      <button className="button button-primary" disabled={busy !== ''} onClick={() => void createInvoice(milestone.id)}>
                        {busy === `invoice-${milestone.id}` ? <><span className="spinner spinner-light" /> Creating invoice…</> : 'Create PayPal invoice'}
                      </button>
                    ) : null}
                    {milestone.status === 'PAYMENT_PENDING' && milestone.invoices[0].id && (
                      <button type="button" className="button button-secondary refresh-button" disabled={busy !== ''} onClick={() => void act(`sync-${milestone.id}`, () => api.syncInvoice(user.id, milestone.invoices[0].id))}>
                        {busy === `sync-${milestone.id}` ? <><span className="spinner" /> Refreshing…</> : '↻ Refresh status'}
                      </button>
                    )}
                  </>
                ) : milestone.payment_readiness.paypal_invoice_allowed ? (
                  <button className="button button-primary" disabled={busy !== ''} onClick={() => void createInvoice(milestone.id)}>
                    {busy === `invoice-${milestone.id}` ? <><span className="spinner spinner-light" /> Creating invoice…</> : 'Create PayPal invoice'}
                  </button>
                ) : (
                  <p className="muted small-copy">A PayPal invoice becomes available after your approval.</p>
                )}
              </div>
            </section>
          ))}
        </section>
      </div>

      <details className="secondary-detail-accordion card section-card">
        <summary>Payment record and invoices</summary>
        <InvoiceTable agreement={agreement} />
      </details>
      <details className="secondary-detail-accordion card section-card">
        <summary>Activity · {audit.length} events</summary>
        {audit.length === 0 ? <p className="muted">No activity recorded yet.</p> : (
          <ol className="activity-list" aria-label="Agreement activity">
            {audit.slice().reverse().map((entry) => {
              const description = activityDescription(entry);
              return (
                <li className="activity-entry" key={entry.id}>
                  <span className={`activity-dot actor-icon actor-icon-${description.actor.toLowerCase()}`} aria-hidden="true">
                    {description.actor === 'Provider' ? 'P' : description.actor === 'Client' ? 'C' : description.actor === 'AI' ? 'AI' : 'PP'}
                  </span>
                  <div className="activity-copy">
                    <strong>{description.message}</strong>
                    <span>{description.actor}</span>
                  </div>
                  <time dateTime={entry.created_at ?? undefined}>
                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : 'Just now'}
                  </time>
                </li>
              );
            })}
          </ol>
        )}
      </details>
    </>
  );
}

export default ClientAgreementDetail;
