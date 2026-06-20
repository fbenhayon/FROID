import React, { useCallback, useEffect, useRef, useState } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { apiUrl } from "../../lib/api";
import { FroidTooltip } from "../ui/FroidTooltip";

const PRESETS = [
  {
    text: "Explique a leitura clinica das zonas dominantes desta sessao",
    desc: "Usa o IPM, coerencia, zonas e dissonancias atuais para gerar uma leitura contextualizada.",
  },
  {
    text: "O que o IPM atual sugere sobre a energia emocional do paciente?",
    desc: "Diferencia intensidade global de direcao do desequilibrio e evita conclusoes diagnosticas.",
  },
  {
    text: "Como interpretar as dissonancias faciais-vocais observadas?",
    desc: "Relaciona dissonancia, FACS, voz e possiveis limites de interpretacao.",
  },
  {
    text: "Quais marcadores bioacusticos merecem atencao neste momento?",
    desc: "Foca em MFCC7, MFCC9, F0, jitter, shimmer, pausas e sub-harmonicos quando disponiveis.",
  },
  {
    text: "Este paciente se compara como a base populacional anonima?",
    desc: "Consulta o Data Mart anonimo se estiver disponivel e aplica k-anonimato antes do benchmark.",
  },
  {
    text: "Quais padroes aparecem em casos similares na base anonima?",
    desc: "Executa consulta populacional agregada, bloqueando coortes pequenas por governanca LGPD.",
  },
  {
    text: "Explique a diferenca entre IPM e IDM para esta sessao",
    desc: "Clarifica intensidade global, direcao do desequilibrio e limites de inferencia.",
  },
  {
    text: "Que perguntas clinicas podem aprofundar esta leitura?",
    desc: "Sugere caminhos de exploracao ao profissional sem substituir julgamento clinico.",
  },
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
  engine?: string;
  citations?: string[];
  safety?: boolean;
  intent?: string;
}

interface Props {
  zones: PerceptionZone[];
  ipmScore: number;
  coherenceStatus: string;
  baselineEstablished: boolean;
  sessionId?: string;
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

export const AIInsights: React.FC<Props> = ({
  zones,
  ipmScore,
  coherenceStatus,
  baselineEstablished,
  sessionId = "",
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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
    };
  }, [zones, ipmScore, coherenceStatus, baselineEstablished, sessionId]);

  const ask = useCallback(
    async (text: string) => {
      const prompt = text.trim();
      if (!prompt || loading) return;

      setLastError("");
      setMessages((prev) => [...prev, { role: "user", content: prompt }]);
      setInput("");
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
            content: data.result_text || "Sem resposta disponivel.",
            engine: data.engine_used,
            citations: data.citations || [],
            safety: data.safety_check_passed,
            intent: data.intent,
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
            engine: "offline",
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
              {message.role === "assistant" && (
                <div className="mt-2 flex flex-wrap gap-1 text-[9px] text-slate-400">
                  {message.engine && <span>{message.engine}</span>}
                  {message.intent && <span>{message.intent}</span>}
                  {message.safety === false && (
                    <span className="font-bold text-red-500">bloqueado</span>
                  )}
                  {message.citations && message.citations.length > 0 && (
                    <span>fontes: {message.citations.join(", ")}</span>
                  )}
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

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void ask(input);
          }}
          placeholder="Pergunte ao FROID Explica..."
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

      <div className="mt-2 flex flex-wrap gap-1">
        {PRESETS.map((preset, index) => (
          <FroidTooltip
            key={preset.text}
            width={300}
            content={
              <div className="max-w-[280px]">
                <p className="text-[11px] font-bold text-slate-900">
                  {preset.text}
                </p>
                <p className="mt-1 text-[10px] text-slate-600">
                  {preset.desc}
                </p>
              </div>
            }
          >
            <button
              onClick={() => void ask(preset.text)}
              className="max-w-[150px] truncate rounded border border-transparent bg-slate-100 px-2 py-1 text-left text-[9px] text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
            >
              {index + 1}.{" "}
              {preset.text.length > 26
                ? `${preset.text.slice(0, 26)}...`
                : preset.text}
            </button>
          </FroidTooltip>
        ))}
      </div>
    </div>
  );
};
