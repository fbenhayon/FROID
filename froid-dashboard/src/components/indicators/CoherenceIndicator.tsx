import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

export interface CoherenceIndicatorProps {
  status: string;
}

interface StatusMeta {
  bg: string;
  ring: string;
  text: string;
  icon: string;
  title: string;
  description: string;
  ping: boolean;
  pulse: boolean;
}

export const CoherenceIndicator: React.FC<CoherenceIndicatorProps> = ({ status }) => {
  const normalized = status.toUpperCase().trim();

  const meta = useMemo<StatusMeta>(() => {
    if (normalized.includes("DISSONANCIA ALTA")) {
      return {
        bg: "bg-red-600", ring: "ring-red-300", text: "text-red-800", icon: "🔴",
        title: "Dissonância Crítica",
        description: "ALERTA CLÍNICO MÁXIMO: Contradição severa entre prosódia vocal e microexpressão facial. As AUs ativas contradizem a zona de energia dominante. O paciente está provavelmente suprimindo uma emoção de alta intensidade.",
        ping: true, pulse: true,
      };
    }
    if (normalized.includes("DISSONANCIA")) {
      return {
        bg: "bg-red-500", ring: "ring-red-200", text: "text-red-700", icon: "⚠️",
        title: "Dissonância Detectada",
        description: "Incoerência confirmada: a carga emocional vocal diverge da expressão facial capturada pelo motor FACS. Indica supressão consciente, defesa de ego ou mascaramento social em curso.",
        ping: true, pulse: true,
      };
    }
    if (normalized.includes("COERENTE")) {
      return {
        bg: "bg-emerald-500", ring: "ring-emerald-200", text: "text-emerald-700", icon: "✅",
        title: "Sincronia Total",
        description: "Expressão facial e prosódia vocal alinhadas nos 12 canais de percepção. O paciente está emitindo sinais congruentes — o afeto detectado é genuíno.",
        ping: false, pulse: false,
      };
    }
    if (normalized.includes("EMBOTAMENTO")) {
      return {
        bg: "bg-sky-500", ring: "ring-sky-200", text: "text-sky-700", icon: "🧊",
        title: "Embotamento Afetivo",
        description: "Paralisia ou hipotonia de Unidades de Ação faciais combinada à presença de carga vocal. Sugere desconexão afetiva, shutdown neurológico ou fadiga emocional profunda.",
        ping: false, pulse: false,
      };
    }
    if (normalized.includes("NEUTRO")) {
      return {
        bg: "bg-slate-400", ring: "ring-slate-200", text: "text-slate-700", icon: "⚖️",
        title: "Estado Neutro",
        description: "Ausência de ativação emocional significativa em ambos os canais (voz e face). Estado basal de repouso cognitivo ou processamento não-afetivo.",
        ping: false, pulse: false,
      };
    }
    return {
      bg: "bg-slate-200", ring: "ring-slate-100", text: "text-slate-600", icon: "⏸️",
      title: "Calibrando...",
      description: "Aguardando pacote de fusão multimodal do motor FROID para determinar sincronia voz-face. Certifique-se de que o stream de vídeo e áudio estão ativos.",
      ping: false, pulse: false,
    };
  }, [normalized]);

  return (
    <div className="flex flex-col items-center justify-center w-full p-4">
      <FroidTooltip content={<div className="space-y-2"><p className="font-bold text-slate-900">Sincronia Voz-Face (FROID Fusion)</p><p className="text-slate-600">Métrica crítica que contrasta a emoção detectada na análise acústica das 12 Zonas de Percepção com as Unidades de Ação (AUs) faciais em tempo real.</p><p className="text-slate-600"><strong>Dissonância:</strong> o paciente está mascarando emocionalmente.</p><p className="text-slate-600"><strong>Embotamento:</strong> ausência de ativação facial com carga vocal sugere desconexão afetiva profunda.</p></div>} width={360}>
        <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-6 cursor-help border-b border-dashed border-transparent hover:border-slate-300 transition-colors pb-0.5">
          Sincronia Voz-Face
        </h3>
      </FroidTooltip>

      <div className="relative flex items-center justify-center w-20 h-20 mb-4">
        {meta.ping && <span className={`absolute inset-0 rounded-full ${meta.bg} opacity-30 animate-ping`} />}
        {meta.pulse && <span className={`absolute inset-[-4px] rounded-full ${meta.bg} opacity-20 animate-pulse`} />}
        <div className={`relative z-10 flex items-center justify-center w-16 h-16 rounded-full shadow-xl ${meta.bg} ${meta.ring} ring-4 transition-all duration-500`}>
          <span className="text-2xl drop-shadow-sm select-none">{meta.icon}</span>
        </div>
      </div>

      <div className="text-center mt-2">
        <FroidTooltip content={<div className="space-y-1"><p className="font-bold text-slate-900">{meta.title}</p><p className="text-slate-600 leading-relaxed">{meta.description}</p><p className="text-[10px] font-mono text-slate-400 mt-2">Raw status: {status}</p></div>} width={340}>
          <p className={`text-sm font-bold uppercase tracking-wide ${meta.text} cursor-help`}>{meta.title}</p>
        </FroidTooltip>
        <p className="text-[10px] font-medium text-slate-400 mt-1 max-w-[200px] break-words leading-relaxed">{status}</p>
      </div>
    </div>
  );
};
