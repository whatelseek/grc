import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../lib/api";
import { canEdit, useAuth } from "../lib/auth";
import {
  ASSESSMENT_STATUS_LABELS,
  STATUS_LABELS,
  criticality,
  criticalityClass,
  dateTime,
  hours,
  implementationClass,
} from "../lib/format";
import type {
  Assessment,
  Client,
  DashboardRow,
  System,
  SurveyDetail,
  User,
} from "../lib/types";

export default function ClientPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [client, setClient] = useState<Client | null>(null);
  const [systems, setSystems] = useState<System[]>([]);
  const [rows, setRows] = useState<DashboardRow[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [people, setPeople] = useState<User[]>([]);
  const [form, setForm] = useState({ name: "", business_owner: "", it_owner: "" });
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!clientId) return;
    const [clientData, systemsData, dashboardData, assessmentData] = await Promise.all([
      api.get<Client>(`/clients/${clientId}`),
      api.get<System[]>(`/clients/${clientId}/systems`),
      api.get<DashboardRow[]>(`/dashboard?client_id=${clientId}`),
      api.get<Assessment[]>(`/assessments?client_id=${clientId}`),
    ]);
    setClient(clientData);
    setSystems(systemsData);
    setRows(dashboardData);
    setAssessments(assessmentData);
    if (canEdit(user)) {
      setPeople(await api.get<User[]>("/users").catch(() => []));
    }
  }, [clientId, user]);

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, [reload]);

  async function addSystem(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/clients/${clientId}/systems`, form);
      setForm({ name: "", business_owner: "", it_owner: "" });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось добавить систему");
    }
  }

  async function startAssessment() {
    setError(null);
    try {
      const assessment = await api.post<Assessment>("/assessments", {
        client_id: clientId,
        target_ig: 1,
      });
      navigate(`/assessments/${assessment.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать оценку");
    }
  }

  async function startSurvey(systemId: string, assigneeId: string) {
    setError(null);
    try {
      const survey = await api.post<SurveyDetail>("/surveys", {
        system_id: systemId,
        assignee_id: assigneeId || null,
      });
      navigate(`/surveys/${survey.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать опросник");
    }
  }

  if (!client) return <div className="page">{error ?? "Загрузка…"}</div>;

  const surveysBySystem = new Map<string, DashboardRow[]>();
  for (const row of rows) {
    surveysBySystem.set(row.system_id, [...(surveysBySystem.get(row.system_id) ?? []), row]);
  }

  return (
    <div className="page">
      <div className="breadcrumbs">
        <Link to="/clients">Клиенты</Link> / {client.name}
      </div>
      <h1>{client.name}</h1>
      {error && <div className="error">{error}</div>}

      <section className="card">
        <header className="system-head">
          <div>
            <h2>Аудит по CIS Controls</h2>
            <div className="muted">
              Оценка мер защиты предприятия: что внедрено, где разрывы и кто их закрывает
            </div>
          </div>
          <div className="new-survey">
            {assessments.length > 1 && (
              <Link className="button-link" to={`/assessments/compare?client_id=${clientId}`}>
                Сравнить аудиты
              </Link>
            )}
            {canEdit(user) && (
              <button type="button" onClick={startAssessment}>
                Новая оценка
              </button>
            )}
          </div>
        </header>

        <table className="table">
          <thead>
            <tr>
              <th>Оценка</th>
              <th>Фреймворк</th>
              <th>Цель</th>
              <th>Статус</th>
              <th>Реализация</th>
              <th>Открытых мер</th>
              <th>Обновлена</th>
            </tr>
          </thead>
          <tbody>
            {assessments.map((assessment) => (
              <tr key={assessment.id}>
                <td>
                  <Link to={`/assessments/${assessment.id}`}>{assessment.name}</Link>
                </td>
                <td className="small">
                  CIS {assessment.framework_version}
                </td>
                <td>IG{assessment.target_ig}</td>
                <td>{ASSESSMENT_STATUS_LABELS[assessment.status]}</td>
                <td>
                  <span className={implementationClass(assessment.implementation)}>
                    {criticality(assessment.implementation)}
                  </span>
                </td>
                <td>
                  <Link to={`/assessments/${assessment.id}/remediation`}>{assessment.gaps_open}</Link>
                </td>
                <td className="small">{dateTime(assessment.updated_at)}</td>
              </tr>
            ))}
            {assessments.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  Оценок пока нет
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <h2 className="section-heading">Оценка влияния (BIA)</h2>

      {systems.length === 0 && <p className="empty">У клиента ещё нет систем.</p>}

      {systems.map((system) => (
        <section key={system.id} className="card">
          <header className="system-head">
            <div>
              <h2>{system.name}</h2>
              <div className="muted">
                Владелец процесса: {system.business_owner || "—"} · ИТ-владелец: {system.it_owner || "—"}
              </div>
            </div>
            {canEdit(user) && (
              <NewSurveyButton people={people} onStart={(assignee) => startSurvey(system.id, assignee)} />
            )}
          </header>

          <table className="table">
            <thead>
              <tr>
                <th>Опросник</th>
                <th>Статус</th>
                <th>Заполнено</th>
                <th>Критичность</th>
                <th>MTPD</th>
                <th>RTO</th>
                <th>RPO</th>
                <th>Обновлён</th>
              </tr>
            </thead>
            <tbody>
              {(surveysBySystem.get(system.id) ?? []).map((row) => (
                <tr key={row.survey_id}>
                  <td>
                    <Link to={`/surveys/${row.survey_id}`}>Открыть</Link>
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
                  <td>{dateTime(row.updated_at)}</td>
                </tr>
              ))}
              {(surveysBySystem.get(system.id) ?? []).length === 0 && (
                <tr>
                  <td colSpan={8} className="muted">
                    Опросников пока нет
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      ))}

      {canEdit(user) && (
        <form className="card inline-form" onSubmit={addSystem}>
          <h2>Новая система</h2>
          <input
            placeholder="Название системы"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <input
            placeholder="Владелец процесса"
            value={form.business_owner}
            onChange={(e) => setForm({ ...form, business_owner: e.target.value })}
          />
          <input
            placeholder="ИТ-владелец"
            value={form.it_owner}
            onChange={(e) => setForm({ ...form, it_owner: e.target.value })}
          />
          <button type="submit">Добавить</button>
        </form>
      )}
    </div>
  );
}

function NewSurveyButton({
  people,
  onStart,
}: {
  people: User[];
  onStart: (assigneeId: string) => void;
}) {
  const [assignee, setAssignee] = useState("");
  return (
    <div className="new-survey">
      <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
        <option value="">Без назначения</option>
        {people.map((person) => (
          <option key={person.id} value={person.id}>
            {person.full_name || person.email}
          </option>
        ))}
      </select>
      <button type="button" onClick={() => onStart(assignee)}>
        Новый опросник
      </button>
    </div>
  );
}
