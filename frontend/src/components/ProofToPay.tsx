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

  return (
    <section className="proof-to-pay" aria-label={`Proof-to-Pay for ${milestone.title}`}>
      <div className="proof-to-pay-heading">
        <span className="proof-to-pay-label">PROOF-TO-PAY</span>
        <span className="proof-to-pay-current">{milestone.status === 'PAID' ? 'Complete' : `Step ${current + 1} of ${STEPS.length}`}</span>
      </div>
      <ol className="proof-steps">
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
    </section>
  );
}
