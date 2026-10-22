import { hours } from "../../lib/format";
import ChartFrame from "./ChartFrame";
import { Tooltip, useTooltip } from "./Tooltip";

const REQUIRED = "#0f3c64";
const CURRENT = "#7391d7";
const GAP = "#9a390d";

export interface RecoveryRow {
  survey_id: string;
  system_name: string;
  client_name: string;
  required_rto: number | null;
  current_rto: number | null;
  current_rto_beyond_scale: boolean;
  rto_gap: number | null;
  required_rpo: number | null;
  current_rpo: number | null;
  current_rpo_beyond_scale: boolean;
  rpo_gap: number | null;
}

interface Props {
  rows: RecoveryRow[];
  metric: "rto" | "rpo";
}

/** Before → after per item, so a dumbbell: one hue in two shades, with the
 *  shortfall drawn in the status colour. The axis is logarithmic because the
 *  periods the questionnaire asks about span minutes to weeks. */
export default function GapDumbbell({ rows, metric }: Props) {
  const { tip, show, hide } = useTooltip();
  const required = (row: RecoveryRow) => (metric === "rto" ? row.required_rto : row.required_rpo);
  const current = (row: RecoveryRow) => (metric === "rto" ? row.current_rto : row.current_rpo);
  const beyond = (row: RecoveryRow) =>
    metric === "rto" ? row.current_rto_beyond_scale : row.current_rpo_beyond_scale;
  const gap = (row: RecoveryRow) => (metric === "rto" ? row.rto_gap : row.rpo_gap);

  const plotted = rows
    .filter((row) => required(row) !== null && (current(row) !== null || beyond(row)))
    .sort((a, b) => (gap(b) ?? 0) - (gap(a) ?? 0))
    .slice(0, 12);

  const labelWidth = 170;
  const width = 1060;
  const rowHeight = 28;
  const height = plotted.length * rowHeight + 26;
  const axisRight = width - 24;

  // Minutes to a month on a log scale; 2 minutes is the shortest period asked about.
  const min = 1 / 30;
  const max = 720;
  const scale = (value: number) => {
    const clamped = Math.min(max, Math.max(min, value));
    const ratio = Math.log(clamped / min) / Math.log(max / min);
    return labelWidth + ratio * (axisRight - labelWidth);
  };
  const ticks = [1 / 30, 1, 8, 24, 168, 720];
  // The scale's last real step: anything worse is marked rather than placed.
  const BEYOND_AT = 168;

  return (
    <ChartFrame
      title={metric === "rto" ? "Разрыв по времени восстановления (RTO)" : "Разрыв по потере данных (RPO)"}
      caption={
        metric === "rto"
          ? "Расчётный объектив против фактического восстановления сейчас. Красным — отставание."
          : "Расчётный объектив против текущих настроек бэкапа. Красным — отставание."
      }
      legend={[
        { label: "Нужно по расчёту", color: REQUIRED },
        { label: "Фактически сейчас", color: CURRENT },
        { label: "Отставание", color: GAP },
      ]}
      empty={plotted.length === 0}
      emptyNote="Нужны ответы на вопросы 79–80 (текущие возможности) и рассчитанный объектив."
      table={
        <table className="table small">
          <thead>
            <tr>
              <th>Система</th>
              <th>Нужно</th>
              <th>Сейчас</th>
              <th>Отставание</th>
            </tr>
          </thead>
          <tbody>
            {plotted.map((row) => (
              <tr key={row.survey_id}>
                <th scope="row">{row.system_name}</th>
                <td>{hours(required(row))}</td>
                <td>{beyond(row) ? "вне шкалы" : hours(current(row))}</td>
                <td>
                  {(gap(row) ?? 0) > 0
                    ? `${beyond(row) ? "не менее " : ""}${hours(gap(row))}`
                    : "нет"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="svg" role="img" aria-label="Разрыв восстановления">
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={scale(tick)} y1={0} x2={scale(tick)} y2={height - 20} className="grid-line" />
            <text x={scale(tick)} y={height - 6} className="axis-label tick">
              {hours(tick)}
            </text>
          </g>
        ))}

        {plotted.map((row, index) => {
          const y = index * rowHeight + 14;
          const need = scale(required(row)!);
          const now = scale(beyond(row) ? BEYOND_AT : current(row)!);
          const behind = (gap(row) ?? 0) > 0;
          return (
            <g
              key={row.survey_id}
              onMouseMove={(event) =>
                show(event, [
                  row.system_name,
                  `Нужно: ${hours(required(row))}`,
                  `Сейчас: ${beyond(row) ? "вне шкалы" : hours(current(row))}`,
                  behind
                    ? `Отставание: ${beyond(row) ? "не менее " : ""}${hours(gap(row))}`
                    : "Объектив выполняется",
                ])
              }
              onMouseLeave={hide}
            >
              <text x={0} y={y + 4} className="axis-label">
                {row.system_name.length > 24 ? `${row.system_name.slice(0, 23)}…` : row.system_name}
              </text>
              <line
                x1={Math.min(need, now)}
                y1={y}
                x2={Math.max(need, now)}
                y2={y}
                stroke={behind ? GAP : "#d0d0d0"}
                strokeWidth={2}
                strokeLinecap="round"
              />
              <circle cx={need} cy={y} r={5} fill={REQUIRED} stroke="#fff" strokeWidth={2} />
              {beyond(row) ? (
                <>
                  <circle cx={now} cy={y} r={5} fill="#fff" stroke={CURRENT} strokeWidth={2} />
                  <text x={now + 10} y={y + 4} className="value-label">
                    дольше шкалы
                  </text>
                </>
              ) : (
                <circle cx={now} cy={y} r={5} fill={CURRENT} stroke="#fff" strokeWidth={2} />
              )}
              {/* A generous, invisible hit area: the marks themselves are small. */}
              <rect x={0} y={y - 12} width={width} height={24} fill="transparent" />
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </ChartFrame>
  );
}
