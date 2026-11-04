import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, formatMoney, type Intent } from '../../api';
import { NextStep } from '../../components/NextStep';
import { useRole } from '../../context/RoleContext';

const DEMO_REQUEST =
  'An e-commerce company needs a website from a digital agency. Total budget $600: Design $150, Development $350, Final Handover $100.';

function NewAgreementWizard() {
  const { user } = useRole();
  const navigate = useNavigate();
  const [requestText, setRequestText] = useState(DEMO_REQUEST);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [busy, setBusy] = useState<'parse' | 'propose' | null>(null);
  const [error, setError] = useState('');

  function updateMilestone(index: number, patch: Partial<Intent['milestones'][number]>) {
    setIntent((current) => current && ({
      ...current,
      milestones: current.milestones.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function acceptCriterionRewrite(milestoneIndex: number, criterion: string, rewrite: string) {
    setIntent((current) => current && ({
      ...current,
      milestones: current.milestones.map((milestone, index) => {
        if (index !== milestoneIndex) return milestone;
        const criteria = [...milestone.acceptance_criteria];
        const criterionIndex = criteria.indexOf(criterion);
        if (criterionIndex >= 0) criteria[criterionIndex] = rewrite;
        return { ...milestone, acceptance_criteria: criteria };
      }),
    }));
  }

  async function analyze() {
    setBusy('parse');
    setError('');
    try {
      const parsed = await api.parseIntent(user.id, requestText);
      setIntent(parsed);
      setAnswers(parsed.missing_information.map(() => ''));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The request could not be analyzed.');
    } finally {
      setBusy(null);
    }
  }

  async function propose() {
    if (!intent) return;
    setBusy('propose');
    setError('');
    try {
      const answered = intent.missing_information
        .map((question, index) => answers[index]?.trim() ? `${question}: ${answers[index].trim()}` : '')
        .filter(Boolean);
      const remaining = intent.missing_information.filter((_, index) => !answers[index]?.trim());
      const payload: Intent = {
        ...intent,
        requirements: [...intent.requirements, ...answered],
        missing_information: remaining,
      };
      const agreement = await api.createAgreement(user.id, payload);
      await api.publishAgreement(user.id, agreement.id);
      navigate(`/client/agreements/${agreement.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The agreement could not be proposed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="breadcrumb"><Link to="/client">Agreements</Link><span>/</span><span>New agreement</span></div>
      <div className="page-heading compact-heading">
        <div>
          <p className="eyebrow">NEW AGREEMENT · STEP 1 OF 2</p>
          <h1>Start with the intent.</h1>
          <p className="page-subtitle">AI structures the request. You review every term before proposing it.</p>
        </div>
      </div>
      <NextStep>
        {intent
          ? 'Review the proposed milestones, fill in anything missing, and send the agreement to your provider.'
          : 'Describe the work and budget. The Intent Agent will flag details that still need your input.'}
      </NextStep>

      <section className="card wizard-section">
        <div className="section-title-row">
          <div className="step-number">01</div>
          <div><h2>Describe your project</h2><p className="muted">Be clear about the outcome and budget. Unknowns stay visible.</p></div>
        </div>
        <label className="field-label" htmlFor="project-request">Business request</label>
        <textarea
          id="project-request"
          className="text-area"
          rows={5}
          value={requestText}
          onChange={(event) => setRequestText(event.target.value)}
          placeholder="Describe the work, budget, deliverables, and timeline…"
        />
        <div className="form-actions">
          <button type="button" className="button button-primary" disabled={busy !== null || !requestText.trim()} onClick={() => void analyze()}>
            {busy === 'parse' ? <><span className="spinner spinner-light" /> Analyzing…</> : <><span aria-hidden="true">✦</span> Analyze with AI</>}
          </button>
          <span className="helper-text">Your agreement stays a draft until you review and propose it.</span>
        </div>
      </section>

      {error && (
        <div className={`alert ${error.toLowerCase().includes('busy') ? 'alert-warning' : 'alert-error'}`} role="alert">
          <span>{error}</span>
          {error.toLowerCase().includes('busy') && (
            <button type="button" className="text-button" onClick={() => void analyze()} disabled={busy !== null}>Retry</button>
          )}
        </div>
      )}

      {intent && (
        <section className="card wizard-section result-section">
          <div className="section-title-row">
            <div className="step-number">02</div>
            <div><p className="eyebrow">REVIEW BEFORE YOU PROPOSE</p><h2>{intent.project_type}</h2></div>
          </div>
          <div className="intent-summary">
            <div><span className="summary-label">Total budget</span><strong>{formatMoney(intent.budget_cents)}</strong></div>
            <div><span className="summary-label">Currency</span><strong>{intent.currency}</strong></div>
            <div><span className="summary-label">Deadline</span><strong>{intent.deadline || 'Not specified'}</strong></div>
          </div>

          {intent.missing_information.length > 0 && (
            <div className="missing-box">
              <div className="missing-heading"><span aria-hidden="true">!</span><div><h3>Information still needed</h3><p>AI did not guess these details. Add answers now or leave them open.</p></div></div>
              <div className="missing-fields">
                {intent.missing_information.map((question, index) => (
                  <label className="field" key={`${question}-${index}`}>
                    <span>{question}</span>
                    <input
                      className="text-input"
                      value={answers[index] ?? ''}
                      onChange={(event) => setAnswers((current) => current.map((answer, answerIndex) => answerIndex === index ? event.target.value : answer))}
                      placeholder="Add an answer (optional)"
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="milestone-editor-list">
            {intent.milestones.map((milestone, index) => (
              <article className="milestone-editor" key={`${milestone.title}-${index}`}>
                <div className="milestone-editor-heading">
                  <span className="milestone-index">{String(index + 1).padStart(2, '0')}</span>
                  <label className="field milestone-name-field">
                    <span>Milestone</span>
                    <input className="text-input" value={milestone.title} onChange={(event) => updateMilestone(index, { title: event.target.value })} />
                  </label>
                  <label className="field amount-field">
                    <span>Amount (USD)</span>
                    <input
                      className="text-input"
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={(milestone.amount_cents / 100).toFixed(2)}
                      onChange={(event) => updateMilestone(index, { amount_cents: Math.round(Number(event.target.value) * 100) })}
                    />
                  </label>
                </div>
                <label className="field">
                  <span>Deliverables <small>one per line</small></span>
                  <textarea className="text-area compact-area" rows={2} value={milestone.deliverables.join('\n')} onChange={(event) => updateMilestone(index, { deliverables: event.target.value.split('\n').map((line) => line.trim()).filter(Boolean) })} />
                </label>
                <label className="field">
                  <span>Acceptance criteria <small>one per line</small></span>
                  <textarea className="text-area compact-area" rows={2} value={milestone.acceptance_criteria.join('\n')} onChange={(event) => updateMilestone(index, { acceptance_criteria: event.target.value.split('\n').map((line) => line.trim()).filter(Boolean) })} />
                </label>
                {milestone.criteria_quality?.filter((item) => !item.objectively_verifiable && item.rewritten_criterion).map((item) => {
                  const accepted = milestone.acceptance_criteria.includes(item.rewritten_criterion);
                  return (
                    <div className="criterion-quality" key={`${item.criterion}-${item.rewritten_criterion}`}>
                      <p><strong>Needs a measurable check:</strong> {item.reason}</p>
                      <p><span className="muted">Original:</span> {item.criterion}</p>
                      <p><span className="muted">Suggested rewrite:</span> {item.rewritten_criterion}</p>
                      <button
                        type="button"
                        className={accepted ? 'text-button quality-accepted' : 'text-button'}
                        disabled={accepted}
                        onClick={() => acceptCriterionRewrite(index, item.criterion, item.rewritten_criterion)}
                      >
                        {accepted ? 'Rewrite accepted' : 'Use this rewrite'}
                      </button>
                    </div>
                  );
                })}
              </article>
            ))}
          </div>
          <div className="total-check">
            <span>Milestone total</span>
            <strong className={intent.milestones.reduce((sum, item) => sum + item.amount_cents, 0) === intent.budget_cents ? 'amount-match' : 'amount-mismatch'}>
              {formatMoney(intent.milestones.reduce((sum, item) => sum + item.amount_cents, 0))}
              {intent.milestones.reduce((sum, item) => sum + item.amount_cents, 0) === intent.budget_cents ? ' · Matches budget' : ` · Budget is ${formatMoney(intent.budget_cents)}`}
            </strong>
          </div>
          <div className="form-actions form-actions-end">
            <Link to="/client" className="button button-secondary">Cancel</Link>
            <button type="button" className="button button-primary" disabled={busy !== null || intent.milestones.some((item) => !item.title.trim() || !item.deliverables.length || !item.acceptance_criteria.length) || intent.milestones.reduce((sum, item) => sum + item.amount_cents, 0) !== intent.budget_cents} onClick={() => void propose()}>
              {busy === 'propose' ? <><span className="spinner spinner-light" /> Sending…</> : 'Propose agreement'}
            </button>
          </div>
        </section>
      )}
    </>
  );
}

export default NewAgreementWizard;
