import { formatMoney, type Agreement, type Role } from '../api';
import { StatusBadge } from './StatusBadge';

export function AgreementSummaryStrip({
  agreement,
  role,
  nextAction,
}: {
  agreement: Agreement;
  role: Role;
  nextAction: string;
}) {
  const paidCents = agreement.milestones
    .filter((milestone) => milestone.status === 'PAID')
    .reduce((sum, milestone) => sum + milestone.amount_cents, 0);
  const progress = agreement.total_amount_cents > 0
    ? Math.min(100, Math.round((paidCents / agreement.total_amount_cents) * 100))
    : 0;

  return (
    <section className="agreement-summary-strip" aria-label="Agreement summary">
      <div className="summary-next-action">
        <span className="eyebrow">YOUR NEXT ACTION</span>
        <strong>{nextAction}</strong>
      </div>
      <div className="summary-progress">
        <div className="summary-progress-label">
          <span>Progress · {progress}%</span>
          <strong>{formatMoney(paidCents)} paid / {formatMoney(agreement.total_amount_cents)}</strong>
        </div>
        <div
          className="summary-progress-track"
          role="progressbar"
          aria-label="Agreement amount paid"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <span style={{ width: `${progress}%` }} />
        </div>
        <small>{role === 'client' ? 'Client view' : 'Provider view'}</small>
      </div>
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
