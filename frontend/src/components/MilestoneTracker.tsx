import type { Milestone } from '../api';
import { formatMoney } from '../api';
import { StatusBadge } from './StatusBadge';
import { ProofToPay } from './ProofToPay';

export function MilestoneTracker({ milestones }: { milestones: Milestone[] }) {
  const paid = milestones.filter((item) => item.status === 'PAID').length;
  return (
    <section className="card section-card">
      <div className="section-heading">
        <div><p className="eyebrow">PROJECT ROADMAP</p><h2>Milestone progress</h2></div>
        <span className="muted">{paid} of {milestones.length} paid</span>
      </div>
      <ol className="tracker-list" aria-label="Milestone progress">
        {milestones.map((milestone) => (
          <li className="tracker-item" key={milestone.id}>
            <div className="tracker-content">
              <div className="tracker-title-row">
                <div>
                  <h3><span className="tracker-order">{String(milestone.order).padStart(2, '0')}</span>{milestone.title}</h3>
                  <span>{formatMoney(milestone.amount_cents)}</span>
                </div>
                <StatusBadge status={milestone.status} />
              </div>
              <p>{milestone.description}</p>
              <ProofToPay milestone={milestone} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
