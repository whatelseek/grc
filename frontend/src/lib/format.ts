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

export function criticalityClass(value: number | null): string {
  if (value === null) return "chip";
  if (value >= 0.85) return "chip chip-extreme";
  if (value >= 0.6) return "chip chip-high";
  if (value >= 0.35) return "chip chip-medium";
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
