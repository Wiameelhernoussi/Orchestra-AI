// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, type Agreement } from '../../api';
import { RoleProvider } from '../../context/RoleContext';
import ClientAgreementDetail from './ClientAgreementDetail';

const criterion = 'Mockups for Home, Catalog, Product, Cart, and Account pages are delivered.';
const submittedUrl = 'https://www.figma.com/design/example';

const agreement: Agreement = {
  id: 'agreement-1',
  title: 'Website design',
  description: '',
  status: 'ACTIVE',
  total_amount_cents: 15000,
  currency: 'USD',
  client_org_id: 'client-org',
  provider_org_id: 'provider-org',
  created_at: null,
  milestones: [
    {
      id: 'milestone-1',
      title: 'Design',
      description: 'Deliver the design mockups.',
      order: 1,
      status: 'IN_REVIEW',
      amount_cents: 15000,
      acceptance_criteria: [criterion],
      criteria: [{ id: 'criterion-1', description: criterion }],
      evidence: [
        {
          id: 'evidence-1',
          type: 'submission',
          content: JSON.stringify({
            text: 'Design work is ready to review.',
            links: [submittedUrl],
            criterion_ids: ['criterion-1'],
            attachments: [],
          }),
          submission_status: 'SUBMITTED',
          verification_status: 'ADVISORY',
          ai_report: {
            criteria_results: [
              {
                criterion,
                status: 'missing',
                explanation: 'A URL was submitted but criterion details are not demonstrated.',
              },
            ],
            overall_verdict: 'insufficient',
            report: 'Additional evidence is required.',
          },
          link_checks: [
            {
              url: submittedUrl,
              https: true,
              http_status: null,
              title: null,
              result: 'unavailable',
              reason: 'Connection timed out.',
              github_repo_exists: null,
              github_expected_files: [],
            },
          ],
          created_at: null,
        },
      ],
      invoices: [],
      payment_readiness: {
        status: 'BLOCKED',
        score: 55,
        ready: false,
        paypal_invoice_allowed: false,
        client_approval_allowed: true,
        client_acknowledged_advisory: false,
        advisory_verdict: 'insufficient',
        blocking_reasons: ['All acceptance criteria must be verified.'],
        completed_checks: [],
        checks: [],
        next_action: {
          actor: 'PROVIDER',
          action: 'Submit evidence for the remaining acceptance criteria.',
        },
        criteria_summary: {
          total: 1,
          verified: 0,
          unverified: 1,
          criteria: [{ criterion, status: 'missing' }],
        },
        approval_status: 'PENDING',
        approval_details: null,
        paypal_status: 'NOT_CREATED',
        webhook_payment_confirmed: false,
        scope_defined: true,
        next_milestone_title: null,
        next_milestone_unlocked: true,
        client_next_action: 'Review the evidence.',
        provider_next_action: 'Wait for client review.',
      },
    },
  ],
};

describe('ClientAgreementDetail', () => {
  afterEach(() => vi.restoreAllMocks());

  it('requires acknowledgement and shows the client approval badge afterwards', async () => {
    const approvedAgreement: Agreement = {
      ...agreement,
      milestones: agreement.milestones.map((milestone) => ({
        ...milestone,
        status: 'APPROVED',
        payment_readiness: {
          ...milestone.payment_readiness,
          status: 'READY_FOR_PAYMENT',
          ready: true,
          paypal_invoice_allowed: true,
          client_approval_allowed: false,
          client_acknowledged_advisory: true,
          approval_status: 'APPROVED',
          approval_details: {
            approver_name: 'Alice Chen',
            approved_at: '2026-11-09T12:00:00Z',
            advisory_overridden: true,
          },
        },
      })),
    };
    vi.spyOn(api, 'health').mockResolvedValue({ demo_mode: 'mock' });
    vi.spyOn(api, 'getAgreement')
      .mockResolvedValueOnce(agreement)
      .mockResolvedValue(approvedAgreement);
    vi.spyOn(api, 'auditLogs').mockResolvedValue([]);
    const approve = vi.spyOn(api, 'approveMilestone')
      .mockResolvedValue(approvedAgreement.milestones[0]);

    render(
      <MemoryRouter initialEntries={['/client/agreements/agreement-1']}>
        <RoleProvider>
          <Routes>
            <Route path="/client/agreements/:id" element={<ClientAgreementDetail />} />
          </Routes>
        </RoleProvider>
      </MemoryRouter>,
    );

    const urlLinks = await screen.findAllByRole('link', { name: submittedUrl });
    expect(urlLinks.some((link) => link.getAttribute('href') === submittedUrl)).toBe(true);

    const approveButton = screen.getByRole('button', { name: 'Approve deliverable' });
    expect(approveButton).toBeEnabled();
    expect(approveButton).toHaveAttribute('aria-describedby', 'approval-blocker-milestone-1');
    expect(screen.getByText(/AI advice does not decide approval/i)).toBeInTheDocument();
    expect(screen.getAllByText(criterion).length).toBeGreaterThan(1);
    fireEvent.click(screen.getByText('Deterministic link checks · 1'));
    expect(screen.getByText('Inaccessible to automated checker')).toBeInTheDocument();

    fireEvent.click(approveButton);
    const dialog = screen.getByRole('dialog', { name: 'Confirm your approval' });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveTextContent('The Evidence Agent advisory is insufficient.');
    expect(screen.getByText('These criteria were not verified by the AI:')).toBeInTheDocument();
    const checkbox = within(dialog).getByRole('checkbox', {
      name: 'I reviewed the submitted evidence and attachments myself and accept this decision.',
    });
    const confirmButton = within(dialog).getByRole('button', { name: 'Confirm approval' });
    expect(confirmButton).toBeDisabled();
    fireEvent.click(checkbox);
    expect(confirmButton).toBeEnabled();
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(approve).toHaveBeenCalledWith(
        'demo-client',
        'agreement-1',
        'milestone-1',
        true,
      );
    });
    expect(await screen.findByText(
      'Approved by client (AI advisory was not sufficient)',
    )).toBeInTheDocument();
  });
});
