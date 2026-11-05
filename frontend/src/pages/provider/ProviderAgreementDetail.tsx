import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, formatMoney, type Agreement, type AuditEntry } from '../../api';
import { AdvisoryCard } from '../../components/AdvisoryCard';
import { MilestoneTracker } from '../../components/MilestoneTracker';
import { NextStep } from '../../components/NextStep';
import { StatusBadge } from '../../components/StatusBadge';
import { useRole } from '../../context/RoleContext';
import { InvoiceTable } from '../../components/InvoiceTable';
import {
  agreementNextStep,
  DESIGN_SAMPLE_PARTIAL,
  DESIGN_SAMPLE_SUFFICIENT,
} from '../../presentation';

function ProviderAgreementDetail() {
  const { id = '' } = useParams();
  const { user, demoMode } = useRole();
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [evidenceText, setEvidenceText] = useState<Record<string, string>>({});
  const [evidenceLinks, setEvidenceLinks] = useState<Record<string, string>>({});
  const [revisionNote, setRevisionNote] = useState('');

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [nextAgreement, nextAudit] = await Promise.all([
        api.getAgreement('provider', id, user.id),
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
  const hasPendingPayment = useMemo(() => agreement?.milestones.some((item) => item.status === 'PAYMENT_PENDING') ?? false, [agreement]);
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

  async function submitEvidence(milestoneId: string) {
    const links = (evidenceLinks[milestoneId] ?? '').split('\n').map((item) => item.trim()).filter(Boolean);
    setBusy(`evidence-${milestoneId}`);
    setError('');
    try {
      await api.submitEvidence(user.id, id, milestoneId, evidenceText[milestoneId] ?? '', links);
      setEvidenceText((current) => ({ ...current, [milestoneId]: '' }));
      setEvidenceLinks((current) => ({ ...current, [milestoneId]: '' }));
      await load(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Evidence could not be submitted.');
    } finally {
      setBusy('');
    }
  }

  if (loading) return <div className="loading-panel"><span className="spinner" /> Loading agreement…</div>;
  if (!agreement) return <div className="alert alert-error" role="alert">{error || 'Agreement not found.'} <Link to="/provider">Back to work</Link></div>;

  return (
    <>
      <div className="breadcrumb"><Link to="/provider">My work</Link><span>/</span><span>{agreement.title}</span></div>
      <div className="page-heading detail-heading">
        <div><p className="eyebrow">PROVIDER AGREEMENT</p><h1>{agreement.title}</h1><p className="page-subtitle">{formatMoney(agreement.total_amount_cents)} total · {agreement.milestones.length} milestones</p></div>
        <StatusBadge status={agreement.status} />
      </div>
      <NextStep>{agreementNextStep(agreement, 'provider')}</NextStep>
      {error && <div className="alert alert-error" role="alert">{error} <button type="button" className="text-button" onClick={() => void load()}>Retry</button></div>}

      {agreement.status === 'PROPOSED' && (
        <section className="card proposal-actions">
          <div><p className="eyebrow">CLIENT PROPOSAL</p><h2>Review the agreement</h2><p className="muted">Accept to activate the project, or decline with an optional note.</p></div>
          <div className="form-actions">
            <button type="button" className="button button-secondary" disabled={busy !== ''} onClick={() => void act('refuse', () => api.refuseAgreement(user.id, agreement.id, revisionNote))}>{busy === 'refuse' ? 'Declining…' : 'Decline proposal'}</button>
            <button type="button" className="button button-primary" disabled={busy !== ''} onClick={() => void act('accept', () => api.acceptAgreement(user.id, agreement.id))}>{busy === 'accept' ? 'Accepting…' : 'Accept agreement'}</button>
          </div>
          <label className="field proposal-note"><span>Note <small>optional</small></span><input className="text-input" value={revisionNote} onChange={(event) => setRevisionNote(event.target.value)} placeholder="Add context for the client" /></label>
        </section>
      )}

      <MilestoneTracker milestones={agreement.milestones} />
      <section className="card section-card">
        <div className="section-heading"><div><p className="eyebrow">PAYMENT RECORD</p><h2>Invoices</h2></div></div>
        <InvoiceTable agreement={agreement} />
      </section>
      <section className="provider-milestones">
        {agreement.milestones.map((milestone) => (
          <article className="card section-card provider-milestone-card" key={milestone.id}>
            <div className="section-heading">
              <div><p className="eyebrow">MILESTONE {String(milestone.order).padStart(2, '0')} · {formatMoney(milestone.amount_cents)}</p><h2>{milestone.title}</h2></div>
              <StatusBadge status={milestone.status} />
            </div>
            <p className="milestone-description">{milestone.description}</p>
            <div className="criteria-block"><h3 className="subsection-title">Acceptance criteria</h3><ul className="plain-list">{milestone.acceptance_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul></div>

            {milestone.status === 'PENDING' || milestone.status === 'REVISION_REQUESTED' ? (
              <div className="provider-action-row">
                <p className="muted">{milestone.order > 1 ? 'Previous milestone must be paid before this work can start.' : 'Ready when you are.'}</p>
                <button type="button" className="button button-primary" disabled={busy !== '' || (milestone.order > 1 && agreement.milestones[milestone.order - 2]?.status !== 'PAID')} onClick={() => void act(`start-${milestone.id}`, () => api.startMilestone(user.id, agreement.id, milestone.id))}>
                  {busy === `start-${milestone.id}` ? 'Starting…' : 'Start milestone'}
                </button>
              </div>
            ) : null}

            {milestone.status === 'IN_PROGRESS' && (
              <div className="evidence-form">
                <h3 className="subsection-title">Submit evidence</h3>
                {demoMode === 'mock' && milestone.order === 1 && (
                  <details className="sample-evidence">
                    <summary>Use sample design evidence for the demo</summary>
                    <p className="muted">In mock mode, the AI advisory simulates criterion matching. Client approval remains a separate human decision.</p>
                    <div className="form-actions">
                      <button type="button" className="button button-secondary" onClick={() => setEvidenceText((current) => ({ ...current, [milestone.id]: DESIGN_SAMPLE_PARTIAL }))}>Load partial sample</button>
                      <button type="button" className="button button-secondary" onClick={() => setEvidenceText((current) => ({ ...current, [milestone.id]: DESIGN_SAMPLE_SUFFICIENT }))}>Load complete sample</button>
                    </div>
                  </details>
                )}
                <label className="field"><span>What did you deliver?</span><textarea className="text-area" rows={3} value={evidenceText[milestone.id] ?? ''} onChange={(event) => setEvidenceText((current) => ({ ...current, [milestone.id]: event.target.value }))} placeholder="Describe the completed work and how it meets the criteria…" /></label>
                <label className="field"><span>Evidence links <small>one URL per line</small></span><textarea className="text-area compact-area" rows={2} value={evidenceLinks[milestone.id] ?? ''} onChange={(event) => setEvidenceLinks((current) => ({ ...current, [milestone.id]: event.target.value }))} placeholder="https://…" /></label>
                <div className="form-actions">
                  <button type="button" className="button button-secondary" disabled={busy !== '' || (!(evidenceText[milestone.id] ?? '').trim() && !(evidenceLinks[milestone.id] ?? '').trim())} onClick={() => void submitEvidence(milestone.id)}>
                    {busy === `evidence-${milestone.id}` ? <><span className="spinner" /> Assessing…</> : 'Submit evidence'}
                  </button>
                  {milestone.evidence.length > 0 && <button type="button" className="button button-primary" disabled={busy !== ''} onClick={() => void act(`review-${milestone.id}`, () => api.submitForReview(user.id, agreement.id, milestone.id))}>{busy === `review-${milestone.id}` ? 'Submitting…' : 'Submit for client review'}</button>}
                </div>
              </div>
            )}

            {milestone.evidence.length > 0 && (
              <div className="evidence-stack provider-evidence">
                <h3 className="subsection-title">Submitted evidence & advisory</h3>
                {milestone.evidence.map((item) => (
                  <div className="evidence-card" key={item.id}>
                    <p className="evidence-copy">{(() => {
                      try {
                        const parsed = JSON.parse(item.content) as { text?: unknown };
                        return typeof parsed.text === 'string' ? parsed.text : item.content;
                      } catch { return item.content; }
                    })()}</p>
                    {item.ai_report && <AdvisoryCard report={item.ai_report} linkFacts={item.link_checks} />}
                  </div>
                ))}
              </div>
            )}

            {milestone.invoices[0] && (
              <div className="provider-payment-status">
                <span>Invoice {milestone.invoices[0].paypal_invoice_id ?? 'being prepared'}</span>
                <StatusBadge status={milestone.invoices[0].status} />
                {milestone.invoices[0].status === 'PAID' && audit.some((entry) =>
                  entry.action === 'paypal_invoice_status_updated'
                  && entry.entity_id === milestone.invoices[0].id
                  && entry.details.status === 'PAID',
                ) && (
                  <p className="webhook-confirmed" role="status" aria-live="polite">
                    <span aria-hidden="true">✓</span>
                    <span><strong>Payment confirmed by PayPal webhook</strong><small>Milestone marked paid · event traced in activity</small></span>
                  </p>
                )}
                {milestone.status === 'PAYMENT_PENDING' && (
                  <button type="button" className="button button-secondary" disabled={busy !== ''} onClick={() => void act(`sync-${milestone.id}`, () => api.syncInvoice(user.id, milestone.invoices[0].id))}>{busy === `sync-${milestone.id}` ? 'Refreshing…' : 'Refresh payment status'}</button>
                )}
              </div>
            )}
          </article>
        ))}
      </section>
    </>
  );
}

export default ProviderAgreementDetail;
