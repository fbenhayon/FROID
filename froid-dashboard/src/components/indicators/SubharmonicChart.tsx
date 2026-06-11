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

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const percent = (value: number) => Math.round(clamp(value) * 100);

const metricColor = (value: number) => {
  const pct = percent(value);
  if (pct < 15) return "#15803d";
  if (pct < 30) return "#22c55e";
  if (pct < 50) return "#eab308";
  if (pct < 70) return "#f97316";
  return "#dc2626";
};

const readNumber = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
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

    const acoustic5_12 = readNumber(audioMeta, "subharmonic_energy_5_12hz");
    const acoustic12_20 = readNumber(audioMeta, "subharmonic_energy_12_20hz");
    const acoustic85_165 = readNumber(audioMeta, "energy_85_165hz");
    const hasAcoustic =
      acoustic5_12 !== null || acoustic12_20 !== null || acoustic85_165 !== null;

    const dissonanceLoad = clamp(
      arr.filter((zone) => !!zone.facial_dissonance_detected).length / 5,
    );
    const traumaProxy = clamp(zoneLoad(arr, [7, 8, 12]) * 0.72 + dissonanceLoad * 0.28);
    const limbicProxy = clamp(zoneLoad(arr, [2, 8, 11]) * 0.68 + dissonanceLoad * 0.18);
    const tensionProxy = clamp(zoneLoad(arr, [4, 9]) * 0.6 + zoneLoad(arr, [7]) * 0.25);

    const tremor5_12 = acoustic5_12 ?? traumaProxy;
    const upper12_20 = acoustic12_20 ?? limbicProxy;
    const tension85_165 = acoustic85_165 ?? tensionProxy;
    const flooding = clamp(tremor5_12 * 0.58 + tension85_165 * 0.42);
    const shutdown = clamp(tremor5_12 * (1 - tension85_165) + compensationLoad(arr) * 0.32);
    const compensation = compensationLoad(arr);

    const items: Omit<SubharmonicMetric, "color">[] = [
      {
        id: "sna_5_12",
        label: "Tremor SNA profundo",
        band: "5-12 Hz",
        value: tremor5_12,
        source: acoustic5_12 !== null ? "acustico" : "proxy",
        tooltip:
          "Energia sub-harmônica entre 5 e 12 Hz. No motor Python, esta banda rastreia tremores autonômicos profundos ligados a flooding, dissociação e trauma.",
      },
      {
        id: "limbic_12_20",
        label: "Modulação límbica",
        band: "12-20 Hz",
        value: upper12_20,
        source: acoustic12_20 !== null ? "acustico" : "proxy",
        tooltip:
          "Faixa superior de modulação autonômica. Ajuda a separar tensão límbica alta de tremor visceral profundo.",
      },
      {
        id: "vocal_85_165",
        label: "Tensão vocal basal",
        band: "85-165 Hz",
        value: tension85_165,
        source: acoustic85_165 !== null ? "acustico" : "proxy",
        tooltip:
          "Energia vocal basal usada no cruzamento de risco. Quando sobe junto da banda 5-12 Hz, aponta sobrecarga autonômica/flooding.",
      },
      {
        id: "flooding",
        label: "Flooding autonômico",
        band: "5-12 + 85-165",
        value: flooding,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Composição entre tremor profundo e tensão vocal. Representa risco de sobrecarga autonômica ativa.",
      },
      {
        id: "shutdown",
        label: "Shutdown dissociativo",
        band: "SNA - tensão",
        value: shutdown,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Cresce quando há tremor autonômico com baixa energia vocal basal ou muitas zonas compensatórias, sugerindo supressão/dissociação.",
      },
      {
        id: "compensation",
        label: "Compensação zonal",
        band: "Offsetting",
        value: compensation,
        source: "proxy",
        tooltip:
          "Carga de zonas em BRANCO ou com desvio negativo. Mantém a ponte entre o mapa zonal atual e o futuro motor acústico completo.",
      },
    ];

    const clinicalInsight =
      typeof audioMeta?.clinical_insight === "string"
        ? audioMeta.clinical_insight
        : tremor5_12 > 0.4 && tension85_165 > 0.6
          ? "ALERTA SEVERO: sobrecarga autonômica crítica por tremor profundo cruzado com tensão vocal."
          : tremor5_12 > 0.4
            ? "ALERTA DE DISSOCIAÇÃO: tremor autonômico profundo predominando sobre a emissão vocal basal."
            : "Sistema Nervoso Autônomo estável. Fluxo simpático regular.";

    return {
      hasAcousticData: hasAcoustic,
      insight: clinicalInsight,
      metrics: items.map((item) => ({
        ...item,
        color: metricColor(item.value),
      })),
    };
  }, [zones, audioMeta]);

  const dominant = metrics.reduce(
    (top, metric) => (metric.value > top.value ? metric : top),
    metrics[0],
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
      <div className="mb-2 flex shrink-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            DNA Sub-harmônico
          </span>
          <span
            className="ml-2 rounded px-1.5 py-0.5 text-[8px] font-black uppercase text-white"
            style={{ backgroundColor: dominant.color }}
          >
            {dominant.label} {percent(dominant.value)}%
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded px-1.5 py-0.5 text-[8px] font-black uppercase ${
              hasAcousticData ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
            }`}
          >
            {hasAcousticData ? "acústico" : "proxy"}
          </span>
          <FroidTooltip
            content={
              <div className="max-w-[320px]">
                <p className="font-bold">DNA dos sub-harmônicos</p>
                <p className="mt-1 text-[10px] leading-relaxed">
                  O gráfico está preparado para receber as bandas acústicas
                  5-12 Hz, 12-20 Hz e 85-165 Hz. Enquanto elas não chegam do
                  backend, usa proxies de zonas, compensações e dissonâncias.
                </p>
              </div>
            }
            width={340}
          >
            <span className="cursor-help border-b border-dashed border-slate-300 text-[10px] text-slate-400">
              ?
            </span>
          </FroidTooltip>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 auto-rows-fr grid-cols-[minmax(118px,0.95fr)_minmax(120px,1.4fr)_42px_18px] gap-x-2">
        {metrics.map((metric) => (
          <React.Fragment key={metric.id}>
            <div className="flex h-full min-h-0 flex-col justify-center overflow-visible">
              <FroidTooltip
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
                <span className="block cursor-help">
                  <span className="block truncate text-[9px] font-black uppercase leading-none text-slate-700">
                    {metric.label}
                  </span>
                  <span className="mt-0.5 block text-[7px] font-bold uppercase leading-none tracking-wide text-slate-400">
                    {metric.band} - {metric.source}
                  </span>
                </span>
              </FroidTooltip>
            </div>

            <div className="relative flex h-full min-h-0 items-center overflow-visible">
              <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-slate-100" />
              <div
                className="absolute left-0 top-1/2 h-3 -translate-y-1/2 rounded-r-full transition-all duration-1000 ease-out"
                style={{
                  width: `${percent(metric.value)}%`,
                  backgroundColor: metric.color,
                  boxShadow:
                    metric.id === dominant.id ? `0 0 8px ${metric.color}66` : "none",
                }}
                title={metric.tooltip}
              />
              <span
                className="absolute top-1/2 -translate-y-1/2 pl-1 font-mono text-[8px] font-black text-slate-700 transition-all duration-1000 ease-out"
                style={{ left: `min(calc(${percent(metric.value)}% + 3px), 78%)` }}
              >
                {metric.source}
              </span>
            </div>

            <div className="flex h-full min-h-0 items-center justify-end font-mono text-[10px] font-black text-slate-700">
              {percent(metric.value)}%
            </div>

            <div className="flex h-full min-h-0 items-center justify-end">
              <FroidTooltip
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
                <span className="cursor-help text-[10px] font-bold text-slate-400">
                  ?
                </span>
              </FroidTooltip>
            </div>
          </React.Fragment>
        ))}
      </div>

      <p className="mt-1 shrink-0 truncate text-[9px] font-medium text-slate-500">
        {insight}
      </p>
    </div>
  );
};
