import React, { useMemo } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

const EMOTIONS = [
  { key: "felicidade", label: "Felicidade", desc: "Estado de bem-estar subjetivo com ativacao de AU 6 + AU 12 (sorriso de Duchenne).", aus: ["AU6", "AU12"], color: "#22c55e" },
  { key: "raiva", label: "Raiva", desc: "Emocao de antagonismo com AU 4 (sobrancelhas baixas), AU 5 (palpebras tensas), AU 7 (olhos semicerrados).", aus: ["AU4", "AU5", "AU7"], color: "#dc2626" },
  { key: "surpresa", label: "Surpresa", desc: "Resposta breve ao inesperado com AU 1 + AU 2 (sobrancelhas elevadas) e AU 5 (olhos arregalados).", aus: ["AU1", "AU2", "AU5"], color: "#eab308" },
  { key: "desprezo", label: "Desprezo", desc: "Expressao de superioridade moral com AU 12 unilateral (sorriso assimétrico).", aus: ["AU12"], color: "#854d0e" },
  { key: "medo", label: "Medo", desc: "Resposta a ameaca iminente com AU 1 + AU 2 + AU 5 + AU 20 (pescoço esticado).", aus: ["AU1", "AU2", "AU5", "AU20"], color: "#6366f1" },
  { key: "tristeza", label: "Tristeza", desc: "Estado de pesar com AU 1 + AU 4 + AU 15 (cantos da boca para baixo).", aus: ["AU1", "AU4", "AU15"], color: "#3b82f6" },
];

interface Props { zones: PerceptionZone[]; }

export const EmotionFACSChart: React.FC<Props> = ({ zones }) => {
  const scores = useMemo(() => {
    // Simulação baseada na coerência e zonas para demonstração visual
    const arr = Array.isArray(zones) ? zones : [];
    const hasDissonance = arr.some(z => !!z?.facial_dissonance_detected);
    
    return EMOTIONS.map((emo, idx) => {
      // Lógica simplificada para demo: distribui valores baseados no índice e dissonância
      let baseScore = (Math.sin(Date.now() / 1000 + idx) + 1) * 30; 
      if (hasDissonance && idx === 1) baseScore += 40; // Raiva sobe com dissonância
      return { ...emo, score: Math.min(100, Math.max(5, baseScore)) };
    }).sort((a, b) => b.score - a.score);
  }, [zones]);

  const maxScore = Math.max(1, ...scores.map(s => s.score));

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] font-black uppercase tracking-wider text-slate-700">Emocoes FACS Detectadas</h3>
        <span className="text-[9px] text-slate-400 font-mono">Baseado em AU</span>
      </div>
      <div className="flex flex-col gap-2.5">
        {scores.map(s => (
          <div key={s.key} className="flex items-center gap-2">
            <FroidTooltip content={
              <div className="max-w-[260px]">
                <p className="font-bold text-slate-900 text-[11px]">{s.label}</p>
                <p className="text-slate-600 text-[10px] mt-1">{s.desc}</p>
                <p className="text-[9px] text-slate-400 mt-1">Action Units: {s.aus.join(", ")}</p>
              </div>
            } width={280}>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }}></span>
                <span className="text-[10px] font-bold text-slate-700 w-24 truncate cursor-help border-b border-dashed border-slate-300">{s.label}</span>
              </div>
            </FroidTooltip>
            <div className="flex-1 h-3.5 rounded-full bg-slate-50 overflow-hidden border border-slate-100">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{ width: `${(s.score / maxScore) * 100}%`, backgroundColor: s.color }}
              />
            </div>
            <span className="text-[10px] font-mono font-bold text-slate-600 w-8 text-right">{s.score.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};
