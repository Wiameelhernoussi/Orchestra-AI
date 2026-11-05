import type { AgreementStatus, MilestoneStatus } from '../api';
import { useEffect, useRef, useState } from 'react';

type Status = AgreementStatus | MilestoneStatus | string;

const LABELS: Record<string, string> = {
  DRAFT: 'Draft',
  PROPOSED: 'Proposed',
  ACTIVE: 'Active',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
  REJECTED: 'Declined',
  PENDING: 'Pending',
  IN_PROGRESS: 'In progress',
  IN_REVIEW: 'In review',
  REVISION_REQUESTED: 'Revision requested',
  APPROVED: 'Approved',
  INVOICING: 'Creating invoice',
  PAYMENT_PENDING: 'Payment pending',
  PAID: 'Paid',
  INVOICE_CANCELLED: 'Invoice cancelled',
  INVOICE_EXPIRED: 'Invoice expired',
  SENT: 'Sent',
};

export function StatusBadge({ status }: { status: Status }) {
  const previousStatus = useRef(status);
  const [changed, setChanged] = useState(false);
  useEffect(() => {
    if (previousStatus.current === status) return;
    previousStatus.current = status;
    setChanged(true);
    const timer = window.setTimeout(() => setChanged(false), 650);
    return () => window.clearTimeout(timer);
  }, [status]);

  const tone =
    status === 'PAID' || status === 'COMPLETED'
      ? 'success'
      : status === 'PAYMENT_PENDING' || status === 'IN_REVIEW'
        ? 'warning'
        : status === 'REJECTED' || status === 'CANCELLED' || status.includes('EXPIRED')
          ? 'danger'
          : status === 'ACTIVE' || status === 'APPROVED'
            ? 'accent'
            : 'neutral';

  return (
    <span className={`status-badge status-${tone}${changed ? ' status-changed' : ''}`}>
      <span className="status-dot" aria-hidden="true" />
      {LABELS[status] ?? status.replace(/_/g, ' ')}
    </span>
  );
}
