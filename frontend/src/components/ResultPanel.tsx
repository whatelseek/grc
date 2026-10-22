import { DAMAGE_LABELS, criticality, criticalityClass, hours } from "../lib/format";
import type { Result } from "../lib/types";

export default function ResultPanel({ result }: { result: Result }) {
  const { progress } = result;
  const percent = progress.required_total
    ? Math.round((progress.required_filled / progress.required_total) * 100)
    : 0;

  return (
    <aside className="side">
      <div className="card">
        <h3>Прогресс</h3>
        <div className="bar">
          <div className="bar-fill" style={{ width: `${percent}%` }} />
        </div>
        <p className="muted">
          {progress.required_filled} из {progress.required_total} обязательных вопросов
          {progress.warnings > 0 && <> · замечаний: {progress.warnings}</>}
        </p>
      </div>

      <div className="card">
        <h3>Расчёт</h3>
        <dl className="metrics">
          <div>
            <dt>Общая критичность</dt>
            <dd>
              <span className={criticalityClass(result.overall_criticality)}>
                {criticality(result.overall_criticality)}
              </span>
            </dd>
          </div>
          <div>
            <dt>MTPD</dt>
            <dd>{hours(result.mtpd_hours, result.mtpd_beyond_scale)}</dd>
          </div>
          <div>
            <dt>RTO</dt>
            <dd>{hours(result.rto_hours)}</dd>
          </div>
          <div>
            <dt>RPO</dt>
            <dd>{hours(result.rpo_hours)}</dd>
          </div>
        </dl>

        <table className="table small">
          <thead>
            <tr>
              <th>Тип ущерба</th>
              <th>Недоступность</th>
              <th>Потеря данных</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(result.criticality_by_type).map(([type, series]) => (
              <tr key={type}>
                <th scope="row">{DAMAGE_LABELS[type] ?? type}</th>
                <td>{criticality(series.availability?.criticality ?? null)}</td>
                <td>{criticality(series.integrity?.criticality ?? null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.issues.length > 0 && (
        <div className="card">
          <h3>Замечания</h3>
          <ul className="issues">
            {result.issues.slice(0, 40).map((issue) => (
              <li key={`${issue.code}-${issue.severity}`}>
                <a href={`#q${issue.code}`}>№{issue.code}</a>{" "}
                <span className={issue.severity === "warning" ? "warn" : "todo"}>{issue.message}</span>
              </li>
            ))}
          </ul>
          {result.issues.length > 40 && (
            <p className="muted">…и ещё {result.issues.length - 40}</p>
          )}
        </div>
      )}
    </aside>
  );
}
