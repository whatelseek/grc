import { useRef, useState } from "react";

import { api, getToken } from "../lib/api";
import {
  FUNCTION_LABELS,
  IMPLEMENTATION_LABELS,
  dateTime,
  fileSize,
  plural,
} from "../lib/format";

const FIELD_LABELS: Record<string, string> = {
  status: "статус",
  owner: "ответственный",
  due_date: "срок",
  priority: "приоритет",
  notes: "комментарий",
  migrated_out: "требование исключено из каталога",
  framework_version: "версия каталога",
};

function describe(value: string | null): string {
  if (value === null) return "—";
  return IMPLEMENTATION_LABELS[value] ?? value;
}
import type {
  AssessmentItem,
  EvidenceFile,
  HistoryEntry,
  ImplementationStatus,
  Priority,
  Safeguard,
} from "../lib/types";

const STATUSES: ImplementationStatus[] = [
  "not_implemented",
  "partial",
  "implemented",
  "not_applicable",
];
const PRIORITIES: Priority[] = ["high", "medium", "low"];

interface Props {
  safeguard: Safeguard;
  item: AssessmentItem | undefined;
  assessmentId: string;
  history: HistoryEntry[];
  disabled: boolean;
  onChange: (patch: Partial<AssessmentItem>) => void;
  onEvidenceChange: (safeguardId: string, files: EvidenceFile[]) => void;
}

export default function SafeguardRow({
  safeguard,
  item,
  assessmentId,
  history,
  disabled,
  onChange,
  onEvidenceChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const status = item?.status ?? "not_implemented";
  const evidence = item?.evidence ?? [];
  const needsWork = status === "not_implemented" || status === "partial";

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getToken();
      const response = await fetch(
        `/api/assessments/${assessmentId}/items/${safeguard.id}/evidence`,
        { method: "POST", body: form, headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Не удалось загрузить файл");
      }
      onEvidenceChange(safeguard.id, [...evidence, (await response.json()) as EvidenceFile]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить файл");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeFile(file: EvidenceFile) {
    setError(null);
    try {
      await api.delete(`/evidence/${file.id}`);
      onEvidenceChange(
        safeguard.id,
        evidence.filter((entry) => entry.id !== file.id),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить файл");
    }
  }

  return (
    <div className={`safeguard status-${status}`} id={`sg${safeguard.id}`}>
      <div className="safeguard-head">
        <span className="sg-id">{safeguard.id}</span>
        <div className="sg-main">
          <button type="button" className="link sg-title" onClick={() => setOpen((o) => !o)}>
            {safeguard.title}
          </button>
          <div className="sg-meta">
            <span className="ig-tag">IG{safeguard.ig}</span>
            <span>{FUNCTION_LABELS[safeguard.security_function] ?? safeguard.security_function}</span>
            <span>{safeguard.asset_class}</span>
            {evidence.length > 0 && (
              <span className="evidence-count">
                {evidence.length} {plural(evidence.length, "файл", "файла", "файлов")}
              </span>
            )}
          </div>
        </div>
        <select
          className="sg-status"
          value={status}
          disabled={disabled}
          onChange={(e) => onChange({ status: e.target.value as ImplementationStatus })}
        >
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {IMPLEMENTATION_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      {open && (
        <div className="safeguard-body">
          <p className="pre small muted">{safeguard.description}</p>

          {needsWork && (
            <div className="remediation-fields">
              <label>
                Ответственный
                <input
                  value={item?.owner ?? ""}
                  disabled={disabled}
                  onChange={(e) => onChange({ owner: e.target.value })}
                />
              </label>
              <label>
                Срок
                <input
                  type="date"
                  value={item?.due_date ?? ""}
                  disabled={disabled}
                  onChange={(e) => onChange({ due_date: e.target.value || null })}
                />
              </label>
              <label>
                Приоритет
                <select
                  value={item?.priority ?? ""}
                  disabled={disabled}
                  onChange={(e) => onChange({ priority: (e.target.value || null) as Priority | null })}
                >
                  <option value="">не задан</option>
                  {PRIORITIES.map((value) => (
                    <option key={value} value={value}>
                      {value === "high" ? "Высокий" : value === "medium" ? "Средний" : "Низкий"}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          <label>
            Комментарий
            <textarea
              rows={2}
              value={item?.notes ?? ""}
              disabled={disabled}
              onChange={(e) => onChange({ notes: e.target.value })}
            />
          </label>

          <div className="evidence">
            <div className="evidence-list">
              {evidence.map((file) => (
                <span key={file.id} className="evidence-chip">
                  <a href={`/api/evidence/${file.id}`} target="_blank" rel="noreferrer">
                    {file.filename}
                  </a>
                  <span className="muted small"> {fileSize(file.size_bytes)}</span>
                  {!disabled && (
                    <button type="button" className="link" onClick={() => removeFile(file)}>
                      ×
                    </button>
                  )}
                </span>
              ))}
              {evidence.length === 0 && <span className="muted small">Доказательств пока нет</span>}
            </div>
            {!disabled && (
              <label className="upload">
                <input
                  ref={fileInput}
                  type="file"
                  disabled={busy}
                  onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                />
                {busy ? "Загрузка…" : "Приложить файл"}
              </label>
            )}
          </div>
          {error && <div className="error">{error}</div>}

          {history.length > 0 && (
            <details className="history">
              <summary>
                История изменений · {history.length}
              </summary>
              <ul>
                {history.map((entry) => (
                  <li key={entry.id}>
                    <span className="muted">{dateTime(entry.changed_at)}</span>{" "}
                    {FIELD_LABELS[entry.field] ?? entry.field}: {describe(entry.old_value)} →{" "}
                    {describe(entry.new_value)}
                    {entry.changed_by && <span className="muted"> · {entry.changed_by}</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
