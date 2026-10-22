import ChartFrame from "./ChartFrame";
import { Tooltip, useTooltip } from "./Tooltip";

/** Status palette, not a categorical one: the four steps of the questionnaire's own
 *  damage ladder. Every bar is directly labelled, so the colour never carries the
 *  level on its own. */
export const BAND_COLORS: Record<string, string> = {
  Низкий: "#096d68",
  Средний: "#cd9340",
  Высокий: "#9a390d",
  "Крайне высокий": "#500005",
};

interface Row {
  band: string;
  count: number;
}

export default function BandBars({ rows }: { rows: Row[] }) {
  const { tip, show, hide } = useTooltip();
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const max = Math.max(1, ...rows.map((row) => row.count));

  const rowHeight = 34;
  const barHeight = 14;
  const labelWidth = 136;
  const width = 460;
  const height = rows.length * rowHeight + 8;

  return (
    <ChartFrame
      title="Профиль критичности портфеля"
      caption="Сколько систем попало в каждый уровень по расчёту"
      empty={total === 0}
      emptyNote="Ни один опросник ещё не набрал оценок."
      table={
        <table className="table small">
          <thead>
            <tr>
              <th>Уровень</th>
              <th>Систем</th>
              <th>Доля</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.band}>
                <th scope="row">{row.band}</th>
                <td>{row.count}</td>
                <td>{total ? `${Math.round((row.count / total) * 100)}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="svg" role="img" aria-label="Профиль критичности">
        {rows.map((row, index) => {
          const y = index * rowHeight + 6;
          const barWidth = (row.count / max) * (width - labelWidth - 48);
          return (
            <g key={row.band}>
              <text x={0} y={y + barHeight} className="axis-label">
                {row.band}
              </text>
              <rect
                x={labelWidth}
                y={y + 2}
                width={Math.max(row.count > 0 ? 3 : 0, barWidth)}
                height={barHeight}
                rx={4}
                fill={BAND_COLORS[row.band]}
                onMouseMove={(event) =>
                  show(event, [
                    row.band,
                    `${row.count} из ${total} систем`,
                    total ? `${Math.round((row.count / total) * 100)}% портфеля` : "",
                  ])
                }
                onMouseLeave={hide}
              />
              <text x={labelWidth + Math.max(3, barWidth) + 8} y={y + barHeight} className="value-label">
                {row.count}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </ChartFrame>
  );
}
