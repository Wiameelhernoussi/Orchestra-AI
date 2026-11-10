// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api } from '../../api';
import { RoleProvider } from '../../context/RoleContext';
import Layout from './Layout';

describe('payment mode banner', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows Mock mode when the backend health endpoint reports mock', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'mock' });

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
  });

  it('does not imply PayPal Sandbox mode when backend health is unavailable', async () => {
    vi.spyOn(api, 'health').mockRejectedValue(new Error('Backend unavailable'));

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
});
