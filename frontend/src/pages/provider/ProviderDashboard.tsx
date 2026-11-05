import { useCallback, useEffect, useState } from 'react';
import { api, type Agreement } from '../../api';
import { NextStep } from '../../components/NextStep';
import { useRole } from '../../context/RoleContext';
import { AgreementCards } from '../../components/AgreementCards';

function ProviderDashboard() {
  const { user } = useRole();
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setError('');
    try {
      setAgreements(await api.listAgreements('provider', user.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Agreements could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [user.id]);
  useEffect(() => { void load(); }, [load]);

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">PROVIDER WORKSPACE</p><h1>Deliver, submit, get paid.</h1><p className="page-subtitle">Accept proposals, share evidence, and track each milestone through client approval and PayPal payment.</p></div>
      </div>
      <NextStep>{agreements.some((item) => item.status === 'PROPOSED') ? 'Review the proposed agreement and accept or decline it.' : agreements.length > 0 && agreements.every((item) => item.status === 'COMPLETED') ? 'All milestones are paid. Agreement completed.' : 'Open an active agreement to continue the next available milestone.'}</NextStep>
      {error && <div className="alert alert-error" role="alert">{error} <button type="button" className="text-button" onClick={() => void load()}>Retry</button></div>}
      {loading ? <div className="loading-panel"><span className="spinner" /> Loading agreements…</div> : agreements.length === 0 ? (
        <section className="empty-state card"><div className="empty-icon" aria-hidden="true">⌁</div><h2>Your next project will appear here.</h2><p>When a client proposes an agreement, review the scope and milestones here.</p></section>
      ) : (
        <AgreementCards agreements={agreements} role="provider" />
      )}
    </>
  );
}

export default ProviderDashboard;
