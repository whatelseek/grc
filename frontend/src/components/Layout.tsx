import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "../lib/auth";

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
        <div className="brand">BIA / AIA опросник</div>
        <nav>
          <NavLink to="/clients">Клиенты</NavLink>
          <NavLink to="/dashboard">Сводка</NavLink>
          {user?.role === "admin" && <NavLink to="/users">Пользователи</NavLink>}
        </nav>
        <div className="who">
          <span>
            {user?.full_name || user?.email}
            <small> · {ROLE_LABELS[user?.role ?? ""]}</small>
          </span>
          <button type="button" className="link" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
