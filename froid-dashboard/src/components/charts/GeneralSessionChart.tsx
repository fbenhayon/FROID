import React, { useMemo } from "react";
import { PerceptionZone, HEX_PALETTE } from "../../lib/froid-engine";
import { ZONE_CLINICAL_DESCRIPTIONS } from "../../lib/froid-data";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props { zones: PerceptionZone[]; }

export const GeneralSessionChart: React.FC<Props> = ({ zones }) => {
  const rows = useMemo(() => {
    const arr = Array.isArray(zones) ? zones.filter(z => z && typeof z.zone === "number") : [];
    return arr.sort((a, b) => a.zone - b.zone);
  }, [zones]);

  const maxDev = useMemo(() => Math.max(0.1, ...rows.map(z => Math.abs(z?.deviation_score || 0))), [rows]);

  const h = 380;
  const w = 52;
  const gap = 5;
  const chartH = 260;
  const baseY = 340;
  const zeroY = baseY - chartH / 2;

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Índice Geral da Sessão (Média 10s)</h3>
        <span className="text-[9px] text-slate-400 font-mono">DR = Repouso Inicial</span>
      </div>
      <svg viewBox={`0 0 ${rows.length * (w + gap) + 20} ${h}`} className="w-full h-auto min-w-[380px]">
        <line x1={0} y1={zeroY} x2={rows.length * (w + gap) + 20} y2={zeroY} stroke="#e2e8f0" strokeWidth={1} />
        <line x1={0} y1={baseY - chartH} x2={rows.length * (w + gap) + 20} y2={baseY - chartH} stroke="#f1f5f9" strokeWidth={1} />
        <line x1={0} y1={baseY} x2={rows.length * (w + gap) + 20} y2={baseY} stroke="#f1f5f9" strokeWidth={1} />

        {rows.map((z, i) => {
          const x = 16 + i * (w + gap);
          const dev = typeof z.deviation_score === "number" ? z.deviation_score : 0;
          const barH = Math.min(chartH / 2, (Math.abs(dev) / maxDev) * (chartH / 2));
          const isPos = dev >= 0;
          const y = isPos ? zeroY - barH : zeroY;
          const color = HEX_PALETTE[z.cor_plot] || "#94a3b8";
          const short = (z.tema || "").split(" vs. ")[0];

          return (
            <g key={z.zone}>
              <rect x={x} y={y} width={w} height={Math.max(1, barH)} rx={4} fill={color} opacity={0.85} className="transition-all duration-700" />
              <text x={x + w / 2} y={isPos ? y - 4 : y + barH + 12} textAnchor="middle" className="fill-slate-600 text-[9px] font-mono">
                {dev > 0 ? "+" : ""}{dev.toFixed(1)}
              </text>
              <text x={x + w / 2} y={baseY + 14} textAnchor="start" transform={`rotate(45, ${x + w / 2}, ${baseY + 14})`} className="fill-slate-500 text-[9px] font-medium">
                {z.zone}. {short.slice(0, 12)}
              </text>
              <FroidTooltip content={
                <div className="space-y-1 max-w-[260px]">
                  <p className="font-bold text-slate-900 text-xs">Zona {z.zone} — {z.tema}</p>
                  <p className="text-slate-600 text-[11px] leading-snug">{ZONE_CLINICAL_DESCRIPTIONS[z.zone] || ""}</p>
                </div>
              } width={280}>
                <rect x={x} y={zeroY - chartH / 2} width={w} height={chartH} fill="transparent" className="cursor-help" />
              </FroidTooltip>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
