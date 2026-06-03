import React, { useMemo } from "react";
import { PerceptionZone, HEX_PALETTE } from "../../lib/froid-engine";

interface Props { zones: PerceptionZone[]; }

export const DominantZonesChart: React.FC<Props> = ({ zones }) => {
  const sorted = useMemo(() => {
    const arr = Array.isArray(zones) ? zones : [];
    return arr
      .filter(z => z && Math.abs(z.deviation_score || 0) > 0.3)
      .sort((a, b) => Math.abs(b?.deviation_score || 0) - Math.abs(a?.deviation_score || 0))
      .slice(0, 5);
  }, [zones]);

  const maxScore = useMemo(() => {
    return Math.max(1, ...sorted.map(z => Math.abs(z?.deviation_score || 0)));
  }, [sorted]);

  if (!sorted.length) {
    return (
      <div className="w-full mt-2 border-t border-slate-100 pt-2">
        <h3 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Zonas Dominantes</h3>
        <p className="text-[10px] italic text-slate-400 text-center py-2">Sem ativação significativa</p>
      </div>
    );
  }

  return (
    <div className="w-full mt-2 border-t border-slate-100 pt-2">
      <h3 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Zonas Dominantes</h3>
      <div className="flex flex-col gap-1.5">
        {sorted.map(z => {
          const pct = (Math.abs(z.deviation_score || 0) / maxScore) * 100;
          const hex = HEX_PALETTE[z.cor_plot] || "#94a3b8";
          return (
            <div key={z.zone} className="flex items-center gap-2">
              <span className="w-5 text-right text-[10px] font-bold text-slate-500">{z.zone}</span>
              <div className="flex-1 h-4 rounded-full bg-slate-100 overflow-hidden relative">
                <div className="h-full rounded-full transition-all duration-700 flex items-center justify-end pr-1" style={{ width: `${Math.min(100, pct)}%`, backgroundColor: hex }}>
                  <span className="text-[9px] font-bold text-white drop-shadow" style={{ textShadow: "0 1px 2px rgba(0,0,0,0.6)" }}>
                    {(z.deviation_score || 0).toFixed(1)}
                  </span>
                </div>
              </div>
              <span className="w-24 truncate text-[9px] text-slate-500 leading-none" title={z.tema || ""}>
                {(z.tema || "").split(" vs. ")[0] || "-"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
