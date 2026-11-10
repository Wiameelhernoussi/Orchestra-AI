import type { Milestone } from '../api';

const STEPS = [
  { title: 'Started', actor: 'Provider', icon: '↗' },
  { title: 'Evidence submitted', actor: 'Provider', icon: '▤' },
  { title: 'AI advisory', actor: 'AI', icon: '✳' },
  { title: 'Client approval', actor: 'Client', icon: '✓' },
  { title: 'Invoice sent', actor: 'PayPal', icon: '$' },
  { title: 'Paid', actor: 'PayPal', icon: '✓' },
];

export function proofToPayProgress(milestone: Milestone): number {
  if (milestone.status === 'PAID') return STEPS.length - 1;
  if (milestone.status === 'PAYMENT_PENDING') return 5;
  if (milestone.status === 'INVOICE_CANCELLED' || milestone.status === 'INVOICE_EXPIRED') return 4;
  if (milestone.status === 'APPROVED' || milestone.status === 'INVOICING') return 4;
  if (milestone.status === 'IN_REVIEW' || milestone.status === 'REVISION_REQUESTED') {
    return milestone.status === 'REVISION_REQUESTED'
      ? 1
      : milestone.evidence.some((item) => item.ai_report) ? 3 : 2;
  }
  if (milestone.status === 'IN_PROGRESS') {
    if (milestone.evidence.some((item) => item.ai_report)) return 3;
    if (milestone.evidence.length > 0) return 2;
    return 1;
  }
  return 0;
}

function completedSteps(milestone: Milestone): number {
  if (milestone.status === 'PAID') return STEPS.length;
  const progress = proofToPayProgress(milestone);
  if (milestone.status === 'PENDING') return 0;
  if (milestone.status === 'IN_PROGRESS') {
    if (milestone.evidence.some((item) => item.ai_report)) return 3;
    return milestone.evidence.length > 0 ? 2 : 1;
  }
  if (milestone.status === 'REVISION_REQUESTED') return 1;
  if (milestone.status === 'IN_REVIEW') {
    return milestone.evidence.some((item) => item.ai_report) ? 3 : 2;
  }
  if (milestone.status === 'APPROVED') return 4;
  if (milestone.status === 'INVOICING') return 4;
  if (
    milestone.status === 'PAYMENT_PENDING' ||
    milestone.status === 'INVOICE_CANCELLED' ||
    milestone.status === 'INVOICE_EXPIRED'
  ) return 5;
  return progress;
}

export function ProofToPay({ milestone }: { milestone: Milestone }) {
  const current = proofToPayProgress(milestone);
  const completed = completedSteps(milestone);
  const readiness = milestone.payment_readiness;
  const readinessLabel = readiness.status.replace(/_/g, ' ').toLowerCase();
  const invoiceAllowed = readiness.paypal_invoice_allowed;

  return (
    <section className="proof-to-pay" aria-label={`Proof-to-Pay for ${milestone.title}`}>
      <div className="proof-to-pay-heading">
        <span className="proof-to-pay-label">PROOF-TO-PAY</span>
        <span className="proof-to-pay-current">{milestone.status === 'PAID' ? 'Complete' : `Step ${current + 1} of ${STEPS.length}`}</span>
      </div>
      <ol className="proof-steps" aria-label="Proof-to-Pay workflow steps">
        {STEPS.map((step, index) => {
          const isComplete = index < completed;
          const isCurrent = index === current && milestone.status !== 'PAID';
          return (
            <li
              className={`proof-step${isComplete ? ' is-complete' : ''}${isCurrent ? ' is-current' : ''}`}
              key={step.title}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="proof-step-track" aria-hidden="true" />
              <span className="proof-step-icon" aria-hidden="true">{isComplete ? '✓' : step.icon}</span>
              <strong>{step.title}</strong>
              <span className="proof-step-actor">
                <span className={`actor-mark actor-${step.actor.toLowerCase()}`} aria-hidden="true">{step.actor === 'Provider' ? 'P' : step.actor === 'Client' ? 'C' : step.actor === 'PayPal' ? 'PP' : 'AI'}</span>
                {step.actor}
              </span>
            </li>
          );
        })}
      </ol>

      <section className={`readiness-panel${readiness.ready ? ' is-ready' : ''}`} aria-label="Payment readiness">
        <div className="readiness-heading">
          <div>
            <span className="proof-to-pay-label">PAYMENT READINESS</span>
            <strong className="readiness-score">{readiness.score}%</strong>
          </div>
          <span className={`readiness-status readiness-${readiness.status.toLowerCase()}`}>
            {readinessLabel}
          </span>
        </div>
        <div
          className="readiness-progress"
          role="progressbar"
          aria-label="Payment readiness score"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={readiness.score}
        >
          <span style={{ width: `${readiness.score}%` }} />
        </div>
        <ul className="readiness-checks">
          {readiness.checks.map((check) => (
            <li className={check.complete ? 'is-complete' : check.required ? 'is-pending' : 'is-optional'} key={check.key}>
              <span aria-hidden="true">{check.complete ? '✓' : check.required ? '○' : '—'}</span>
              <span>{check.label}{!check.required && <small> Optional</small>}</span>
            </li>
          ))}
        </ul>

        {readiness.ready && invoiceAllowed ? (
          <div className="readiness-unlocked" role="status">
            <strong>✓ Payment unlocked</strong>
            <span>Human approval recorded. PayPal invoice creation is available.</span>
          </div>
        ) : readiness.status !== 'INVOICE_SENT' && readiness.status !== 'PAID' ? (
          <div className="readiness-blocked">
            <strong>{readiness.status === 'READY_FOR_APPROVAL' ? 'Ready for client approval' : 'Payment blocked'}</strong>
            {readiness.blocking_reasons.length > 0 && (
              <ul>
                {readiness.blocking_reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            )}
          </div>
        ) : null}
        <p className="readiness-next-action">
          <strong>Next action · {readiness.next_action.actor}</strong>
          <span>{readiness.next_action.action}</span>
        </p>
        {readiness.criteria_summary.total > 0 && (
          <p className="readiness-criteria-summary">
            {readiness.criteria_summary.verified}/{readiness.criteria_summary.total} criteria verified
          </p>
        )}
      </section>
    </section>
  );
}
