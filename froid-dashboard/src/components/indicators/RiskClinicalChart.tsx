import React, { useMemo } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

const RISK_ITEMS = [
  { key: "depressao", label: "Depressao", desc: "Estado de humor persistentemente baixo, perda de interesse e fadiga cognitiva.", zones: [3, 5, 10] },
  { key: "mania", label: "Mania", desc: "Periodo de humor elevado, expansivo ou irritavel com aumento da atividade psicomotora.", zones: [2, 7, 11] },
  { key: "estresse", label: "Estresse", desc: "Resposta fisiologica e psicologica a demandas que excedem recursos de coping.", zones: [1, 8, 12] },
  { key: "ansiedade", label: "Ansiedade", desc: "Antecipacao apreensiva de ameaca futura com tensao somatica e vigilancia excessiva.", zones: [2, 7, 8] },
  { key: "dissociacao", label: "Dissociacao", desc: "Descontinuidade na integracao normal da consciencia, memoria, identidade ou percepcao.", zones: [4, 9, 12] },
  { key: "trauma", label: "Trauma", desc: "Resposta adaptativa a eventos ameacadores a vida com reexperienciencia e hipervigilancia.", zones: [4, 7, 8] },
];

interface Props { zones: PerceptionZone[]; }

export const RiskClinicalChart: React.FC<Props> = ({ zones }) => {
  const scores = useMemo(() => {
    const arr = Array.isArray(zones) ? zones : [];
    return RISK_ITEMS.map(item => {
      const score = item.zones.reduce((sum, zid) => {
        const z = arr.find(z => z.zone === zid);
        return sum + (Math.abs(z?.deviation_score || 0));
      }, 0) / item.zones.length;
      return { ...item, score: Math.min(100, score * 25) };
    }).sort((a, b) => b.score - a.score);
  }, [zones]);

  const maxScore = Math.max(1, ...scores.map(s => s.score));

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] font-black uppercase tracking-wider text-slate-700">Riscos Clinicos Multimodais</h3>
        <span className="text-[9px] text-slate-400 font-mono">Atualizado a cada 10s</span>
      </div>
      <div className="flex flex-col gap-2.5">
        {scores.map(s => (
          <div key={s.key} className="flex items-center gap-2">
            <FroidTooltip content={
              <div className="max-w-[260px]">
                <p className="font-bold text-slate-900 text-[11px]">{s.label}</p>
                <p className="text-slate-600 text-[10px] mt-1">{s.desc}</p>
                <p className="text-[9px] text-slate-400 mt-1">Zonas correlatas: {s.zones.join(", ")}</p>
              </div>
            } width={280}>
              <span className="text-[10px] font-bold text-slate-700 w-24 truncate cursor-help border-b border-dashed border-slate-300">{s.label}</span>
            </FroidTooltip>
            <div className="flex-1 h-3.5 rounded-full bg-slate-50 overflow-hidden border border-slate-100">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{ width: `${(s.score / maxScore) * 100}%`, backgroundColor: s.score > 70 ? "#dc2626" : s.score > 40 ? "#ea580c" : s.score > 20 ? "#ca8a04" : "#16a34a" }}
              />
            </div>
            <span className="text-[10px] font-mono font-bold text-slate-600 w-8 text-right">{s.score.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};
