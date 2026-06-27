import React, { useCallback, useEffect, useRef, useState } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { apiUrl } from "../../lib/api";
import {
  loadProfessionalPrompts,
  PROFESSIONAL_PROMPTS_EVENT,
  type ProfessionalPrompt,
} from "../../lib/professional-prompts";

const PRESETS = [
  { text: "Como este paciente se compara a media populacional em Zonas FROID?" },
  { text: "Identificar padroes atipicos comparados a base de dados" },
  { text: "Este paciente esta acima ou abaixo da media em riscos clinicos?" },
  { text: "Progresso nas ultimas sessoes versus populacao" },
  { text: "Velocidade de melhora comparada a casos similares" },
  { text: "Perfil vocal facial similar a quais condicoes na base?" },
  { text: "Casos mais parecidos com este paciente top 5" },
  { text: "Intervencoes mais eficazes para perfis similares" },
  { text: "Predicao de resposta terapeutica baseada em casos analogos" },
  { text: "Alertas: padroes de risco identificados na base populacional" },
  { text: "Explique a leitura clinica das zonas dominantes desta sessao" },
  { text: "O que o IPM atual sugere sobre a energia emocional do paciente?" },
  { text: "Como interpretar as dissonancias faciais-vocais observadas?" },
  { text: "Quais marcadores bioacusticos merecem atencao neste momento?" },
  { text: "Este paciente se compara com a base populacional anonima?" },
  { text: "Quais padroes aparecem em casos similares na base anonima?" },
  { text: "Explique a diferenca entre IPM e IDM para esta sessao" },
  { text: "Que perguntas clinicas podem aprofundar esta leitura?" },
  { text: "Explique o resumo geral da sessao e seus cortes de 10 minutos" },
  { text: "Quais mudancas ocorreram entre baseline e media da sessao?" },
  { text: "Quais dissonancias registradas exigem maior atencao clinica?" },
  { text: "Como interpretar os biomarcadores acusticos desta sessao?" },
];

interface FroidExplicaResponse {
  result_text: string;
  engine_used: string;
  citations?: string[];
  safety_check_passed: boolean;
  intent: "knowledge" | "analytics" | string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  safety?: boolean;
}

interface Props {
  zones: PerceptionZone[];
  ipmScore: number;
  coherenceStatus: string;
  baselineEstablished: boolean;
  sessionId?: string;
  extraContext?: Record<string, unknown>;
}

function compactZone(zone: PerceptionZone) {
  return {
    zone: zone.zone,
    theme: zone.tema,
    deviation_score: Number(zone.deviation_score || 0),
    color: zone.cor_plot,
    facial_dissonance_detected: Boolean(zone.facial_dissonance_detected),
    active_aus: zone.dissonance_details?.active_aus || [],
  };
}

function cleanFroidExplicaText(text: string) {
  return String(text || "")
    .replace(
      /\n?\s*FROID Explica RAG[^\n]*(\n\s*(knowledge|analytics|bloqueado))?(\n\s*fontes:[^\n]*)?/gi,
      "",
    )
    .replace(/\n?\s*fontes:\s*[^\n]+/gi, "")
    .trim();
}

