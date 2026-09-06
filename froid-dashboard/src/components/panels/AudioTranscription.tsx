import React from "react";
import { FroidTooltip } from "../ui/FroidTooltip";
import { normalizeSessionLocale, type SessionLocale } from "../../lib/localization";
import { tooltipText } from "../../lib/tooltip-i18n";

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
  locale?: SessionLocale;
  // Controle do corte semântico, exibido junto ao título "Resumo da Fala IA"
  // (barra de tempo acima, botão compacto ao lado do título). Opcional: sem
  // esses props o cabeçalho de corte simplesmente não é renderizado.
  cutElapsedLabel?: string;
  cutRemainingLabel?: string;
  cutProgress?: number;
  onCloseCut?: () => void;
  closeCutDisabled?: boolean;
}

const biomarkerTooltips: Record<string, string> = {
  mfcc7:
    "MFCC7: coeficiente cepstral do envelope espectral. O FROID acompanha sua elevacao durante fala de valencia negativa. A literatura associa esse padrao a lentificacao psicomotora. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
  mfcc9:
    "MFCC9: coeficiente cepstral acompanhado em fala neutra, contra a referencia do proprio paciente. Quedas sustentadas sao descritas na literatura como correlato acustico de tensao laringea. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
  jitter:
    "Jitter no FROID é um índice proxy interno normalizado, derivado de ZCR escalado, útil para observar instabilidade vocal relativa. Não equivale diretamente ao jitter percentual normativo de Praat.",
  shimmer:
    "Shimmer no FROID é um índice proxy interno normalizado da variação relativa do envelope RMS, útil para observar instabilidade de energia vocal. Não equivale diretamente ao shimmer em dB.",
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
  if (value <= stable) return { label: "Estável", color: "#22c55e" };
  if (value <= warning) return { label: "Atenção", color: "#f59e0b" };
  return { label: "Alterado", color: "#ef4444" };
};

