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
  const biomarkerItems = [
    { key: "mfcc7", label: "MFCC7", value: mfcc7.toFixed(2) },
    { key: "mfcc9", label: "MFCC9", value: mfcc9.toFixed(2) },
    { key: "jitter", label: "Jitter", value: jitter.toFixed(3) },
    { key: "shimmer", label: "Shimmer", value: shimmer.toFixed(3) },
  ];
  const orderedSummaries = [...conversationSummaries].sort(
    (a, b) => b.startMinute - a.startMinute,
  );

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3 space-y-2">
      <div className="rounded-md border border-slate-100 bg-white px-2 py-2">
        <div className="flex items-center justify-between gap-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">
          <span>Resumos IA 10min</span>
          <div className="flex items-center gap-1">
            <span className={`rounded px-1.5 py-0.5 text-[8px] ${sttClass}`}>
              {sttLabel}
            </span>
            <span>{orderedSummaries.length}</span>
          </div>
        </div>
        <div className="mt-1 max-h-48 space-y-1 overflow-y-auto">
          {orderedSummaries.length === 0 && (
            <p className="text-[10px] italic leading-snug text-slate-400">
              Aguardando fechamento do primeiro bloco de 10 minutos.
            </p>
          )}
          {orderedSummaries.map((item) => (
            <div
              key={item.id}
              className="rounded border border-slate-100 bg-slate-50 px-2 py-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] font-mono font-bold text-slate-500">
                    {item.startMinute}-{item.endMinute}min
                  </span>
                  {item.trigger === "manual" && (
                    <span className="rounded bg-blue-100 px-1 text-[8px] font-bold uppercase text-blue-700">
                      manual
                    </span>
                  )}
                </div>
                <strong className="truncate text-[10px] text-slate-800">
                  {limitWords(item.theme, 6)}
                </strong>
              </div>
              <p className="mt-0.5 text-[10px] leading-snug text-slate-600">
                {limitWords(item.summary, 60)}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md bg-slate-50 border border-slate-100 px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-500">
          <span>Biomarcadores vocais</span>
          <span className={`rounded px-1.5 py-0.5 text-[8px] ${bioacousticClass}`}>
            {bioacousticLabel}
          </span>
        </div>
        <div className="mt-1 grid grid-cols-2 gap-2 text-[10px] text-slate-600">
          {biomarkerItems.map((item) => (
            <FroidTooltip key={item.key} content={<p>{biomarkerTooltips[item.key]}</p>} width={270}>
              <div className="cursor-help rounded bg-white p-1.5 border border-slate-100">
                {item.label}: <strong>{item.value}</strong>
              </div>
            </FroidTooltip>
          ))}
        </div>
      </div>
    </div>
  );
};
