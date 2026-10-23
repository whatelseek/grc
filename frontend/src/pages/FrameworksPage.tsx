import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import type { Framework, FrameworkVersion } from "../lib/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  published: "Опубликована",
  archived: "В архиве",
};

export default function FrameworksPage() {
  const [versions, setVersions] = useState<FrameworkVersion[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [catalogue, setCatalogue] = useState<Framework | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftVersion, setDraftVersion] = useState("");

  const reload = useCallback(
    async (openId?: string) => {
      const list = await api.get<FrameworkVersion[]>("/frameworks");
      setVersions(list);
      const id =
        openId ?? selectedId ?? list.find((v) => v.status === "published")?.id ?? list[0]?.id;
      if (id) {
        setSelectedId(id);
        setCatalogue(await api.get<Framework>(`/frameworks/${id}`));
      }
    },
    [selectedId],
  );

  useEffect(() => {
    reload().catch((err) => setError(err.message));
    // Load once; later refreshes go through the handlers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = versions.find((version) => version.id === selectedId) ?? null;
  const editable = selected?.status === "draft";

  async function act<T>(run: () => Promise<T>, keepId?: string) {
    setError(null);
    try {
      await run();
      await reload(keepId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  async function select(id: string) {
    setSelectedId(id);
    setError(null);
    try {
      setCatalogue(await api.get<Framework>(`/frameworks/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось открыть версию");
    }
  }

  return (
    <div className="page">
      <h1>Требования</h1>
      <p className="muted">
        Опубликованная версия неизменна: оценки, проведённые по ней, должны читаться так
        же и через год. Чтобы поправить требования, создайте черновик, отредактируйте и
        опубликуйте — новые оценки пойдут уже по нему.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Версия</th>
              <th>Статус</th>
              <th>Контролей</th>
              <th>Требований</th>
              <th>Своих</th>
              <th>Оценок по ней</th>
              <th>Создана</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id} className={version.id === selectedId ? "row-selected" : undefined}>
                <td>
                  <button type="button" className="link" onClick={() => select(version.id)}>
                    {version.version}
                  </button>
                </td>
                <td>{STATUS_LABELS[version.status]}</td>
                <td>{version.control_count}</td>
                <td>{version.safeguard_count}</td>
                <td>{version.custom_count || "—"}</td>
                <td>{version.assessments_using || "—"}</td>
                <td className="small">{dateTime(version.created_at)}</td>
                <td className="small">
                  {version.status === "draft" ? (
                    <button
                      type="button"
                      className="link"
                      onClick={() => act(() => api.post(`/frameworks/${version.id}/publish`), version.id)}
                    >
                      опубликовать
                    </button>
                  ) : (
                    version.status === "published" && (
                      <button
                        type="button"
                        className="link"
                        onClick={() => act(() => api.post(`/frameworks/${version.id}/archive`), version.id)}
                      >
                        в архив
                      </button>
                    )
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <form
          className="card inline-form"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!draftVersion.trim()) return;
            setError(null);
            try {
              const draft = await api.post<FrameworkVersion>(`/frameworks/${selected.id}/draft`, {
                version: draftVersion.trim(),
              });
              setDraftVersion("");
              // Open the draft that was just created, not the version it came from.
              await reload(draft.id);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Не удалось создать черновик");
            }
          }}
        >
          <h2>Черновик на основе версии {selected.version}</h2>
          <input
            placeholder="Номер новой версии, например v8.1.2-internal"
            value={draftVersion}
            onChange={(e) => setDraftVersion(e.target.value)}
            required
          />
          <button type="submit">Создать черновик</button>
        </form>
      )}

      {catalogue && selected && (
        <CatalogueEditor
          catalogue={catalogue}
          editable={editable}
          onChanged={setCatalogue}
          onError={setError}
          frameworkId={selected.id}
        />
      )}
    </div>
  );
}

function CatalogueEditor({
  catalogue,
  editable,
  frameworkId,
  onChanged,
  onError,
}: {
  catalogue: Framework;
  editable: boolean;
  frameworkId: string;
  onChanged: (framework: Framework) => void;
  onError: (message: string | null) => void;
}) {
  const [open, setOpen] = useState<string | null>(catalogue.controls[0]?.number ?? null);

  // A different version may not have the control that was open.
  useEffect(() => {
    setOpen((current) =>
      current && catalogue.controls.some((control) => control.number === current)
        ? current
        : (catalogue.controls[0]?.number ?? null),
    );
  }, [catalogue]);

  async function call(run: () => Promise<Framework>) {
    onError(null);
    try {
      onChanged(await run());
    } catch (err) {
      onError(err instanceof Error ? err.message : "Не удалось сохранить требование");
    }
  }

  return (
    <>
      <h2 className="section-heading">
        {catalogue.title} · {catalogue.version}
        {!editable && <span className="muted"> — только чтение</span>}
      </h2>

      {catalogue.controls.map((control) => (
        <section className="card control" key={control.number}>
          <header className="control-head">
            <button
              type="button"
              className="link control-title"
              onClick={() => setOpen((current) => (current === control.number ? null : control.number))}
            >
              <span className="control-number">{control.number}</span>
              {control.title}
            </button>
            <div className="control-score">
              <span className="muted small">{control.safeguards.length}</span>
              {editable && (
                <button
                  type="button"
                  className="link"
                  onClick={() =>
                    call(() => api.delete<Framework>(`/frameworks/controls/${control.id}`))
                  }
                >
                  удалить
                </button>
              )}
            </div>
          </header>

          {open === control.number && (
            <div className="safeguards">
              {control.safeguards.map((safeguard) => (
                <div className="safeguard requirement" key={safeguard.id}>
                  <div className="safeguard-head">
                    <span className="sg-id">{safeguard.id}</span>
                    <div className="sg-main">
                      <div className="sg-title">
                        {safeguard.title}
                        {safeguard.is_custom && <span className="ig-tag custom"> своё</span>}
                      </div>
                      <div className="sg-meta">
                        <span className="ig-tag">IG{safeguard.ig}</span>
                        <span>{safeguard.security_function || "—"}</span>
                        <span>{safeguard.asset_class || "—"}</span>
                      </div>
                    </div>
                    {editable && (
                      <div className="requirement-actions">
                        <button
                          type="button"
                          className="link"
                          onClick={() => {
                            const title = window.prompt("Формулировка требования", safeguard.title);
                            if (title && title !== safeguard.title) {
                              call(() =>
                                api.patch<Framework>(`/frameworks/safeguards/${safeguard.uuid}`, {
                                  title,
                                }),
                              );
                            }
                          }}
                        >
                          править
                        </button>
                        <button
                          type="button"
                          className="link"
                          onClick={() =>
                            call(() =>
                              api.delete<Framework>(`/frameworks/safeguards/${safeguard.uuid}`),
                            )
                          }
                        >
                          удалить
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {editable && control.id && (
                <NewRequirement
                  controlId={control.id}
                  controlNumber={control.number}
                  nextIndex={control.safeguards.length + 1}
                  frameworkId={frameworkId}
                  onCreated={onChanged}
                  onError={onError}
                />
              )}
            </div>
          )}
        </section>
      ))}

      {editable && (
        <NewControl frameworkId={frameworkId} onCreated={onChanged} onError={onError} />
      )}
    </>
  );
}

function NewRequirement({
  controlId,
  controlNumber,
  nextIndex,
  frameworkId,
  onCreated,
  onError,
}: {
  controlId: string;
  controlNumber: string;
  nextIndex: number;
  frameworkId: string;
  onCreated: (framework: Framework) => void;
  onError: (message: string | null) => void;
}) {
  const [form, setForm] = useState({
    code: `${controlNumber}.${nextIndex}`,
    title: "",
    ig: 1,
    security_function: "",
    asset_class: "",
  });

  return (
    <form
      className="inline-form requirement-form"
      onSubmit={async (event) => {
        event.preventDefault();
        onError(null);
        try {
          onCreated(
            await api.post<Framework>(`/frameworks/${frameworkId}/safeguards`, {
              control_id: controlId,
              ...form,
            }),
          );
          setForm({ ...form, code: "", title: "" });
        } catch (err) {
          onError(err instanceof Error ? err.message : "Не удалось добавить требование");
        }
      }}
    >
      <input
        placeholder="Код"
        value={form.code}
        onChange={(e) => setForm({ ...form, code: e.target.value })}
        required
      />
      <input
        placeholder="Формулировка требования"
        value={form.title}
        onChange={(e) => setForm({ ...form, title: e.target.value })}
        required
      />
      <select value={form.ig} onChange={(e) => setForm({ ...form, ig: Number(e.target.value) })}>
        {[1, 2, 3].map((level) => (
          <option key={level} value={level}>
            IG{level}
          </option>
        ))}
      </select>
      <button type="submit">Добавить требование</button>
    </form>
  );
}

function NewControl({
  frameworkId,
  onCreated,
  onError,
}: {
  frameworkId: string;
  onCreated: (framework: Framework) => void;
  onError: (message: string | null) => void;
}) {
  const [form, setForm] = useState({ number: "", title: "" });

  return (
    <form
      className="card inline-form"
      onSubmit={async (event) => {
        event.preventDefault();
        onError(null);
        try {
          onCreated(await api.post<Framework>(`/frameworks/${frameworkId}/controls`, form));
          setForm({ number: "", title: "" });
        } catch (err) {
          onError(err instanceof Error ? err.message : "Не удалось добавить контроль");
        }
      }}
    >
      <h2>Новый контроль</h2>
      <input
        placeholder="Номер"
        value={form.number}
        onChange={(e) => setForm({ ...form, number: e.target.value })}
        required
      />
      <input
        placeholder="Название"
        value={form.title}
        onChange={(e) => setForm({ ...form, title: e.target.value })}
        required
      />
      <button type="submit">Добавить</button>
    </form>
  );
}
