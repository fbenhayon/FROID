import React, { useState, useRef, useEffect, useCallback } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

const PRESETS = [
  {
    text: "Como este paciente se compara à média populacional em Zonas FROID?",
    desc: "Análise estatística cruzada: percentil de ativação subconsciente vs base anônima de 12.000+ perfis.",
  },
  {
    text: "Identificar padrões atípicos comparados à base de dados",
    desc: "Detecção de outliers multimodais: dissonâncias faciais-vocais não presentes em 92% da população clínica.",
  },
  {
    text: "Este paciente está acima ou abaixo da média em riscos clínicos?",
    desc: "Cálculo de risco psicossomático baseado em IPM, coerência e picos de zonas críticas (7, 8, 12).",
  },
  {
    text: "Progresso nas últimas X semanas vs população",
    desc: "Comparativo longitudinal: velocidade de reestruturação do baseline entre sessões consecutivas.",
  },
  {
    text: "Velocidade de melhora comparada a casos similares",
    desc: "Benchmarking terapêutico: taxa de variação do IPM em janelas de 60s vs casos com perfil congruente.",
  },
  {
    text: "Perfil vocal/facial similar a quais condições na base?",
    desc: "Correlação diagnóstica probabilística com padrões de supressão, evitação, trauma ou burnout.",
  },
  {
    text: "Casos mais parecidos com este paciente (top 5)",
    desc: "Matching por similaridade de vetor de 12 zonas: recupera IDs anônimos com ≥75% de correspondência.",
  },
  {
    text: "Intervenções mais eficazes para perfis similares",
    desc: "Recomendação baseada em evidência: protocolos TCC, DBT, EMDR ou análise focalizada com maior taxa de resposta.",
  },
  {
    text: "Predição de resposta terapêutica baseada em casos análogos",
    desc: "Modelagem preditiva: probabilidade de resposta positiva em 8 semanas com intervalo de confiança.",
  },
  {
    text: "Alertas: padrões de risco identificados na base populacional",
    desc: "Flagging automático: múltiplas dissonâncias simultâneas, embotamento agudo ou picos de Zona 12 >4.0.",
  },
  {
    text: "Arquitetura FROID: Motor Bioacústico e Análise Espectral",
    desc: "Explique como voz, MFCC7/MFCC9 e sub-harmônicos compõem a análise multimodal do sistema.",
  },
  {
    text: "Arquitetura Analítica do Coeficiente MFCC9",
    desc: "Descreva o papel clínico do MFCC9 na diferenciação entre ansiedade somática e depressão.",
  },
  {
    text: "Mapeamento Anatômico das Unidades de Ação Faciais",
    desc: "Relacione AUs faciais, dissonância e zonas FROID para a interpretação clínica.",
  },
  {
    text: "Qual é a diferença técnica entre Jitter e Shimmer?",
    desc: "Explique em linguagem clínica e técnica a relação desses marcadores com a voz.",
  },
  {
    text: "Como o FROID mede retardo psicomotor via áudio?",
    desc: "Associe taxa de elocução, energia acústica e sinais de depressão na sessão.",
  },
];

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  zones: import("../../lib/froid-engine").PerceptionZone[];
  ipmScore: number;
  coherenceStatus: string;
  baselineEstablished: boolean;
}

