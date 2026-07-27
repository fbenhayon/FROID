import React, { useMemo } from "react";
import { AcousticBiomarkers } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

interface Props {
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
  locale?: SessionLocale;
}

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const read = (audioMeta: Props["audioMeta"], key: keyof AcousticBiomarkers) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : 0;
};

const percent = (value: number) => Math.round(clamp(value) * 100);

export const SpectralBandsChart: React.FC<Props> = ({ audioMeta, locale = "pt-BR" }) => {
  const metrics = useMemo(
    () => [
      {
        label: "Delta",
        band: "0.5-4 Hz",
        value: read(audioMeta, "spectral_delta_0_4hz"),
        color: "#7DD3FC",
        tooltip:
          "Delta (0,5–4 Hz): oscilação lenta do envelope vocal, usada como marcador de carga vegetativa basal e de baixa variabilidade dinâmica. Valores altos sugerem lentificação e retraimento; valores baixos, maior mobilização.",
      },
      {
        label: "Theta",
        band: "4-8 Hz",
        value: read(audioMeta, "spectral_theta_4_8hz"),
        color: "#A5B4FC",
        tooltip:
          "Theta (4–8 Hz): componente de modulação lenta relacionado a flutuações afetivas e à organização narrativa sob esforço emocional. Realça quando o paciente elabora conteúdo emocionalmente carregado.",
      },
      {
        label: "Alpha",
        band: "8-12 Hz",
        value: read(audioMeta, "spectral_alpha_8_12hz"),
        color: "#6EE7B7",
        tooltip:
          "Alpha (8–12 Hz): faixa de estabilização moduladora entre os ritmos lentos e a resposta autônoma mais ativa. Serve de referência de equilíbrio entre relaxamento e ativação.",
      },
      {
        label: "Beta",
        band: "12-30 Hz",
        value: read(audioMeta, "spectral_beta_12_30hz"),
        color: "#FBBF24",
        tooltip:
          "Beta (12–30 Hz): ativação rápida associada a tensão cognitiva, vigilância, pressão articulatória e mobilização autônoma. Picos acompanham momentos de alerta, esforço ou ansiedade.",
      },
      {
        label: "Gama",
        band: "30-80 Hz",
        value: read(audioMeta, "spectral_gamma_30_80hz"),
        color: "#FB7185",
        tooltip:
          "Gama (30–80 Hz): energia espectral de alta frequência, interpretada com cautela como indicador de descarga fina, tensão e aspereza vocal. É a banda mais exploratória — leia sempre junto às demais.",
      },
    ],
    [audioMeta],
  );

  const index = read(audioMeta, "spectral_band_index");
  const mfcc7Delta = read(audioMeta, "mfcc7_delta");
  const mfcc9Delta = read(audioMeta, "mfcc9_delta");
  const mfcc7DeltaDelta = read(audioMeta, "mfcc7_delta_delta");
  const mfcc9DeltaDelta = read(audioMeta, "mfcc9_delta_delta");
  const hasData = metrics.some((metric) => metric.value > 0);
  const metricPercentages = metrics.map((metric) => percent(metric.value));
  const maxMetricPercentage = Math.max(...metricPercentages, 1);

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      <div className="mb-1.5 flex shrink-0 items-start justify-between gap-3">
        <div>
          <FroidTooltip
            width={360}
            content={
              <div>
                <p className="font-bold text-slate-100">{tooltipText(locale, "Bandas neuroacústicas")}</p>
                <p className="mt-1">
                  {tooltipText(
                    locale,
                    "Leitura das modulações vocais Delta, Theta, Alpha, Beta e Gama da trilha do paciente. A nomenclatura é analógica para bandas de voz, não EEG, consolidada a cada 1 segundo e cruzada com os deltas cepstrais MFCC7/MFCC9.",
                  )}
                </p>
              </div>
            }
          >
            <h3 className="cursor-help text-[13px] font-black text-slate-100">
              Bandas neuroacústicas
            </h3>
          </FroidTooltip>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            Consolidação bioacústica: {Number(audioMeta?.bioacoustic_window_ms || 1000)}ms
          </p>
        </div>
        <FroidTooltip
          width={300}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Índice geral das bandas")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Média ponderada da energia das cinco bandas neuroacústicas em 0–100%. Sintetiza o nível global de modulação vocal do momento — útil como leitura rápida antes de detalhar banda a banda.",
                )}
              </p>
            </div>
          }
        >
          <div className="shrink-0 cursor-help rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
            <p className="text-[8px] font-black uppercase">Índice geral</p>
            <p className="font-mono text-[12px] font-black">{percent(index)}%</p>
          </div>
        </FroidTooltip>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-5 items-stretch gap-1.5 overflow-hidden px-1">
        {metrics.map((metric) => (
          <FroidTooltip
            key={metric.label}
            fullWidth
            width={340}
            content={
              <div>
                <p className="font-bold text-slate-100">
                  {metric.label} | {metric.band}
                </p>
                <p className="mt-1">{tooltipText(locale, metric.tooltip)}</p>
              </div>
            }
          >
            <div className="flex h-full min-w-0 cursor-help flex-col items-center">
              <span className="mb-1 font-mono text-[9px] font-black text-slate-100">
                {percent(metric.value)}%
              </span>
              <div className="flex min-h-0 w-full flex-1 items-end justify-center overflow-hidden rounded-md bg-slate-800/70 px-1 pt-1">
                <div
                  className="w-full max-w-8 rounded-t-sm transition-all duration-700"
                  style={{
                    height: `${Math.max(3, (percent(metric.value) / maxMetricPercentage) * 100)}%`,
                    backgroundColor: metric.color,
                  }}
                />
              </div>
              <span className="mt-1 block w-full truncate text-center text-[9px] font-black text-slate-100">
                {metric.label}
              </span>
              <span className="block w-full truncate text-center text-[7px] font-bold text-slate-500">
                {metric.band}
              </span>
            </div>
          </FroidTooltip>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-700 pt-2 font-mono text-[9px] text-slate-300">
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔMFCC7 — velocidade do MFCC7")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Primeira derivada (taxa de variação) do coeficiente cepstral MFCC7. É o marcador que o FROID isola na fala de valência negativa: quando se eleva, contribui para o risco depressivo.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DMFCC7 {mfcc7Delta.toFixed(4)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔMFCC9 — velocidade do MFCC9")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Primeira derivada do coeficiente cepstral MFCC9. Quedas em discurso neutro sugerem tensão autônoma latente nas pregas vocais, associada à ansiedade somática.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DMFCC9 {mfcc9Delta.toFixed(4)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔΔMFCC7 — aceleração do MFCC7")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Segunda derivada do MFCC7: captura mudanças bruscas na trajetória do timbre. Realça transições rápidas de estado emocional, não apenas o nível sustentado.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DDMFCC7 {mfcc7DeltaDelta.toFixed(4)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔΔMFCC9 — aceleração do MFCC9")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Segunda derivada do MFCC9: mede a rapidez com que a tensão vocal latente muda ao longo da fala, complementando a leitura de ansiedade somática.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DDMFCC9 {mfcc9DeltaDelta.toFixed(4)}</span>
        </FroidTooltip>
      </div>
      {!hasData && (
        <p className="mt-2 text-[9px] italic text-slate-500">
          Aguardando voz do paciente para consolidar as bandas.
        </p>
      )}
    </div>
  );
};
