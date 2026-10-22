import type { Answer, TemplateQuestion, Template } from "../lib/types";

interface Props {
  question: TemplateQuestion;
  answer: Answer | undefined;
  template: Template;
  disabled: boolean;
  issue: string | null;
  onChange: (patch: Partial<Answer>) => void;
}

export default function QuestionField({ question, answer, template, disabled, issue, onChange }: Props) {
  const options = question.option_list ? template.option_lists[question.option_list] ?? [] : [];
  const value = answer?.text ?? "";

  return (
    <div className="question" id={`q${question.code}`}>
      <div className="question-head">
        <span className="code">{question.code}</span>
        <div>
          <div className="question-text">
            {question.text}
            {!question.required && <span className="muted"> · необязательно</span>}
          </div>
          {question.help && <div className="help">{question.help}</div>}
        </div>
      </div>

      <div className="question-input">
        {question.kind === "text" && (
          <input
            type="text"
            value={value}
            disabled={disabled}
            onChange={(e) => onChange({ text: e.target.value })}
          />
        )}

        {question.kind === "textarea" && (
          <textarea
            rows={3}
            value={value}
            disabled={disabled}
            onChange={(e) => onChange({ text: e.target.value })}
          />
        )}

        {question.kind === "select" && (
          <select value={value} disabled={disabled} onChange={(e) => onChange({ text: e.target.value })}>
            <option value="">— выберите —</option>
            {options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        )}

        {question.kind === "select_text" && (
          <div className="stack">
            <select
              value={answer?.selections?.[0] ?? ""}
              disabled={disabled}
              onChange={(e) =>
                onChange({ selections: e.target.value ? [e.target.value] : null, text: value })
              }
            >
              <option value="">— выберите —</option>
              {options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <textarea
              rows={2}
              placeholder="Пояснение"
              value={value}
              disabled={disabled}
              onChange={(e) => onChange({ text: e.target.value, selections: answer?.selections ?? null })}
            />
          </div>
        )}

        {question.kind === "multiselect3" && (
          <div className="stack">
            {[0, 1, 2].map((index) => (
              <select
                key={index}
                value={answer?.selections?.[index] ?? ""}
                disabled={disabled}
                onChange={(e) => {
                  const next = [...(answer?.selections ?? [])];
                  next[index] = e.target.value;
                  const cleaned = next.filter(Boolean);
                  onChange({
                    selections: cleaned.length ? cleaned : null,
                    text: cleaned.join(", ") || null,
                  });
                }}
              >
                <option value="">{index === 0 ? "— основная область —" : "— ещё область —"}</option>
                {options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ))}
          </div>
        )}
      </div>

      {issue && <div className={issue.startsWith("⚠") ? "warn" : "todo"}>{issue}</div>}
    </div>
  );
}
