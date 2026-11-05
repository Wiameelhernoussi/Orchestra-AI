import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Agreement } from '../../api';
import { NextStep } from '../../components/NextStep';
import { useRole } from '../../context/RoleContext';
import { AgreementCards } from '../../components/AgreementCards';

function ClientDashboard() {
  const { user } = useRole();
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      setAgreements(await api.listAgreements('client', user.id));
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
        <div>
          <p className="eyebrow">CLIENT WORKSPACE</p>
          <h1>Review, approve, pay.</h1>
          <p className="page-subtitle">Track milestones, review evidence, and approve payment with confidence.</p>
        </div>
        <Link className="button button-primary" to="/client/new">
          <span aria-hidden="true">＋</span> New agreement
        </Link>
      </div>
      <NextStep>
        {agreements.length > 0 && agreements.every((item) => item.status === 'COMPLETED')
          ? 'All milestones are paid. Agreement completed.'
          : agreements.length
            ? 'Open an agreement to review its milestones and the provider’s latest evidence.'
            : 'Describe a project to create your first structured agreement.'}
      </NextStep>

      {error && <div className="alert alert-error" role="alert">{error} <button className="text-button" onClick={() => void load()}>Retry</button></div>}
      {loading ? (
        <div className="loading-panel"><span className="spinner" /> Loading agreements…</div>
      ) : agreements.length === 0 ? (
        <section className="empty-state card">
          <div className="empty-icon" aria-hidden="true">◎</div>
          <h2>Your first agreement starts with an idea.</h2>
          <p>Turn a business request into milestones, reviewable evidence, and human-approved payments.</p>
          <Link className="button button-primary" to="/client/new">Create an agreement</Link>
        </section>
      ) : (
        <AgreementCards agreements={agreements} role="client" />
      )}
    </>
  );
}

export default ClientDashboard;