export const AIInsights: React.FC<Props> = ({
  zones,
  ipmScore,
  coherenceStatus,
  baselineEstablished,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const fetchKnowledge = useCallback(async (query: string): Promise<string> => {
    try {
      const apiUrl =
        ((import.meta as any).env?.VITE_API_URL ||
          "https://froid.com.br/api" ||
          "http://localhost:8000") +
        "/api/knowledge?q=" +
        encodeURIComponent(query);
      const res = await fetch(apiUrl);
      if (!res.ok) return "";
      const data = await res.json();
      return (data.results || [])
        .map((r: any) => `[${r.source}] ${r.content}`)
        .join("\n");
    } catch {
      return "";
    }
  }, []);

  const callAI = useCallback(
    async (promptText: string): Promise<string> => {
      const safeZones = Array.isArray(zones) ? zones : [];
      const sorted = [...safeZones].sort(
        (a, b) =>
          Math.abs(b?.deviation_score || 0) - Math.abs(a?.deviation_score || 0),
      );
      const top = sorted[0];
      const dissonant = safeZones.filter(
        (z) => !!z?.facial_dissonance_detected,
      ).length;

      const knowledge = await fetchKnowledge(promptText);
      const systemMsg = `Você é FROID-IA, assistente clínico especializado em bioacústica facial-vocal.
Dados atuais: IPM=${ipmScore.toFixed(1)}, Coerência=${coherenceStatus}, Baseline=${baselineEstablished ? "OK" : "Calibrando"}, Zona dominante=${top ? `${top.zone} (${top.tema})` : "--"}, Dissonâncias=${dissonant}.
Base de conhecimento FROID/NotebookLM:
${knowledge || "Base de conhecimento local indisponível."}
Responda em português de forma objetiva e clinicamente útil.`;

      const apiUrl =
        ((import.meta as any).env?.VITE_API_URL ||
          "https://froid.com.br/api" ||
          "http://localhost:8000") + "/api/insights";
      try {
        const res = await fetch(apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [
              { role: "system", content: systemMsg },
              { role: "user", content: promptText },
            ],
            model: "gpt-4o-mini",
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error)
          throw new Error(
            typeof data.error === "string"
              ? data.error
              : JSON.stringify(data.error),
          );
        return data.choices?.[0]?.message?.content || "Sem resposta.";
      } catch (e: any) {
        setLastError(`Falha: ${e.message}`);
        return `[FROID-IA Local] "${promptText.slice(0, 30)}..." → Zona ${top?.zone || "--"}, IPM ${ipmScore.toFixed(1)}, Coerência: ${coherenceStatus}. ${dissonant > 0 ? `${dissonant} dissonância(s).` : "Sinais congruentes."}`;
      }
    },
    [zones, ipmScore, coherenceStatus, baselineEstablished, fetchKnowledge],
  );

  const ask = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;
      setLastError("");
      setMessages((prev) => [...prev, { role: "user", content: text.trim() }]);
      setInput("");
      setLoading(true);
      const resp = await callAI(text.trim());
      setMessages((prev) => [...prev, { role: "assistant", content: resp }]);
      setLoading(false);
    },
    [loading, callAI],
  );

  return (
    <div className="flex flex-col h-full border-t border-slate-200 pt-3 mt-2 min-h-[200px]">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">🛡️</span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Insights IA
          </h3>
        </div>
        {lastError && (
          <span className="text-[9px] text-red-600 bg-red-50 px-2 py-0.5 rounded font-bold">
            {lastError}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto space-y-3 bg-slate-50/50 rounded-lg border border-slate-100 p-2 mb-2 min-h-[120px]">
        {messages.length === 0 && (
          <div className="text-center py-4">
            <p className="text-[11px] text-slate-400">
              Selecione um prompt nativo ou pergunte à IA.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[92%] rounded-xl px-3 py-2 text-[11px] leading-snug whitespace-pre-wrap ${m.role === "user" ? "bg-blue-600 text-white rounded-br-none" : "bg-white border border-slate-200 text-slate-700 rounded-bl-none shadow-sm"}`}
            >
              <p className="font-semibold text-[9px] opacity-80 mb-0.5">
                {m.role === "user" ? "Você" : "FROID-IA"}
              </p>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-xl rounded-bl-none px-3 py-2 shadow-sm">
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce" />
                <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce delay-75" />
                <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce delay-150" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          placeholder="Pergunte à IA..."
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          onClick={() => ask(input)}
          disabled={!input.trim() || loading}
          className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-40"
        >
          ➤
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {PRESETS.map((p, i) => (
          <FroidTooltip
            key={i}
            content={
              <div className="max-w-[280px]">
                <p className="font-bold text-slate-900 text-[11px]">{p.text}</p>
                <p className="text-slate-600 text-[10px] mt-1">{p.desc}</p>
              </div>
            }
            width={300}
          >
            <button
              onClick={() => ask(p.text)}
              className="text-[9px] bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-700 rounded px-2 py-1 border border-transparent hover:border-blue-200 transition-colors max-w-[150px] truncate text-left"
            >
              {i + 1}. {p.text.length > 26 ? p.text.slice(0, 26) + "…" : p.text}
            </button>
          </FroidTooltip>
        ))}
      </div>
    </div>
  );
};
