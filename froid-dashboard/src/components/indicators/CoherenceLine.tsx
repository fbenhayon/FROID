import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props { status: string; }

const STATE_HELP: Record<string, string> = {
  "DISSONÂNCIA CRÍTICA":
    "Divergência acentuada e sustentada entre o que a voz e a face expressam e o conteúdo falado. Sinaliza conflito interno intenso — priorize acolher antes de aprofundar.",
  "DISSONÂNCIA":
    "A expressão emocional (voz/face) não acompanha o discurso. Pode indicar conteúdo mascarado ou ambivalência sobre o que está sendo dito.",
  EMBOTAMENTO:
    "Redução global da resposta emocional: voz e face pouco reativas ao conteúdo. Comum em retraimento, defesa ou desconexão afetiva.",
  "SINCRONIA TOTAL":
    "Voz, face e fala alinhadas — o afeto expresso coincide com o conteúdo. Sinal de presença emocional autêntica no momento.",
  "NEUTRO / CALIBRANDO":
    "Sem sinal suficiente ou ainda estabelecendo a linha de base. Aguarde alguns segundos de fala para uma leitura confiável.",
};

export const CoherenceLine: React.FC<Props> = ({ status }) => {
  const meta = useMemo(() => {
    const s = (status || "NEUTRO").toUpperCase();
    if (s.includes("ALTA")) return { color: "#dc2626", pct: 95, label: "DISSONÂNCIA CRÍTICA" };
    if (s.includes("DISSONANCIA")) return { color: "#ef4444", pct: 75, label: "DISSONÂNCIA" };
    if (s.includes("EMBOTAMENTO")) return { color: "#0ea5e9", pct: 55, label: "EMBOTAMENTO" };
    if (s.includes("COERENTE")) return { color: "#22c55e", pct: 100, label: "SINCRONIA TOTAL" };
    return { color: "#94a3b8", pct: 30, label: "NEUTRO / CALIBRANDO" };
  }, [status]);
  return (
    <div className="w-full bg-white rounded-lg border border-slate-100 p-2">
      <div className="flex items-center justify-between mb-1">
        <FroidTooltip
          width={340}
          content={
            <div className="space-y-1">
              <p className="font-bold text-slate-900">Sincronia Voz-Face</p>
              <p>
                Mede o quanto a expressão vocal e a facial acompanham, em tempo
                real, o conteúdo que o paciente verbaliza. Quanto maior a
                coerência, mais o afeto expresso condiz com o que é dito; a
                dissonância aponta possível conteúdo mascarado ou conflito
                interno.
              </p>
              <p className="border-t border-slate-100 pt-1">
                <span className="font-bold" style={{ color: meta.color }}>{meta.label}:</span>{" "}
                {STATE_HELP[meta.label]}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-300 text-[10px] font-bold uppercase tracking-wider text-slate-400">Sincronia Voz-Face</span>
        </FroidTooltip>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600`}>{meta.label}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${meta.pct}%`, backgroundColor: meta.color }} />
      </div>
    </div>
  );
};
