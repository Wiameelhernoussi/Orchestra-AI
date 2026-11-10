import { useMemo, useState } from 'react';
import { formatMoney, type Agreement, type Role } from '../api';
import { StatusBadge } from './StatusBadge';
import { agreementAction } from '../presentation';
import { Link } from 'react-router-dom';

type AgreementFilter = 'all' | 'needs-action' | 'waiting' | 'paid';

export function agreementFilterBucket(
  agreement: Agreement,
  role: Role,
): Exclude<AgreementFilter, 'all'> {
  if (
    agreement.status === 'COMPLETED'
    || (agreement.milestones.length > 0 && agreement.milestones.every((item) => item.status === 'PAID'))
  ) return 'paid';
  if (agreement.status === 'REJECTED' || agreement.status === 'CANCELLED') return 'waiting';

  const action = agreementAction(agreement, role);
  const needsAction = role === 'client'
    ? ['Review evidence', 'Pay invoice'].includes(action)
    : ['Review proposal', 'Submit evidence', 'Start milestone'].includes(action);
  return needsAction ? 'needs-action' : 'waiting';
}

export function AgreementCards({
  agreements,
  role,
}: {
  agreements: Agreement[];
  role: Role;
}) {
  const basePath = role === 'client' ? '/client' : '/provider';
  const [filter, setFilter] = useState<AgreementFilter>('all');
  const counts = useMemo(() => ({
    'needs-action': agreements.filter((item) => agreementFilterBucket(item, role) === 'needs-action').length,
    waiting: agreements.filter((item) => agreementFilterBucket(item, role) === 'waiting').length,
    paid: agreements.filter((item) => agreementFilterBucket(item, role) === 'paid').length,
  }), [agreements, role]);
  const visibleAgreements = useMemo(
    () => agreements
      .filter((item) => filter === 'all' || agreementFilterBucket(item, role) === filter)
      .slice()
      .sort((left, right) => {
        const order: Record<Exclude<AgreementFilter, 'all'>, number> = {
          'needs-action': 0,
          waiting: 1,
          paid: 2,
        };
        return order[agreementFilterBucket(left, role)] - order[agreementFilterBucket(right, role)];
      }),
    [agreements, filter, role],
  );
  const filters: { id: AgreementFilter; label: string; count?: number }[] = [
    { id: 'all', label: 'All' },
    { id: 'needs-action', label: 'Needs my action', count: counts['needs-action'] },
    { id: 'waiting', label: 'Waiting', count: counts.waiting },
    { id: 'paid', label: 'Paid', count: counts.paid },
  ];

  return (
    <>
      <div className="agreement-filters" role="group" aria-label="Filter agreements">
        {filters.map((item) => (
          <button
            type="button"
            className={filter === item.id ? 'agreement-filter-chip selected' : 'agreement-filter-chip'}
            aria-pressed={filter === item.id}
            key={item.id}
            onClick={() => setFilter(item.id)}
          >
            {item.label}{item.count !== undefined ? ` · ${item.count}` : ''}
          </button>
        ))}
      </div>
      <div className="agreement-grid">
      {visibleAgreements.map((agreement) => {
        const paid = agreement.milestones.filter((item) => item.status === 'PAID');
        const paidCents = paid.reduce((sum, item) => sum + item.amount_cents, 0);
        const action = agreementAction(agreement, role);
        return (
          <Link
            className="agreement-card card"
            to={`${basePath}/agreements/${agreement.id}`}
            key={agreement.id}
          >
            <div className="card-topline">
              <span className="card-kicker">{agreement.milestones.length} milestones</span>
              <StatusBadge status={agreement.status} />
            </div>
            <h2>{agreement.title}</h2>
            <p className="muted">{role === 'client' ? 'Paid / total' : 'Agreement total'}</p>
            <div className="agreement-progress">
              <div
                className="progress-track"
                role="progressbar"
                aria-label="Milestones paid"
                aria-valuemin={0}
                aria-valuemax={agreement.milestones.length}
                aria-valuenow={paid.length}
              >
                <span
                  style={{
                    width: `${agreement.milestones.length > 0 ? (paid.length / agreement.milestones.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <div className="progress-labels">
                <span>{paid.length} of {agreement.milestones.length} milestones paid</span>
                <strong>
                  {role === 'client'
                    ? `${formatMoney(paidCents)} / ${formatMoney(agreement.total_amount_cents)}`
                    : formatMoney(agreement.total_amount_cents)}
                </strong>
              </div>
            </div>
            <div className="card-bottom">
              <span className="action-badge">{action}</span>
              <span className="arrow-link" aria-hidden="true">↗</span>
            </div>
          </Link>
        );
      })}
      </div>
      {visibleAgreements.length === 0 && (
        <p className="agreement-filter-empty" role="status">No agreements in this filter.</p>
      )}
    </>
  );
}