export const AIInsights: React.FC<Props> = ({
  zones,
  ipmScore,
  coherenceStatus,
  baselineEstablished,
  sessionId = "",
  extraContext = {},
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState("");
  const [selectedProfessionalPrompt, setSelectedProfessionalPrompt] = useState("");
  const [professionalPrompts, setProfessionalPrompts] = useState<ProfessionalPrompt[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const refresh = () => setProfessionalPrompts(loadProfessionalPrompts());
    refresh();
    window.addEventListener(PROFESSIONAL_PROMPTS_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(PROFESSIONAL_PROMPTS_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const buildClinicalContext = useCallback(() => {
    const safeZones = Array.isArray(zones) ? zones : [];
    const sorted = [...safeZones].sort(
      (a, b) =>
        Math.abs(b?.deviation_score || 0) - Math.abs(a?.deviation_score || 0),
    );
    const dominant = sorted[0] ? compactZone(sorted[0]) : null;
    const dissonanceCount = safeZones.filter(
      (zone) => zone?.facial_dissonance_detected,
    ).length;

    return {
      session_id: sessionId,
      ipm_score: Number(ipmScore || 0),
      coherence_status: coherenceStatus || "NEUTRO",
      baseline_established: Boolean(baselineEstablished),
      dominant_zone: dominant,
      dissonance_count: dissonanceCount,
      zones: sorted.slice(0, 12).map(compactZone),
      ...extraContext,
    };
  }, [
    zones,
    ipmScore,
    coherenceStatus,
    baselineEstablished,
    sessionId,
    extraContext,
  ]);

  const ask = useCallback(
    async (text: string) => {
      const prompt = text.trim();
      if (!prompt || loading) return;

      setLastError("");
      setInput("");
      setMessages((prev) => [...prev, { role: "user", content: prompt }]);

      setLoading(true);

      try {
        const response = await fetch(apiUrl("/api/froid-explica/query"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query_text: prompt,
            session_id: sessionId,
            context: buildClinicalContext(),
          }),
        });

        const data: FroidExplicaResponse = await response.json();
        if (!response.ok) {
          const detail =
            typeof (data as any)?.detail === "string"
              ? (data as any).detail
              : `HTTP ${response.status}`;
          throw new Error(detail);
        }

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              cleanFroidExplicaText(data.result_text) ||
              "Sem resposta disponivel.",
            safety: data.safety_check_passed,
          },
        ]);
      } catch (error: any) {
        const message = error?.message || "Falha ao consultar FROID Explica.";
        setLastError(message);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "FROID Explica nao conseguiu completar a consulta agora. Verifique o backend e tente novamente.",
            safety: false,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [buildClinicalContext, loading, sessionId],
  );

  return (
    <div className="flex h-full min-h-[200px] flex-col border-t border-slate-200 pt-3 mt-2">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[9px] font-bold text-white">
            FROID
          </span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            FROID Explica
          </h3>
        </div>
        {lastError && (
          <span className="rounded bg-red-50 px-2 py-0.5 text-[9px] font-bold text-red-600">
            {lastError}
          </span>
        )}
      </div>

      <div className="mb-2 min-h-[120px] flex-1 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50/50 p-2 space-y-3">
        {messages.length === 0 && (
          <div className="py-4 text-center">
            <p className="text-[11px] text-slate-400">FROID Explica pronto.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[92%] rounded-xl px-3 py-2 text-[11px] leading-snug whitespace-pre-wrap ${
                message.role === "user"
                  ? "rounded-br-none bg-blue-600 text-white"
                  : "rounded-bl-none border border-slate-200 bg-white text-slate-700 shadow-sm"
              }`}
            >
              <p className="mb-0.5 text-[9px] font-semibold opacity-80">
                {message.role === "user" ? "Voce" : "FROID Explica"}
              </p>
              {message.content}
              {message.role === "assistant" && message.safety === false && (
                <div className="mt-2 text-[9px] font-bold text-red-500">
                  Consulta bloqueada por governanca de dados.
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl rounded-bl-none border border-slate-200 bg-white px-3 py-2 shadow-sm">
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 delay-75" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 delay-150" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="grid gap-2 md:grid-cols-2">
        <div className="relative">
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Prompts FROID Explica
          </label>
          <select
            value={selectedPrompt}
            disabled={loading}
            onChange={(event) => {
              const prompt = event.target.value;
              if (!prompt) return;
              setSelectedPrompt("");
              void ask(prompt);
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <option value="">Selecione um prompt...</option>
            {PRESETS.map((preset, index) => (
              <option key={preset.text} value={preset.text}>
                {index + 1}. {preset.text}
              </option>
            ))}
          </select>
        </div>

        <div className="relative">
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Meus Prompts...
          </label>
          <select
            value={selectedProfessionalPrompt}
            disabled={loading || professionalPrompts.length === 0}
            onChange={(event) => {
              const prompt = event.target.value;
              if (!prompt) return;
              setSelectedProfessionalPrompt("");
              void ask(prompt);
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <option value="">
              {professionalPrompts.length
                ? "Selecione meus prompts..."
                : "Nenhum prompt pessoal cadastrado"}
            </option>
            {professionalPrompts.map((prompt, index) => (
              <option key={prompt.id} value={prompt.text}>
                {index + 1}. {prompt.title || prompt.text}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="mt-2 flex gap-2">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void ask(input);
          }}
          placeholder="Pergunta livre ao FROID Explica..."
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          onClick={() => void ask(input)}
          disabled={!input.trim() || loading}
          className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-40"
        >
          Enviar
        </button>
      </div>
    </div>
  );
};
