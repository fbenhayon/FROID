import React, { useMemo } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props { zones: PerceptionZone[]; ipmScore: number; coherenceStatus: string; }

export const RiskChart: React.FC<Props> = ({ zones, ipmScore, coherenceStatus }) => {
  const risk = useMemo(() => {
    const arr = Array.isArray(zones) ? zones : [];
    const hasCritical = arr.some(z => (z?.deviation_score || 0) > 3.0);
    const hasDissonance = arr.some(z => !!z?.facial_dissonance_detected);
    const hasEmbotamento = coherenceStatus === "EMBOTAMENTO";

    if (hasCritical && hasDissonance) return { level: "CRÍTICO", color: "#7f1d1d", bg: "bg-red-900", text: "text-red-100", pct: 100, desc: "Mascaramento em colapso + pico extremo." };
    if (hasCritical) return { level: "ALTO", color: "#dc2626", bg: "bg-red-600", text: "text-white", pct: 85, desc: "Desvio extremo em zona primária." };
    if (hasDissonance) return { level: "ELEVADO", color: "#ea580c", bg: "bg-orange-600", text: "text-white", pct: 70, desc: "Dissonância facial-vocal confirmada." };
    if (hasEmbotamento) return { level: "MODERADO", color: "#ca8a04", bg: "bg-yellow-600", text: "text-white", pct: 50, desc: "Embotamento afetivo detectado." };
    if (ipmScore > 70) return { level: "ATENÇÃO", color: "#2563eb", bg: "bg-blue-600", text: "text-white", pct: 35, desc: "IPM acima do percentil 85." };
    return { level: "NORMAL", color: "#16a34a", bg: "bg-green-600", text: "text-white", pct: 15, desc: "Perfil dentro da faixa terapêutica." };
  }, [zones, ipmScore, coherenceStatus]);

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Risco Clínico</span>
        <FroidTooltip content={<div className="max-w-[200px]"><p className="font-bold">Risco FROID</p><p className="text-[10px]">Calculado com base em picos de IDM, dissonâncias e embotamento.</p></div>} width={220}>
          <span className="cursor-help text-[10px] text-slate-400 border-b border-dashed border-slate-300">?</span>
        </FroidTooltip>
      </div>
      <div className="flex items-center gap-3 mb-1">
        <div className={`px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wide ${risk.bg} ${risk.text}`}>{risk.level}</div>
        <div className="flex-1 h-4 rounded-full bg-slate-100 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${risk.pct}%`, backgroundColor: risk.color }} />
        </div>
        <span className="text-[11px] font-bold text-slate-600 w-10 text-right">{risk.pct}%</span>
      </div>
      <p className="text-[10px] text-slate-500 leading-tight mt-1">{risk.desc}</p>
    </div>
  );
};
