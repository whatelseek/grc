import { useState } from "react";

import logo from "../assets/vexa-logo-light.png";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="title-slide">
      <form className="login" onSubmit={submit}>
        <img className="logo" src={logo} alt="VEXA partners" />
        <h1>
          Оценка влияния
          <br />
          недоступности и потери данных
        </h1>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={busy}>
          {busy ? "Входим…" : "Войти"}
        </button>
        <p className="muted small">
          Доступ выдаёт администратор проекта. Если войти не получается, напишите своему
          консультанту.
        </p>
      </form>
    </div>
  );
}
