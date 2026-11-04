import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, formatMoney, type Agreement } from '../../api';
import { NextStep } from '../../components/NextStep';
import { useRole } from '../../context/RoleContext';
import { DataGrid } from '../../components/DataGrid';
import type { ColDef } from 'ag-grid-community';

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
  const columns: ColDef<Agreement>[] = [
    { field: 'title', headerName: 'Agreement', minWidth: 220 },
    { field: 'status', headerName: 'Status', maxWidth: 150 },
    {
      field: 'total_amount_cents',
      headerName: 'Total',
      valueFormatter: ({ value }) => typeof value === 'number' ? formatMoney(value) : '',
      maxWidth: 150,
    },
    {
      headerName: 'Next milestone',
      valueGetter: ({ data }) => data?.milestones.find((item) => item.status !== 'PAID')?.title ?? 'Complete',
      minWidth: 180,
    },
    {
      headerName: '',
      sortable: false,
      filter: false,
      maxWidth: 110,
      cellRenderer: ({ data }: { data?: Agreement }) => data ? <Link to={`/provider/agreements/${data.id}`}>Open ↗</Link> : null,
    },
  ];

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">PROVIDER WORKSPACE</p><h1>Your work, in focus.</h1><p className="page-subtitle">Accept proposals, deliver against milestones, and submit evidence for review.</p></div>
      </div>
      <NextStep>{agreements.some((item) => item.status === 'PROPOSED') ? 'Review the proposed agreement and accept or decline it.' : 'Open an active agreement to continue the next available milestone.'}</NextStep>
      {error && <div className="alert alert-error" role="alert">{error} <button type="button" className="text-button" onClick={() => void load()}>Retry</button></div>}
      {loading ? <div className="loading-panel"><span className="spinner" /> Loading agreements…</div> : agreements.length === 0 ? (
        <section className="empty-state card"><div className="empty-icon" aria-hidden="true">⌁</div><h2>Your next project will appear here.</h2><p>When a client proposes an agreement, review the scope and milestones here.</p></section>
      ) : (
        <DataGrid rows={agreements} columns={columns} label="Provider agreements" />
      )}
    </>
  );
}

export default ProviderDashboard;
