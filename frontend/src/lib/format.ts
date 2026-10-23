export function hours(value: number | null, beyondScale = false): string {
  if (value === null) return beyondScale ? "вне шкалы" : "—";
  if (value < 1 / 60) return `${Math.round(value * 3600)} сек`;
  if (value < 1) return `${Math.round(value * 60)} мин`;
  if (value < 24) return `${trim(value)} ч`;
  if (value < 24 * 14) return `${trim(value / 24)} сут`;
  return `${trim(value / 24)} сут`;
}

function trim(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
}

export function criticality(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

/** Criticality maps onto the same four-step damage ladder the questionnaire uses:
 *  25% низкий, 50% средний, 75% высокий, 100% крайне высокий. */
export function criticalityClass(value: number | null): string {
  if (value === null) return "chip";
  if (value > 0.75) return "chip chip-extreme";
  if (value > 0.5) return "chip chip-high";
  if (value > 0.25) return "chip chip-medium";
  return "chip chip-low";
}

export const DAMAGE_LABELS: Record<string, string> = {
  financial: "Финансовый",
  regulatory: "Регуляторный",
  operational: "Операционный",
  reputational: "Репутационный",
};

export const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  submitted: "Отправлен",
  reviewed: "Проверен",
};

export function dateTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

/** Russian plural: 1 система, 2 системы, 5 систем. */
export function plural(count: number, one: string, few: string, many: string): string {
  const mod100 = Math.abs(count) % 100;
  const mod10 = mod100 % 10;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

export function systems(count: number): string {
  return plural(count, "система", "системы", "систем");
}

export const IMPLEMENTATION_LABELS: Record<string, string> = {
  not_implemented: "Не внедрено",
  partial: "Частично",
  implemented: "Внедрено",
  not_applicable: "Не применимо",
};

export const PRIORITY_LABELS: Record<string, string> = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

export const FUNCTION_LABELS: Record<string, string> = {
  Govern: "Govern · управление",
  Identify: "Identify · учёт",
  Protect: "Protect · защита",
  Detect: "Detect · обнаружение",
  Respond: "Respond · реагирование",
  Recover: "Recover · восстановление",
};

export const ASSESSMENT_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  in_progress: "В работе",
  completed: "Завершена",
};

/** Implementation runs 0–100%; the bands mirror the status colours of the checklist. */
export function implementationClass(value: number | null): string {
  if (value === null) return "chip";
  if (value >= 0.9) return "chip chip-low";
  if (value >= 0.6) return "chip chip-medium";
  if (value >= 0.3) return "chip chip-high";
  return "chip chip-extreme";
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export function shortDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("ru-RU") : "—";
}
