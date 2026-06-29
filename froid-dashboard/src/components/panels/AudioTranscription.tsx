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
}

const biomarkerTooltips: Record<string, string> = {
  mfcc7:
    "MFCC7 indica componentes espectrais associados a valencia negativa e risco depressivo quando se eleva em fala emocionalmente negativa.",
  mfcc9:
    "MFCC9 e acompanhado em fala neutra; quedas ou desvios podem sugerir tensao autonomica latente e ansiedade somatica.",
  jitter:
    "Jitter mede microvariacoes ciclo a ciclo da frequencia vocal, uteis para observar instabilidade laringea, esforco e estresse cognitivo.",
  shimmer:
    "Shimmer mede variacoes de amplitude entre ciclos vocais, indicando instabilidade de energia, tensao e controle respiratorio/vocal.",
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

const StabilityGauge: React.FC<{
  label: string;
  value: number;
  max: number;
  stable: number;
  warning: number;
  tooltip: string;
}> = ({ label, value, max, stable, warning, tooltip }) => {
  const ratio = clamp(value / Math.max(max, 0.0001));
  const angle = Math.PI - Math.PI * ratio;
  const dotX = 100 + 75 * Math.cos(angle);
  const dotY = 75 - 75 * Math.sin(angle);
  const status = classifyStability(value, stable, warning);

  return (
    <FroidTooltip content={<p>{tooltip}</p>} width={270}>
      <div className="cursor-help rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-center">
        <p className="text-[10px] font-black uppercase text-slate-200">{label}</p>
        <svg viewBox="0 0 200 95" className="mx-auto mt-1 h-14 w-full">
          <path
            d="M 25 75 A 75 75 0 0 1 175 75"
            fill="none"
            stroke="#334155"
            strokeLinecap="round"
            strokeWidth="14"
          />
          <circle cx={dotX} cy={dotY} r="7" fill={status.color} />
        </svg>
        <p className="font-mono text-[12px] font-black text-slate-100">
          {value.toFixed(3)}
        </p>
        <span
          className="mt-1 inline-flex rounded-full px-2 py-0.5 text-[9px] font-black uppercase"
          style={{ backgroundColor: `${status.color}22`, color: status.color }}
        >
          {status.label}
        </span>
      </div>
    </FroidTooltip>
  );
};

export const AudioTranscription: React.FC<Props> = ({
  audioMeta: providedAudioMeta,
  conversationSummaries = [],
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
    { key: "mfcc7", label: "MFCC7", value: mfcc7 },
    { key: "mfcc9", label: "MFCC9", value: mfcc9 },
  ];
  const orderedSummaries = [...conversationSummaries].sort(
    (a, b) => b.startMinute - a.startMinute,
  );

  return (
    <div className="w-full space-y-2 rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-100 shadow-sm">
      <div className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2">
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

      <div className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-300">
          <span>Biomarcadores vocais</span>
          <span className={`rounded px-1.5 py-0.5 text-[8px] ${bioacousticClass}`}>
            {bioacousticLabel}
          </span>
        </div>
        <div className="mt-2 space-y-2 text-[10px]">
          <div className="rounded-[18px] border border-slate-700 bg-slate-950 px-4 py-3">
            <p className="mb-3 text-[11px] font-black uppercase tracking-wide text-slate-300">
              Grafico Comparativo MFCC7 x MFCC9
            </p>
            <div className="space-y-4">
            {mfccItems.map((item) => (
              <FroidTooltip
                key={item.key}
                content={<p>{biomarkerTooltips[item.key]}</p>}
                width={300}
              >
                <div className="grid cursor-help grid-cols-[72px_minmax(0,1fr)_62px] items-center gap-3">
                  <span className="text-[13px] font-black text-slate-100">{item.label}</span>
                  <div className="h-5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-slate-300 transition-all duration-500"
                      style={{
                        width: `${Math.max(3, (Math.max(0, item.value) / mfccMax) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="text-right font-mono text-[14px] font-black text-slate-100">
                    {item.value.toFixed(2)}
                  </span>
                </div>
              </FroidTooltip>
            ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <StabilityGauge
              label="Jitter"
              value={jitter}
              max={0.06}
              stable={0.02}
              warning={0.04}
              tooltip={biomarkerTooltips.jitter}
            />
            <StabilityGauge
              label="Shimmer"
              value={shimmer}
              max={1}
              stable={0.3}
              warning={0.6}
              tooltip={biomarkerTooltips.shimmer}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
