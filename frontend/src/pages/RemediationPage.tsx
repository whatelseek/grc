import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, downloadUrl } from "../lib/api";
import {
  IMPLEMENTATION_LABELS,
  PRIORITY_LABELS,
  criticality,
  plural,
  shortDate,
} from "../lib/format";
import type { AssessmentDetail, Gap } from "../lib/types";

type Sort = "ig" | "due" | "control";

export default function RemediationPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<Sort>("ig");
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);

  useEffect(() => {
    if (!assessmentId) return;
    api
      .get<AssessmentDetail>(`/assessments/${assessmentId}`)
      .then(setAssessment)
      .catch((err) => setError(err.message));
  }, [assessmentId]);

  const gaps = useMemo(() => {
    const rows = [...(assessment?.result.gaps ?? [])];
    const filtered = onlyUnassigned ? rows.filter((gap) => !gap.owner) : rows;
    const priorityRank: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return filtered.sort((a, b) => {
      if (sort === "due") {
        return (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999");
      }
      if (sort === "control") {
        return Number(a.control) - Number(b.control) || a.safeguard_id.localeCompare(b.safeguard_id);
      }
      return (
        a.ig - b.ig ||
        (priorityRank[a.priority ?? ""] ?? 3) - (priorityRank[b.priority ?? ""] ?? 3) ||
        a.safeguard_id.localeCompare(b.safeguard_id)
      );
    });
  }, [assessment, sort, onlyUnassigned]);

  if (error) return <div className="page error">{error}</div>;
  if (!assessment) return <div className="page">Загрузка…</div>;

  const overdue = (gap: Gap) =>
    gap.due_date !== null && new Date(gap.due_date) < new Date(new Date().toDateString());

  return (
    <div className="page">
      <div className="breadcrumbs">
        <Link to="/clients">Клиенты</Link> /{" "}
        <Link to={`/clients/${assessment.client_id}`}>{assessment.client_name}</Link> /{" "}
        <Link to={`/assessments/${assessment.id}`}>аудит</Link> / план
      </div>

      <h1>План устранения несоответствий</h1>
      <p className="muted">
        Меры защиты в объёме IG{assessment.target_ig}, которые не внедрены или внедрены
        частично. Сначала IG1 — это базовая кибергигиена, с которой начинают.
      </p>

      <section className="kpis">
        <div className="tile tile-critical">
          <div className="tile-value">{gaps.length}</div>
          <div className="tile-label">
            {plural(gaps.length, "мера требует", "меры требуют", "мер требуют")} работы
          </div>
          <div className="tile-note">
            {gaps.filter((gap) => gap.ig === 1).length} из них в IG1
          </div>
        </div>
        <div className="tile">
          <div className="tile-value">{gaps.filter((gap) => gap.owner).length}</div>
          <div className="tile-label">назначены ответственные</div>
        </div>
        <div className="tile">
          <div className="tile-value">{gaps.filter((gap) => gap.due_date).length}</div>
          <div className="tile-label">со сроком</div>
          <div className="tile-note">{gaps.filter(overdue).length} просрочено</div>
        </div>
        <div className="tile">
          <div className="tile-value">{criticality(assessment.result.overall.implementation)}</div>
          <div className="tile-label">текущая реализация</div>
        </div>
      </section>

      <div className="toolbar">
        <label>
          Сортировка
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="ig">по группе и приоритету</option>
            <option value="due">по сроку</option>
            <option value="control">по контролю</option>
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={onlyUnassigned}
            onChange={(e) => setOnlyUnassigned(e.target.checked)}
          />
          только без ответственного
        </label>
        <button
          type="button"
          className="ghost"
          onClick={() =>
            downloadUrl(`/assessments/${assessment.id}/remediation.csv`, "cis-remediation.csv")
          }
        >
          Экспорт в CSV
        </button>
        <button
          type="button"
          onClick={() =>
            downloadUrl(
              `/assessments/${assessment.id}/report.docx`,
              `Аудит ${assessment.client_name ?? ""}.docx`.trim(),
            )
          }
        >
          Скачать отчёт
        </button>
      </div>

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Мера</th>
              <th>Что сделать</th>
              <th>Группа</th>
              <th>Статус</th>
              <th>Приоритет</th>
              <th>Ответственный</th>
              <th>Срок</th>
              <th>Доказательства</th>
            </tr>
          </thead>
          <tbody>
            {gaps.map((gap) => (
              <tr key={gap.safeguard_id}>
                <td>
                  <Link to={`/assessments/${assessment.id}#sg${gap.safeguard_id}`}>
                    {gap.safeguard_id}
                  </Link>
                </td>
                <td>
                  {gap.title}
                  <div className="muted small">
                    {gap.control}. {gap.control_title}
                  </div>
                </td>
                <td>
                  <span className="ig-tag">IG{gap.ig}</span>
                </td>
                <td>{IMPLEMENTATION_LABELS[gap.status]}</td>
                <td>{gap.priority ? PRIORITY_LABELS[gap.priority] : "—"}</td>
                <td>{gap.owner || <span className="muted">не назначен</span>}</td>
                <td className={overdue(gap) ? "warn" : undefined}>{shortDate(gap.due_date)}</td>
                <td>{gap.evidence_count || "—"}</td>
              </tr>
            ))}
            {gaps.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  Все меры защиты в объёме IG{assessment.target_ig} внедрены.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
