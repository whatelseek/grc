import { useState } from "react";

export interface TipState {
  x: number;
  y: number;
  lines: string[];
}

export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null);
  const show = (event: React.MouseEvent, lines: string[]) => {
    const box = (event.currentTarget as SVGElement).ownerSVGElement?.getBoundingClientRect();
    if (!box) return;
    setTip({ x: event.clientX - box.left, y: event.clientY - box.top, lines });
  };
  return { tip, show, hide: () => setTip(null) };
}

export function Tooltip({ tip }: { tip: TipState | null }) {
  if (!tip) return null;
  return (
    <div className="tip" style={{ left: tip.x, top: tip.y }} role="status">
      {tip.lines.map((line, index) => (
        <div key={line} className={index === 0 ? "tip-head" : undefined}>
          {line}
        </div>
      ))}
    </div>
  );
}
