import React, { useMemo } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props { zones: PerceptionZone[]; }

export const SubharmonicChart: React.FC<Props> = ({ zones }) => {
  const offsetZones = useMemo(() => {
    const arr = Array.isArray(zones) ? zones.filter(z => z && typeof z.zone === "number") : [];
    return arr
      .filter(z => z.cor_plot === "BRANCO" || (z.deviation_score || 0) < -0.3)
      .sort((a, b) => (a.deviation_score || 0) - (b.deviation_score || 0))
      .slice(0, 6);
  }, [zones]);

  const totalOffset = offsetZones.length;

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Compensação / Sub-harmônicos</span>
        <FroidTooltip content={<div className="max-w-[200px]"><p className="font-bold">Zonas de Compensação</p><p className="text-[10px]">Zonas em BRANCO ou com desvio negativo indicam equilíbrio energético.</p></div>} width={220}>
          <span className="cursor-help text-[10px] text-slate-400 border-b border-dashed border-slate-300">?</span>
        </FroidTooltip>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${totalOffset > 3 ? "bg-slate-800 text-white" : "bg-slate-200 text-slate-700"}`}>
          {totalOffset}
        </span>
      </div>

      {totalOffset === 0 ? (
        <p className="text-[10px] text-slate-400 italic">Nenhuma compensação ativa.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {offsetZones.map(z => {
            const dev = z.deviation_score || 0;
            const barW = Math.min(100, Math.abs(dev) * 25);
            const short = (z.tema || "").split(" vs. ")[0];
            return (
              <div key={z.zone} className="flex items-center gap-2">
                <span className="w-5 text-right text-[10px] font-black text-slate-600">{z.zone}</span>
                <div className="flex-1 h-2.5 rounded-full bg-slate-50 overflow-hidden border border-slate-100">
                  <div className="h-full rounded-full bg-slate-400 transition-all duration-700" style={{ width: `${barW}%` }} />
                </div>
                <span className="text-[10px] font-mono text-slate-500 w-10 text-right">{dev.toFixed(2)}</span>
                <span className="text-[9px] text-slate-400 truncate w-20 text-left">{short.slice(0, 15)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
