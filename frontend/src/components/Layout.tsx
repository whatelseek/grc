import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

import logo from "../assets/vexa-logo-light.png";
import { useAuth } from "../lib/auth";
import ThemeToggle from "./ThemeToggle";

const ROLE_LABELS: Record<string, string> = {
  admin: "администратор",
  consultant: "консультант",
  respondent: "владелец системы",
};

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="app">
      <header className="topbar">
        <img className="logo" src={logo} alt="VEXA partners" />
        <nav>
          <NavLink to="/clients">Клиенты</NavLink>
          <NavLink to="/analytics">Аналитика</NavLink>
          <NavLink to="/dashboard">Сводка</NavLink>
          {user?.role === "admin" && <NavLink to="/users">Пользователи</NavLink>}
        </nav>
        <div className="who">
          <span>
            {user?.full_name || user?.email}
            <span className="muted"> · {ROLE_LABELS[user?.role ?? ""]}</span>
          </span>
          <ThemeToggle />
          <button type="button" className="link" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
