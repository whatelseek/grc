/** Offline demo backend: serves /api/* from memory so the published preview is clickable.
 *  Only loaded when the bundle is built with VITE_DEMO=1; the real app always talks to
 *  the FastAPI service. Nothing is persisted — a reload restores the seed data. */
import type { Answer, Client, DashboardRow, SurveyDetail, System, Template, User } from "../lib/types";
import templateJson from "./questionnaire.json";
import { evaluate } from "./scoring";

const template = templateJson as unknown as Template;

const DEMO_USER: User = {
  id: "u-consultant",
  email: "consultant@vexa.example",
  full_name: "Консультант VEXA",
  role: "consultant",
  is_active: true,
  client_ids: ["c-romashka", "c-vasilek"],
};

const clients: Client[] = [
  { id: "c-romashka", name: "ООО «Ромашка»", code: "RMK", notes: "", is_active: true, system_count: 2 },
  { id: "c-vasilek", name: "АО «Василёк»", code: "VSL", notes: "", is_active: true, system_count: 2 },
];

const systems: System[] = [
  { id: "s-1c", client_id: "c-romashka", name: "1С: Бухгалтерия", business_owner: "Е. Смирнова", it_owner: "А. Петров", description: "", survey_count: 1 },
  { id: "s-crm", client_id: "c-romashka", name: "CRM для продаж", business_owner: "И. Орлов", it_owner: "А. Петров", description: "", survey_count: 1 },
  { id: "s-wms", client_id: "c-vasilek", name: "WMS склада", business_owner: "Д. Кузнецов", it_owner: "М. Рябов", description: "", survey_count: 1 },
  { id: "s-mail", client_id: "c-vasilek", name: "Корпоративная почта", business_owner: "О. Белова", it_owner: "М. Рябов", description: "", survey_count: 0 },
];

interface DemoSurvey {
  id: string;
  system_id: string;
  status: "draft" | "submitted" | "reviewed";
  assignee_id: string | null;
  updated_at: string;
  submitted_at: string | null;
  answers: Map<number, Answer>;
}

const matrixCodes = template.matrices.flatMap((m) => m.rows.map((r) => ({ code: r.code, part: m.part })));

/** Seeds one filled survey: a damage ladder that rises with the length of the outage. */
function seedAnswers(availability: string[], integrity: string, texts: Record<number, string>) {
  const answers = new Map<number, Answer>();
  for (const question of template.questions) {
    const text = texts[question.code];
    if (!text) continue;
    answers.set(question.code, {
      question_code: question.code,
      text,
      level: null,
      selections: question.kind === "multiselect3" ? [text] : null,
    });
  }
  for (const matrix of template.matrices) {
    matrix.rows.forEach((row, index) => {
      answers.set(row.code, {
        question_code: row.code,
        text: null,
        level: matrix.part === 3 ? availability[index] : integrity,
        selections: null,
      });
    });
  }
  return answers;
}

const COMMON_TEXTS: Record<number, string> = {
  1: "Е. Смирнова, руководитель отдела, Финансы",
  2: "1С: Бухгалтерия",
  3: "Финансы и казначейство",
  4: "Выставление счетов, закрытие периода, платежи поставщикам",
  8: "100 – 1000",
  9: "Да, есть критичные окна, в которые сбой недопустим",
  10: "Есть на отдельные виды операций",
  11: "Через 8 часов встанут платежи, через сутки — риск просрочки по договорам",
  12: "Последний рабочий день",
  16: "Да",
  17: "Частично / потенциально",
  18: "Да",
  19: "Частично / потенциально",
  76: "24 часа",
  77: "8 часов",
  78: "2 часа",
  79: "24 часа",
  80: "8 часов",
};

const RISING = ["Низкий", "Средний", "Средний", "Высокий", "Высокий", "Крайне высокий", "Крайне высокий"];
const MILD = ["Низкий", "Низкий", "Низкий", "Средний", "Средний", "Средний", "Высокий"];

const surveys: DemoSurvey[] = [
  {
    id: "sv-1c",
    system_id: "s-1c",
    status: "submitted",
    assignee_id: null,
    updated_at: "2026-10-20T09:40:00Z",
    submitted_at: "2026-10-20T09:40:00Z",
    answers: seedAnswers(RISING, "Высокий", COMMON_TEXTS),
  },
  {
    id: "sv-crm",
    system_id: "s-crm",
    status: "draft",
    assignee_id: null,
    updated_at: "2026-10-21T14:05:00Z",
    submitted_at: null,
    answers: seedAnswers(MILD, "Средний", { ...COMMON_TEXTS, 2: "CRM для продаж", 3: "Продажи и исполнение заказов" }),
  },
  {
    id: "sv-wms",
    system_id: "s-wms",
    status: "draft",
    assignee_id: null,
    updated_at: "2026-10-22T08:15:00Z",
    // Deliberately only partly filled, so the preview shows the «Проверка» hints at work.
    answers: new Map(
      matrixCodes
        .filter((row) => row.part === 3)
        .slice(0, 14)
        .map((row, index) => [
          row.code,
          { question_code: row.code, text: null, level: RISING[index % 7], selections: null },
        ]),
    ),
    submitted_at: null,
  },
];

