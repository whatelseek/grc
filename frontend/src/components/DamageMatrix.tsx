import { useState } from "react";

import { DAMAGE_LABELS } from "../lib/format";
import type { Answer, Issue, Matrix } from "../lib/types";

interface Props {
  matrix: Matrix;
  levels: string[];
  answers: Map<number, Answer>;
  issues: Map<number, Issue>;
  disabled: boolean;
  onChange: (code: number, level: string) => void;
}

/** The workbook keeps «<тип> ущерб» as the first line of the prompt; the heading shows it already. */
function promptBody(prompt: string): string {
  const [first, ...rest] = prompt.split("\n");
  return rest.length ? rest.join("\n") : first;
}

export default function DamageMatrix({ matrix, levels, answers, issues, disabled, onChange }: Props) {
  const [openDescriptions, setOpenDescriptions] = useState(false);
  const perArea = matrix.descriptions.length > 1;

  return (
    <section className="card matrix">
      <header>
        <h3>{DAMAGE_LABELS[matrix.damage_type] ?? matrix.damage_type} ущерб</h3>
        <p className="muted pre">{promptBody(matrix.prompt)}</p>
        <button type="button" className="link" onClick={() => setOpenDescriptions((o) => !o)}>
          {openDescriptions ? "Скрыть описания уровней" : "Показать описания уровней ущерба"}
        </button>
      </header>

      {openDescriptions && (
        <div className="levels">
          <table className="table levels-table">
            <thead>
              <tr>
                {perArea && <th>Функциональная область</th>}
                {levels.map((level) => (
                  <th key={level}>{level}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.descriptions.map((description, index) => (
                <tr key={description.area ?? index}>
                  {perArea && <th scope="row">{description.area}</th>}
                  {levels.map((level) => (
                    <td key={level} className="pre small">
                      {description.levels[level] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <table className="table pick-grid">
        <thead>
          <tr>
            <th className="period-col">Срок</th>
            {levels.map((level) => (
              <th key={level}>{level}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row) => {
            const issue = issues.get(row.code);
            const selected = answers.get(row.code)?.level ?? "";
            return (
              <tr key={row.code} id={`q${row.code}`} className={issue?.severity === "warning" ? "row-warn" : ""}>
                <th scope="row" className="period-col">
                  <span className="code">{row.code}</span> {row.label}
                  {issue && (
                    <div className={issue.severity === "warning" ? "warn" : "todo"}>{issue.message}</div>
                  )}
                </th>
                {levels.map((level) => (
                  <td key={level} className="pick">
                    <label>
                      <input
                        type="radio"
                        name={`q${row.code}`}
                        checked={selected === level}
                        disabled={disabled}
                        onChange={() => onChange(row.code, level)}
                      />
                      <span className="sr-only">{level}</span>
                    </label>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
