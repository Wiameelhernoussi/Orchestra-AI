import { useState } from 'react';
import { api, type Invoice, type Role } from '../api';

function displayTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : 'Not recorded';
}

export function PayPalInvoicePanel({
  invoice,
  role,
  userId,
}: {
  invoice: Invoice;
  role: Role;
  userId: string;
}) {
  const [qrCode, setQrCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [reminderSent, setReminderSent] = useState(false);
  const lastReminderAt = invoice.last_reminder_at
    ? new Date(invoice.last_reminder_at).getTime()
    : Number.NaN;
  const reminderRecentlySent = invoice.last_reminder_status === 'sent'
    && Number.isFinite(lastReminderAt)
    && Date.now() - lastReminderAt < 24 * 60 * 60 * 1000;

  async function showQrCode() {
    setBusy(true);
    setError('');
    try {
      const result = await api.invoiceQrCode(userId, invoice.id);
      setQrCode(result.qr_code_base64);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'QR code could not be loaded.');
    } finally {
      setBusy(false);
    }
  }

  async function sendReminder() {
    if (!window.confirm('Send a payment reminder to the client from PayPal Sandbox?')) return;
    setBusy(true);
    setError('');
    try {
      const result = await api.sendInvoiceReminder(userId, invoice.id);
      setReminderSent(true);
      setMessage(result.status === 'already_sent' ? 'A reminder was already sent in the last 24 hours.' : 'Payment reminder sent.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Payment reminder could not be sent.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="paypal-invoice-panel">
      <summary>PayPal Sandbox · invoice timeline and events</summary>
      <div className="paypal-invoice-content">
        <p className="paypal-invoice-id"><span>Invoice ID</span><code>{invoice.paypal_invoice_id ?? 'Preparing invoice'}</code></p>
        {invoice.payer_view_url && (
          <a href={invoice.payer_view_url} target="_blank" rel="noreferrer">Open PayPal Sandbox payment page ↗</a>
        )}
        {invoice.status === 'PAID' && (
          <p className="webhook-confirmed" role="status">
            <span aria-hidden="true">✓</span>
            <strong>
              {invoice.payment_confirmation === 'verified_webhook'
                ? 'Payment confirmed by verified PayPal webhook'
                : invoice.payment_confirmation === 'manual_sync'
                  ? 'Payment confirmed by PayPal status sync'
                  : 'Payment status is paid; confirmation source is not recorded'}
            </strong>
          </p>
        )}
        <ol className="paypal-invoice-timeline" aria-label="Invoice timeline">
          <li><span>Created</span><time>{displayTime(invoice.created_at)}</time></li>
          <li><span>Sent</span><time>{displayTime(invoice.sent_at)}</time></li>
          <li><span>Paid</span><time>{displayTime(invoice.paid_at)}</time></li>
        </ol>
        {role === 'client' && invoice.status === 'SENT' && (
          <div className="paypal-panel-action">
            <button type="button" className="button button-secondary" disabled={busy} onClick={() => void showQrCode()}>
              {busy ? 'Loading…' : qrCode ? 'Refresh payment QR code' : 'Pay by QR code'}
            </button>
            {qrCode && <img className="paypal-qr-code" src={`data:image/png;base64,${qrCode}`} alt="PayPal Sandbox invoice payment QR code" />}
          </div>
        )}
        {role === 'provider' && invoice.status === 'SENT' && (
          <button
            type="button"
            className="button button-secondary"
            disabled={busy || reminderSent || reminderRecentlySent}
            onClick={() => void sendReminder()}
          >
            {busy ? 'Sending…' : reminderSent || reminderRecentlySent ? 'Reminder sent recently' : 'Send payment reminder'}
          </button>
        )}
        {message && <p role="status">{message}</p>}
        {error && <p className="alert alert-error" role="alert">{error}</p>}
        <h4>Events received from PayPal</h4>
        {invoice.webhook_events?.length ? (
          <ul className="paypal-event-list">
            {invoice.webhook_events.map((event, index) => (
              <li key={`${event.event_type}-${event.created_at ?? index}`}>
                <strong>{event.event_type}</strong>
                <span>Signature verified: {event.signature_verified ? 'Yes' : 'No'}</span>
                <span>{event.processed === 'processed' ? 'Processed' : 'Ignored'}</span>
                <time>{displayTime(event.created_at)}</time>
                {event.duplicate_deliveries > 0 && <span>Duplicate deliveries ignored: {event.duplicate_deliveries}</span>}
              </li>
            ))}
          </ul>
        ) : <p>No verified PayPal webhook events recorded for this invoice.</p>}
        {invoice.last_reminder_at && (
          <p className="muted small-copy">
            Reminder {invoice.last_reminder_status ?? 'attempt'} · {displayTime(invoice.last_reminder_at)}
          </p>
        )}
      </div>
    </details>
  );
}
