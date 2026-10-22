import { STATUS_LABELS } from "../../lib/format";
import ChartFrame from "./ChartFrame";
import { Tooltip, useTooltip } from "./Tooltip";

const STATUS_COLORS: Record<string, string> = {
  draft: "var(--series-neutral)",
  submitted: "var(--series-current)",
  reviewed: "var(--series-required)",
};

export interface CollectionRow {
  status: string;
  count: number;
}

/** Part-to-whole at a glance, three segments: one stacked bar, directly labelled. */
export default function CollectionBar({ rows }: { rows: CollectionRow[] }) {
  const { tip, show, hide } = useTooltip();
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const width = 460;
  const height = 64;
  let offset = 0;

  return (
    <ChartFrame
      title="Ход сбора"
      caption="Статусы опросников по выбранным клиентам"
      legend={rows.map((row) => ({ label: STATUS_LABELS[row.status], color: STATUS_COLORS[row.status] }))}
      empty={total === 0}
      emptyNote="Опросников пока нет."
      table={
        <table className="table small">
          <thead>
            <tr>
              <th>Статус</th>
              <th>Опросников</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.status}>
                <th scope="row">{STATUS_LABELS[row.status]}</th>
                <td>{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="svg" role="img" aria-label="Ход сбора">
        {rows.map((row) => {
          if (!row.count) return null;
          const segment = (row.count / total) * width;
          const x = offset;
          offset += segment;
          return (
            <g
              key={row.status}
              onMouseMove={(event) =>
                show(event, [
                  STATUS_LABELS[row.status],
                  `${row.count} из ${total}`,
                  `${Math.round((row.count / total) * 100)}%`,
                ])
              }
              onMouseLeave={hide}
            >
              <rect
                x={x}
                y={0}
                // 2px of surface between segments.
                width={Math.max(2, segment - 2)}
                height={18}
                rx={4}
                fill={STATUS_COLORS[row.status]}
              />
              <text x={x} y={38} className="value-label strong">
                {row.count}
              </text>
              <text x={x} y={54} className="axis-label">
                {STATUS_LABELS[row.status]}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </ChartFrame>
  );
}
