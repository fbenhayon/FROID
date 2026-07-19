import React, { useMemo } from "react";
import { AcousticBiomarkers } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
}

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const read = (audioMeta: Props["audioMeta"], key: keyof AcousticBiomarkers) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : 0;
};

const percent = (value: number) => Math.round(clamp(value) * 100);

export const SpectralBandsChart: React.FC<Props> = ({ audioMeta }) => {
  const metrics = useMemo(
    () => [
      {
        label: "Delta",
        band: "0.5-4 Hz",
        value: read(audioMeta, "spectral_delta_0_4hz"),
        color: "#7DD3FC",
        tooltip:
          "Delta 0.5-4 Hz: oscilacao lenta do envelope vocal, usada como marcador de carga vegetativa basal e baixa variabilidade dinâmica.",
      },
      {
        label: "Theta",
        band: "4-8 Hz",
        value: read(audioMeta, "spectral_theta_4_8hz"),
        color: "#A5B4FC",
        tooltip:
          "Theta 4-8 Hz: componente de modulação lenta relacionado a flutuações afetivas e organização narrativa sob esforco emocional.",
      },
      {
        label: "Alpha",
        band: "8-12 Hz",
        value: read(audioMeta, "spectral_alpha_8_12hz"),
        color: "#6EE7B7",
        tooltip:
          "Alpha 8-12 Hz: faixa de estabilização moduladora entre ritmos lentos e resposta autônoma mais ativa.",
      },
      {
        label: "Beta",
        band: "12-30 Hz",
        value: read(audioMeta, "spectral_beta_12_30hz"),
        color: "#FBBF24",
        tooltip:
          "Beta 12-30 Hz: ativação rápida associada a tensão cognitiva, vigilância, pressao articulatoria e mobilizacao autônoma.",
      },
      {
        label: "Gama",
        band: "30-80 Hz",
        value: read(audioMeta, "spectral_gamma_30_80hz"),
        color: "#FB7185",
        tooltip:
          "Gama 30-80 Hz: energia espectral de alta frequência, interpretada com cautela como indicador de descarga fina, tensão e aspereza vocal.",
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
                <p className="font-bold text-slate-100">Bandas neuroacusticas</p>
                <p className="mt-1">
                  Leitura das modulações vocais Delta, Theta, Alpha, Beta e
                  Gama da trilha do paciente. A nomenclatura e analogica para
                  bandas de voz, não EEG, consolidada a cada 1 segundo e
                  cruzada com os deltas cepstrais MFCC7/MFCC9.
                </p>
              </div>
            }
          >
            <h3 className="cursor-help text-[13px] font-black text-slate-100">
              Bandas neuroacusticas
            </h3>
          </FroidTooltip>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            Consolidacao bioacustica: {Number(audioMeta?.bioacoustic_window_ms || 1000)}ms
          </p>
        </div>
        <div className="shrink-0 rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
          <p className="text-[8px] font-black uppercase">Índice geral</p>
          <p className="font-mono text-[12px] font-black">{percent(index)}%</p>
        </div>
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
                <p className="mt-1">{metric.tooltip}</p>
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
        <span>DMFCC7 {mfcc7Delta.toFixed(4)}</span>
        <span>DMFCC9 {mfcc9Delta.toFixed(4)}</span>
        <span>DDMFCC7 {mfcc7DeltaDelta.toFixed(4)}</span>
        <span>DDMFCC9 {mfcc9DeltaDelta.toFixed(4)}</span>
      </div>
      {!hasData && (
        <p className="mt-2 text-[9px] italic text-slate-500">
          Aguardando voz do paciente para consolidar as bandas.
        </p>
      )}
    </div>
  );
};
