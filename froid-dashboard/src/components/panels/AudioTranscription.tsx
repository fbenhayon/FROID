import React from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

type FroidAudioMetaWindow = Window &
  typeof globalThis & {
    __froidAudioMeta?: Record<string, unknown>;
  };

interface ConversationSummary {
  id: string;
  startMinute: number;
  endMinute: number;
  theme: string;
  summary: string;
  trigger?: "automatico_10min" | "manual" | "final";
}

interface Props {
  audioMeta?: Record<string, unknown>;
  conversationSummaries?: ConversationSummary[];
  section?: "all" | "summary" | "biomarkers";
}

const biomarkerTooltips: Record<string, string> = {
  mfcc7:
    "MFCC7 indica componentes espectrais associados a valencia negativa e risco depressivo quando se eleva em fala emocionalmente negativa.",
  mfcc9:
    "MFCC9 e acompanhado em fala neutra; quedas ou desvios podem sugerir tensao autonomica latente e ansiedade somatica.",
  jitter:
    "Jitter no FROID e um indice proxy interno normalizado, derivado de ZCR escalado, util para observar instabilidade vocal relativa. Nao equivale diretamente ao jitter percentual normativo de Praat.",
  shimmer:
    "Shimmer no FROID e um indice proxy interno normalizado da variacao relativa do envelope RMS, util para observar instabilidade de energia vocal. Nao equivale diretamente ao shimmer em dB.",
};

function limitWords(text: string, maxWords: number) {
  return String(text || "").trim().split(/\s+/).filter(Boolean).slice(0, maxWords).join(" ");
}

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const classifyStability = (
  value: number,
  stable: number,
  warning: number,
) => {
  if (value <= stable) return { label: "Estavel", color: "#22c55e" };
  if (value <= warning) return { label: "Atencao", color: "#f59e0b" };
  return { label: "Alterado", color: "#ef4444" };
};

const StabilityBar: React.FC<{
  label: string;
  value: number;
  max: number;
  relativeMax: number;
  stable: number;
  warning: number;
  tooltip: string;
}> = ({ label, value, max, relativeMax, stable, warning, tooltip }) => {
  const percentage = Math.round(clamp(value / Math.max(max, 0.0001)) * 100);
  const relativePercentage = Math.max(
    3,
    clamp(value / Math.max(relativeMax, 0.0001)) * 100,
  );
  const status = classifyStability(value, stable, warning);

  return (
    <FroidTooltip content={<p>{tooltip}</p>} width={270}>
      <div className="w-full cursor-help rounded-lg border border-slate-700 bg-slate-950 p-2.5">
        <div className="mb-1 grid min-w-0 grid-cols-[12px_minmax(0,1fr)_48px] items-center gap-2">
          <span
            className="h-5 w-3 rounded-sm"
            style={{ backgroundColor: status.color }}
          />
          <div className="min-w-0">
            <p className="truncate text-[10px] font-black text-slate-100">{label}</p>
            <p className="truncate text-[8px] font-bold uppercase" style={{ color: status.color }}>
              {status.label} · idx. {value.toFixed(3)}
            </p>
          </div>
          <span className="text-right font-mono text-[10px] font-black text-slate-100">
            {percentage}%
          </span>
        </div>
        <div className="ml-5 h-2.5 w-[calc(100%-1.25rem)] overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${relativePercentage}%`, backgroundColor: status.color }}
          />
        </div>
      </div>
    </FroidTooltip>
  );
};

