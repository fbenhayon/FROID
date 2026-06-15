import React from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

type FroidAudioMetaWindow = Window &
  typeof globalThis & {
    __froidAudioMeta?: Record<string, unknown>;
  };

interface Props {
  snippet: string;
  wordsCount: number;
  totalWords: number;
  tone: string;
  wordsPerMinute10m: number;
  sessionTheme: string;
  themeMinuteMark: number;
}

export const AudioTranscription: React.FC<Props> = ({
  snippet,
  wordsCount,
  totalWords,
  tone,
  wordsPerMinute10m,
  sessionTheme,
  themeMinuteMark,
}) => {
  const toneColor: Record<string, string> = {
    neutro: "text-slate-500",
    ansioso: "text-amber-600",
    triste: "text-blue-600",
    irritado: "text-red-600",
    alegre: "text-green-600",
    suprimido: "text-purple-600",
  };

  const audioMeta =
    (typeof window !== "undefined"
      ? (window as FroidAudioMetaWindow).__froidAudioMeta
      : undefined) || {};
  const mfcc7 = Number(audioMeta.mfcc7 ?? 0);
  const mfcc9 = Number(audioMeta.mfcc9 ?? 0);
  const jitter = Number(audioMeta.jitter ?? 0);
  const shimmer = Number(audioMeta.shimmer ?? 0);

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Transcrição & Métricas Vocais
          </span>
          <FroidTooltip
            content={
              <div className="max-w-[260px]">
                <p className="font-bold">Análise Vocal em Tempo Real</p>
                <p className="text-[11px] mt-1">
                  Snippet transcrito, tom emocional inferido pela prosódia,
                  contagem de palavras por minuto (média dos últimos 10 minutos)
                  e tema semântico da sessão atualizado a cada 10 minutos.
                </p>
                <p className="text-[10px] text-slate-400 mt-1">
                  Integração futura: gpt-realtime-whisper
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
        <span
          className={`text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 ${toneColor[tone] || "text-slate-500"}`}
        >
          Tom: {tone}
        </span>
      </div>

      <div className="rounded-lg bg-slate-50 p-2.5 border border-slate-100">
        <p className="text-[11px] text-slate-700 italic leading-relaxed">
          "{snippet || "Aguardando fala do paciente..."}"
        </p>
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

      <div className="flex items-center justify-between rounded-md bg-blue-50 border border-blue-100 px-2 py-1.5">
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-bold text-blue-800">
            Média 10min:
          </span>
          <span className="text-[10px] font-mono font-bold text-blue-700">
            {wordsPerMinute10m.toFixed(0)} ppm
          </span>
        </div>
        <span className="text-[9px] text-blue-500">palavras/min</span>
      </div>

      <div className="rounded-md bg-slate-50 border border-slate-100 px-2 py-2">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wider text-slate-500">
          <span>Biomarcadores vocais</span>
          <span>Edge AI</span>
        </div>
        <div className="mt-1 grid grid-cols-2 gap-2 text-[10px] text-slate-600">
          <div className="rounded bg-white p-1.5 border border-slate-100">
            MFCC7: <strong>{mfcc7.toFixed(2)}</strong>
          </div>
          <div className="rounded bg-white p-1.5 border border-slate-100">
            MFCC9: <strong>{mfcc9.toFixed(2)}</strong>
          </div>
          <div className="rounded bg-white p-1.5 border border-slate-100">
            Jitter: <strong>{jitter.toFixed(3)}</strong>
          </div>
          <div className="rounded bg-white p-1.5 border border-slate-100">
            Shimmer: <strong>{shimmer.toFixed(3)}</strong>
          </div>
        </div>
      </div>

      {sessionTheme && (
        <div className="rounded-md bg-amber-50 border border-amber-100 px-2 py-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-bold text-amber-800 uppercase">
              Tema da Sessão ({themeMinuteMark}min)
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
