import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, formatMoney, type PaywallCheckout, type PaywallRecommendations } from '../../api';
import { useRole } from '../../context/RoleContext';

const TOPICS = [
  { id: 'productivity', label: 'Productivity' },
  { id: 'freelancing', label: 'Freelancing' },
  { id: 'artificial-intelligence', label: 'Artificial intelligence' },
] as const;

function ClientPaywallAssistant() {
  const { user, demoMode } = useRole();
  const [searchParams] = useSearchParams();
  const returnedPurchaseId = searchParams.get('purchase_id');
  const [topics, setTopics] = useState<string[]>(['productivity']);
  const [budget, setBudget] = useState(500);
  const [result, setResult] = useState<PaywallRecommendations | null>(null);
  const [selectedOfferId, setSelectedOfferId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [checkout, setCheckout] = useState<PaywallCheckout | null>(null);
  const [unlocked, setUnlocked] = useState<PaywallCheckout | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadRecommendations = useCallback(async (selectedTopics: string[], selectedBudget: number) => {
    setLoading(true);
    setError('');
    try {
      const next = await api.paywallRecommendations(user.id, selectedTopics, selectedBudget);
      setResult(next);
      setSelectedOfferId((current) =>
        next.recommendations.some((offer) => offer.id === current)
          ? current
          : next.recommendations[0]?.id ?? '',
      );
      setConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Recommendations could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [user.id]);

  function recommend() {
    void loadRecommendations(topics, budget);
  }

  useEffect(() => {
    if (!returnedPurchaseId) return;
    let active = true;
    setLoading(true);
    api.capturePaywallPurchase(user.id, returnedPurchaseId)
      .then((purchase) => {
        if (active) {
          setUnlocked(purchase);
          setCheckout(purchase);
          setError('');
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'PayPal has not confirmed this payment yet.');
          setCheckout({ purchase_id: returnedPurchaseId, status: 'PENDING', approval_url: null });
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [returnedPurchaseId, user.id]);

  useEffect(() => {
    if (!returnedPurchaseId) void loadRecommendations(['productivity'], 500);
  }, [loadRecommendations, returnedPurchaseId]);

  async function startCheckout() {
    if (!selectedOfferId || !confirmed) return;
    setLoading(true);
    setError('');
    setCheckout(null);
    setUnlocked(null);
    try {
      const created = await api.createPaywallPurchase(
        user.id,
        selectedOfferId,
        budget,
        true,
      );
      setCheckout(created);
      if (created.status === 'CAPTURED') setUnlocked(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'PayPal checkout could not be started.');
    } finally {
      setLoading(false);
    }
  }

  async function confirmPayment() {
    if (!checkout) return;
    setLoading(true);
    setError('');
    try {
      const captured = await api.capturePaywallPurchase(user.id, checkout.purchase_id);
      setCheckout(captured);
      setUnlocked(captured);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'PayPal has not confirmed this payment yet.');
    } finally {
      setLoading(false);
    }
  }

  const selectedOffer = result?.recommendations.find((offer) => offer.id === selectedOfferId);

  return (
    <>
      <div className="breadcrumb"><Link to="/client">Agreements</Link><span>/</span><span>Paywall assistant</span></div>
      <header className="page-heading paywall-heading">
        <div>
          <p className="eyebrow">CLIENT · PAYPAL SANDBOX</p>
          <h1>Pay only for what you choose.</h1>
          <p className="page-subtitle">The assistant matches demo content to your interests and spending limit.</p>
        </div>
      </header>

      <section className="paywall-trust-note" aria-label="Payment and access policy">
        Recommendations can use Groq AI; checkout always requires your click and PayPal approval.
        Content unlocks only after PayPal confirms the capture.
      </section>

      {demoMode !== 'real' && (
        <div className="alert alert-warning" role="status">
          This paywall demo requires PayPal Sandbox mode. No simulated purchase is available.
        </div>
      )}
      {error && <div className="alert alert-error" role="alert">{error}</div>}

      {!unlocked && (
        <div className="paywall-layout">
          <section className="card paywall-preferences">
            <p className="eyebrow">YOUR PREFERENCES</p>
            <h2>What would you like to read?</h2>
            <fieldset className="paywall-topic-list">
              <legend>Choose up to three topics</legend>
              {TOPICS.map((topic) => (
                <label key={topic.id}>
                  <input
                    type="checkbox"
                    checked={topics.includes(topic.id)}
                    onChange={(event) => {
                      setTopics((current) => event.target.checked
                        ? [...current, topic.id]
                        : current.filter((item) => item !== topic.id));
                      setResult(null);
                      setConfirmed(false);
                      setCheckout(null);
                    }}
                  />
                  {topic.label}
                </label>
              ))}
            </fieldset>
            <label className="field paywall-budget">
              <span>Maximum price <strong>{formatMoney(budget)}</strong></span>
              <input
                type="range"
                min={0}
                max={500}
                step={50}
                value={budget}
                onChange={(event) => {
                  setBudget(Number(event.target.value));
                  setResult(null);
                  setConfirmed(false);
                  setCheckout(null);
                }}
              />
            </label>
            <button type="button" className="button button-primary" disabled={loading} onClick={recommend}>
              {loading ? 'Thinking…' : 'Find my content'}
            </button>
          </section>

          <section className="paywall-results" aria-live="polite">
            {result && (
              <>
                <p className="paywall-assistant-explanation">
                  <strong>
                    {result.assistant_mode === 'groq_ai'
                      ? 'AI recommendations'
                      : result.assistant_mode === 'rules_fallback'
                        ? 'Preference matches'
                        : 'Demo preference matches'}
                  </strong>
                  {' · '}{result.explanation}
                </p>
                {result.recommendations.length === 0 ? (
                  <div className="card paywall-empty">No content matches this price limit. Raise your maximum to see options.</div>
                ) : result.recommendations.map((offer) => (
                  <button
                    type="button"
                    key={offer.id}
                    className={`card paywall-offer ${selectedOfferId === offer.id ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedOfferId(offer.id);
                      setConfirmed(false);
                      setCheckout(null);
                    }}
                  >
                    <span className="paywall-offer-topline">
                      <span className="paywall-topic-chip">{offer.topic.replace('-', ' ')}</span>
                      <strong>{formatMoney(offer.price_cents, offer.currency)}</strong>
                    </span>
                    <strong className="paywall-offer-title">{offer.title}</strong>
                    <span>{offer.preview}</span>
                    <small>{offer.reason}</small>
                  </button>
                ))}
              </>
            )}
          </section>
        </div>
      )}

      {!unlocked && selectedOffer && (
        <section className="card paywall-checkout">
          <label className="paywall-confirmation">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>
              I choose <strong>{selectedOffer.title}</strong> for{' '}
              <strong>{formatMoney(selectedOffer.price_cents, selectedOffer.currency)}</strong>.
              I will review and approve the payment in PayPal Sandbox.
            </span>
          </label>
          <button
            type="button"
            className="button button-primary"
            disabled={!confirmed || loading || demoMode !== 'real'}
            onClick={() => void startCheckout()}
          >
            Continue to PayPal Sandbox
          </button>
          {checkout?.approval_url && (
            <a className="button button-paypal" href={checkout.approval_url} target="_blank" rel="noreferrer">
              Open PayPal Sandbox approval ↗
            </a>
          )}
          {checkout && checkout.status !== 'CAPTURED' && (
            <button type="button" className="text-button" disabled={loading} onClick={() => void confirmPayment()}>
              I approved in PayPal · check payment
            </button>
          )}
        </section>
      )}

      {unlocked && (
        <article className="card paywall-unlocked">
          <p className="eyebrow">PAYMENT CONFIRMED BY PAYPAL</p>
          <h2>{unlocked.title}</h2>
          <p className="paywall-content">{unlocked.content}</p>
          {unlocked.captured_at && <time dateTime={unlocked.captured_at}>Access unlocked after payment confirmation.</time>}
        </article>
      )}
    </>
  );
}

export default ClientPaywallAssistant;
