import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { useRole } from '../../context/RoleContext';

const paywallAssistantEnabled = import.meta.env.VITE_ENABLE_PAYWALL_ASSISTANT === 'true';

function Layout() {
  const { role, user, setRole, demoMode, demoModeError } = useRole();
  const navigate = useNavigate();
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState('');
  const isClient = role === 'client';
  const activeRole = role ?? 'client';

  async function resetDemo() {
    if (!window.confirm('Reset the demo agreements and return to the sample $600 project?')) {
      return;
    }
    setResetting(true);
    setResetError('');
    try {
      await api.resetDemo();
      navigate(activeRole === 'client' ? '/client' : '/provider');
      window.location.reload();
    } catch (error) {
      setResetError(error instanceof Error ? error.message : 'Demo reset failed.');
    } finally {
      setResetting(false);
    }
  }

  function signOut() {
    if (!window.confirm('Sign out of this demo account?')) return;
    setRole(null);
    navigate('/', { state: { chooseRoleMessage: 'Choose your role to enter a workspace.' } });
  }

  function openOtherRole() {
    const otherRole = activeRole === 'client' ? 'provider' : 'client';
    const route = otherRole === 'client' ? '/client' : '/provider';
    window.open(`${route}?demoRole=${otherRole}`, '_blank', 'noopener,noreferrer');
  }

  const navLinks = isClient
    ? [
        { to: '/client', label: 'Agreements', end: true },
        { to: '/client/new', label: 'New agreement', end: true },
      ...(paywallAssistantEnabled
        ? [{ to: '/client/paywall', label: 'Paywall assistant', end: true }]
        : []),
    ]
    : [{ to: '/provider', label: 'My work', end: true }];

  return (
    <div className={`app-shell role-${activeRole}`}>
      <header className="topbar">
        <div className="topbar-main">
          <div className="brand-group">
            <Link to={isClient ? '/client' : '/provider'} className="brand">
              <span className="brand-mark" aria-hidden="true">O</span>
              <span>ORCHESTRA <b>AI</b></span>
            </Link>
            <p className="brand-tagline">
              {isClient ? 'Review, approve, pay.' : 'Deliver, submit, get paid.'}
            </p>
          </div>
          <div className="topbar-actions">
            <details className="topbar-menu">
              <summary>Demo tools</summary>
              <div className="topbar-menu-panel">
                <button type="button" onClick={resetDemo} disabled={resetting}>
                  {resetting ? 'Resetting…' : 'Reset demo'}
                </button>
                <button type="button" onClick={openOtherRole}>
                  Open the {isClient ? 'provider' : 'client'} role in a new tab
                </button>
              </div>
            </details>
            <details className="topbar-menu account-menu">
              <summary>{user.name} ▾</summary>
              <div className="topbar-menu-panel">
                <span>{user.orgName}</span>
                <button type="button" onClick={signOut}>Sign out of demo account</button>
              </div>
            </details>
          </div>
        </div>
        <div className="topbar-sub">
          <nav className="main-nav" aria-label="Main navigation">
            {navLinks.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="session-identity">
            <span className={`avatar avatar-${activeRole}`} aria-hidden="true">{isClient ? 'SC' : 'DS'}</span>
            <span>
              <strong>{user.orgName}</strong>
              <small>{isClient ? 'Client workspace' : 'Provider workspace'}</small>
            </span>
            <span className={`demo-label ${demoMode === 'mock' ? 'mock-mode-label' : ''}`}>
              <span /> {demoMode === 'mock'
                ? 'Mock mode · simulated payments'
                : demoMode === 'real'
                  ? 'PayPal Sandbox'
                  : demoMode === 'loading'
                    ? 'Checking payment mode…'
                    : 'Payment mode unavailable'}
            </span>
          </div>
        </div>
      </header>

      <main className="page-container">
        {resetError && (
          <div className="alert alert-error" role="alert">
            {resetError}
          </div>
        )}
        {demoModeError && <div className="alert alert-warning" role="status">{demoModeError}</div>}
        <aside className={`workspace-role-banner workspace-role-${role}`} aria-label={`${isClient ? 'Client' : 'Provider'} role permissions`}>
          <span className="workspace-role-icon" aria-hidden="true">{isClient ? '✓' : '↗'}</span>
          <span className="workspace-role-copy">
            <strong>{isClient ? 'Client workspace · Review, approve, pay' : 'Provider workspace · Deliver, submit, get paid'}</strong>
            <small>{isClient
              ? 'You can review evidence, request revisions, approve deliverables, and pay invoices. You cannot submit provider evidence.'
              : 'You can deliver work and submit evidence. You cannot approve your own deliverables or confirm PayPal payments.'}</small>
          </span>
        </aside>
        <Outlet />
      </main>
      <footer className="app-footer">
        <span>ORCHESTRA AI</span>
        <span>
          {demoMode === 'mock'
            ? 'From intent to agreement. From evidence to approval. From approval to payment. · Simulated payments'
            : demoMode === 'real'
              ? 'From intent to agreement. From evidence to approval. From approval to payment. · PayPal Sandbox'
              : 'From intent to agreement. From evidence to approval. From approval to payment. · Payment mode not confirmed'}
        </span>
      </footer>
    </div>
  );
}

export default Layout;
