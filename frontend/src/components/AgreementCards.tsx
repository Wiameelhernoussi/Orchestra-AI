import { formatMoney, type Agreement, type Role } from '../api';
import { StatusBadge } from './StatusBadge';
import { agreementAction } from '../presentation';
import { Link } from 'react-router-dom';

export function AgreementCards({
  agreements,
  role,
}: {
  agreements: Agreement[];
  role: Role;
}) {
  const basePath = role === 'client' ? '/client' : '/provider';

  return (
    <div className="agreement-grid">
      {agreements.map((agreement) => {
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
  );
}
