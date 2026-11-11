import { Link, Navigate, useLocation } from 'react-router-dom';
import { PermissionMatrix } from '../components/PermissionMatrix';
import { useRole } from '../context/RoleContext';

const STEPS = [
  { title: 'Define', icon: '✳', accent: 'define' },
  { title: 'Prove', icon: '↗', accent: 'prove' },
  { title: 'Verify', icon: '◉', accent: 'verify' },
  { title: 'Approve', icon: '✓', accent: 'approve' },
  { title: 'Pay', icon: '$', accent: 'pay' },
];

function LandingPage() {
  const { role, setRole } = useRole();
  const location = useLocation();
  const chooseRoleMessage = (location.state as { chooseRoleMessage?: string } | null)?.chooseRoleMessage;
  if (role) return <Navigate to={role === 'client' ? '/client' : '/provider'} replace />;

  return (
    <div className="landing-page landing-design">
      <header className="landing-header">
        <Link className="brand landing-brand" to="/" aria-label="Orchestra AI home">
          <span className="brand-mark" aria-hidden="true">O</span>
          <span>ORCHESTRA <b>AI</b></span>
        </Link>
        <a className="landing-header-link" href="#workflow">The workflow <span aria-hidden="true">↓</span></a>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-design-hero">
            <div className="landing-design-copy">
              {chooseRoleMessage && <p className="choose-role-message" role="status">{chooseRoleMessage}</p>}
              <p className="landing-eyebrow"><span /> One clear path from work to payment</p>
              <h1>Make work clear.<br /><span>Move with confidence.</span></h1>
              <p className="hero-value">Agree on the work. Share proof. Decide together. Pay through PayPal Sandbox.</p>
              <p className="sandbox-disclosure">Sandbox prototype, no escrow.</p>
            </div>
            <div className="landing-design-art" aria-hidden="true">
              <span className="landing-art-orbit landing-art-orbit-one" />
              <span className="landing-art-orbit landing-art-orbit-two" />
              <div className="landing-art-card">
                <span>01 — AGREEMENT</span>
                <strong>Clear scope.<br />Shared expectations.</strong>
                <div><i /><i /><i /><i /><i /></div>
              </div>
              <span className="landing-art-spark">✳</span>
            </div>
          </div>
        </section>

        <section className="landing-flow-section" id="workflow" aria-label="Five steps">
          <ol className="landing-flow" aria-label="Define, Prove, Verify, Approve, Pay">
            {STEPS.map((step, index) => (
              <li className={`landing-flow-step flow-${step.accent}`} key={step.title}>
                <span className="landing-flow-icon" aria-hidden="true">{step.icon}</span>
                <span className="landing-flow-title">{step.title}</span>
                {index < STEPS.length - 1 && <span className="landing-flow-connector" aria-hidden="true">→</span>}
              </li>
            ))}
          </ol>
        </section>

        <section className="landing-role-section" aria-labelledby="role-heading">
          <div className="landing-role-heading">
            <p className="landing-eyebrow dark-eyebrow">CHOOSE YOUR SIDE</p>
            <h2 id="role-heading">Where will you begin?</h2>
          </div>
          <div className="landing-role-cards">
            <Link
              className="landing-role-card client-role-card"
              to="/client"
              onClick={() => setRole('client')}
            >
              <span className="landing-role-icon" aria-hidden="true">◉</span>
              <span className="landing-role-card-copy">
                <strong>I'm a client</strong>
                <small>Define the work. Review and approve it.</small>
              </span>
              <span className="landing-role-arrow" aria-hidden="true">↗</span>
            </Link>
            <Link
              className="landing-role-card provider-role-card"
              to="/provider"
              onClick={() => setRole('provider')}
            >
              <span className="landing-role-icon" aria-hidden="true">✦</span>
              <span className="landing-role-card-copy">
                <strong>I'm a provider</strong>
                <small>Deliver the work. Share your evidence.</small>
              </span>
              <span className="landing-role-arrow" aria-hidden="true">↗</span>
            </Link>
          </div>
        </section>

        <PermissionMatrix />
      </main>
      <footer className="landing-footer landing-design-footer">
        <span className="footer-brand">ORCHESTRA AI</span>
        <span>AI advises. You decide.</span>
        <span>PayPal Sandbox · No escrow</span>
      </footer>
    </div>
  );
}

export default LandingPage;
