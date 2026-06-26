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
  sna_5_12: "#25A84A",
  limbic_12_20: "#3D8FE6",
  vocal_85_165: "#875ED4",
  flooding: "#FF9800",
  shutdown: "#FF4560",
  compensation: "#22B3BE",
};

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const percent = (value: number) => Math.round(clamp(value) * 100);

const polarPoint = (cx: number, cy: number, radius: number, angle: number) => {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
};

const piePath = (
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number,
) => {
  const start = polarPoint(cx, cy, radius, endAngle);
  const end = polarPoint(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
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
        band: "5-12 Hz - acustico",
        value: tremor5_12,
        source: acoustic5_12 !== null ? "acustico" : "proxy",
        tooltip:
          "Energia sub-harmonica entre 5 e 12 Hz. Esta banda rastreia tremores autonomicos profundos ligados a flooding, dissociacao e trauma.",
      },
      {
        id: "limbic_12_20",
        label: "Modulacao limbica",
        band: "12-20 Hz - acustico",
        value: upper12_20,
        source: acoustic12_20 !== null ? "acustico" : "proxy",
        tooltip:
          "Faixa superior de modulacao autonomica. Ajuda a separar tensao limbica alta de tremor visceral profundo.",
      },
      {
        id: "vocal_85_165",
        label: "Tensao vocal basal",
        band: "85-165 Hz - acustico",
        value: tension85_165,
        source: acoustic85_165 !== null ? "acustico" : "proxy",
        tooltip:
          "Energia vocal basal usada no cruzamento de risco. Quando sobe junto da banda 5-12 Hz, aponta sobrecarga autonomica/flooding.",
      },
      {
        id: "flooding",
        label: "Flooding autonomico",
        band: "5-12 + 85-165",
        value: flooding,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Composicao entre tremor profundo e tensao vocal. Representa risco de sobrecarga autonomica ativa.",
      },
      {
        id: "shutdown",
        label: "Shutdown dissociativo",
        band: "SNA - tensao",
        value: shutdown,
        source: hasAcoustic ? "acustico" : "proxy",
        tooltip:
          "Cresce quando ha tremor autonomico com baixa energia vocal basal ou muitas zonas compensatorias, sugerindo supressao/dissociacao.",
      },
      {
        id: "compensation",
        label: "Compensacao zonal",
        band: "Offsetting - proxy",
        value: compensation,
        source: "proxy",
        tooltip:
          "Carga de zonas em BRANCO ou com desvio negativo. Mantem a ponte entre o mapa zonal atual e o futuro motor acustico completo.",
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
  const total = values.reduce((sum, value) => sum + value, 0) || 1;
  const maxValue = Math.max(...values, 1);
  const generalIndex = Math.round(
    values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1),
  );
  let currentAngle = 0;
  const slices = metrics.map((metric) => {
    const value = percent(metric.value);
    const startAngle = currentAngle;
    const sweep = (value / total) * 360;
    const endAngle = startAngle + sweep;
    currentAngle = endAngle;
    const labelPoint = polarPoint(120, 120, 84, startAngle + sweep / 2);
    return { metric, value, startAngle, endAngle, labelPoint };
  });

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-1 flex shrink-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[15px] font-black uppercase tracking-wide text-slate-950">
            DNA Sub-harmonico
          </h3>
          <p className="truncate text-[10px] font-semibold text-slate-500">
            Componente percentual dos indicadores sub-harmonicos.
          </p>
        </div>
        <div className="shrink-0 rounded-2xl border border-blue-100 bg-blue-50 px-3 py-1 text-center text-blue-800">
          <span className="block text-[9px] font-black uppercase">Indice geral</span>
          <strong className="font-mono text-[14px]">{generalIndex}%</strong>
        </div>
      </div>

      <div className="relative min-h-0 flex-[0.95]">
        <svg viewBox="0 0 240 240" className="mx-auto h-full max-h-[208px] w-full">
          {slices.map(({ metric, value, startAngle, endAngle, labelPoint }) => (
            <g key={metric.id} className="cursor-help">
              <title>{`${metric.label}: ${value}%`}</title>
              <path
                d={piePath(120, 120, 78, startAngle, endAngle)}
                fill={metric.color}
                stroke="#ffffff"
                strokeWidth={4}
                className="transition-opacity hover:opacity-90"
              />
              {value >= 8 && (
                <text
                  x={labelPoint.x}
                  y={labelPoint.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-white text-[12px] font-black"
                >
                  {value}%
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pt-1">
        <div className="mb-1">
          <h4 className="text-[12px] font-black text-slate-950">
            Distribuicao dos indicadores
          </h4>
          <p className="text-[10px] font-medium text-slate-500">
            Percentual por componente e descricao tecnica.
          </p>
        </div>
        <div className="space-y-2">
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
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-5 w-3 shrink-0"
                        style={{ backgroundColor: metric.color }}
                      />
                      <div className="min-w-0">
                        <span className="block truncate text-[11px] font-black uppercase text-slate-900">
                          {index + 1}. {metric.label}
                        </span>
                        <span className="block truncate text-[9px] font-bold uppercase tracking-wide text-slate-400">
                          {metric.band} | {metric.source}
                        </span>
                      </div>
                    </div>
                    <span className="font-mono text-[11px] font-black" style={{ color: metric.color }}>
                      {value}%
                    </span>
                  </div>
                  <div className="ml-5 h-2.5 overflow-hidden rounded-full bg-slate-100">
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

      <p className="mt-1 shrink-0 truncate text-[9px] font-medium text-slate-500">
        {dominant.label}: {percent(dominant.value)}% |{" "}
        {hasAcousticData ? "acustico" : "proxy"} | {insight}
      </p>
    </div>
  );
};
