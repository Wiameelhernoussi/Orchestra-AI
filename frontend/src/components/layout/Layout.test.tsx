// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api } from '../../api';
import { RoleProvider } from '../../context/RoleContext';
import Layout from './Layout';

describe('payment mode banner', () => {
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('shows Mock mode when the backend health endpoint reports mock', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'mock' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');

    render(
      <MemoryRouter initialEntries={['/client']}>
        <RoleProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/client" element={<p>Client home</p>} />
            </Route>
          </Routes>
        </RoleProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Mock mode · simulated payments')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: 'Choose demo role' })).not.toBeInTheDocument();
  });

  it('does not imply PayPal Sandbox mode when backend health is unavailable', async () => {
    vi.spyOn(api, 'health').mockRejectedValue(new Error('Backend unavailable'));
    window.sessionStorage.setItem('orchestra.demo.role', 'client');

    render(
      <MemoryRouter initialEntries={['/client']}>
        <RoleProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/client" element={<p>Client home</p>} />
            </Route>
          </Routes>
        </RoleProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Payment mode unavailable')).toBeInTheDocument();
    expect(screen.queryByText('PayPal Sandbox')).not.toBeInTheDocument();
  });

  it('keeps demo tools collapsed and opens the other role in a separate tab', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    render(
      <MemoryRouter initialEntries={['/client']}>
        <RoleProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/client" element={<p>Client home</p>} />
            </Route>
          </Routes>
        </RoleProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('PayPal Sandbox')).toBeInTheDocument();
    expect(screen.getByText('Demo tools').closest('details')).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('Demo tools'));
    fireEvent.click(screen.getByRole('button', { name: 'Open the provider role in a new tab' }));
    expect(open).toHaveBeenCalledWith('/provider?demoRole=provider', '_blank', 'noopener,noreferrer');
  });

  it('confirms sign out and clears only this tab demo role', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'real' });
    window.sessionStorage.setItem('orchestra.demo.role', 'client');
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={['/client']}>
        <RoleProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/client" element={<p>Client home</p>} />
            </Route>
            <Route path="/" element={<p>Choose your role</p>} />
          </Routes>
        </RoleProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText('Alice Chen ▾'));
    fireEvent.click(screen.getByRole('button', { name: 'Sign out of demo account' }));
    expect(await screen.findByText('Choose your role')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('orchestra.demo.role')).toBeNull();
    expect(window.confirm).toHaveBeenCalledWith('Sign out of this demo account?');
  });
});
