import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { Client, Role, User } from "../lib/types";

const ROLES: Role[] = ["admin", "consultant", "respondent"];
const ROLE_LABELS: Record<Role, string> = {
  admin: "администратор",
  consultant: "консультант",
  respondent: "владелец системы",
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "respondent" as Role,
    client_ids: [] as string[],
  });
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const [userList, clientList] = await Promise.all([
      api.get<User[]>("/users"),
      api.get<Client[]>("/clients"),
    ]);
    setUsers(userList);
    setClients(clientList);
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, []);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/users", form);
      setForm({ email: "", password: "", full_name: "", role: "respondent", client_ids: [] });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать пользователя");
    }
  }

  async function setClientsFor(user: User, clientIds: string[]) {
    setError(null);
    try {
      await api.patch(`/users/${user.id}`, { client_ids: clientIds });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось изменить доступ");
    }
  }

  async function toggleActive(user: User) {
    setError(null);
    try {
      await api.patch(`/users/${user.id}`, { is_active: !user.is_active });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось изменить пользователя");
    }
  }

  return (
    <div className="page">
      <h1>Пользователи</h1>
      {error && <div className="error">{error}</div>}

      <table className="table">
        <thead>
          <tr>
            <th>Email</th>
            <th>Имя</th>
            <th>Роль</th>
            <th>Доступные клиенты</th>
            <th>Активен</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.email}</td>
              <td>{user.full_name || "—"}</td>
              <td>{ROLE_LABELS[user.role]}</td>
              <td>
                <select
                  multiple
                  size={Math.min(4, Math.max(2, clients.length))}
                  value={user.client_ids}
                  onChange={(e) =>
                    setClientsFor(
                      user,
                      [...e.target.selectedOptions].map((option) => option.value),
                    )
                  }
                >
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <button type="button" className="link" onClick={() => toggleActive(user)}>
                  {user.is_active ? "да" : "нет"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="card inline-form" onSubmit={create}>
        <h2>Новый пользователь</h2>
        <input
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
        <input
          placeholder="Имя"
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
        <input
          type="password"
          placeholder="Пароль (мин. 6 символов)"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          minLength={6}
          required
        />
        <select
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
        <select
          multiple
          size={Math.min(4, Math.max(2, clients.length))}
          value={form.client_ids}
          onChange={(e) =>
            setForm({
              ...form,
              client_ids: [...e.target.selectedOptions].map((option) => option.value),
            })
          }
        >
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name}
            </option>
          ))}
        </select>
        <button type="submit">Создать</button>
      </form>
    </div>
  );
}