export const AudioTranscription: React.FC<Props> = ({
  audioMeta: providedAudioMeta,
  conversationSummaries = [],
  section = "all",
}) => {
  const audioMeta =
    providedAudioMeta ||
    (typeof window !== "undefined"
      ? (window as FroidAudioMetaWindow).__froidAudioMeta
      : undefined) ||
    {};
  const mfcc7 = Number(audioMeta.mfcc7 ?? 0);
  const mfcc9 = Number(audioMeta.mfcc9 ?? 0);
  const jitter = Number(audioMeta.jitter ?? 0);
  const shimmer = Number(audioMeta.shimmer ?? 0);
  const provider = String(audioMeta.provider || "");
  const transcriptionStatus = String(audioMeta.transcription_status || "");
  const bioacousticStatus = String(audioMeta.bioacoustic_status || "");
  const bioacousticTrack = String(audioMeta.bioacoustic_track || "");
  const bioacousticLabel =
    bioacousticStatus === "monitoring"
      ? bioacousticTrack === "patient-webrtc"
        ? "Bio paciente"
        : bioacousticTrack === "direct-local-patient"
        ? "Bio PC presencial"
        : bioacousticTrack === "semantic-fallback"
        ? "Bio fallback"
        : "Bio bruta"
      : bioacousticStatus === "waiting_patient"
        ? "Bio aguardando paciente"
      : bioacousticStatus === "error"
        ? "Bio off"
        : "Bio prep";
  const bioacousticClass =
    bioacousticStatus === "monitoring"
      ? bioacousticTrack === "patient-webrtc"
        ? "bg-emerald-50 text-emerald-700"
        : bioacousticTrack === "direct-local-patient"
        ? "bg-emerald-50 text-emerald-700"
        : bioacousticTrack === "semantic-fallback"
        ? "bg-amber-50 text-amber-700"
        : "bg-emerald-50 text-emerald-700"
      : bioacousticStatus === "waiting_patient"
        ? "bg-cyan-50 text-cyan-700"
      : bioacousticStatus === "error"
        ? "bg-red-50 text-red-700"
        : "bg-slate-100 text-slate-500";

  const sttLabel = provider.includes("openai")
    ? "STT por cortes"
    : provider.includes("browser-live")
      ? "STT local"
    : transcriptionStatus === "transcribing"
      ? "Corte em analise"
      : transcriptionStatus === "listening"
        ? "Captura ativa"
        : transcriptionStatus === "restarting"
          ? "Captura reiniciando"
          : transcriptionStatus === "error"
            ? "Captura off"
            : "Captura local";
  const sttClass = provider.includes("openai")
    ? "bg-green-50 text-green-700"
    : provider.includes("browser-live")
      ? "bg-cyan-50 text-cyan-700"
    : transcriptionStatus === "transcribing" || transcriptionStatus === "listening"
      ? "bg-blue-50 text-blue-700"
      : transcriptionStatus === "restarting"
        ? "bg-amber-50 text-amber-700"
        : transcriptionStatus === "error"
          ? "bg-red-50 text-red-700"
          : "bg-slate-100 text-slate-500";
  const mfccMax = Math.max(mfcc7, mfcc9, 0.01);
  const mfccItems = [
    { key: "mfcc7", label: "MFCC7", value: mfcc7, color: "#3b82f6" },
    { key: "mfcc9", label: "MFCC9", value: mfcc9, color: "#8b5cf6" },
  ];
  const perturbationMax = Math.max(jitter, shimmer, 0.01);
  const orderedSummaries = [...conversationSummaries].sort(
    (a, b) => b.startMinute - a.startMinute,
  );

  return (
    <div className="w-full space-y-2 rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      {section !== "biomarkers" && (
      <div className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-2">
        <div className="flex items-center justify-between gap-2 text-[9px] font-bold uppercase tracking-wider text-slate-300">
          <span>Resumo da Fala IA</span>
          <div className="flex items-center gap-1">
            <span className={`rounded px-1.5 py-0.5 text-[8px] ${sttClass}`}>
              {sttLabel}
            </span>
            <span>{orderedSummaries.length}</span>
          </div>
        </div>
        <div className="mt-1 max-h-44 space-y-1 overflow-y-auto">
          {orderedSummaries.length === 0 && (
            <p className="text-[10px] italic leading-snug text-slate-400">
              Aguardando fechamento do primeiro bloco de 10 minutos.
            </p>
          )}
          {orderedSummaries.map((item) => (
            <div
              key={item.id}
              className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] font-mono font-bold text-slate-400">
                    {item.startMinute}-{item.endMinute}min
                  </span>
                  {item.trigger === "manual" && (
                    <span className="rounded bg-blue-950 px-1 text-[8px] font-bold uppercase text-blue-200">
                      manual
                    </span>
                  )}
                </div>
                <strong className="truncate text-[10px] text-slate-100">
                  {limitWords(item.theme, 6)}
                </strong>
              </div>
              <p className="mt-0.5 text-[10px] leading-snug text-slate-300">
                {limitWords(item.summary, 60)}
              </p>
            </div>
          ))}
        </div>
      </div>
      )}

      {section !== "summary" && (
      <div className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-300">
          <span>Biomarcadores vocais</span>
          <span className={`rounded px-1.5 py-0.5 text-[8px] ${bioacousticClass}`}>
            {bioacousticLabel}
          </span>
        </div>
        <div className="mt-2 space-y-2 text-[10px]">
          <div className="rounded-xl border border-slate-700 bg-slate-950 p-2.5">
            <p className="mb-3 text-[11px] font-black uppercase tracking-wide text-slate-300">
              Grafico Comparativo MFCC7 x MFCC9
            </p>
            <div className="space-y-2">
            {mfccItems.map((item) => (
              <FroidTooltip
                key={item.key}
                content={<p>{biomarkerTooltips[item.key]}</p>}
                width={300}
              >
                <div className="w-full cursor-help">
                  <div className="mb-1 grid min-w-0 grid-cols-[12px_minmax(0,1fr)_48px] items-center gap-2">
                    <span
                      className="h-5 w-3 rounded-sm"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-[10px] font-black text-slate-100">
                      {item.label}
                    </span>
                    <span className="text-right font-mono text-[10px] font-black text-slate-100">
                      {Math.round((Math.max(0, item.value) / mfccMax) * 100)}%
                    </span>
                  </div>
                  <div className="ml-5 h-2.5 w-[calc(100%-1.25rem)] overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.max(3, (Math.max(0, item.value) / mfccMax) * 100)}%`,
                        backgroundColor: item.color,
                      }}
                    />
                  </div>
                  <p className="mt-1 text-right font-mono text-[8px] text-slate-400">
                    valor {item.value.toFixed(2)}
                  </p>
                </div>
              </FroidTooltip>
            ))}
            </div>
          </div>

          <div className="space-y-2">
            <StabilityBar
              label="Jitter idx."
              value={jitter}
              max={1}
              relativeMax={perturbationMax}
              stable={0.2}
              warning={0.45}
              tooltip={biomarkerTooltips.jitter}
            />
            <StabilityBar
              label="Shimmer idx."
              value={shimmer}
              max={1}
              relativeMax={perturbationMax}
              stable={0.3}
              warning={0.6}
              tooltip={biomarkerTooltips.shimmer}
            />
          </div>
        </div>
      </div>
      )}
    </div>
  );
};
