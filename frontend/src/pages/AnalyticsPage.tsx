import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import BandBars from "../components/charts/BandBars";
import CollectionBar, { type CollectionRow } from "../components/charts/CollectionBar";
import DamageProfile, { type DamageRow } from "../components/charts/DamageProfile";
import GapDumbbell, { type RecoveryRow } from "../components/charts/GapDumbbell";
import { api } from "../lib/api";
import { criticality, hours, implementationClass, plural, systems } from "../lib/format";
import type { Client } from "../lib/types";

interface RecoveryControls {
  assessment_id: string;
  client_id: string;
  client_name: string;
  target_ig: number;
  controls: { control: string; title: string; implementation: number | null; not_implemented: number }[];
}

interface Analytics {
  kpis: {
    surveys_total: number;
    surveys_scored: number;
    surveys_complete: number;
    high_criticality: number;
    rto_gaps: number;
    rpo_gaps: number;
  };
  criticality_profile: { band: string; count: number }[];
  collection: CollectionRow[];
  recovery: RecoveryRow[];
  damage_profile: DamageRow[];
  recovery_controls?: RecoveryControls[];
}

export default function AnalyticsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Client[]>("/clients").then(setClients).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setData(null);
    api
      .get<Analytics>(`/analytics${clientId ? `?client_id=${clientId}` : ""}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [clientId]);

  if (error) return <div className="page error">{error}</div>;
  if (!data) return <div className="page">Загрузка…</div>;

  const { kpis } = data;
  const worst = data.recovery.find((row) => (row.rto_gap ?? 0) > 0);
  // A current capability past the end of the scale only gives a lower bound.
  const worstGap = worst
    ? `${worst.current_rto_beyond_scale ? "отставание не менее" : "отставание"} ${hours(worst.rto_gap)}`
    : null;
  const misses = (count: number) =>
    `${systems(count)} не ${plural(count, "укладывается", "укладываются", "укладываются")}`;

  return (
    <div className="page">
      <h1>Аналитика портфеля</h1>
      <p className="muted">
        Считается по тем же ответам, что и каждый опросник: расчёт обновляется сразу после
        сохранения.
      </p>

      <div className="toolbar">
        <label>
          Клиент
          <select value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">Все клиенты</option>
            {clients.map((client) => (
              <option key={client.id} value={client.id}>
                {client.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section className="kpis">
        <Tile
          value={kpis.surveys_total}
          label={plural(kpis.surveys_total, "опросник", "опросника", "опросников")}
          note={`${kpis.surveys_complete} заполнено полностью`}
        />
        <Tile
          value={kpis.high_criticality}
          label={`${systems(kpis.high_criticality)} высокой и крайне высокой критичности`}
          tone={kpis.high_criticality ? "serious" : undefined}
        />
        <Tile
          value={kpis.rto_gaps}
          label={`${misses(kpis.rto_gaps)} в расчётный RTO`}
          tone={kpis.rto_gaps ? "critical" : "good"}
          note={worst ? `Худшая: ${worst.system_name}, ${worstGap}` : "Отставаний нет"}
        />
        <Tile
          value={kpis.rpo_gaps}
          label={`${misses(kpis.rpo_gaps)} в расчётный RPO`}
          tone={kpis.rpo_gaps ? "critical" : "good"}
        />
      </section>

      <div className="chart-grid">
        <BandBars rows={data.criticality_profile} />
        <CollectionBar rows={data.collection} />
      </div>

      {kpis.rto_gaps > 0 && (data.recovery_controls ?? []).length > 0 && (
        <section className="card recovery-link">
          <h3>Чем закрываются эти разрывы</h3>
          <p className="muted small">
            Сроки восстановления держатся на мерах CIS: контроль 11 отвечает за
            восстановление данных, контроль 17 — за реагирование на инциденты.
          </p>
          <div className="table-scroll">
          <table className="table small">
            <thead>
              <tr>
                <th>Клиент</th>
                <th>11. Data Recovery</th>
                <th>17. Incident Response</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(data.recovery_controls ?? []).map((row) => (
                <tr key={row.assessment_id}>
                  <th scope="row">{row.client_name}</th>
                  {row.controls.map((control) => (
                    <td key={control.control}>
                      <span className={implementationClass(control.implementation)}>
                        {criticality(control.implementation)}
                      </span>
                      {control.not_implemented > 0 && (
                        <span className="muted small"> · {control.not_implemented} не внедрено</span>
                      )}
                    </td>
                  ))}
                  <td>
                    <Link to={`/assessments/${row.assessment_id}`}>открыть аудит</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      )}

      <GapDumbbell rows={data.recovery} metric="rto" />
      <GapDumbbell rows={data.recovery} metric="rpo" />
      <DamageProfile rows={data.damage_profile} />

      <p className="muted small">
        Подробности по каждой системе — в <Link to="/dashboard">сводке</Link>.
      </p>
    </div>
  );
}

function Tile({
  value,
  label,
  note,
  tone,
}: {
  value: number;
  label: string;
  note?: string;
  tone?: "good" | "serious" | "critical";
}) {
  return (
    <div className={`tile${tone ? ` tile-${tone}` : ""}`}>
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  );
}
