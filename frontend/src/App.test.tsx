// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { api } from './api';
import App from './App';

describe('workspace route guards', () => {
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('redirects an unselected session to role selection', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'mock' });
    window.sessionStorage.clear();
    render(<MemoryRouter initialEntries={['/client']}><App /></MemoryRouter>);

    expect(await screen.findByRole('status')).toHaveTextContent('Choose your role');
    expect(screen.queryByText('CLIENT WORKSPACE')).not.toBeInTheDocument();
  });

  it('enters only the selected role and stores the non-secret demo role per tab', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.clear();
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);

    fireEvent.click(screen.getAllByRole('link', { name: /I'm a client/ })[0]);

    expect(await screen.findByText('CLIENT WORKSPACE')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('orchestra.demo.role')).toBe('client');
    expect(screen.queryByRole('button', { name: 'Client' })).not.toBeInTheDocument();
  });

  it('uses the role bootstrap query for an independent second tab', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.clear();
    render(<MemoryRouter initialEntries={['/provider?demoRole=provider']}><App /></MemoryRouter>);

    expect(await screen.findByText('PROVIDER WORKSPACE')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('orchestra.demo.role')).toBe('provider');
  });

  it('does not let a provider session enter a client route', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'provider');
    render(<MemoryRouter initialEntries={['/client']}><App /></MemoryRouter>);

    expect(await screen.findByRole('status')).toHaveTextContent('Choose your role');
    expect(screen.queryByText('CLIENT WORKSPACE')).not.toBeInTheDocument();
  });

  it('does not let a client session enter a provider route', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');
    render(<MemoryRouter initialEntries={['/provider']}><App /></MemoryRouter>);

    expect(await screen.findByRole('status')).toHaveTextContent('Choose your role');
    expect(screen.queryByText('PROVIDER WORKSPACE')).not.toBeInTheDocument();
  });

  it('hides the disabled paywall link and redirects its route to the client dashboard', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');
    render(<MemoryRouter initialEntries={['/client/paywall']}><App /></MemoryRouter>);

    expect(await screen.findByText('CLIENT WORKSPACE')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Paywall assistant' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Pay only for what you choose.' })).not.toBeInTheDocument();
  });

  it('returns an already selected role to its workspace instead of allowing an in-place role change', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);

    expect(await screen.findByText('CLIENT WORKSPACE')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /I'm a provider/ })).not.toBeInTheDocument();
  });
});
