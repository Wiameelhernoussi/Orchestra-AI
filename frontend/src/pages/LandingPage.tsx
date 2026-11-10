import { Link } from 'react-router-dom';
import { useRole } from '../context/RoleContext';
import { PermissionMatrix } from '../components/PermissionMatrix';

const STEPS = [
  { title: 'Request', actor: 'Client describes the work', icon: '01' },
  { title: 'Agreement', actor: 'Intent becomes milestones', icon: '02' },
  { title: 'Evidence', actor: 'Provider submits proof', icon: '03' },
  { title: 'Approval', actor: 'Client makes the decision', icon: '04' },
  { title: 'Payment', actor: 'PayPal settles the invoice', icon: '05' },
];

function LandingPage() {
  const { setRole } = useRole();
  return (
    <div className="landing-page">
      <header className="landing-header">
        <Link className="brand landing-brand" to="/" aria-label="Orchestra AI home">
          <span className="brand-mark" aria-hidden="true">O</span>
          <span>ORCHESTRA <b>AI</b></span>
        </Link>
        <a className="landing-header-link" href="#how-it-works">How it works <span aria-hidden="true">↓</span></a>
      </header>

      <main>
        <section className="landing-hero">
          <div className="hero-grid">
            <div className="hero-copy">
              <p className="landing-eyebrow"><span /> A clearer way to work together</p>
              <h1>Agree.<br /><span>Verify.</span> Pay.</h1>
              <p className="hero-value">
                Turn a business request into clear milestones, reviewable evidence,
                human approval, and a PayPal invoice.
              </p>
              <div className="hero-actions">
                <Link className="landing-cta landing-cta-client" to="/client" onClick={() => setRole('client')}>
                  Try as Client <span aria-hidden="true">↗</span>
                </Link>
                <Link className="landing-cta landing-cta-provider" to="/provider" onClick={() => setRole('provider')}>
                  Try as Provider <span aria-hidden="true">↗</span>
                </Link>
              </div>
              <p className="hero-note">Interactive prototype · PayPal Sandbox · No real funds</p>
            </div>
            <div className="hero-visual" aria-label="A milestone moving from agreement to verified payment">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="hero-orbit-label">ONE SHARED RECORD</div>
              <div className="proof-card proof-card-top">
                <span className="proof-card-icon provider-icon" aria-hidden="true">↗</span>
                <span><small>PROVIDER SUBMITTED</small><strong>Design evidence</strong></span>
                <span className="proof-card-check" aria-hidden="true">✓</span>
              </div>
              <div className="hero-proof-core">
                <span className="core-mark" aria-hidden="true">O</span>
                <strong>Proof-to-Pay</strong>
                <span>Every step accounted for</span>
              </div>
              <div className="proof-card proof-card-bottom">
                <span className="proof-card-icon paypal-icon" aria-hidden="true">$</span>
                <span><small>PAYPAL SANDBOX</small><strong>Invoice settled</strong></span>
                <span className="proof-card-check" aria-hidden="true">✓</span>
              </div>
              <span className="hero-spark spark-one" aria-hidden="true">✳</span>
              <span className="hero-spark spark-two" aria-hidden="true">✳</span>
            </div>
          </div>
          <div className="hero-bottomline">
            <span>BUILT FOR REMOTE WORK</span>
            <span>Agencies <i /> Freelancers <i /> Clients</span>
          </div>
        </section>

        <section className="landing-section problem-section">
          <div className="section-lead">
            <p className="landing-eyebrow dark-eyebrow">THE PROBLEM</p>
            <h2>Work gets scattered.<br /><span>Trust shouldn’t.</span></h2>
          </div>
          <div className="problem-copy">
            <p>Agreements live in email. Deliverables live in chat. Approval gets lost in a thread. Invoices arrive somewhere else.</p>
            <div className="fragment-row" aria-label="Scattered work artifacts">
              <span><b>@</b> email</span><span><b>•••</b> chats</span><span><b>▤</b> files</span><span><b>$</b> invoices</span>
            </div>
            <p className="problem-answer">Orchestra brings the agreement, evidence, approval, and payment status into one traceable flow.</p>
          </div>
        </section>

        <section className="landing-section how-section" id="how-it-works">
          <div className="section-heading-landing">
            <div>
              <p className="landing-eyebrow dark-eyebrow">ONE CONNECTED WORKFLOW</p>
              <h2>How it works</h2>
            </div>
            <p>People stay in control at the moments that matter.</p>
          </div>
          <ol className="landing-steps" aria-label="How it works">
            {STEPS.map((step, index) => (
              <li className={`landing-step landing-step-${index + 1}`} key={step.title}>
                <span className="step-count">{step.icon}</span>
                <span className="step-connector" aria-hidden="true">{index < STEPS.length - 1 ? '→' : '✓'}</span>
                <h3>{step.title}</h3>
                <p>{step.actor}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="landing-section audience-section">
          <div className="audience-art" aria-hidden="true">
            <div className="audience-orbit" />
            <span className="audience-symbol audience-symbol-one">A</span>
            <span className="audience-symbol audience-symbol-two">F</span>
            <span className="audience-symbol audience-symbol-three">C</span>
            <span className="audience-center">↔</span>
          </div>
          <div className="audience-copy">
            <p className="landing-eyebrow dark-eyebrow">MADE FOR WORK THAT CROSSES DISTANCE</p>
            <h2>Good work deserves<br />a clear path to paid.</h2>
            <p>For agencies, freelancers, and clients who plan, deliver, and collaborate remotely.</p>
            <div className="audience-tags"><span>Agencies</span><span>Freelancers</span><span>Remote clients</span></div>
          </div>
        </section>

        <section className="trust-section">
          <div className="trust-heading">
            <p className="landing-eyebrow">A HUMAN-CENTERED TRUST MODEL</p>
            <h2>A human-centered<br />trust model.</h2>
          </div>
          <div className="trust-detail">
            <p className="trust-statement">AI advises. Humans decide. PayPal settles. Everything is traced.</p>
            <div className="trust-roles">
              <div><span className="trust-icon ai-trust">AI</span><span><strong>AI advises</strong><small>Evidence review is advisory only.</small></span></div>
              <div><span className="trust-icon human-trust">人</span><span><strong>Humans decide</strong><small>The client approves every milestone.</small></span></div>
              <div><span className="trust-icon paypal-trust">$</span><span><strong>PayPal settles</strong><small>Payment status follows the invoice.</small></span></div>
            </div>
            <p className="sandbox-disclosure">Sandbox prototype: standard PayPal invoicing, no escrow.</p>
          </div>
        </section>

        <PermissionMatrix />

        <section className="landing-final-cta">
          <div><p className="landing-eyebrow">START WITH YOUR SIDE OF THE STORY</p><h2>Make the next project clearer.</h2></div>
          <div className="hero-actions">
            <Link className="landing-cta landing-cta-client" to="/client" onClick={() => setRole('client')}>Try as Client <span aria-hidden="true">↗</span></Link>
            <Link className="landing-cta landing-cta-provider" to="/provider" onClick={() => setRole('provider')}>Try as Provider <span aria-hidden="true">↗</span></Link>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <span className="footer-brand">ORCHESTRA AI</span>
        <span>From intent to agreement. From evidence to approval. From approval to payment.</span>
        <span>PayPal Sandbox · Demo prototype</span>
      </footer>
    </div>
  );
}

export default LandingPage;
