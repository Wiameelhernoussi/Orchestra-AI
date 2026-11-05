import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, formatMoney, type Agreement, type AuditEntry } from '../../api';
import { AdvisoryCard } from '../../components/AdvisoryCard';
import { MilestoneTracker } from '../../components/MilestoneTracker';
import { NextStep } from '../../components/NextStep';
import { StatusBadge } from '../../components/StatusBadge';
import { useRole } from '../../context/RoleContext';
import { InvoiceTable } from '../../components/InvoiceTable';
import { activityDescription, agreementNextStep } from '../../presentation';

function evidenceText(content: string): { text: string; links: string[] } {
  try {
    const parsed: unknown = JSON.parse(content);
    if (typeof parsed === 'object' && parsed !== null && 'text' in parsed) {
      const value = parsed as { text?: unknown; links?: unknown };
      return {
        text: typeof value.text === 'string' ? value.text : content,
        links: Array.isArray(value.links) ? value.links.filter((item): item is string => typeof item === 'string') : [],
      };
    }
  } catch {
    // Older evidence records store plain text.
  }
  return { text: content, links: [] };
}

function ClientAgreementDetail() {
  const { id = '' } = useParams();
  const { user, demoMode } = useRole();
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});

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

  if (loading) return <div className="loading-panel"><span className="spinner" /> Loading agreement…</div>;
  if (!agreement) {
    return <div className="alert alert-error" role="alert">{error || 'Agreement not found.'} <Link to="/client">Back to agreements</Link></div>;
  }
  const paidTotal = agreement.milestones.filter((item) => item.status === 'PAID').reduce((sum, item) => sum + item.amount_cents, 0);
  return (
    <>
      <div className="breadcrumb"><Link to="/client">Agreements</Link><span>/</span><span>{agreement.title}</span></div>
      <div className="page-heading detail-heading">
        <div>
          <p className="eyebrow">CLIENT AGREEMENT</p>
          <h1>{agreement.title}</h1>
          <p className="page-subtitle">{formatMoney(paidTotal)} paid of {formatMoney(agreement.total_amount_cents)} · {agreement.milestones.length} milestones</p>
        </div>
        <StatusBadge status={agreement.status} />
      </div>
      <NextStep>{agreementNextStep(agreement, 'client')}</NextStep>
      {error && <div className="alert alert-error" role="alert">{error} <button type="button" className="text-button" onClick={() => void load()}>Retry</button></div>}

      <MilestoneTracker milestones={agreement.milestones} />
      <section className="card section-card">
        <div className="section-heading"><div><p className="eyebrow">PAYMENT RECORD</p><h2>Invoices</h2></div></div>
        <InvoiceTable agreement={agreement} />
      </section>

      <section className="detail-sections">
        <div className="detail-main-column">
          {agreement.milestones.map((milestone) => (
            <section className="card section-card" key={milestone.id}>
              <div className="section-heading">
                <div><p className="eyebrow">MILESTONE {String(milestone.order).padStart(2, '0')}</p><h2>{milestone.title}</h2></div>
                <StatusBadge status={milestone.status} />
              </div>
              <h3 className="subsection-title">Acceptance criteria</h3>
              <ul className="plain-list criteria-plain-list">
                {milestone.acceptance_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}
              </ul>

              {milestone.evidence.length > 0 && (
                <div className="evidence-stack">
                  <h3 className="subsection-title">Provider evidence</h3>
                  {milestone.evidence.map((item) => {
                    const parsed = evidenceText(item.content);
                    return (
                      <article className="evidence-card" key={item.id}>
                        <div className="evidence-meta"><span>Submitted evidence</span><span>{item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span></div>
                        {parsed.text && <p className="evidence-copy">{parsed.text}</p>}
                        {parsed.links.map((link) => <a className="evidence-link" href={link} target="_blank" rel="noreferrer" key={link}>{link} ↗</a>)}
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
                  <div className="form-actions">
                    <button className="button button-secondary" disabled={busy !== ''} onClick={() => void act(`revision-${milestone.id}`, () => api.requestRevision(user.id, agreement.id, milestone.id, revisionNotes[milestone.id] ?? milestone.evidence[milestone.evidence.length - 1]?.ai_report?.revision_request_draft ?? ''))}>
                      {busy === `revision-${milestone.id}` ? 'Requesting…' : 'Request revision'}
                    </button>
                    <button className="button button-primary" disabled={busy !== ''} onClick={() => void act(`approve-${milestone.id}`, () => api.approveMilestone(user.id, agreement.id, milestone.id))}>
                      {busy === `approve-${milestone.id}` ? 'Approving…' : 'Approve deliverable'}
                    </button>
                  </div>
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
                      <button type="button" className="button button-secondary" disabled={busy !== ''} onClick={() => void act(`sync-${milestone.id}`, () => api.syncInvoice(user.id, milestone.invoices[0].id))}>
                        Simulate mock payment
                      </button>
                    ) : milestone.invoices[0].status === 'SENT' ? (
                      <a className="button button-paypal" href={milestone.invoices[0].payer_view_url ?? undefined} target="_blank" rel="noreferrer">
                        Pay with PayPal Sandbox <span aria-hidden="true">↗</span>
                      </a>
                    ) : milestone.status === 'APPROVED' ? (
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
                ) : milestone.status === 'APPROVED' ? (
                  <button className="button button-primary" disabled={busy !== ''} onClick={() => void createInvoice(milestone.id)}>
                    {busy === `invoice-${milestone.id}` ? <><span className="spinner spinner-light" /> Creating invoice…</> : 'Create PayPal invoice'}
                  </button>
                ) : (
                  <p className="muted small-copy">A PayPal invoice becomes available after your approval.</p>
                )}
              </div>
            </section>
          ))}
        </div>

        <aside className="card section-card audit-card">
          <div className="section-heading"><div><p className="eyebrow">TRACEABILITY</p><h2>Activity</h2></div><span className="audit-count">{audit.length}</span></div>
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
        </aside>
      </section>
    </>
  );
}

export default ClientAgreementDetail;
