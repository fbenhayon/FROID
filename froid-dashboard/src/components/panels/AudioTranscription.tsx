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
}

interface Props {
  snippet: string;
  wordsCount: number;
  totalWords: number;
  tone: string;
  wordsPerMinute10m: number;
  sessionTheme: string;
  themeMinuteMark: number;
  audioMeta?: Record<string, unknown>;
  conversationSummaries?: ConversationSummary[];
  activeSpeaker?: "PAC" | "DR";
  onSpeakerChange?: (speaker: "PAC" | "DR") => void;
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

export const AudioTranscription: React.FC<Props> = ({
  snippet,
  wordsCount,
  totalWords,
  tone,
  wordsPerMinute10m,
  sessionTheme,
  themeMinuteMark,
  audioMeta: providedAudioMeta,
  conversationSummaries = [],
  activeSpeaker = "PAC",
  onSpeakerChange,
}) => {
  const toneColor: Record<string, string> = {
    neutro: "text-slate-600",
    ansioso: "text-amber-700",
    triste: "text-blue-700",
    irritado: "text-red-700",
    alegre: "text-green-700",
    suprimido: "text-purple-700",
  };

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
  const transcriptionError = String(audioMeta.transcription_error || "");
  const interimText = String(audioMeta.transcription_interim || "");
  const bioacousticStatus = String(audioMeta.bioacoustic_status || "");
  const bioacousticPipeline = String(audioMeta.bioacoustic_pipeline || "");
  const bioacousticTrack = String(audioMeta.bioacoustic_track || "");
  const bioacousticWarning = String(
    audioMeta.bioacoustic_warning || audioMeta.bioacoustic_error || "",
  );
  const bioacousticLabel =
    bioacousticStatus === "monitoring"
      ? bioacousticTrack === "patient-webrtc"
        ? "Bio PAC"
        : bioacousticTrack === "semantic-fallback"
        ? "Bio fallback"
        : "Bio bruta"
      : bioacousticStatus === "waiting_patient"
        ? "Bio aguardando PAC"
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
    ? "GPT-4o STT"
    : provider.includes("browser-live")
      ? "STT ao vivo"
    : transcriptionStatus === "transcribing"
      ? "STT enviando"
      : transcriptionStatus === "listening"
        ? "STT ouvindo"
        : transcriptionStatus === "restarting"
          ? "STT reiniciando"
          : transcriptionStatus === "error"
            ? "STT off"
            : "STT local";
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
  const placeholder =
    transcriptionStatus === "listening"
      ? "Microfone ativo. Fale por alguns segundos para iniciar a transcricao..."
      : transcriptionStatus === "transcribing"
        ? "Audio capturado. Enviando para transcricao..."
        : transcriptionStatus === "restarting"
          ? "Reiniciando captura de audio..."
          : transcriptionStatus === "error" && transcriptionError
            ? transcriptionError
            : "Aguardando fala do paciente...";

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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Transcricao & Metricas Vocais
          </span>
          <FroidTooltip
            content={
              <div className="max-w-[260px]">
                <p className="font-bold">Analise Vocal em Tempo Real</p>
                <p className="text-[11px] mt-1">
                  Transcricao em blocos curtos, tom vocal, palavras por minuto,
                  biomarcadores acusticos e resumo da conversa a cada 10 minutos.
                </p>
              </div>
            }
            width={280}
          >
            <span className="cursor-help text-[10px] text-slate-400 border-b border-dashed border-slate-300">
              ?
            </span>
          </FroidTooltip>
        </div>
        <div className="flex items-center gap-1">
          {onSpeakerChange ? (
            <div className="flex overflow-hidden rounded border border-slate-200 bg-slate-50">
              {(["PAC", "DR"] as const).map((speaker) => (
                <button
                  key={speaker}
                  type="button"
                  onClick={() => onSpeakerChange(speaker)}
                  className={`px-1.5 py-0.5 text-[9px] font-black ${
                    activeSpeaker === speaker
                      ? "bg-slate-800 text-white"
                      : "text-slate-500 hover:bg-white"
                  }`}
                >
                  {speaker}
                </button>
              ))}
            </div>
          ) : (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-600">
              DR/PAC auto
            </span>
          )}
          <span
            title={transcriptionError || provider || transcriptionStatus || "STT local"}
            className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${sttClass}`}
          >
            {sttLabel}
          </span>
          <span
            title={
              bioacousticWarning ||
              bioacousticPipeline ||
              "Trilha bioacustica bruta independente"
            }
            className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${bioacousticClass}`}
          >
            {bioacousticLabel}
          </span>
        </div>
      </div>

      <div className="min-h-[8.75rem] max-h-[8.75rem] overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-2.5">
        <p className="whitespace-pre-wrap text-[11px] leading-5 text-slate-700">
          {snippet || interimText || placeholder}
        </p>
        {snippet && interimText && (
          <p className="mt-1 whitespace-pre-wrap text-[11px] leading-5 text-blue-600">
            {interimText}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5">
          <span className="block text-[8px] font-bold uppercase tracking-wider text-amber-700">
            Tom vocal
          </span>
          <strong className={`text-[11px] uppercase ${toneColor[tone] || "text-slate-600"}`}>
            {tone}
          </strong>
        </div>
        <div className="rounded-md border border-blue-100 bg-blue-50 px-2 py-1.5">
          <span className="block text-[8px] font-bold uppercase tracking-wider text-blue-700">
            Palavras/min
          </span>
          <strong className="font-mono text-[11px] text-blue-800">
            {wordsPerMinute10m.toFixed(0)} ppm
          </strong>
        </div>
      </div>

      <div className="flex items-center justify-between text-[9px] text-slate-500">
        <span>
          Janela atual: <strong className="text-slate-700">{wordsCount}</strong>{" "}
          palavras
        </span>
        <span>
          Total: <strong className="text-slate-700">{totalWords}</strong>
        </span>
      </div>

      <div className="rounded-md border border-slate-100 bg-white px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-500">
          <span>Resumos IA 10min</span>
          <span>{orderedSummaries.length}</span>
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
                <span className="text-[9px] font-mono font-bold text-slate-500">
                  {item.startMinute}-{item.endMinute}min
                </span>
                <strong className="truncate text-[10px] text-slate-800">
                  {item.theme}
                </strong>
              </div>
              <p className="mt-0.5 text-[10px] leading-snug text-slate-600">
                {item.summary}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md bg-slate-50 border border-slate-100 px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-500">
          <span>Biomarcadores vocais</span>
          <span>Edge AI</span>
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

      {sessionTheme && (
        <div className="rounded-md bg-amber-50 border border-amber-100 px-2 py-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-bold text-amber-800 uppercase">
              Tema da Sessao ({themeMinuteMark}min)
            </span>
          </div>
          <p className="text-[10px] text-amber-900 leading-snug mt-0.5">
            {sessionTheme}
          </p>
        </div>
      )}
    </div>
  );
};
