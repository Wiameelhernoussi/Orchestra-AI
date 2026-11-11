// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { PaymentTotalsStrip } from './PaymentTotalsStrip';

describe('PaymentTotalsStrip', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows totals returned by the payments summary API', async () => {
    vi.spyOn(api, 'paymentTotals').mockResolvedValue({
      total_invoiced_cents: 60000,
      paid_cents: 15000,
      pending_cents: 45000,
    });

    render(<PaymentTotalsStrip userId="client-user" />);

    expect(await screen.findByText('$600.00')).toBeInTheDocument();
    expect(screen.getByText('$150.00')).toBeInTheDocument();
    expect(screen.getByText('$450.00')).toBeInTheDocument();
  });
});
