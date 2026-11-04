import type { ColDef } from 'ag-grid-community';
import type { Agreement } from '../api';
import { formatMoney } from '../api';
import { DataGrid } from './DataGrid';

interface InvoiceRow {
  milestone: string;
  invoiceId: string;
  status: string;
  amount: number;
  payerLink: string;
}

export function InvoiceTable({ agreement }: { agreement: Agreement }) {
  const rows: InvoiceRow[] = agreement.milestones.flatMap((milestone) =>
    milestone.invoices.map((invoice) => ({
      milestone: milestone.title,
      invoiceId: invoice.paypal_invoice_id ?? 'Preparing',
      status: invoice.status,
      amount: invoice.amount_cents,
      payerLink: invoice.payer_view_url ?? '',
    })),
  );
  const columns: ColDef<InvoiceRow>[] = [
    { field: 'milestone', minWidth: 170 },
    { field: 'invoiceId', headerName: 'Invoice ID', minWidth: 200 },
    { field: 'status', maxWidth: 140 },
    {
      field: 'amount',
      valueFormatter: ({ value }) => typeof value === 'number' ? formatMoney(value) : '',
      maxWidth: 140,
    },
    {
      headerName: 'Payer link',
      sortable: false,
      filter: false,
      cellRenderer: ({ data }: { data?: InvoiceRow }) => data?.payerLink
        ? <a href={data.payerLink} target="_blank" rel="noreferrer">Open ↗</a>
        : '—',
      maxWidth: 130,
    },
  ];

  return <DataGrid rows={rows} columns={columns} label="Agreement invoices" />;
}
