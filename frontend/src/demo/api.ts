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

const RTO_SCALE_HOURS: Record<string, number | null> = {
  "15 минут": 0.25,
  "30 минут": 0.5,
  "1 час": 1,
  "4 часа": 4,
  "8 часов": 8,
  "24 часа": 24,
  "3 суток": 72,
  "7 суток": 168,
  "более 7 суток": null,
};
const RPO_SCALE_HOURS: Record<string, number | null> = {
  "0 (потеря недопустима)": 0,
  "2 минуты": 2 / 60,
  "15 минут": 0.25,
  "2 часа": 2,
  "8 часов": 8,
  "24 часа": 24,
  "3 суток": 72,
  "7 суток": 168,
  "2 недели": 336,
  "более 2 недель": null,
};

function toHours(label: string | null | undefined, scale: Record<string, number | null>) {
  if (!label || !(label in scale)) return { hours: null as number | null, beyond: false };
  const value = scale[label];
  return value === null ? { hours: null, beyond: true } : { hours: value, beyond: false };
}

function bandFor(criticality: number | null): string | null {
  if (criticality === null) return null;
  if (criticality > 0.75) return "Крайне высокий";
  if (criticality > 0.5) return "Высокий";
  if (criticality > 0.25) return "Средний";
  return "Низкий";
}

/** Mirrors backend/app/analytics.py for the offline preview. */
function analytics(clientId: string | null) {
  const scoped = surveys.filter(
    (survey) => !clientId || system(survey.system_id).client_id === clientId,
  );
  const profile: Record<string, number> = {
    Низкий: 0,
    Средний: 0,
    Высокий: 0,
    "Крайне высокий": 0,
  };
  const statuses: Record<string, number> = { draft: 0, submitted: 0, reviewed: 0 };
  const damage: Record<string, { availability: number[]; integrity: number[] }> = {};
  const recovery: any[] = [];
  let scored = 0;
  let complete = 0;

  for (const survey of scoped) {
    const result = evaluate(template, [...survey.answers.values()]);
    statuses[survey.status] += 1;
    if (result.progress.required_filled >= result.progress.required_total) complete += 1;

    const band = bandFor(result.overall_criticality);
    if (band) {
      profile[band] += 1;
      scored += 1;
    }

    for (const [type, series] of Object.entries(result.criticality_by_type)) {
      const bucket = (damage[type] ??= { availability: [], integrity: [] });
      for (const key of ["availability", "integrity"] as const) {
        const entry = series[key];
        if (entry && entry.answered) bucket[key].push(entry.criticality);
      }
    }

    const text = (code: number) => survey.answers.get(code)?.text ?? null;
    const currentRto = toHours(text(79), RTO_SCALE_HOURS);
    const currentRpo = toHours(text(80), RPO_SCALE_HOURS);
    const gap = (required: number | null, current: number | null, beyond: boolean) => {
      if (required === null) return null;
      if (beyond) return Math.max(0, 168 - required) || 168;
      if (current === null) return null;
      return Math.round((current - required) * 10000) / 10000;
    };

    if (result.rto_hours !== null || result.rpo_hours !== null) {
      const parent = system(survey.system_id);
      recovery.push({
        survey_id: survey.id,
        system_name: parent.name,
        client_name: client(parent.client_id).name,
        criticality: result.overall_criticality,
        band,
        required_rto: result.rto_hours,
        current_rto: currentRto.hours,
        current_rto_beyond_scale: currentRto.beyond,
        stated_rto: toHours(text(77), RTO_SCALE_HOURS).hours,
        required_rpo: result.rpo_hours,
        current_rpo: currentRpo.hours,
        current_rpo_beyond_scale: currentRpo.beyond,
        stated_rpo: toHours(text(78), RPO_SCALE_HOURS).hours,
        rto_gap: gap(result.rto_hours, currentRto.hours, currentRto.beyond),
        rpo_gap: gap(result.rpo_hours, currentRpo.hours, currentRpo.beyond),
      });
    }
  }

  const mean = (values: number[]) =>
    values.length ? Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10000) / 10000 : null;

  return {
    kpis: {
      surveys_total: scoped.length,
      surveys_scored: scored,
      surveys_complete: complete,
      high_criticality: profile["Высокий"] + profile["Крайне высокий"],
      rto_gaps: recovery.filter((row) => (row.rto_gap ?? 0) > 0).length,
      rpo_gaps: recovery.filter((row) => (row.rpo_gap ?? 0) > 0).length,
    },
    criticality_profile: ["Низкий", "Средний", "Высокий", "Крайне высокий"].map((band) => ({
      band,
      count: profile[band],
    })),
    collection: ["draft", "submitted", "reviewed"].map((status) => ({
      status,
      count: statuses[status],
    })),
    recovery: recovery.sort((a, b) => (b.rto_gap ?? -Infinity) - (a.rto_gap ?? -Infinity)),
    damage_profile: Object.entries(damage)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([type, values]) => ({
        damage_type: type,
        availability: mean(values.availability),
        integrity: mean(values.integrity),
        systems: Math.max(values.availability.length, values.integrity.length),
      })),
  };
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
  // The CIS audit is not part of the offline preview; an empty list keeps the UI whole.
  if (path === "/assessments") return json([]);
  if (path === "/analytics") return json(analytics(query.get("client_id")));
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
