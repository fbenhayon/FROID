import React, { useCallback, useEffect, useRef, useState } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { apiUrl } from "../../lib/api";
import {
  loadProfessionalPrompts,
  PROFESSIONAL_PROMPTS_EVENT,
  type ProfessionalPrompt,
} from "../../lib/professional-prompts";

const PRESETS = [
  { text: "Como este paciente se compara a média populacional em Zonas FROID?" },
  { text: "Identificar padrões atipicos comparados a base de dados" },
  { text: "Este paciente está acima ou abaixo da média em riscos clínicos?" },
  { text: "Progresso nas últimas sessões versus populacao" },
  { text: "Velocidade de melhora comparada a casos similares" },
  { text: "Perfil vocal facial similar a quais condições na base?" },
  { text: "Casos mais parecidos com este paciente top 5" },
  { text: "Intervencoes mais eficazes para perfis similares" },
  { text: "Predição de resposta terapêutica baseada em casos analogos" },
  { text: "Alertas: padrões de risco identificados na base populacional" },
  { text: "Explique a leitura clínica das zonas dominantes desta sessão" },
  { text: "O que o IPM atual sugere sobre a energia emocional do paciente?" },
  { text: "Como interpretar as dissonâncias faciais-vocais observadas?" },
  { text: "Quais marcadores bioacústicos merecem atenção neste momento?" },
  { text: "Este paciente se compara com a base populacional anonima?" },
  { text: "Quais padrões aparecem em casos similares na base anonima?" },
  { text: "Explique a diferença entre IPM e IDM para esta sessão" },
  { text: "Que perguntas clínicas podem aprofundar esta leitura?" },
  { text: "Explique o resumo geral da sessão e seus cortes de 10 minutos" },
  { text: "Quais mudancas ocorreram entre baseline e média da sessão?" },
  { text: "Quais dissonâncias registradas exigem maior atenção clínica?" },
  { text: "Como interpretar os biomarcadores acústicos desta sessão?" },
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
  controlsSticky?: boolean;
  rootClassName?: string;
  messagesClassName?: string;
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

const SCIENTIFIC_CITATION_MARKERS = [
  "referência cientifica",
  "referência científica",
  "davis",
  "mermelstein",
  "eyben",
  "wollmer",
  "schuller",
  "opensmile",
  "ekman",
  "friesen",
  "hager",
  "facs",
  "boersma",
  "weenink",
  "praat",
  "kroenke",
  "spitzer",
  "williams",
  "phq-9",
  "phq9",
  "hamilton",
  "ham-d",
  "hamd",
  "young",
  "ymrs",
  "doi",
  "pubmed",
  "journal",
  "artigo",
  "paper",
];

function normalizeCitationText(citation: string) {
  return String(citation || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function isScientificCitation(citation: string) {
  const normalized = normalizeCitationText(citation);
  return SCIENTIFIC_CITATION_MARKERS.some((marker) =>
    normalized.includes(normalizeCitationText(marker)),
  );
}

function appendCitations(text: string, citations?: string[]) {
  const cleanCitations = Array.from(
    new Set(
      (citations || [])
        .map((citation) => String(citation || "").trim())
        .filter((citation) => citation && isScientificCitation(citation)),
    ),
  );
  if (!cleanCitations.length || /refer[eê]ncias utilizadas/i.test(text)) {
    return text;
  }
  return `${text}\n\nReferências utilizadas:\n${cleanCitations
    .slice(0, 6)
    .map((citation) => `- ${citation}`)
    .join("\n")}`;
}

export const AIInsights: React.FC<Props> = ({
  zones,
  ipmScore,
  coherenceStatus,
  baselineEstablished,
  sessionId = "",
  extraContext = {},
  controlsSticky = false,
  rootClassName = "",
  messagesClassName = "",
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
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(apiUrl("/api/froid-explica/query"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            query_text: prompt,
            session_id: sessionId,
            conversation_history: messages.slice(-6).map((message) => ({
              role: message.role,
              content: message.content,
            })),
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
            content: appendCitations(
              cleanFroidExplicaText(data.result_text) ||
                "Sem resposta disponível.",
              data.citations,
            ),
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
              "FROID Explica não conseguiu completar a consulta agora. Verifique o backend e tente novamente.",
            safety: false,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [buildClinicalContext, loading, messages, sessionId],
  );

  return (
    <div className={`flex h-full min-h-[200px] flex-col border-t border-slate-700 pt-3 mt-2 text-slate-100 ${rootClassName}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[9px] font-bold text-white">
            FROID
          </span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            FROID Explica
          </h3>
        </div>
        {lastError && (
          <span className="rounded bg-red-950/60 px-2 py-0.5 text-[9px] font-bold text-red-200">
            {lastError}
          </span>
        )}
      </div>

      <div className={`mb-2 min-h-[120px] flex-1 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-2 space-y-3 ${messagesClassName}`}>
        {messages.length === 0 && (
          <div className="py-4 text-center">
            <p className="text-[11px] text-slate-500">FROID Explica pronto.</p>
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
                  : "rounded-bl-none border border-slate-700 bg-slate-900 text-slate-200 shadow-sm"
              }`}
            >
              <p className="mb-0.5 text-[9px] font-semibold opacity-80">
                {message.role === "user" ? "Você" : "FROID Explica"}
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
            <div className="rounded-xl rounded-bl-none border border-slate-700 bg-slate-900 px-3 py-2 shadow-sm">
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

      <div className={controlsSticky ? "sticky bottom-0 z-10 border-t border-slate-700 bg-slate-900/95 pt-2 backdrop-blur" : ""}>
        <div className="grid gap-2 md:grid-cols-2">
          <div className="relative">
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-400">
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
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 shadow-sm outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
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
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-400">
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
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 shadow-sm outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
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
            className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          <button
            onClick={() => void ask(input)}
            disabled={!input.trim() || loading}
            className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
          >
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
};
