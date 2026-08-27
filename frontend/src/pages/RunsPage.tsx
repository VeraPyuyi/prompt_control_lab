import { useMemo } from "react";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";

import { copy, decisionLabel } from "../i18n";
import { formatNumber } from "../lib/utils";
import type { Language, RunSummary } from "../types";
import { EmptyPanel } from "../components/StatePanel";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

export function RunsPage({ runs, language }: { runs: RunSummary[]; language: Language }) {
  const labels = copy[language];
  const columns = useMemo(() => {
    const column = createColumnHelper<RunSummary>();
    return [
      column.accessor((row) => row.id ?? row.name ?? row.path ?? "—", { id: "run", header: labels.run }),
      column.accessor((row) => row.score ?? row.mean_score, { id: "score", header: labels.score, cell: (info) => formatNumber(info.getValue()) }),
      column.accessor((row) => row.gate_status ?? row.decision, { id: "gate", header: labels.gate, cell: (info) => <Badge>{decisionLabel(info.getValue(), language)}</Badge> }),
      column.accessor("model", { header: labels.model, cell: (info) => info.getValue() ?? "—" }),
      column.accessor("provider", { header: labels.provider, cell: (info) => info.getValue() ?? "—" }),
    ];
  }, [labels, language]);
  const table = useReactTable({ data: runs, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.runTitle} lead={labels.runLead} />
      {!runs.length ? <EmptyPanel language={language} /> : (
        <Card className="table-card">
          <div className="table-scroll">
            <table>
              <thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>)}</thead>
              <tbody>{table.getRowModel().rows.map((row) => <tr key={row.id}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
