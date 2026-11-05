import type { Agreement, AuditEntry, Role } from './api';

export function agreementNextStep(agreement: Agreement, role: Role): string {
  if (agreement.status === 'COMPLETED') {
    return 'All milestones are paid. Agreement completed.';
  }
  if (agreement.status === 'PROPOSED') {
    return role === 'provider'
      ? 'Review the scope, then accept the proposal to begin delivery.'
      : 'Waiting for the provider to review the proposal.';
  }
  if (agreement.status === 'REJECTED' || agreement.status === 'CANCELLED') {
    return agreement.status === 'REJECTED'
      ? 'The provider declined this agreement.'
      : 'This agreement was cancelled.';
  }

  const milestones = agreement.milestones;
  if (milestones.some((item) => item.status === 'IN_REVIEW')) {
    return role === 'client'
      ? 'Review the submitted evidence, then approve it yourself or request a revision.'
      : 'Waiting for the client to review the submitted evidence.';
  }
  if (milestones.some((item) => item.status === 'PAYMENT_PENDING')) {
    return 'Waiting for PayPal payment confirmation. This page checks for updates automatically.';
  }
  if (role === 'client' && milestones.some((item) => item.status === 'APPROVED')) {
    return 'Create the PayPal invoice for the approved milestone.';
  }
  if (milestones.some((item) => item.status === 'REVISION_REQUESTED')) {
    return role === 'provider'
      ? 'Update the deliverable using the client’s revision notes, then submit new evidence.'
      : 'The provider is updating the deliverable using your revision notes.';
  }
  if (milestones.some((item) => item.status === 'IN_PROGRESS')) {
    return role === 'provider'
      ? 'Submit evidence for each acceptance criterion, then send the milestone for client review.'
      : 'The provider is working on the current milestone.';
  }
  if (role === 'provider') {
    const nextMilestone = milestones.find((item) => item.status !== 'PAID');
    return nextMilestone
      ? `Start ${nextMilestone.title} when you are ready.`
      : 'Continue with the active agreement.';
  }
  const nextMilestone = milestones.find((item) => item.status !== 'PAID');
  if (nextMilestone?.status === 'PENDING') {
    return `Waiting for the provider to start ${nextMilestone.title}.`;
  }
  return 'Follow the project milestones below. Only your approval can move a deliverable to payment.';
}

export function agreementAction(agreement: Agreement, role: Role): string {
  if (agreement.status === 'COMPLETED') return 'Completed';
  if (agreement.status === 'PROPOSED') {
    return role === 'provider' ? 'Review proposal' : 'Waiting for provider';
  }
  if (agreement.milestones.some((item) => item.status === 'IN_REVIEW')) {
    return role === 'client' ? 'Review evidence' : 'Waiting for client';
  }
  if (agreement.milestones.some((item) => item.status === 'APPROVED')) {
    return role === 'client' ? 'Pay invoice' : 'Waiting for client';
  }
  if (agreement.milestones.some((item) => item.status === 'PAYMENT_PENDING')) {
    return 'Waiting for payment';
  }
  if (agreement.milestones.some((item) => item.status === 'IN_PROGRESS')) {
    return role === 'provider' ? 'Submit evidence' : 'Waiting for provider';
  }
  if (agreement.status === 'REJECTED') return 'Declined';
  if (agreement.status === 'CANCELLED') return 'Cancelled';
  return role === 'provider' ? 'Start milestone' : 'Waiting for provider';
}

const ACTIVITY_COPY: Record<string, { message: string; actor: string }> = {
  agreement_created: { message: 'Agreement created', actor: 'Client' },
  agreement_published: { message: 'Agreement sent to provider', actor: 'Client' },
  agreement_accepted: { message: 'Agreement accepted', actor: 'Provider' },
  agreement_refused: { message: 'Agreement declined', actor: 'Provider' },
  milestone_started: { message: 'Milestone started', actor: 'Provider' },
  evidence_submitted: { message: 'Evidence submitted', actor: 'Provider' },
  ai_advisory_generated: { message: 'AI advisory generated', actor: 'AI' },
  milestone_submitted_for_review: {
    message: 'Evidence submitted for client review',
    actor: 'Provider',
  },
  milestone_approved: { message: 'Milestone approved by client', actor: 'Client' },
  milestone_revision_requested: { message: 'Revision requested', actor: 'Client' },
  invoice_created_or_retried: { message: 'Invoice sent to client', actor: 'PayPal' },
  invoice_status_synchronized: { message: 'Payment status refreshed', actor: 'PayPal' },
  paypal_invoice_status_updated: {
    message: 'Payment confirmed by PayPal webhook',
    actor: 'PayPal',
  },
  agreement_completed: { message: 'Agreement completed', actor: 'PayPal' },
  demo_seeded: { message: 'Demo agreement created', actor: 'Client' },
};

export function activityDescription(
  entry: AuditEntry,
): { message: string; actor: string } {
  if (entry.action === 'paypal_invoice_status_updated') {
    const status = entry.details.status;
    return {
      message: status === 'PAID'
        ? 'Payment confirmed by PayPal webhook'
        : 'PayPal invoice status updated',
      actor: 'PayPal',
    };
  }
  const description = ACTIVITY_COPY[entry.action];
  if (description) return description;

  const actor = entry.user_id
    ? entry.user_id.includes('client')
      ? 'Client'
      : entry.user_id.includes('provider')
        ? 'Provider'
        : 'Provider'
    : 'PayPal';
  return {
    message: 'Project activity recorded',
    actor,
  };
}

export const DESIGN_SAMPLE_PARTIAL =
  'Mockups for the Home, Catalog, Product, and Account pages are included in the submitted files. A style guide is included in the submitted files.';

export const DESIGN_SAMPLE_SUFFICIENT =
  'Mockups for the Home, Catalog, Product, Cart, and Account pages are included in the submitted files. A style guide is included in the submitted files.';
