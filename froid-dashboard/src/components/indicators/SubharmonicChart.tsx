import React, { useMemo } from "react";
import { AcousticBiomarkers, PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  zones: PerceptionZone[];
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
}

type SubharmonicMetric = {
  id: string;
  label: string;
  band: string;
  value: number;
  color: string;
  source: "acustico" | "proxy";
  tooltip: string;
};

const DNA_COLORS: Record<string, string> = {
  nuclear_infrasound: "#5CC9FF",
  limbic_12_20: "#6B8CFF",
  vocal_85_165: "#9A5BFF",
  flooding: "#FFB22E",
  shutdown: "#FF5D9B",
  neurogenic: "#66D7FF",
  somatoaffective: "#6EF2A8",
};

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const percent = (value: number) => Math.round(clamp(value) * 100);

const readNumber = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const readMetaNumber = (
  audioMeta: Props["audioMeta"],
  key: string,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const readMetric = (
  audioMeta: Props["audioMeta"],
  preferredKey: keyof AcousticBiomarkers,
  fallbackKey?: keyof AcousticBiomarkers,
) => {
  const preferred = readNumber(audioMeta, preferredKey);
  if (preferred !== null) return preferred;
  return fallbackKey ? readNumber(audioMeta, fallbackKey) : null;
};

const zoneLoad = (zones: PerceptionZone[], ids: number[]) => {
  const selected = ids
    .map((id) => zones.find((zone) => zone.zone === id))
    .filter(Boolean) as PerceptionZone[];

  if (!selected.length) return 0;

  const average =
    selected.reduce(
      (sum, zone) => sum + Math.max(0, zone.deviation_score || 0),
      0,
    ) / selected.length;

  return clamp(average / 4);
};

const compensationLoad = (zones: PerceptionZone[]) => {
  const offsets = zones.filter(
    (zone) => zone.cor_plot === "BRANCO" || (zone.deviation_score || 0) < -0.3,
  );
  return clamp(offsets.length / 6);
};

export const SubharmonicChart: React.FC<Props> = ({ zones, audioMeta }) => {
  const { metrics, insight, hasAcousticData } = useMemo(() => {
    const arr = Array.isArray(zones)
      ? zones.filter((zone) => zone && typeof zone.zone === "number")
      : [];

    const acoustic5_12 = readMetric(
      audioMeta,
      "dna_infrasound_nuclear",
      "subharmonic_energy_5_12hz",
    );
    const acoustic12_20 = readMetric(
      audioMeta,
      "dna_limbic_modulation",
      "subharmonic_energy_12_20hz",
    );
    const acoustic85_165 = readMetric(
      audioMeta,
      "dna_vocal_basal_tension",
      "energy_85_165hz",
    );
    const acoustic20_40 =
      readMetric(audioMeta, "dna_neurogenic_resonance", "subharmonic_energy_20_40hz") ??
      readMetaNumber(audioMeta, "subharmonic_energy_20_40hz");
    const acousticFlooding = readNumber(audioMeta, "dna_autonomic_flooding");
    const acousticShutdown = readNumber(audioMeta, "dna_dissociative_shutdown");
    const acousticSomato = readNumber(audioMeta, "dna_somatoaffective_dissonance");
    const hasAcoustic =
      acoustic5_12 !== null ||
      acoustic12_20 !== null ||
      acoustic85_165 !== null ||
      acoustic20_40 !== null;

    const dissonanceLoad = clamp(
      arr.filter((zone) => !!zone.facial_dissonance_detected).length / 5,
    );
    const traumaProxy = clamp(zoneLoad(arr, [7, 8, 12]) * 0.72 + dissonanceLoad * 0.28);
    const limbicProxy = clamp(zoneLoad(arr, [2, 8, 11]) * 0.68 + dissonanceLoad * 0.18);
    const tensionProxy = clamp(zoneLoad(arr, [4, 9]) * 0.6 + zoneLoad(arr, [7]) * 0.25);

    const tremor5_12 = acoustic5_12 ?? traumaProxy;
    const upper12_20 = acoustic12_20 ?? limbicProxy;
    const tension85_165 = acoustic85_165 ?? tensionProxy;
    const flooding = acousticFlooding ?? clamp(tremor5_12 * 0.58 + tension85_165 * 0.42);
    const shutdown =
      acousticShutdown ??
      clamp(tremor5_12 * (1 - tension85_165) + compensationLoad(arr) * 0.32);
    const neurogenic = acoustic20_40 ?? clamp(upper12_20 * 0.44 + dissonanceLoad * 0.22);
    const somatoaffective =
      acousticSomato ??
      clamp(tremor5_12 * 0.34 + tension85_165 * 0.34 + dissonanceLoad * 0.32);

    const items: Omit<SubharmonicMetric, "color">[] = [
      {
        id: "nuclear_infrasound",
        label: "Infrassom Nuclear",
        band: "5-12 Hz | Tremor SNA profundo",
        value: tremor5_12,
        source: acoustic5_12 !== null ? "acustico" : "proxy",
        tooltip:
          "Infrassom Nuclear: leitura da faixa 5-12 Hz, associada a tremor profundo do Sistema Nervoso Autonomo e ativacao inconsciente.",
      },
      {
        id: "limbic_12_20",
        label: "Modulacao limbica",
        band: "12-20 Hz | Reatividade afetiva",
        value: upper12_20,
        source: acoustic12_20 !== null ? "acustico" : "proxy",
        tooltip:
          "Modulacao Limbica: faixa 12-20 Hz, usada para estimar reatividade afetiva e variacao autonoma ligada a estados emocionais.",
      },
      {
        id: "vocal_85_165",
        label: "Tensao vocal basal",
        band: "85-165 Hz | Rigidez laringea",
        value: tension85_165,
        source: acoustic85_165 !== null ? "acustico" : "proxy",
        tooltip:
          "Tensao Vocal Basal: faixa 85-165 Hz, relacionada a rigidez laringea, hipercontrole vocal e esforco de sustentacao.",
      },
      {
        id: "flooding",
        label: "Flooding autonomico",
        band: "5-12 + 85-165 Hz | Colisao autonoma",
        value: flooding,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Flooding Autonomico: colisao entre energia 5-12 Hz e tensao vocal basal, indicando sobrecarga neurofisiologica ativa.",
      },
      {
        id: "shutdown",
        label: "Shutdown dissociativo",
        band: "Queda energetica | Coerencia reduzida",
        value: shutdown,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Shutdown Dissociativo: queda energetica com reducao de coerencia, sugerindo supressao defensiva, embotamento ou retraimento autonomico.",
      },
      {
        id: "neurogenic",
        label: "Ressonancia neurogenica",
        band: "20-40 Hz | Descarga vegetativa",
        value: neurogenic,
        source: acoustic20_40 !== null ? "acustico" : "proxy",
        tooltip:
          "Ressonancia Neurogenica: faixa 20-40 Hz, associada a descarga vegetativa, regulacao autonoma e reorganizacao neurofisiologica.",
      },
      {
        id: "somatoaffective",
        label: "Dissonancia somatoafetiva",
        band: "Calma verbal x tensao sub-harmonica",
        value: somatoaffective,
        source: "proxy",
        tooltip:
          "Dissonancia Somatoafetiva: contraste entre calma verbal aparente e tensao sub-harmonica, indicando possivel conflito corpo-fala.",
      },
    ];

    const clinicalInsight =
      typeof audioMeta?.clinical_insight === "string"
        ? audioMeta.clinical_insight
        : tremor5_12 > 0.4 && tension85_165 > 0.6
          ? "ALERTA SEVERO: sobrecarga autonomica critica por tremor profundo cruzado com tensao vocal."
          : tremor5_12 > 0.4
            ? "ALERTA DE DISSOCIACAO: tremor autonomico profundo predominando sobre a emissao vocal basal."
            : "Sistema Nervoso Autonomo estavel. Fluxo simpatico regular.";

    return {
      hasAcousticData: hasAcoustic,
      insight: clinicalInsight,
      metrics: items.map((item) => ({
        ...item,
        color: DNA_COLORS[item.id] || "#64748B",
      })),
    };
  }, [zones, audioMeta]);

  const dominant = metrics.reduce(
    (top, metric) => (metric.value > top.value ? metric : top),
    metrics[0],
  );
  const values = metrics.map((metric) => percent(metric.value));
  const maxValue = Math.max(...values, 1);
  const generalIndex = Math.round(
    values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1),
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      <div className="mb-1.5 flex shrink-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[13px] font-black text-slate-100">
            Sub-harmonicos
          </h3>
          <p className="truncate text-[10px] font-medium text-slate-400">
            Percentual por componente e substancia tecnica
          </p>
        </div>
        <div className="shrink-0 rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
          <span className="block text-[8px] font-black uppercase">
            Indice geral
          </span>
          <strong className="font-mono text-[12px]">{generalIndex}%</strong>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden pr-1">
        <div className="space-y-1">
          {metrics.map((metric, index) => {
            const value = percent(metric.value);
            return (
              <FroidTooltip
                key={metric.id}
                content={
                  <div className="max-w-[340px]">
                    <p className="font-bold">
                      {metric.label} ({metric.band})
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed">
                      {metric.tooltip}
                    </p>
                  </div>
                }
                width={360}
              >
                <div className="cursor-help">
                  <div className="mb-0.5 grid min-w-0 grid-cols-[10px_minmax(0,1fr)_42px] items-start gap-1.5">
                    <span
                      className="mt-0.5 h-4 w-2.5"
                      style={{ backgroundColor: metric.color }}
                    />
                    <div className="min-w-0">
                      <span className="block truncate text-[10px] font-black leading-tight text-slate-100">
                        {index + 1}. {metric.label}
                      </span>
                      <span className="block truncate text-[8px] font-bold leading-tight tracking-wide text-[#9bc9ff]">
                        {metric.band}
                      </span>
                    </div>
                    <span
                      className="rounded-full border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-center font-mono text-[10px] font-black"
                      style={{ color: metric.color }}
                    >
                      {value}%
                    </span>
                  </div>
                  <div className="ml-4 h-1.5 w-[calc(100%-1rem)] overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${(value / maxValue) * 100}%`,
                        backgroundColor: metric.color,
                      }}
                    />
                  </div>
                </div>
              </FroidTooltip>
            );
          })}
        </div>
      </div>

      <p className="mt-1 shrink-0 truncate text-[8px] font-medium text-slate-400">
        {dominant.label}: {percent(dominant.value)}% |{" "}
        {hasAcousticData ? "acustico" : "proxy"} | {insight}
      </p>
    </div>
  );
};
