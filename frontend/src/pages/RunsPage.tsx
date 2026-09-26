import { FormEvent, useMemo, useState } from "react";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";

import { importCheckpointRun } from "../api";
import { copy, decisionLabel } from "../i18n";
import { formatNumber } from "../lib/utils";
import type { Language, RunSummary } from "../types";
import { EmptyPanel } from "../components/StatePanel";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

const IMPORT_TEXT = {
  en: {
    title: "Import checkpoint metrics",
    help: "Create a local descriptive Run from a CSV up to 1 MB. Required: seed, checkpoint_id, mean_score, and stage or step.",
    name: "Run name",
    file: "Checkpoint metrics CSV",
    action: "Import checkpoint run",
    importing: "Importing…",
    missing: "Choose a run name and CSV file.",
  },
  zh: {
    title: "导入 Checkpoint 指标",
    help: "从不超过 1 MB 的 CSV 创建本地描述性 Run。必填列：seed、checkpoint_id、mean_score，以及 stage 或 step。",
    name: "Run 名称",
    file: "Checkpoint 指标 CSV",
    action: "导入 Checkpoint Run",
    importing: "正在导入…",
    missing: "请填写 Run 名称并选择 CSV 文件。",
  },
} as const;

function readLocalFile(file: File): Promise<string> {
  if (typeof file.text === "function") return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result ?? "")));
    reader.addEventListener("error", () => reject(reader.error ?? new Error("Could not read CSV")));
    reader.readAsText(file, "utf-8");
  });
}

export function RunsPage({
  runs,
  language,
  onCheckpointImported,
  checkpointImportEnabled,
}: {
  runs: RunSummary[];
  language: Language;
  onCheckpointImported: (runName: string) => Promise<void>;
  checkpointImportEnabled: boolean;
}) {
  const labels = copy[language];
  const importLabels = IMPORT_TEXT[language];
  const [runName, setRunName] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
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

  async function submitCheckpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runName.trim() || !csvFile) {
      setImportError(importLabels.missing);
      return;
    }
    setImporting(true);
    setImportError("");
    try {
      const result = await importCheckpointRun(runName, await readLocalFile(csvFile));
      const savedName = result.run.name;
      if (!savedName) throw new Error("The API did not return the saved run name.");
      await onCheckpointImported(savedName);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : String(error));
    } finally {
      setImporting(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.runTitle} lead={labels.runLead} />
      {checkpointImportEnabled ? <Card className="checkpoint-import-card">
        <div>
          <h2>{importLabels.title}</h2>
          <p>{importLabels.help}</p>
        </div>
        <form className="checkpoint-import-form" onSubmit={(event) => void submitCheckpoint(event)}>
          <label>
            <span>{importLabels.name}</span>
            <input
              type="text"
              value={runName}
              maxLength={120}
              onChange={(event) => setRunName(event.target.value)}
            />
          </label>
          <label>
            <span>{importLabels.file}</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setCsvFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="button" type="submit" disabled={importing}>
            {importing ? importLabels.importing : importLabels.action}
          </button>
        </form>
        {importError ? <p className="form-error" role="alert">{importError}</p> : null}
      </Card> : null}
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
