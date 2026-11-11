// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { RoleProvider } from '../context/RoleContext';
import LandingPage from './LandingPage';

describe('LandingPage', () => {
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('presents the five-step flow, role entry cards, compact permissions, and Sandbox disclosure', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <RoleProvider><LandingPage /></RoleProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /make work clear.*move with confidence/i })).toBeTruthy();
    expect(screen.getByRole('list', { name: 'Define, Prove, Verify, Approve, Pay' })).toBeTruthy();
    for (const step of ['Define', 'Prove', 'Verify', 'Approve', 'Pay']) {
      expect(screen.getByText(step)).toBeInTheDocument();
    }
    expect(screen.getByText('Sandbox prototype, no escrow.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Where will you begin?' })).toBeInTheDocument();
    expect(screen.getByText('AI advises')).toBeInTheDocument();
    expect(screen.getByText('People decide')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /I'm a client/ })).toHaveAttribute('href', '/client');
    expect(screen.getByRole('link', { name: /I'm a provider/ })).toHaveAttribute('href', '/provider');

    fireEvent.click(screen.getByText('View full matrix'));
    expect(screen.getByRole('table', { name: /permission matrix/i })).toBeInTheDocument();
    expect(screen.getByText('Creates after recorded client approval')).toBeInTheDocument();
    expect(screen.getByText(/AI never approves, creates invoices, or confirms payment/)).toBeInTheDocument();
  });
});
