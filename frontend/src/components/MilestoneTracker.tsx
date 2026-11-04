import type { Milestone } from '../api';
import { formatMoney } from '../api';
import type { ColDef } from 'ag-grid-community';
import { DataGrid } from './DataGrid';

export function MilestoneTracker({ milestones }: { milestones: Milestone[] }) {
  const paid = milestones.filter((item) => item.status === 'PAID').length;
  const columns: ColDef<Milestone>[] = [
    { field: 'order', headerName: '#', maxWidth: 90 },
    { field: 'title', headerName: 'Milestone', minWidth: 190 },
    { field: 'status', maxWidth: 170 },
    {
      field: 'amount_cents',
      headerName: 'Amount',
      valueFormatter: ({ value }) => typeof value === 'number' ? formatMoney(value) : '',
      maxWidth: 140,
    },
    { field: 'description', headerName: 'Deliverable', minWidth: 240 },
  ];
  return (
    <section className="card section-card">
      <div className="section-heading">
        <div><p className="eyebrow">PROJECT ROADMAP</p><h2>Milestone progress</h2></div>
        <span className="muted">{paid} of {milestones.length} paid</span>
      </div>
      <DataGrid rows={milestones} columns={columns} label="Milestone progress" />
    </section>
  );
}
