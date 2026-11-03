import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useRole } from '../../context/RoleContext';

function Layout() {
  const { role, user, switchRole } = useRole();
  const location = useLocation();
  const navigate = useNavigate();

  const isClient = role === 'client';
  const handleRoleSwitch = () => {
    switchRole();
    navigate(isClient ? '/provider' : '/client');
  };
  const navLinks = isClient
    ? [
        { to: '/client', label: 'Dashboard' },
        { to: '/client/new', label: 'New Agreement' },
      ]
    : [
        { to: '/provider', label: 'Dashboard' },
      ];

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa' }}>
      {/* Header */}
      <header
        style={{
          background: isClient ? '#0070ba' : '#2d8659',
          color: 'white',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 56,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Link to="/" style={{ color: 'white', textDecoration: 'none', fontWeight: 700, fontSize: 20 }}>
            🎵 Orchestra AI
          </Link>
          <nav style={{ display: 'flex', gap: 16 }}>
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                style={{
                  color: 'white',
                  textDecoration: 'none',
                  opacity: location.pathname === link.to ? 1 : 0.75,
                  fontWeight: location.pathname === link.to ? 600 : 400,
                }}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 14, opacity: 0.9 }}>
            {user.name} · {user.orgName}
          </span>
          <button
            onClick={handleRoleSwitch}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: '1px solid rgba(255,255,255,0.4)',
              color: 'white',
              padding: '6px 14px',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Switch to {isClient ? 'Provider' : 'Client'}
          </button>
        </div>
      </header>

      {/* Demo Bar */}
      <div
        style={{
          background: '#fff3cd',
          borderBottom: '1px solid #ffc107',
          padding: '6px 24px',
          fontSize: 13,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span>
          ⚡ <strong>Demo Mode</strong> — Viewing as{' '}
          <strong>{isClient ? 'Client (ShopFlow Inc)' : 'Provider (DevStudio Agency)'}</strong>
        </span>
        <span style={{ color: '#856404' }}>PayPal Sandbox · Hackathon 2026</span>
      </div>

      {/* Content */}
      <main style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
