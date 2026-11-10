// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { api } from '../api';
import { RoleProvider } from '../context/RoleContext';
import LandingPage from './LandingPage';

describe('LandingPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('presents the promise, workflow, trust model, sandbox disclosure, and both entry points', () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'mock' });
    render(
      <MemoryRouter initialEntries={['/']}>
        <RoleProvider><LandingPage /></RoleProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /agree.*verify.*pay/i })).toBeTruthy();
    expect(screen.getByText(/Turn a business request into clear milestones/)).toBeTruthy();
    expect(screen.getByRole('list', { name: 'How it works' })).toBeTruthy();
    for (const step of ['Request', 'Agreement', 'Evidence', 'Approval', 'Payment']) {
      expect(screen.getByRole('heading', { name: step })).toBeTruthy();
    }
    expect(screen.getByText('AI advises. Humans decide. PayPal settles. Everything is traced.')).toBeTruthy();
    expect(screen.getByText('Sandbox prototype: standard PayPal invoicing, no escrow.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Who does what' })).toBeTruthy();
    expect(screen.getByRole('table', { name: /permission matrix/i })).toBeTruthy();
    expect(screen.getByText('Creates after recorded client approval')).toBeTruthy();
    expect(screen.getByText(/AI never approves work, creates invoices, or confirms payment/)).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /Try as Client/ })[0]).toHaveAttribute('href', '/client');
    expect(screen.getAllByRole('link', { name: /Try as Provider/ })[0]).toHaveAttribute('href', '/provider');
    expect(screen.getByText(/From intent to agreement\. From evidence to approval\./)).toBeTruthy();
  });
});
