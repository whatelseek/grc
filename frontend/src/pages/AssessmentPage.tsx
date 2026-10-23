import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import SafeguardRow from "../components/SafeguardRow";
import { api, downloadUrl } from "../lib/api";
import { canEdit, useAuth } from "../lib/auth";
import {
  ASSESSMENT_STATUS_LABELS,
  FUNCTION_LABELS,
  IMPLEMENTATION_LABELS,
  criticality,
  implementationClass,
  plural,
} from "../lib/format";
import type {
  AssessmentDetail,
  AssessmentItem,
  EvidenceFile,
  Framework,
  HistoryEntry,
  ImplementationStatus,
} from "../lib/types";

const AUTOSAVE_DELAY_MS = 700;
type StatusFilter = "all" | ImplementationStatus | "open";

export default function AssessmentPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const { user } = useAuth();
  const [framework, setFramework] = useState<Framework | null>(null);
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [items, setItems] = useState<Map<string, AssessmentItem>>(new Map());
  const [saving, setSaving] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [functionFilter, setFunctionFilter] = useState("");
  const [openControls, setOpenControls] = useState<Set<string>>(new Set(["1"]));
  const [history, setHistory] = useState<Map<string, HistoryEntry[]>>(new Map());

  const pending = useRef<Map<string, AssessmentItem>>(new Map());
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!assessmentId) return;
    api
      .get<AssessmentDetail>(`/assessments/${assessmentId}`)
      .then(async (data) => {
        // The audit is read against the catalogue version it was carried out on.
        const frameworkData = await api.get<Framework>(
          `/assessments/framework${data.framework_id ? `?framework_id=${data.framework_id}` : ""}`,
        );
        setFramework(frameworkData);
        setAssessment(data);
        setItems(new Map(data.items.map((item) => [item.safeguard_id, item])));
        const entries = await api
          .get<HistoryEntry[]>(`/assessments/${assessmentId}/history`)
          .catch(() => [] as HistoryEntry[]);
        const grouped = new Map<string, HistoryEntry[]>();
        for (const entry of entries) {
          grouped.set(entry.safeguard_id, [...(grouped.get(entry.safeguard_id) ?? []), entry]);
        }
        setHistory(grouped);
      })
      .catch((err) => setError(err.message));
  }, [assessmentId]);

  const flush = useCallback(async () => {
    if (!assessmentId || pending.current.size === 0) return;
    const batch = [...pending.current.values()];
    pending.current = new Map();
    setSaving("saving");
    try {
      const updated = await api.patch<AssessmentDetail>(`/assessments/${assessmentId}/items`, {
        items: batch.map(({ evidence: _evidence, ...rest }) => rest),
      });
      setAssessment(updated);
      setSaving("saved");
    } catch (err) {
      setSaving("error");
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }, [assessmentId]);

  useEffect(() => {
    const handler = () => void flush();
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
      void flush();
    };
  }, [flush]);

  const queue = useCallback(
    (safeguardId: string, patch: Partial<AssessmentItem>) => {
      setItems((previous) => {
        const current = previous.get(safeguardId) ?? {
          safeguard_id: safeguardId,
          status: "not_implemented" as ImplementationStatus,
          owner: "",
          due_date: null,
          priority: null,
          notes: "",
          evidence: [],
        };
        const next = { ...current, ...patch, safeguard_id: safeguardId };
        const map = new Map(previous);
        map.set(safeguardId, next);
        pending.current.set(safeguardId, next);
        return map;
      });
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), AUTOSAVE_DELAY_MS);
    },
    [flush],
  );

  const setEvidence = useCallback((safeguardId: string, files: EvidenceFile[]) => {
    setItems((previous) => {
      const current = previous.get(safeguardId);
      if (!current) return previous;
      const map = new Map(previous);
      map.set(safeguardId, { ...current, evidence: files });
      return map;
    });
  }, []);

  async function setTarget(targetIg: number) {
    if (!assessmentId) return;
    await flush();
    const updated = await api.patch<AssessmentDetail>(`/assessments/${assessmentId}`, {
      target_ig: targetIg,
    });
    setAssessment(updated);
  }

  async function setStatus(status: "in_progress" | "completed") {
    if (!assessmentId) return;
    await flush();
    const updated = await api.patch<AssessmentDetail>(`/assessments/${assessmentId}`, { status });
    setAssessment(updated);
  }

  const byControl = useMemo(() => {
    const map = new Map<string, { implementation: number | null; counted: number }>();
    for (const row of assessment?.result.by_control ?? []) {
      map.set(row.control, { implementation: row.implementation, counted: row.counted });
    }
    return map;
  }, [assessment]);

  if (error && !assessment) return <div className="page error">{error}</div>;
  if (!framework || !assessment) return <div className="page">Загрузка…</div>;

  const readOnly = assessment.status === "completed" || !canEdit(user);
  const target = assessment.target_ig;
  const { result } = assessment;

  const matches = (safeguardId: string, ig: number, securityFunction: string) => {
    if (ig > target) return false;
    if (functionFilter && securityFunction !== functionFilter) return false;
    const status = items.get(safeguardId)?.status ?? "not_implemented";
    if (statusFilter === "all") return true;
    if (statusFilter === "open") return status === "not_implemented" || status === "partial";
    return status === statusFilter;
  };

  return (
    <div className="page">
      <div className="breadcrumbs">
        <Link to="/clients">Клиенты</Link> /{" "}
        <Link to={`/clients/${assessment.client_id}`}>{assessment.client_name}</Link> / аудит
      </div>

      <header className="survey-head">
        <div>
          <h1>{assessment.name}</h1>
          <p className="muted">
            {framework.title} · каталог {assessment.framework_version} · {assessment.client_name}{" "}
            · статус: {ASSESSMENT_STATUS_LABELS[assessment.status]}
          </p>
        </div>
        <div className="actions">
          <span className={`save save-${saving}`}>
            {saving === "saving" && "Сохранение…"}
            {saving === "saved" && "Сохранено"}
            {saving === "error" && "Ошибка сохранения"}
          </span>
          <Link className="button-link" to={`/assessments/${assessment.id}/remediation`}>
            План устранения
          </Link>
          <Link
            className="button-link"
            to={`/assessments/compare?client_id=${assessment.client_id}&target=${assessment.id}`}
          >
            Сравнить
          </Link>
          {canEdit(user) &&
            (assessment.status === "completed" ? (
              <button type="button" className="ghost" onClick={() => setStatus("in_progress")}>
                Вернуть в работу
              </button>
            ) : (
              <button type="button" onClick={() => setStatus("completed")}>
                Завершить оценку
              </button>
            ))}
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="kpis">
        <div className="tile">
          <div className="tile-value">{criticality(result.overall.implementation)}</div>
          <div className="tile-label">внедрено мер защиты в объёме IG{target}</div>
          <div className="tile-note">
            {result.overall.implemented} полностью, {result.overall.partial} частично из{" "}
            {result.overall.counted} учитываемых
          </div>
        </div>
        {[1, 2, 3].map((level) => {
          const group = result.implementation_groups[`IG${level}`];
          return (
            <div key={level} className={`tile${level === target ? " tile-target" : ""}`}>
              <div className="tile-value">{criticality(group.implementation)}</div>
              <div className="tile-label">
                готовность IG{level}
                {level === target ? " · цель" : ""}
              </div>
              <div className="tile-note">
                {group.in_scope} {plural(group.in_scope, "мера", "меры", "мер")} в объёме
                {group.not_applicable > 0 && `, ${group.not_applicable} неприменимо`}
              </div>
            </div>
          );
        })}
      </section>

      <div className="toolbar">
        <label>
          Целевая группа
          <select
            value={target}
            disabled={readOnly}
            onChange={(e) => setTarget(Number(e.target.value))}
          >
            {framework.implementation_groups.map((group) => (
              <option key={group.level} value={group.level}>
                {group.title} — {group.description}
              </option>
            ))}
          </select>
        </label>
        <label>
          Статус
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
            <option value="all">все</option>
            <option value="open">требуют работы</option>
            {(Object.keys(IMPLEMENTATION_LABELS) as ImplementationStatus[]).map((value) => (
              <option key={value} value={value}>
                {IMPLEMENTATION_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Функция
          <select value={functionFilter} onChange={(e) => setFunctionFilter(e.target.value)}>
            <option value="">все</option>
            {framework.security_functions.map((name) => (
              <option key={name} value={name}>
                {FUNCTION_LABELS[name] ?? name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="ghost" onClick={() => downloadUrl(`/assessments/${assessment.id}/remediation.csv`, "cis-remediation.csv")}>
          Экспорт плана в CSV
        </button>
      </div>

      {framework.controls.map((control) => {
        const visible = control.safeguards.filter((safeguard) =>
          matches(safeguard.id, safeguard.ig, safeguard.security_function),
        );
        if (visible.length === 0) return null;
        const score = byControl.get(control.number);
        const expanded = openControls.has(control.number);
        return (
          <section className="card control" key={control.number}>
            <header className="control-head">
              <button
                type="button"
                className="link control-title"
                aria-expanded={expanded}
                onClick={() =>
                  setOpenControls((previous) => {
                    const next = new Set(previous);
                    if (next.has(control.number)) next.delete(control.number);
                    else next.add(control.number);
                    return next;
                  })
                }
              >
                <span className="control-number">{control.number}</span>
                {control.title}
              </button>
              <div className="control-score">
                <span className="muted small">
                {visible.length} {plural(visible.length, "мера", "меры", "мер")}
              </span>
                <span className={implementationClass(score?.implementation ?? null)}>
                  {criticality(score?.implementation ?? null)}
                </span>
              </div>
            </header>
            {expanded && (
              <div className="safeguards">
                {visible.map((safeguard) => (
                  <SafeguardRow
                    key={safeguard.id}
                    safeguard={safeguard}
                    item={items.get(safeguard.id)}
                    assessmentId={assessment.id}
                    history={history.get(safeguard.id) ?? []}
                    disabled={readOnly}
                    onChange={(patch) => queue(safeguard.id, patch)}
                    onEvidenceChange={setEvidence}
                  />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
