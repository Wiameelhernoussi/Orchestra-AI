// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type Invoice } from '../api';
import { PayPalInvoicePanel } from './PayPalInvoicePanel';

const invoice: Invoice = {
  id: 'invoice-1',
  paypal_invoice_id: 'PAYPAL-1',
  status: 'SENT',
  amount_cents: 15000,
  currency: 'USD',
  payer_view_url: 'https://sandbox.paypal.test/invoice',
  created_at: '2026-11-09T10:00:00Z',
  sent_at: '2026-11-09T10:05:00Z',
  webhook_events: [],
};

describe('PayPalInvoicePanel', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('lets the client request and view the PayPal Sandbox QR code', async () => {
    vi.spyOn(api, 'invoiceQrCode').mockResolvedValue({
      qr_code_base64: 'cG5n',
      content_type: 'image/png',
    });

    render(<PayPalInvoicePanel invoice={invoice} role="client" userId="client-user" />);
    fireEvent.click(screen.getByText('PayPal Sandbox · invoice timeline and events'));
    fireEvent.click(screen.getByRole('button', { name: 'Pay by QR code' }));

    expect(await screen.findByAltText('PayPal Sandbox invoice payment QR code')).toHaveAttribute(
      'src',
      'data:image/png;base64,cG5n',
    );
    expect(api.invoiceQrCode).toHaveBeenCalledWith('client-user', 'invoice-1');
  });

  it('requires confirmation before sending a provider reminder and displays proof events', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(api, 'sendInvoiceReminder').mockResolvedValue({
      status: 'sent',
      sent_at: '2026-11-09T11:00:00Z',
    });
    const paidInvoice: Invoice = {
      ...invoice,
      status: 'PAID',
      payment_confirmation: 'verified_webhook',
      paid_at: '2026-11-09T12:00:00Z',
      webhook_events: [{
        event_type: 'INVOICING.INVOICE.PAID',
        signature_verified: true,
        processed: 'processed',
        created_at: '2026-11-09T12:00:00Z',
        duplicate_deliveries: 2,
      }],
    };

    const paidRender = render(
      <PayPalInvoicePanel invoice={paidInvoice} role="provider" userId="provider-user" />,
    );
    fireEvent.click(screen.getByText('PayPal Sandbox · invoice timeline and events'));

    expect(screen.getByText('Payment confirmed by verified PayPal webhook')).toBeInTheDocument();
    expect(screen.getByText('Duplicate deliveries ignored: 2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send payment reminder' })).not.toBeInTheDocument();

    paidRender.unmount();
    render(<PayPalInvoicePanel invoice={invoice} role="provider" userId="provider-user" />);
    fireEvent.click(screen.getByText('PayPal Sandbox · invoice timeline and events'));
    fireEvent.click(screen.getByRole('button', { name: 'Send payment reminder' }));

    await waitFor(() => {
      expect(api.sendInvoiceReminder).toHaveBeenCalledWith('provider-user', 'invoice-1');
    });
    expect(await screen.findByText('Payment reminder sent.')).toBeInTheDocument();
  });
});
