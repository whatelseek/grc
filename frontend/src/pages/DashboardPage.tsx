import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api, downloadUrl } from "../lib/api";
import { STATUS_LABELS, criticality, criticalityClass, dateTime, hours } from "../lib/format";
import type { Client, DashboardRow } from "../lib/types";

type SortKey = "client" | "system" | "criticality" | "rto";

export default function DashboardPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [rows, setRows] = useState<DashboardRow[]>([]);
  const [sort, setSort] = useState<SortKey>("criticality");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Client[]>("/clients").then(setClients).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const query = clientId ? `?client_id=${clientId}` : "";
    api
      .get<DashboardRow[]>(`/dashboard${query}`)
      .then(setRows)
      .catch((err) => setError(err.message));
  }, [clientId]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      switch (sort) {
        case "client":
          return a.client_name.localeCompare(b.client_name, "ru");
        case "system":
          return a.system_name.localeCompare(b.system_name, "ru");
        case "rto":
          return (a.rto_hours ?? Infinity) - (b.rto_hours ?? Infinity);
        default:
          return (b.overall_criticality ?? -1) - (a.overall_criticality ?? -1);
      }
    });
    return copy;
  }, [rows, sort]);

  return (
    <div className="page">
      <h1>Сводка по системам</h1>
      {error && <div className="error">{error}</div>}

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
        <label>
          Сортировка
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="criticality">по критичности</option>
            <option value="rto">по RTO</option>
            <option value="client">по клиенту</option>
            <option value="system">по системе</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => downloadUrl(`/dashboard/export.csv${clientId ? `?client_id=${clientId}` : ""}`)}
        >
          Экспорт в CSV
        </button>
      </div>

      <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Клиент</th>
            <th>Система</th>
            <th>Владельцы</th>
            <th>Статус</th>
            <th>Заполнено</th>
            <th>Критичность</th>
            <th>MTPD</th>
            <th>RTO</th>
            <th>RPO</th>
            <th>RTO сейчас</th>
            <th>RPO сейчас</th>
            <th>Обновлён</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.survey_id}>
              <td>
                <Link to={`/clients/${row.client_id}`}>{row.client_name}</Link>
              </td>
              <td>
                <Link to={`/surveys/${row.survey_id}`}>{row.system_name}</Link>
              </td>
              <td className="small">
                {row.business_owner || "—"} / {row.it_owner || "—"}
              </td>
              <td>{STATUS_LABELS[row.status]}</td>
              <td>
                {row.required_filled}/{row.required_total}
                {row.warnings > 0 && <span className="warn"> ⚠ {row.warnings}</span>}
              </td>
              <td>
                <span className={criticalityClass(row.overall_criticality)}>
                  {criticality(row.overall_criticality)}
                </span>
              </td>
              <td>{hours(row.mtpd_hours)}</td>
              <td>{hours(row.rto_hours)}</td>
              <td>{hours(row.rpo_hours)}</td>
              <td className="small">{row.current_rto || "—"}</td>
              <td className="small">{row.current_rpo || "—"}</td>
              <td className="small">{dateTime(row.updated_at)}</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={12} className="muted">
                Нет данных
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
    </div>
  );
}
