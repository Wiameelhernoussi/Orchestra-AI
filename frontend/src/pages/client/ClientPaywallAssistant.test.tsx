// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, type PaywallRecommendations } from '../../api';
import { RoleProvider } from '../../context/RoleContext';
import ClientPaywallAssistant from './ClientPaywallAssistant';

const recommendations: PaywallRecommendations = {
  assistant_mode: 'groq_ai',
  explanation: 'Ranked by your topic and budget.',
  recommendations: [
    {
      id: 'focus-workflows',
      title: 'A practical guide to focused work',
      topic: 'productivity',
      price_cents: 199,
      currency: 'USD',
      preview: 'A concise guide to planning.',
      reason: 'Matches your interest and budget.',
    },
  ],
};

function renderPage(path = '/client/paywall', mode: 'mock' | 'real' = 'real') {
  window.sessionStorage.setItem('orchestra.demo.role', 'client');
  vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: mode });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <RoleProvider>
        <Routes>
          <Route path="/client/paywall" element={<ClientPaywallAssistant />} />
        </Routes>
      </RoleProvider>
    </MemoryRouter>,
  );
}

describe('ClientPaywallAssistant', () => {
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('requires an explicit user confirmation before starting PayPal checkout', async () => {
    vi.spyOn(api, 'paywallRecommendations').mockResolvedValue(recommendations);
    const create = vi.spyOn(api, 'createPaywallPurchase').mockResolvedValue({
      purchase_id: 'purchase-1',
      status: 'PENDING',
      approval_url: 'https://www.sandbox.paypal.com/checkoutnow?token=order-1',
    });
    const capture = vi.spyOn(api, 'capturePaywallPurchase');

    renderPage();

    expect(await screen.findByText('AI recommendations')).toBeInTheDocument();
    const purchaseButton = screen.getByRole('button', { name: 'Continue to PayPal Sandbox' });
    expect(purchaseButton).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /I choose A practical guide/ }));
    expect(purchaseButton).toBeEnabled();
    fireEvent.click(purchaseButton);

    expect(await screen.findByRole('link', { name: /Open PayPal Sandbox approval/ })).toHaveAttribute(
      'href',
      'https://www.sandbox.paypal.com/checkoutnow?token=order-1',
    );
    expect(create).toHaveBeenCalledWith('demo-client', 'focus-workflows', 500, true);
    expect(capture).not.toHaveBeenCalled();
  });

  it('captures on the PayPal return route and reveals content only after confirmation', async () => {
    vi.spyOn(api, 'capturePaywallPurchase').mockResolvedValue({
      purchase_id: 'purchase-1',
      status: 'CAPTURED',
      approval_url: null,
      offer_id: 'focus-workflows',
      title: 'A practical guide to focused work',
      content: 'Unlocked sample content.',
      captured_at: '2026-11-11T12:00:00Z',
    });

    renderPage('/client/paywall?purchase_id=purchase-1');

    expect(await screen.findByText('PAYMENT CONFIRMED BY PAYPAL')).toBeInTheDocument();
    expect(screen.getByText('Unlocked sample content.')).toBeInTheDocument();
    await waitFor(() => {
      expect(api.capturePaywallPurchase).toHaveBeenCalledWith('demo-client', 'purchase-1');
    });
  });

  it('disables purchase actions in mock mode', async () => {
    vi.spyOn(api, 'paywallRecommendations').mockResolvedValue(recommendations);

    renderPage('/client/paywall', 'mock');

    expect(await screen.findByText(/requires PayPal Sandbox mode/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue to PayPal Sandbox' })).toBeDisabled();
  });
});
