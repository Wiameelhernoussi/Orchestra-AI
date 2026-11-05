import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { useRole } from '../../context/RoleContext';

function Layout() {
  const { role, user, setRole, demoMode, demoModeError } = useRole();
  const navigate = useNavigate();
  const location = useLocation();
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState('');
  const isClient = role === 'client';

  useEffect(() => {
    if (location.pathname.startsWith('/client') && role !== 'client') setRole('client');
    if (location.pathname.startsWith('/provider') && role !== 'provider') setRole('provider');
  }, [location.pathname, role, setRole]);

  async function resetDemo() {
    if (!window.confirm('Reset the demo agreements and return to the sample $600 project?')) {
      return;
    }
    setResetting(true);
    setResetError('');
    try {
      await api.resetDemo();
      navigate('/client');
      window.location.reload();
    } catch (error) {
      setResetError(error instanceof Error ? error.message : 'Demo reset failed.');
    } finally {
      setResetting(false);
    }
  }

  function chooseRole(nextRole: 'client' | 'provider') {
    setRole(nextRole);
    navigate(nextRole === 'client' ? '/client' : '/provider');
  }

  const navLinks = isClient
    ? [
        { to: '/client', label: 'Agreements', end: true },
        { to: '/client/new', label: 'New agreement', end: true },
      ]
    : [{ to: '/provider', label: 'My work', end: true }];

  return (
    <div className={`app-shell role-${role}`}>
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
            <div className="role-switcher" role="group" aria-label="Choose demo role">
              <button
                type="button"
                className={isClient ? 'role-option selected' : 'role-option'}
                aria-pressed={isClient}
                onClick={() => chooseRole('client')}
              >
                Client
              </button>
              <button
                type="button"
                className={!isClient ? 'role-option selected' : 'role-option'}
                aria-pressed={!isClient}
                onClick={() => chooseRole('provider')}
              >
                Provider
              </button>
            </div>
            <button
              type="button"
              className="button button-quiet reset-button"
              onClick={resetDemo}
              disabled={resetting}
            >
              {resetting ? <span className="spinner" /> : <span aria-hidden="true">↻</span>}
              {resetting ? 'Resetting…' : 'Reset demo'}
            </button>
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
            <span className={`avatar avatar-${role}`} aria-hidden="true">{isClient ? 'SC' : 'DS'}</span>
            <span>
              <strong>{user.orgName}</strong>
              <small>{isClient ? 'Client workspace' : 'Provider workspace'}</small>
            </span>
            <span className={`demo-label ${demoMode === 'mock' ? 'mock-mode-label' : ''}`}>
              <span /> {demoMode === 'mock' ? 'Mock mode · simulated payments' : 'PayPal Sandbox'}
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
            : 'From intent to agreement. From evidence to approval. From approval to payment. · PayPal Sandbox'}
        </span>
      </footer>
    </div>
  );
}

export default Layout;
