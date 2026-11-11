import type { Milestone, Role } from '../api';

function milestoneState(milestone: Milestone): string {
  const readiness = milestone.payment_readiness;
  if (milestone.status === 'PAID' || readiness.status === 'PAID') return 'PAID';
  if (readiness.status === 'READY_FOR_APPROVAL') return 'READY FOR CLIENT APPROVAL';
  if (
    readiness.paypal_invoice_allowed
    || readiness.status === 'INVOICE_CREATED'
    || readiness.status === 'INVOICE_SENT'
  ) return 'INVOICE READY';
  return 'BLOCKED';
}

function whyBlocked(milestone: Milestone, state: string): string {
  if (state === 'PAID') return 'Payment is confirmed; no payment blocker remains.';
  if (state === 'INVOICE READY') {
    return milestone.payment_readiness.paypal_status === 'SENT'
      ? 'The invoice has been sent. The client must complete payment in PayPal.'
      : 'The client has approved the work and the server can create the invoice.';
  }
  if (state === 'READY FOR CLIENT APPROVAL') {
    return 'The provider submitted evidence for review. Client approval is the remaining human gate.';
  }
  return milestone.payment_readiness.blocking_reasons.join(' ')
    || 'The milestone has not met the requirements for client approval or invoicing.';
}

export function PaymentReadinessPanel({
  milestone,
  role,
}: {
  milestone: Milestone;
  role: Role;
}) {
  const readiness = milestone.payment_readiness;
  const state = milestoneState(milestone);
  const paid = state === 'PAID';
  const nextMilestoneUnlocked = paid || readiness.next_milestone_unlocked;
  const progress = paid ? 100 : readiness.score;
  const webhookText = readiness.webhook_payment_confirmed
    ? 'Confirmed by verified PayPal webhook'
    : readiness.paypal_status === 'PAID'
      ? 'Paid status was synchronized from PayPal; no paid webhook is recorded'
      : 'Not confirmed by a paid webhook';
  const approvalText = readiness.approval_details
    ? `Approved by ${readiness.approval_details.approver_name}${readiness.approval_details.approved_at ? ` · ${new Date(readiness.approval_details.approved_at).toLocaleString()}` : ''}${readiness.approval_details.advisory_overridden ? ' · AI advisory limitation acknowledged' : ''}`
    : 'No client approval recorded';

  return (
    <section className="payment-readiness-panel" aria-label={`Payment readiness for ${milestone.title}`}>
      <details className="payment-readiness-details">
        <summary>
          <span className="payment-readiness-summary-title">
            <small>PAYMENT READINESS</small>
            <strong>{state}</strong>
          </span>
          <span className={`payment-readiness-state state-${state.toLowerCase().replace(/ /g, '-')}`}>
            {paid ? '✓ 100%' : `${progress}%`}
          </span>
          <span className="payment-readiness-summary-action">
            {paid
              ? readiness.next_milestone_title
                ? `✓ Next milestone unlocked · ${readiness.next_milestone_title}`
                : '✓ Payment confirmed'
              : role === 'client' ? readiness.client_next_action : readiness.provider_next_action}
          </span>
          <span className="payment-readiness-summary-toggle" aria-hidden="true">⌄</span>
        </summary>
        <div className="payment-readiness-details-content">
          <ul className="payment-readiness-checklist">
            <li className={readiness.scope_defined ? 'complete' : 'pending'}>
              <span aria-hidden="true">{readiness.scope_defined ? '✓' : '○'}</span>
              Agreement scope defined
            </li>
            <li className={milestone.amount_cents > 0 ? 'complete' : 'pending'}>
              <span aria-hidden="true">{milestone.amount_cents > 0 ? '✓' : '○'}</span>
              Milestone amount defined
            </li>
            <li className={milestone.acceptance_criteria.length > 0 ? 'complete' : 'pending'}>
              <span aria-hidden="true">{milestone.acceptance_criteria.length > 0 ? '✓' : '○'}</span>
              Acceptance criteria defined
            </li>
            <li className={milestone.evidence.length > 0 ? 'complete' : 'pending'}>
              <span aria-hidden="true">{milestone.evidence.length > 0 ? '✓' : '○'}</span>
              Evidence submitted
            </li>
            <li className={readiness.advisory_verdict !== 'unavailable' ? 'complete' : 'pending'}>
              <span aria-hidden="true">{readiness.advisory_verdict !== 'unavailable' ? '✓' : '○'}</span>
              <div>
                AI advisory: {readiness.advisory_verdict}
                {readiness.criteria_summary.total > 0
                  ? ` · ${readiness.criteria_summary.unverified} unverified criteria`
                  : ''}
                {readiness.criteria_summary.unverified > 0 && (
                  <ul className="payment-readiness-unverified">
                    {readiness.criteria_summary.criteria
                      .filter((criterion) => criterion.status !== 'verified')
                      .map((criterion) => (
                        <li key={criterion.criterion}>
                          {criterion.criterion} ({criterion.status.replace('_', ' ')})
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            </li>
            <li className={readiness.approval_status === 'APPROVED' ? 'complete' : 'pending'}>
              <span aria-hidden="true">{readiness.approval_status === 'APPROVED' ? '✓' : '○'}</span>
              <span>Human approval · {approvalText}</span>
            </li>
            <li className={readiness.paypal_status !== 'NOT_CREATED' ? 'complete' : 'pending'}>
              <span aria-hidden="true">{readiness.paypal_status !== 'NOT_CREATED' ? '✓' : '○'}</span>
              Invoice status · {readiness.paypal_status}
            </li>
            <li className={readiness.webhook_payment_confirmed ? 'complete' : 'pending'}>
              <span aria-hidden="true">{readiness.webhook_payment_confirmed ? '✓' : '○'}</span>
              {webhookText}
            </li>
            <li className={nextMilestoneUnlocked ? 'complete' : 'pending'}>
              <span aria-hidden="true">{nextMilestoneUnlocked ? '✓' : '○'}</span>
              {readiness.next_milestone_title
                ? nextMilestoneUnlocked
                  ? `Next milestone: unlocked · ${readiness.next_milestone_title}`
                  : `Next milestone · ${readiness.next_milestone_title} locked until this one is paid`
                : 'No next milestone'}
            </li>
          </ul>
          {!paid && (
            <details className="payment-readiness-explanation">
              <summary>Why is payment blocked?</summary>
              <p>{whyBlocked(milestone, state)}</p>
            </details>
          )}
        </div>
      </details>
    </section>
  );
}
