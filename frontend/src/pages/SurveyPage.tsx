import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import DamageMatrix from "../components/DamageMatrix";
import QuestionField from "../components/QuestionField";
import ResultPanel from "../components/ResultPanel";
import { api } from "../lib/api";
import { canEdit, useAuth } from "../lib/auth";
import { STATUS_LABELS } from "../lib/format";
import type { Answer, Issue, SurveyDetail, Template } from "../lib/types";

const AUTOSAVE_DELAY_MS = 700;

export default function SurveyPage() {
  const { surveyId } = useParams<{ surveyId: string }>();
  const { user } = useAuth();
  const [template, setTemplate] = useState<Template | null>(null);
  const [survey, setSurvey] = useState<SurveyDetail | null>(null);
  const [answers, setAnswers] = useState<Map<number, Answer>>(new Map());
  const [saving, setSaving] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [showInstructions, setShowInstructions] = useState(false);

  const pending = useRef<Map<number, Answer>>(new Map());
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!surveyId) return;
    Promise.all([api.get<Template>("/template"), api.get<SurveyDetail>(`/surveys/${surveyId}`)])
      .then(([templateData, surveyData]) => {
        setTemplate(templateData);
        setSurvey(surveyData);
        setAnswers(new Map(surveyData.answers.map((a) => [a.question_code, a])));
      })
      .catch((err) => setError(err.message));
  }, [surveyId]);

  const flush = useCallback(async () => {
    if (!surveyId || pending.current.size === 0) return;
    const batch = [...pending.current.values()];
    pending.current = new Map();
    setSaving("saving");
    try {
      const updated = await api.patch<SurveyDetail>(`/surveys/${surveyId}/answers`, {
        answers: batch,
      });
      setSurvey(updated);
      setSaving("saved");
    } catch (err) {
      setSaving("error");
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  }, [surveyId]);

  // Save on unmount/tab close so a half-finished edit is not lost.
  useEffect(() => {
    const handler = () => void flush();
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
      void flush();
    };
  }, [flush]);

  const queue = useCallback(
    (code: number, patch: Partial<Answer>) => {
      setAnswers((previous) => {
        const current = previous.get(code) ?? {
          question_code: code,
          text: null,
          level: null,
          selections: null,
        };
        const next: Answer = { ...current, ...patch, question_code: code };
        const map = new Map(previous);
        map.set(code, next);
        pending.current.set(code, next);
        return map;
      });
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), AUTOSAVE_DELAY_MS);
    },
    [flush],
  );

  const issues = useMemo(() => {
    const map = new Map<number, Issue>();
    for (const issue of survey?.result.issues ?? []) {
      // A warning is more interesting than a "fill me in" hint on the same question.
      if (!map.has(issue.code) || issue.severity === "warning") map.set(issue.code, issue);
    }
    return map;
  }, [survey]);

  async function act(action: "submit" | "reopen" | "review") {
    if (!surveyId) return;
    await flush();
    setError(null);
    try {
      setSurvey(await api.post<SurveyDetail>(`/surveys/${surveyId}/${action}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Действие не выполнено");
    }
  }

  if (error && !survey) return <div className="page error">{error}</div>;
  if (!template || !survey) return <div className="page">Загрузка…</div>;

  const readOnly = survey.status === "reviewed" || (survey.status === "submitted" && !canEdit(user));
  const questionsByPart = new Map<number, typeof template.questions>();
  for (const question of template.questions) {
    questionsByPart.set(question.part, [...(questionsByPart.get(question.part) ?? []), question]);
  }

  return (
    <div className="page survey">
      <div className="survey-main">
        <div className="breadcrumbs">
          <Link to="/clients">Клиенты</Link> /{" "}
          <Link to={`/clients/${survey.client_id}`}>{survey.client_name}</Link> / {survey.system_name}
        </div>

        <header className="survey-head">
          <div>
            <h1>{survey.system_name}</h1>
            <p className="muted">
              {template.title} · статус: {STATUS_LABELS[survey.status]}
            </p>
          </div>
          <div className="actions">
            <span className={`save save-${saving}`}>
              {saving === "saving" && "Сохранение…"}
              {saving === "saved" && "Сохранено"}
              {saving === "error" && "Ошибка сохранения"}
            </span>
            {survey.status === "draft" && !readOnly && (
              <button type="button" onClick={() => act("submit")}>
                Отправить
              </button>
            )}
            {survey.status === "submitted" && canEdit(user) && (
              <>
                <button type="button" onClick={() => act("reopen")}>
                  Вернуть в работу
                </button>
                <button type="button" onClick={() => act("review")}>
                  Принять
                </button>
              </>
            )}
          </div>
        </header>

        {error && <div className="error">{error}</div>}

        <div className="card">
          <button type="button" className="link" onClick={() => setShowInstructions((o) => !o)}>
            {showInstructions ? "Скрыть инструкцию" : "Инструкция по заполнению"}
          </button>
          {showInstructions && (
            <div className="instructions">
              {template.instructions.map((line) => (
                <p key={line} className="pre">
                  {line}
                </p>
              ))}
            </div>
          )}
        </div>

        {template.parts.map((part) => (
          <section key={part.number} className="part">
            <h2>{part.title}</h2>

            {(questionsByPart.get(part.number) ?? []).map((question) => (
              <div className="card" key={question.code}>
                <QuestionField
                  question={question}
                  answer={answers.get(question.code)}
                  template={template}
                  disabled={readOnly}
                  issue={issues.get(question.code)?.message ?? null}
                  onChange={(patch) => queue(question.code, patch)}
                />
              </div>
            ))}

            {template.matrices
              .filter((matrix) => matrix.part === part.number)
              .map((matrix) => (
                <DamageMatrix
                  key={`${matrix.part}-${matrix.damage_type}`}
                  matrix={matrix}
                  levels={template.levels}
                  answers={answers}
                  issues={issues}
                  disabled={readOnly}
                  onChange={(code, level) => queue(code, { level })}
                />
              ))}
          </section>
        ))}
      </div>

      <ResultPanel result={survey.result} />
    </div>
  );
}
