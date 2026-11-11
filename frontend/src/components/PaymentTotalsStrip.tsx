import { useEffect, useState } from 'react';
import { api, formatMoney, type PaymentTotals } from '../api';

export function PaymentTotalsStrip({ userId }: { userId: string }) {
  const [totals, setTotals] = useState<PaymentTotals | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.paymentTotals(userId)
      .then((result) => { if (active) setTotals(result); })
      .catch(() => { if (active) setError('Payment totals could not be loaded.'); });
    return () => { active = false; };
  }, [userId]);

  if (error) return <p className="payment-totals-error" role="status">{error}</p>;
  if (!totals) return <div className="payment-totals loading" aria-label="Loading payment totals" />;

  return (
    <section className="payment-totals" aria-label="Payment totals">
      <div><span>Total invoiced</span><strong>{formatMoney(totals.total_invoiced_cents)}</strong></div>
      <div><span>Paid</span><strong>{formatMoney(totals.paid_cents)}</strong></div>
      <div><span>Pending</span><strong>{formatMoney(totals.pending_cents)}</strong></div>
    </section>
  );
}
