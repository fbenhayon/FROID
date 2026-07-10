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
          "Delta 0.5-4 Hz: oscilacao lenta do envelope vocal, usada como marcador de carga vegetativa basal e baixa variabilidade dinamica.",
      },
      {
        label: "Theta",
        band: "4-8 Hz",
        value: read(audioMeta, "spectral_theta_4_8hz"),
        color: "#A5B4FC",
        tooltip:
          "Theta 4-8 Hz: componente de modulacao lenta relacionado a flutuacoes afetivas e organizacao narrativa sob esforco emocional.",
      },
      {
        label: "Alpha",
        band: "8-12 Hz",
        value: read(audioMeta, "spectral_alpha_8_12hz"),
        color: "#6EE7B7",
        tooltip:
          "Alpha 8-12 Hz: faixa de estabilizacao moduladora entre ritmos lentos e resposta autonoma mais ativa.",
      },
      {
        label: "Beta",
        band: "12-30 Hz",
        value: read(audioMeta, "spectral_beta_12_30hz"),
        color: "#FBBF24",
        tooltip:
          "Beta 12-30 Hz: ativacao rapida associada a tensao cognitiva, vigilancia, pressao articulatoria e mobilizacao autonoma.",
      },
      {
        label: "Gama",
        band: "30-80 Hz",
        value: read(audioMeta, "spectral_gamma_30_80hz"),
        color: "#FB7185",
        tooltip:
          "Gama 30-80 Hz: energia espectral de alta frequencia, interpretada com cautela como indicador de descarga fina, tensao e aspereza vocal.",
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

  return (
    <div className="h-full rounded-xl border border-slate-700 bg-slate-900 p-3 text-slate-100 shadow-sm">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <FroidTooltip
            width={360}
            content={
              <div>
                <p className="font-bold text-slate-100">Bandas neuroacusticas</p>
                <p className="mt-1">
                  Leitura das modulacoes Delta, Theta, Alpha, Beta e Gama da
                  trilha do paciente, consolidada a cada 1 segundo e cruzada
                  com os deltas cepstrais MFCC7/MFCC9.
                </p>
              </div>
            }
          >
            <h3 className="cursor-help text-[11px] font-bold uppercase tracking-wider text-cyan-200">
              Bandas neuroacusticas
            </h3>
          </FroidTooltip>
          <p className="mt-0.5 text-[9px] text-slate-400">
            Consolidacao bioacustica: {Number(audioMeta?.bioacoustic_window_ms || 1000)}ms
          </p>
        </div>
        <div className="rounded border border-cyan-700 bg-cyan-950 px-2 py-1 text-right">
          <p className="text-[8px] uppercase text-cyan-300">Indice</p>
          <p className="font-mono text-sm font-black text-cyan-100">{percent(index)}%</p>
        </div>
      </div>

      <div className="space-y-2">
        {metrics.map((metric) => (
          <FroidTooltip
            key={metric.label}
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
            <div className="cursor-help">
              <div className="mb-1 flex items-center justify-between text-[9px]">
                <span className="font-bold uppercase tracking-wide text-slate-200">
                  {metric.label} <span className="text-slate-500">{metric.band}</span>
                </span>
                <span className="font-mono text-slate-300">{percent(metric.value)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${percent(metric.value)}%`,
                    backgroundColor: metric.color,
                  }}
                />
              </div>
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
