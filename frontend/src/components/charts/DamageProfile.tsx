import { DAMAGE_LABELS, criticality } from "../../lib/format";
import ChartFrame from "./ChartFrame";
import { Tooltip, useTooltip } from "./Tooltip";

const AVAILABILITY = "#0f3c64";
const INTEGRITY = "#7391d7";

export interface DamageRow {
  damage_type: string;
  availability: number | null;
  integrity: number | null;
  systems: number;
}

/** Two series on one 0–100% axis, so grouped bars rather than two scales. */
export default function DamageProfile({ rows }: { rows: DamageRow[] }) {
  const { tip, show, hide } = useTooltip();
  const labelWidth = 128;
  const width = 1060;
  const groupHeight = 44;
  const barHeight = 13;
  const height = rows.length * groupHeight + 24;
  const axisRight = width - 56;
  const scale = (value: number) => value * (axisRight - labelWidth);

  return (
    <ChartFrame
      title="Что именно создаёт критичность"
      caption="Средняя критичность по типам ущерба, отдельно для простоя и потери данных"
      legend={[
        { label: "Недоступность", color: AVAILABILITY },
        { label: "Потеря данных", color: INTEGRITY },
      ]}
      empty={rows.length === 0}
      table={
        <table className="table small">
          <thead>
            <tr>
              <th>Тип ущерба</th>
              <th>Недоступность</th>
              <th>Потеря данных</th>
              <th>Систем</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.damage_type}>
                <th scope="row">{DAMAGE_LABELS[row.damage_type] ?? row.damage_type}</th>
                <td>{criticality(row.availability)}</td>
                <td>{criticality(row.integrity)}</td>
                <td>{row.systems}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="svg" role="img" aria-label="Профиль по типам ущерба">
        {[0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={labelWidth + scale(tick)}
              y1={0}
              x2={labelWidth + scale(tick)}
              y2={height - 18}
              className="grid-line"
            />
            <text x={labelWidth + scale(tick)} y={height - 4} className="axis-label tick">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}

        {rows.map((row, index) => {
          const y = index * groupHeight + 8;
          const label = DAMAGE_LABELS[row.damage_type] ?? row.damage_type;
          const bars = [
            { key: "availability", value: row.availability, color: AVAILABILITY, name: "Недоступность" },
            { key: "integrity", value: row.integrity, color: INTEGRITY, name: "Потеря данных" },
          ];
          return (
            <g key={row.damage_type}>
              <text x={0} y={y + barHeight + 4} className="axis-label">
                {label}
              </text>
              {bars.map((bar, barIndex) => (
                <g key={bar.key}>
                  <rect
                    x={labelWidth}
                    // 2px of surface between the two fills.
                    y={y + barIndex * (barHeight + 2)}
                    width={Math.max(bar.value ? 3 : 0, scale(bar.value ?? 0))}
                    height={barHeight}
                    rx={4}
                    fill={bar.color}
                    onMouseMove={(event) =>
                      show(event, [label, `${bar.name}: ${criticality(bar.value)}`, `Систем: ${row.systems}`])
                    }
                    onMouseLeave={hide}
                  />
                  <text
                    x={labelWidth + Math.max(3, scale(bar.value ?? 0)) + 6}
                    y={y + barIndex * (barHeight + 2) + barHeight - 2}
                    className="value-label"
                  >
                    {criticality(bar.value)}
                  </text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </ChartFrame>
  );
}
