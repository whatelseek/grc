/** Port of backend/app/scoring.py and validation.py for the offline demo build.
 *  The backend stays the source of truth; this exists so the published preview can
 *  recompute without a server. Kept deliberately close to the Python. */
import type { Answer, Issue, Matrix, Progress, Result, Template } from "../lib/types";

const LEVEL_SCORES: Record<string, number> = {
  Низкий: 0.25,
  Средний: 0.5,
  Высокий: 0.75,
  "Крайне высокий": 1,
};
const LEVEL_ORDER = ["Низкий", "Средний", "Высокий", "Крайне высокий"];
const AVAILABILITY_PART = 3;
const INTEGRITY_PART = 4;

const round4 = (value: number) => Math.round(value * 10000) / 10000;

function matrixRows(template: Template) {
  return template.matrices.flatMap((matrix) =>
    matrix.rows.map((row) => ({ ...row, part: matrix.part, damage_type: matrix.damage_type })),
  );
}

function requiredCodes(template: Template): number[] {
  const codes = template.questions.filter((q) => q.required).map((q) => q.code);
  return [...codes, ...matrixRows(template).map((r) => r.code)].sort((a, b) => a - b);
}

function shortestPeriodAt(
  template: Template,
  answers: Map<number, Answer>,
  part: number,
  level: string,
): number | null {
  const hits = matrixRows(template)
    .filter((row) => row.part === part && answers.get(row.code)?.level === level)
    .map((row) => row.period_hours);
  return hits.length ? Math.min(...hits) : null;
}

function recoveryObjective(template: Template, answers: Map<number, Answer>, part: number) {
  const medium = shortestPeriodAt(template, answers, part, "Средний");
  const high = shortestPeriodAt(template, answers, part, "Высокий");
  const extreme = shortestPeriodAt(template, answers, part, "Крайне высокий");
  const candidates = [
    medium,
    high === null ? null : high / 2,
    extreme === null ? null : extreme / 3,
  ].filter((value): value is number => value !== null);
  return candidates.length ? round4(Math.min(...candidates)) : null;
}

function seriesFor(matrix: Matrix, answers: Map<number, Answer>) {
  let total = 0;
  let answered = 0;
  const rows = matrix.rows.map((row) => {
    const level = answers.get(row.code)?.level ?? null;
    const score = level ? LEVEL_SCORES[level] : undefined;
    if (score !== undefined) {
      total += score * row.weight;
      answered += 1;
    }
    return {
      code: row.code,
      period_label: row.period_label,
      period_hours: row.period_hours,
      weight: row.weight,
      level,
      weighted_score: score === undefined ? null : round4(score * row.weight),
    };
  });
  return { criticality: round4(total), answered, total: matrix.rows.length, rows };
}

function hasValue(answer: Answer | undefined): boolean {
  if (!answer) return false;
  if (answer.level) return true;
  if (answer.selections && answer.selections.length) return true;
  return Boolean((answer.text ?? "").trim());
}

function validate(
  template: Template,
  answers: Map<number, Answer>,
): { issues: Issue[]; progress: Progress } {
  const issues: Issue[] = [];
  const grid = new Set(matrixRows(template).map((r) => r.code));
  const required = requiredCodes(template);

  for (const code of required) {
    if (!hasValue(answers.get(code))) {
      issues.push({
        code,
        severity: "missing",
        message: grid.has(code) ? "← отметьте уровень ущерба" : "← заполните",
      });
    }
  }

  const areas = answers.get(3);
  if (areas?.selections && areas.selections.length > 3) {
    issues.push({ code: 3, severity: "warning", message: "⚠ укажите не более трёх областей" });
  }

  for (const matrix of template.matrices) {
    let worstSoFar = -1;
    let worstLabel: string | null = null;
    for (const row of matrix.rows) {
      const level = answers.get(row.code)?.level;
      if (!level) continue;
      const rank = LEVEL_ORDER.indexOf(level);
      if (rank < worstSoFar) {
        issues.push({
          code: row.code,
          severity: "warning",
          message:
            `⚠ на более длинном сроке уровень мягче, чем «${worstLabel}» ` +
            "на коротком — проверьте или поясните в вопросе 15",
        });
      } else {
        worstSoFar = rank;
        worstLabel = level;
      }
    }
  }

  const filled = required.filter((code) => hasValue(answers.get(code))).length;
  const warnings = issues.filter((issue) => issue.severity === "warning").length;
  return {
    issues,
    progress: {
      required_total: required.length,
      required_filled: filled,
      optional_total: template.questions.length + matrixRows(template).length - required.length,
      warnings,
      complete: filled === required.length && warnings === 0,
    },
  };
}

export function evaluate(template: Template, answerList: Answer[]): Result {
  const answers = new Map(answerList.map((a) => [a.question_code, a]));
  const byType: Result["criticality_by_type"] = {};
  const values: number[] = [];
  let answeredAny = false;

  for (const matrix of template.matrices) {
    const series = seriesFor(matrix, answers);
    values.push(series.criticality);
    if (series.answered) answeredAny = true;
    const bucket = (byType[matrix.damage_type] ??= {});
    bucket[matrix.part === AVAILABILITY_PART ? "availability" : "integrity"] = series;
  }

  const mtpd = shortestPeriodAt(template, answers, AVAILABILITY_PART, "Крайне высокий");
  return {
    overall_criticality: answeredAny ? round4(Math.max(...values)) : null,
    criticality_by_type: byType,
    mtpd_hours: mtpd,
    mtpd_beyond_scale: mtpd === null && answeredAny,
    rto_hours: recoveryObjective(template, answers, AVAILABILITY_PART),
    rpo_hours: recoveryObjective(template, answers, INTEGRITY_PART),
    ...validate(template, answers),
  };
}
