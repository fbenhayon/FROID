import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  data: number[];
  current: number;
  baseline?: number;
}

export const IPMLineChart: React.FC<Props> = ({ data, current, baseline }) => {
  const viewW = 420;
  const viewH = 240; // DOBRADO
  const padLeft = 52;
  const padRight = 20;
  const padTop = 28;
  const padBot = 36;

  const { pathD, areaD, pts } = useMemo(() => {
    const values = Array.isArray(data) ? data.filter(v => typeof v === "number" && !isNaN(v)) : [];
    const n = values.length;
    const base = typeof baseline === "number" && !isNaN(baseline) ? baseline : 50;
    if (n === 0) return { pathD: "", areaD: "", pts: [] as number[][], zeroY: viewH / 2 };

    const w = viewW - padLeft - padRight;
    const h = viewH - padTop - padBot;
    const step = n > 1 ? w / (n - 1) : 0;

    const relValues = values.map(v => Math.max(-12, Math.min(12, v - base)));
    const scaleY = h / 24;

    const points = relValues.map((v, i) => [
      padLeft + i * step,
      (viewH / 2) - (v * scaleY),
    ]);

    let d = `M ${points[0][0]},${points[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const p0 = points[Math.max(0, i - 1)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(n - 1, i + 2)];
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
    }
    const last = points[n - 1];
    return { pathD: d, areaD: `${d} L ${last[0]},${viewH - padBot} L ${points[0][0]},${viewH - padBot} Z`, pts: points, zeroY: viewH / 2 };
  }, [data, baseline]);

  const currentRel = typeof baseline === "number" && !isNaN(baseline) ? current - baseline : 0;
  const relColor = currentRel > 8 ? "#dc2626" : currentRel > 5 ? "#ea580c" : currentRel > 2 ? "#ca8a04" : currentRel < -5 ? "#2563eb" : "#16a34a";

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm px-3 py-4">
      <div className="flex items-center justify-between px-1 mb-2">
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-black text-slate-800 tracking-tight">{currentRel > 0 ? "+" : ""}{currentRel.toFixed(1)}</span>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Δ IPM</span>
          <span className="text-[10px] text-slate-400 font-mono">(baseline: {typeof baseline === "number" ? baseline.toFixed(1) : "--"})</span>
        </div>
        <FroidTooltip content={
          <div className="max-w-[280px]">
            <p className="font-bold">Variação Relativa do IPM</p>
            <p className="text-[11px] mt-1">Linha central = baseline dos 60s iniciais (zero relativo).</p>
            <p className="text-[11px]">Escala: ±10 unidades de desvio. Acima de +5: ativação emocional. Acima de +8: alerta clínico.</p>
          </div>
        } width={300}>
          <span className="cursor-help text-[10px] text-slate-400 border-b border-dashed border-slate-300">?</span>
        </FroidTooltip>
      </div>

      <svg viewBox={`0 0 ${viewW} ${viewH}`} className="w-full h-56">
        <defs>
          <linearGradient id="ipmRelGradV9" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* Grid horizontal com zero no centro */}
        {[-10, -5, 0, 5, 10].map(tick => {
          const relY = (viewH / 2) - (tick * ((viewH - padTop - padBot) / 24));
          return (
            <g key={`y-${tick}`}>
              <line x1={padLeft} y1={relY} x2={viewW - padRight} y2={relY} stroke={tick === 0 ? "#64748b" : "#e2e8f0"} strokeWidth={tick === 0 ? 1.5 : 1} />
              <text x={padLeft - 10} y={relY + 4} textAnchor="end" className={`text-[10px] font-mono ${tick === 0 ? "fill-slate-700 font-bold" : "fill-slate-400"}`}>
                {tick > 0 ? "+" : ""}{tick}
              </text>
            </g>
          );
        })}

        <text x={10} y={viewH / 2} textAnchor="middle" transform={`rotate(-90, 10, ${viewH / 2})`} className="fill-slate-400 text-[10px] font-bold uppercase">Δ IPM</text>

        <line x1={padLeft} y1={viewH - padBot} x2={viewW - padRight} y2={viewH - padBot} stroke="#cbd5e1" strokeWidth={1.5} />
        <line x1={padLeft} y1={padTop} x2={padLeft} y2={viewH - padBot} stroke="#cbd5e1" strokeWidth={1.5} />

        {[0, 1, 2, 3].map(i => {
          const x = padLeft + (i / 3) * (viewW - padLeft - padRight);
          return <text key={`x-${i}`} x={x} y={viewH - 12} textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">-{Math.round((1 - i / 3) * 60)}s</text>;
        })}
        <text x={(viewW + padLeft) / 2} y={viewH - 2} textAnchor="middle" className="fill-slate-400 text-[10px] font-bold uppercase">Tempo</text>

        {pts.length === 0 && <text x={viewW / 2} y={viewH / 2} textAnchor="middle" className="fill-slate-400 text-[11px]">Aguardando série temporal...</text>}
        {pts.length > 0 && (
          <>
            {areaD && <path d={areaD} fill="url(#ipmRelGradV9)" stroke="none" />}
            {pathD && <path d={pathD} fill="none" stroke={relColor} strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" />}
            {pts.map((p, i) => <circle key={`pt-${i}`} cx={p[0]} cy={p[1]} r={3} fill={relColor} opacity={0.7} />)}
            <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={6} fill={relColor} stroke="white" strokeWidth={3} />
          </>
        )}
      </svg>
    </div>
  );
};
