import { useMemo } from 'react';
import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
} from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';

ModuleRegistry.registerModules([AllCommunityModule]);

export function DataGrid<TData>({
  rows,
  columns,
  label,
}: {
  rows: TData[];
  columns: ColDef<TData>[];
  label: string;
}) {
  const defaultColDef = useMemo<ColDef<TData>>(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
      flex: 1,
      minWidth: 130,
    }),
    [],
  );

  return (
    <div className="data-grid" role="region" aria-label={label}>
      <AgGridReact<TData>
        theme={themeQuartz}
        rowData={rows}
        columnDefs={columns}
        defaultColDef={defaultColDef}
        pagination
        paginationPageSize={10}
        domLayout="autoHeight"
        overlayNoRowsTemplate="No records yet."
      />
    </div>
  );
}