const StabilityBar: React.FC<{
  label: string;
  /** Nulo quando o biomarcador NAO foi medido. Zero e uma medida; ausencia
   *  nao e. Com `?? 0` a barra saia vazia e o rotulo dizia "0.000", que num
   *  painel clinico le como estabilidade perfeita. */
  value: number | null;
  max: number;
  relativeMax: number;
  stable: number;
  warning: number;
  tooltip: string;
}> = ({ label, value, max, relativeMax, stable, warning, tooltip }) => {
  if (value === null) {
    return (
      <FroidTooltip content={<p>{tooltip}</p>} width={270} fullWidth>
        <div className="w-full cursor-help rounded-lg border border-slate-800 bg-slate-950 p-2.5">
          <div className="grid min-w-0 grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-2">
            <span className="h-5 w-3 rounded-sm bg-slate-700" />
            <p className="truncate text-[10px] font-black text-slate-400">{label}</p>
            <span className="text-right text-[9px] font-bold uppercase italic text-slate-500">
              nao medido
            </span>
          </div>
        </div>
      </FroidTooltip>
    );
  }
  const percentage = Math.round(clamp(value / Math.max(max, 0.0001)) * 100);
  const relativePercentage = Math.max(
    3,
    clamp(value / Math.max(relativeMax, 0.0001)) * 100,
  );
  const status = classifyStability(value, stable, warning);

  return (
    <FroidTooltip content={<p>{tooltip}</p>} width={270} fullWidth>
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
  locale = normalizeSessionLocale(undefined),
  cutElapsedLabel,
  cutRemainingLabel,
  cutProgress,
  onCloseCut,
  closeCutDisabled,
}) => {
  const showCutControl = Boolean(onCloseCut && cutElapsedLabel && cutRemainingLabel);
  const ui = {
    "pt-BR": { summary: "Resumo da Fala IA", waiting: "Aguardando fechamento do primeiro bloco de 10 minutos.", biomarkers: "Biomarcadores vocais", comparison: "Comparação vocal por indicador", chart: "Gráfico Comparativo MFCC7 x MFCC9", magnitude: "Magnitude relativa | coeficiente bruto à direita" },
    "en-US": { summary: "AI Speech Summary", waiting: "Waiting for the first 10-minute block to close.", biomarkers: "Voice biomarkers", comparison: "Voice comparison by indicator", chart: "MFCC7 vs MFCC9 Comparison", magnitude: "Relative magnitude | raw coefficient on the right" },
    "fr-FR": { summary: "Résumé IA de la parole", waiting: "En attente de la clôture du premier bloc de 10 minutes.", biomarkers: "Biomarqueurs vocaux", comparison: "Comparaison vocale par indicateur", chart: "Comparaison MFCC7 / MFCC9", magnitude: "Amplitude relative | coefficient brut à droite" },
    "es-ES": { summary: "Resumen de voz con IA", waiting: "Esperando el cierre del primer bloque de 10 minutos.", biomarkers: "Biomarcadores vocales", comparison: "Comparación vocal por indicador", chart: "Comparación MFCC7 vs MFCC9", magnitude: "Magnitud relativa | coeficiente bruto a la derecha" },
  }[locale];
  const audioMeta =
    providedAudioMeta ||
    (typeof window !== "undefined"
      ? (window as FroidAudioMetaWindow).__froidAudioMeta
      : undefined) ||
    {};
  // `?? 0` publicava "0,0000" para biomarcador nao medido, no painel do
  // profissional, ao lado dos que foram medidos e sem nada distinguindo os
  // dois. Ausencia sobe como nula e a tela imprime tracos.
  const numeroOuNulo = (valor: unknown): number | null =>
    valor === null || valor === undefined || !Number.isFinite(Number(valor))
      ? null
      : Number(valor);
  const mfcc7 = numeroOuNulo(audioMeta.mfcc7);
  const mfcc9 = numeroOuNulo(audioMeta.mfcc9);
  const jitter = numeroOuNulo(audioMeta.jitter);
  const shimmer = numeroOuNulo(audioMeta.shimmer);
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
      ? "Corte em análise"
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
  const mfccMagnitudeMax = Math.max(Math.abs(mfcc7 ?? 0), Math.abs(mfcc9 ?? 0), 0.01);
  const mfccItems = [
    { key: "mfcc7", label: "MFCC7", value: mfcc7, color: "#3b82f6" },
    { key: "mfcc9", label: "MFCC9", value: mfcc9, color: "#8b5cf6" },
  ];
  const perturbationMax = Math.max(jitter ?? 0, shimmer ?? 0, 0.01);
  // Do PRIMEIRO corte para o último. A lista vinha invertida, e ler a sessão
  // de trás para frente obriga o profissional a reconstruir a ordem de cabeça
  // justamente quando ele está acompanhando a conversa em tempo real.
  const orderedSummaries = [...conversationSummaries].sort(
    (a, b) => a.startMinute - b.startMinute,
  );
  // Extensão da sessão até agora, para posicionar cada corte na régua. Usa o
  // maior fim registrado: sem isso a barra precisaria da duração total, que
  // este painel não recebe.
  const spanMinutes = Math.max(
    1,
    ...orderedSummaries.map((item) => item.endMinute || 0),
  );

  return (
    <div className="w-full space-y-2 rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      {section !== "biomarkers" && (
      <div className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-2">
        {showCutControl && (
          <div className="mb-1.5">
            <div className="flex items-center justify-between font-mono text-[9px] text-cyan-300">
              <span>Atual {cutElapsedLabel}</span>
              <span>Auto em {cutRemainingLabel}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-cyan-950">
              <div
                className="h-full rounded-full bg-cyan-600 transition-all duration-1000"
                style={{ width: `${Math.max(0, Math.min(100, cutProgress ?? 0))}%` }}
              />
            </div>
          </div>
        )}
        <div className="flex items-center justify-between gap-2 text-[9px] font-bold uppercase tracking-wider text-slate-300">
          <div className="flex items-center gap-1.5">
            <span>{ui.summary}</span>
            {showCutControl && (
              <button
                type="button"
                onClick={onCloseCut}
                disabled={closeCutDisabled}
                title="Fecha manualmente o corte atual e gera resumo IA do período."
                className="rounded bg-emerald-700 px-1.5 py-0.5 text-[8px] font-black uppercase tracking-wide text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              >
                Fechar corte
              </button>
            )}
          </div>
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
              {ui.waiting}
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
              {/* Régua do corte no lugar do texto.
                  A transcrição saiu daqui de propósito: durante a sessão ela
                  competia com a escuta, e o que o profissional precisa de
                  relance é ONDE o corte está e QUAL o tema — não reler o que
                  acabou de ouvir. O texto continua inteiro no Relatório da
                  Consulta, que é onde ele serve. */}
              <div
                className="mt-1 h-1 w-full overflow-hidden rounded-full bg-slate-800"
                role="img"
                aria-label={`Corte de ${item.startMinute} a ${item.endMinute} minutos`}
              >
                <div
                  className="h-full rounded-full bg-cyan-700"
                  style={{
                    marginLeft: `${(item.startMinute / spanMinutes) * 100}%`,
                    width: `${Math.max(
                      2,
                      ((item.endMinute - item.startMinute) / spanMinutes) * 100,
                    )}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
      )}

      {section !== "summary" && (
      <div className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-[13px] font-black text-slate-100">{ui.biomarkers}</h3>
            <p className="truncate text-[10px] font-medium text-slate-400">
              {ui.comparison}
            </p>
          </div>
          <span className={`rounded px-1.5 py-0.5 text-[8px] ${bioacousticClass}`}>
            {bioacousticLabel}
          </span>
        </div>
        <div className="mt-2 space-y-2 text-[10px]">
          <div className="rounded-xl border border-slate-700 bg-slate-950 p-2.5">
            <p className="text-[11px] font-black text-slate-100">
              {ui.chart}
            </p>
            <p className="mb-3 text-[8px] text-slate-400">
              {ui.magnitude}
            </p>
            <div className="space-y-2">
            {mfccItems.map((item) => (
              <FroidTooltip
                key={item.key}
                fullWidth
                content={<p>{tooltipText(locale, biomarkerTooltips[item.key])}</p>}
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
                      {item.value === null ? "--" : item.value.toFixed(2)}
                    </span>
                  </div>
                  <div className="ml-5 h-2.5 w-[calc(100%-1.25rem)] overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: item.value === null
                          ? "0%"
                          : `${Math.max(3, (Math.abs(item.value) / mfccMagnitudeMax) * 100)}%`,
                        backgroundColor: item.color,
                      }}
                    />
                  </div>
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
              tooltip={tooltipText(locale, biomarkerTooltips.jitter)}
            />
            <StabilityBar
              label="Shimmer idx."
              value={shimmer}
              max={1}
              relativeMax={perturbationMax}
              stable={0.3}
              warning={0.6}
              tooltip={tooltipText(locale, biomarkerTooltips.shimmer)}
            />
          </div>
        </div>
      </div>
      )}
    </div>
  );
};
