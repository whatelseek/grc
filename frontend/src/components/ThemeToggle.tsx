import { useTheme } from "../lib/theme";

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "светлую" : "тёмную";

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={toggle}
      aria-pressed={theme === "dark"}
      aria-label={`Включить ${next} тему`}
    >
      {theme === "dark" ? "Светлая" : "Тёмная"}
    </button>
  );
}