const system = (id: string) => systems.find((s) => s.id === id)!;
const client = (id: string) => clients.find((c) => c.id === id)!;

function detail(survey: DemoSurvey): SurveyDetail {
  const answers = [...survey.answers.values()].sort((a, b) => a.question_code - b.question_code);
  const parent = system(survey.system_id);
  return {
    id: survey.id,
    system_id: survey.system_id,
    system_name: parent.name,
    client_id: parent.client_id,
    client_name: client(parent.client_id).name,
    status: survey.status,
    template_version: "v1",
    assignee_id: survey.assignee_id,
    updated_at: survey.updated_at,
    submitted_at: survey.submitted_at,
    answers,
    result: evaluate(template, answers),
  };
}

function dashboardRows(clientId: string | null): DashboardRow[] {
  return surveys
    .filter((survey) => !clientId || system(survey.system_id).client_id === clientId)
    .map((survey) => {
      const full = detail(survey);
      const parent = system(survey.system_id);
      const text = (code: number) => survey.answers.get(code)?.text ?? null;
      return {
        survey_id: survey.id,
        client_id: parent.client_id,
        client_name: client(parent.client_id).name,
        system_id: parent.id,
        system_name: parent.name,
        business_owner: parent.business_owner,
        it_owner: parent.it_owner,
        status: survey.status,
        overall_criticality: full.result.overall_criticality,
        mtpd_hours: full.result.mtpd_hours,
        rto_hours: full.result.rto_hours,
        rpo_hours: full.result.rpo_hours,
        stated_mtpd: text(76),
        stated_rto: text(77),
        stated_rpo: text(78),
        current_rto: text(79),
        current_rpo: text(80),
        required_filled: full.result.progress.required_filled,
        required_total: full.result.progress.required_total,
        warnings: full.result.progress.warnings,
        updated_at: survey.updated_at,
      };
    });
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function route(method: string, path: string, query: URLSearchParams, body: any): Response {
  if (path === "/auth/login") return json({ access_token: "demo", token_type: "bearer" });
  if (path === "/auth/me") return json(DEMO_USER);
  if (path === "/users") return json([DEMO_USER]);
  if (path === "/template") return json(template);

  if (path === "/clients") return json(clients);
  const clientMatch = path.match(/^\/clients\/([^/]+)$/);
  if (clientMatch) return json(client(clientMatch[1]) ?? json({ detail: "Клиент не найден" }, 404));
  const systemsMatch = path.match(/^\/clients\/([^/]+)\/systems$/);
  if (systemsMatch) return json(systems.filter((s) => s.client_id === systemsMatch[1]));

  if (path === "/dashboard") return json(dashboardRows(query.get("client_id")));
  if (path === "/dashboard/export.csv") {
    return new Response("Экспорт в CSV доступен в рабочей версии приложения\n", {
      headers: { "Content-Type": "text/csv; charset=utf-8" },
    });
  }

  if (path === "/surveys" && method === "GET") {
    const clientId = query.get("client_id");
    return json(dashboardRows(clientId).map((row) => detail(surveys.find((s) => s.id === row.survey_id)!)));
  }

  const surveyMatch = path.match(/^\/surveys\/([^/]+)(\/.*)?$/);
  if (surveyMatch) {
    const survey = surveys.find((s) => s.id === surveyMatch[1]);
    if (!survey) return json({ detail: "Опросник не найден" }, 404);
    const action = surveyMatch[2];

    if (!action && method === "GET") return json(detail(survey));
    if (action === "/answers" && method === "PATCH") {
      for (const incoming of body.answers as Answer[]) {
        survey.answers.set(incoming.question_code, { ...incoming });
      }
      survey.updated_at = new Date().toISOString();
      return json(detail(survey));
    }
    if (action === "/submit") {
      const result = evaluate(template, [...survey.answers.values()]);
      if (result.progress.required_filled < result.progress.required_total) {
        return json(
          {
            detail:
              `Заполнено ${result.progress.required_filled} из ` +
              `${result.progress.required_total} обязательных вопросов`,
          },
          400,
        );
      }
      survey.status = "submitted";
      survey.submitted_at = new Date().toISOString();
      return json(detail(survey));
    }
    if (action === "/reopen") {
      survey.status = "draft";
      survey.submitted_at = null;
      return json(detail(survey));
    }
    if (action === "/review") {
      survey.status = "reviewed";
      return json(detail(survey));
    }
  }

  if (method === "POST" && (path === "/clients" || path.endsWith("/systems") || path === "/surveys")) {
    return json({ detail: "В демо-режиме данные доступны только для чтения" }, 403);
  }
  return json({ detail: `Нет обработчика для ${method} ${path}` }, 404);
}

export function installDemoApi(): void {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString(), window.location.origin);
    if (!url.pathname.startsWith("/api/")) {
      return new Response(null, { status: 404 });
    }
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    // A touch of latency so the autosave indicator behaves as it does against the server.
    await new Promise((resolve) => setTimeout(resolve, 120));
    return route(init?.method ?? "GET", url.pathname.replace("/api", ""), url.searchParams, body);
  };
}
