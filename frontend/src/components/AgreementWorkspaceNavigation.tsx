import type { CSSProperties } from 'react';
import { formatMoney, type Agreement } from '../api';
import { StatusBadge } from './StatusBadge';

export function AgreementSummaryStrip({
  agreement,
  nextAction,
  onNextAction,
}: {
  agreement: Agreement;
  nextAction: string;
  onNextAction?: () => void;
}) {
  const paidCents = agreement.milestones
    .filter((milestone) => milestone.status === 'PAID')
    .reduce((sum, milestone) => sum + milestone.amount_cents, 0);
  const progress = agreement.total_amount_cents > 0
    ? Math.min(100, Math.round((paidCents / agreement.total_amount_cents) * 100))
    : 0;

  return (
    <section className="agreement-summary-strip" aria-label="Agreement summary">
      <div className="summary-agreement-title">
        <span className="eyebrow">AGREEMENT</span>
        <h2>{agreement.title}</h2>
      </div>
      <div className="summary-progress">
        <div
          className="summary-progress-ring"
          role="progressbar"
          aria-label="Agreement amount paid"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          style={{ '--progress': `${progress * 3.6}deg` } as CSSProperties}
        >
          <span>{progress}%</span>
        </div>
        <div className="summary-progress-copy">
          <strong>{formatMoney(paidCents)} <span>paid</span></strong>
          <small>of {formatMoney(agreement.total_amount_cents)} total</small>
        </div>
      </div>
      <button type="button" className="summary-next-action" onClick={onNextAction}>
        <span className="eyebrow">YOUR NEXT ACTION</span>
        <strong>{nextAction}</strong>
        <span className="summary-next-arrow" aria-hidden="true">→</span>
      </button>
    </section>
  );
}

export function MilestoneRail({
  agreement,
  selectedId,
  onSelect,
}: {
  agreement: Agreement;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className="milestone-rail" aria-label="Agreement milestones">
      {agreement.milestones.map((milestone) => (
        <button
          type="button"
          className={`milestone-rail-item${selectedId === milestone.id ? ' selected' : ''}`}
          aria-current={selectedId === milestone.id ? 'step' : undefined}
          key={milestone.id}
          onClick={() => onSelect(milestone.id)}
        >
          <span className="milestone-rail-order">{String(milestone.order).padStart(2, '0')}</span>
          <span className="milestone-rail-copy">
            <strong>{milestone.title}</strong>
            <small>{formatMoney(milestone.amount_cents)}</small>
          </span>
          <StatusBadge status={milestone.status} />
        </button>
      ))}
    </nav>
  );
}
