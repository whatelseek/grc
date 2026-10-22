import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { canEdit, useAuth } from "../lib/auth";
import type { Client } from "../lib/types";

export default function ClientsPage() {
  const { user } = useAuth();
  const [clients, setClients] = useState<Client[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setClients(await api.get<Client[]>("/clients"));
    setLoading(false);
  }

  useEffect(() => {
    reload().catch((err) => {
      setError(err.message);
      setLoading(false);
    });
  }, []);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/clients", { name, code: code || null });
      setName("");
      setCode("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать клиента");
    }
  }

  return (
    <div className="page">
      <h1>Клиенты</h1>
      <p className="muted">Выберите клиента, чтобы увидеть его системы и опросники.</p>

      {loading ? (
        <p>Загрузка…</p>
      ) : clients.length === 0 ? (
        <p className="empty">Пока нет доступных клиентов.</p>
      ) : (
        <div className="grid">
          {clients.map((client) => (
            <Link key={client.id} to={`/clients/${client.id}`} className="card client-card">
              <h2>{client.name}</h2>
              {client.code && <div className="muted">{client.code}</div>}
              <div className="count">{client.system_count} систем</div>
            </Link>
          ))}
        </div>
      )}

      {canEdit(user) && (
        <form className="card inline-form" onSubmit={create}>
          <h2>Новый клиент</h2>
          <input
            placeholder="Название"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input placeholder="Код (необязательно)" value={code} onChange={(e) => setCode(e.target.value)} />
          <button type="submit">Добавить</button>
          {error && <div className="error">{error}</div>}
        </form>
      )}
    </div>
  );
}
