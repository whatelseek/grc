import { useId, useState, type ReactNode } from "react";

interface Props {
  title: string;
  caption?: string;
  legend?: { label: string; color: string }[];
  /** Every chart ships a table view: identity is never carried by colour alone. */
  table: ReactNode;
  children: ReactNode;
  empty?: boolean;
  emptyNote?: string;
}

export default function ChartFrame({
  title,
  caption,
  legend,
  table,
  children,
  empty,
  emptyNote,
}: Props) {
  const [showTable, setShowTable] = useState(false);
  const id = useId();

  return (
    <figure className="chart card">
      <figcaption>
        <h3>{title}</h3>
        {caption && <p className="muted small">{caption}</p>}
      </figcaption>

      {legend && legend.length > 1 && (
        <ul className="legend">
          {legend.map((item) => (
            <li key={item.label}>
              <span className="swatch" style={{ background: item.color }} aria-hidden="true" />
              {item.label}
            </li>
          ))}
        </ul>
      )}

      {empty ? (
        <p className="empty">{emptyNote ?? "Пока нет данных для этого графика."}</p>
      ) : (
        <>
          <div className="plot" hidden={showTable}>
            {children}
          </div>
          <div className="chart-table" hidden={!showTable} id={`${id}-table`}>
            {table}
          </div>
          <button
            type="button"
            className="link small"
            aria-expanded={showTable}
            aria-controls={`${id}-table`}
            onClick={() => setShowTable((open) => !open)}
          >
            {showTable ? "Показать график" : "Показать таблицу"}
          </button>
        </>
      )}
    </figure>
  );
}
