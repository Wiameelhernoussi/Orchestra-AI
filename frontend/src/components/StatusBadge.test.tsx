// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from './StatusBadge';

describe('StatusBadge', () => {
  it('labels a paid milestone accessibly', () => {
    render(<StatusBadge status="PAID" />);

    expect(screen.getByText('Paid')).toHaveClass('status-badge', 'status-success');
  });

  it('uses a warning tone for pending payment', () => {
    render(<StatusBadge status="PAYMENT_PENDING" />);

    expect(screen.getByText('Payment pending')).toHaveClass('status-warning');
  });
});
