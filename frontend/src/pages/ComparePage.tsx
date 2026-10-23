import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../lib/api";
import { ASSESSMENT_STATUS_LABELS, IMPLEMENTATION_LABELS, criticality, dateTime } from "../lib/format";
import type { Assessment, Comparison, ComparisonRow } from "../lib/types";

export default function ComparePage() {
  const [params, setParams] = useSearchParams();
  const clientId = params.get("client_id") ?? "";
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  const base = params.get("base") ?? "";
  const target = params.get("target") ?? "";

  useEffect(() => {
    const query = clientId ? `?client_id=${clientId}` : "";
    api
      .get<Assessment[]>(`/assessments${query}`)
      .then((rows) => {
        setAssessments(rows);
        // Default to the two most recent audits, oldest of the pair as the base.
        if (!base && !target && rows.length >= 2) {
          setParams({ client_id: clientId, base: rows[1].id, target: rows[0].id });
        }
      })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  useEffect(() => {
    if (!base || !target || base === target) {
      setComparison(null);
      return;
    }
    api
      .get<Comparison>(`/assessments/compare?base=${base}&target=${target}`)
      .then((data) => {
        setComparison(data);
        setError(null);
      })
      .catch((err) => {
        setComparison(null);
        setError(err.message);
      });
  }, [base, target]);

  const sorted = useMemo(
    () => [...assessments].sort((a, b) => a.updated_at.localeCompare(b.updated_at)),
    [assessments],
  );

  function pick(which: "base" | "target", value: string) {
    const next = new URLSearchParams(params);
    next.set(which, value);
    if (clientId) next.set("client_id", clientId);
    setParams(next);
  }

  return (
    <div className="page">
      <h1>Динамика по аудитам</h1>
      <p className="muted">
        Сравнение двух оценок одного клиента: что закрыли, где откатились назад и какие
        требования появились или исчезли вместе с версией каталога.
      </p>

      <div className="toolbar">
        <label>
          Было
          <select value={base} onChange={(e) => pick("base", e.target.value)}>
            <option value="">— выберите —</option>
            {sorted.map((assessment) => (
              <option key={assessment.id} value={assessment.id}>
                {assessment.name} · {dateTime(assessment.updated_at)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Стало
          <select value={target} onChange={(e) => pick("target", e.target.value)}>
            <option value="">— выберите —</option>
            {sorted.map((assessment) => (
              <option key={assessment.id} value={assessment.id}>
                {assessment.name} · {dateTime(assessment.updated_at)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="error">{error}</div>}
      {!comparison && !error && <p className="empty">Выберите две оценки одного клиента.</p>}

      {comparison && (
        <>
          <section className="kpis">
            <div className="tile">
              <div className="tile-value">{criticality(comparison.base.implementation)}</div>
              <div className="tile-label">было · {comparison.base.name}</div>
              <div className="tile-note">
                {ASSESSMENT_STATUS_LABELS[comparison.base.status]} · каталог{" "}
                {comparison.base.framework_version}
              </div>
            </div>
            <div className="tile">
              <div className="tile-value">{criticality(comparison.target.implementation)}</div>
              <div className="tile-label">стало · {comparison.target.name}</div>
              <div className="tile-note">
                {ASSESSMENT_STATUS_LABELS[comparison.target.status]} · каталог{" "}
                {comparison.target.framework_version}
              </div>
            </div>
            <div className={`tile ${(comparison.overall_delta ?? 0) >= 0 ? "tile-good" : "tile-critical"}`}>
              <div className="tile-value">{formatDelta(comparison.overall_delta)}</div>
              <div className="tile-label">изменение реализации</div>
            </div>
            <div className="tile">
              <div className="tile-value">
                {comparison.improved.length}
                <span className="muted"> / {comparison.regressed.length}</span>
              </div>
              <div className="tile-label">улучшено / откатилось</div>
              <div className="tile-note">{comparison.unchanged} без изменений</div>
            </div>
          </section>

          <section className="card">
            <h3>Готовность по группам</h3>
            <table className="table small">
              <thead>
                <tr>
                  <th>Группа</th>
                  <th>Было</th>
                  <th>Стало</th>
                  <th>Изменение</th>
                </tr>
              </thead>
              <tbody>
                {comparison.groups.map((group) => (
                  <tr key={group.group}>
                    <th scope="row">{group.group}</th>
                    <td>{criticality(group.before)}</td>
                    <td>{criticality(group.after)}</td>
                    <td className={deltaClass(group.delta)}>{formatDelta(group.delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <ChangeTable title="Стало лучше" rows={comparison.improved} empty="Улучшений нет." />
          <ChangeTable
            title="Стало хуже"
            rows={comparison.regressed}
            empty="Откатов назад нет."
          />

          {(comparison.only_in_base.length > 0 || comparison.only_in_target.length > 0) && (
            <section className="card">
              <h3>Изменился сам каталог</h3>
              <p className="muted small">
                Эти требования есть только в одной из версий, поэтому в сравнение они не
                попали.
              </p>
              {comparison.only_in_base.length > 0 && (
                <p className="small">
                  Были только в «{comparison.base.name}»: {comparison.only_in_base.join(", ")}
                </p>
              )}
              {comparison.only_in_target.length > 0 && (
                <p className="small">
                  Появились в «{comparison.target.name}»: {comparison.only_in_target.join(", ")}
                </p>
              )}
            </section>
          )}

          <p className="muted small">
            Открыть оценки: <Link to={`/assessments/${comparison.base.id}`}>{comparison.base.name}</Link>
            {" · "}
            <Link to={`/assessments/${comparison.target.id}`}>{comparison.target.name}</Link>
          </p>
        </>
      )}
    </div>
  );
}

function ChangeTable({ title, rows, empty }: { title: string; rows: ComparisonRow[]; empty: string }) {
  return (
    <section className="card">
      <h3>
        {title} <span className="muted">· {rows.length}</span>
      </h3>
      {rows.length === 0 ? (
        <p className="muted small">{empty}</p>
      ) : (
        <div className="table-scroll">
          <table className="table small">
            <thead>
              <tr>
                <th>Требование</th>
                <th>Что это</th>
                <th>Группа</th>
                <th>Было</th>
                <th>Стало</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.safeguard_id}>
                  <td>{row.safeguard_id}</td>
                  <td>{row.title}</td>
                  <td>
                    <span className="ig-tag">IG{row.ig}</span>
                  </td>
                  <td>{IMPLEMENTATION_LABELS[row.before]}</td>
                  <td>{IMPLEMENTATION_LABELS[row.after]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  const points = Math.round(delta * 100);
  return `${points > 0 ? "+" : ""}${points} п.п.`;
}

function deltaClass(delta: number | null): string | undefined {
  if (delta === null || delta === 0) return undefined;
  return delta > 0 ? "delta-up" : "delta-down";
}
