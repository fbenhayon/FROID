import React, { useMemo } from "react";
import { AcousticBiomarkers, PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  zones: PerceptionZone[];
  ipmScore: number;
  coherenceStatus: string;
  baseline?: number | null;
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
}

type RiskItem = {
  id: string;
  label: string;
  scale: string;
  pct: number;
  sharePct: number;
  color: string;
  tooltip: string;
  source: string;
};

const TOOLTIP_TEXT = {
  depression:
    "Risco de Depressão (Depression Risk): deriva diretamente da predição matemática da escala PHQ-9. O algoritmo isola o biomarcador MFCC7 durante a verbalização de conteúdos com valência semântica negativa. Quando este coeficiente se eleva junto a marcadores de retardo psicomotor, como ZCR, pausas prolongadas e menor variação de F0, o percentual de risco depressivo escala.",
  anxiety:
    'Risco de Ansiedade Somática (Anxiety Risk): espelha subescalas de ansiedade e somatização da HAMD. O sistema busca o coeficiente MFCC9 em discurso "neutro"; quedas nos valores acústicos sugerem tensão autônoma latente nas pregas vocais, elevando o risco.',
  mania:
    'Ativação de Mania (Mania Activation): baseada em preditores vocais da YMRS. Monitora pitch/F0 elevado, loudness, taxa acelerada de fala e fluxo espectral mais incisivo ("sharper voice").',
  stress:
    "Estresse Cognitivo (Stress Cognitive): reflete workload contínuo. É detectado por microperturbações laríngeas ciclo a ciclo, com F0 sustentado, Jitter e Shimmer alterados.",
  autonomic:
    "Risco de Dissociação e Trauma: deriva do cruzamento entre infrassom vocal e FACS. Energia sub-harmônica de 5 a 12 Hz, AU15/AU20 e tensão vocal em 85-165 Hz elevam o alerta para flooding, sobrecarga autonômica ou retraumatização.",
};

const clamp = (value: number, min = 0, max = 100) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const mixHex = (from: string, to: string, t: number) => {
  const parse = (hex: string) => ({
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  });
  const a = parse(from);
  const b = parse(to);
  const channel = (start: number, end: number) =>
    Math.round(start + (end - start) * clamp(t, 0, 1))
      .toString(16)
      .padStart(2, "0");

  return `#${channel(a.r, b.r)}${channel(a.g, b.g)}${channel(a.b, b.b)}`;
};

const relativeRiskColor = (relative: number) => {
  const t = clamp(relative, 0, 1);
  if (t < 0.5) return mixHex("#16a34a", "#eab308", t / 0.5);
  if (t < 0.78) return mixHex("#eab308", "#f97316", (t - 0.5) / 0.28);
  return mixHex("#f97316", "#dc2626", (t - 0.78) / 0.22);
};

const RISK_PIE_COLORS: Record<string, string> = {
  depression: "#2C7FB8",
  anxiety: "#FF7F0E",
  mania: "#2CA02C",
  stress: "#D62728",
  autonomic: "#9467BD",
};

const zonePressure = (zones: PerceptionZone[], zoneIds: number[]) => {
  const selected = zoneIds
    .map((id) => zones.find((z) => z.zone === id))
    .filter(Boolean) as PerceptionZone[];

  if (!selected.length) return 0;

  const avgPositive =
    selected.reduce(
      (sum, zone) => sum + Math.max(0, zone.deviation_score || 0),
      0,
    ) / selected.length;

  return clamp(avgPositive * 18, 0, 55);
};

const criticalPeak = (zones: PerceptionZone[]) =>
  clamp(
    Math.max(...zones.map((z) => Math.max(0, z.deviation_score || 0)), 0) * 10,
    0,
    35,
  );

const compensationLoad = (zones: PerceptionZone[]) => {
  const offsets = zones.filter(
    (z) => z.cor_plot === "BRANCO" || (z.deviation_score || 0) < -0.3,
  );
  return clamp(offsets.length * 6, 0, 30);
};

const readNumber = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const readText = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
};

const calculateDeviation = (
  current: number | null,
  baseline: number | null,
) => {
  if (current === null || baseline === null) return null;
  return (current - baseline) / (Math.abs(baseline) + 1e-9);
};

export const RiskChart: React.FC<Props> = ({
  zones,
  ipmScore,
  coherenceStatus,
  baseline,
  audioMeta,
}) => {
  const risks = useMemo<RiskItem[]>(() => {
    const arr = Array.isArray(zones)
      ? zones.filter((z) => z && typeof z.zone === "number")
      : [];

    const dissonanceCount = arr.filter(
      (z) => !!z.facial_dissonance_detected,
    ).length;
    const dissonanceLoad = clamp(dissonanceCount * 12, 0, 36);
    const ipmLoad = clamp((ipmScore - 50) * 0.9, 0, 32);
    const peakLoad = criticalPeak(arr);
    const offsetLoad = compensationLoad(arr);
    const isEmbotamento = coherenceStatus === "EMBOTAMENTO";
    const isCoherenceAlert =
      coherenceStatus !== "NEUTRO" && coherenceStatus !== "COERENTE";
    const valence = (
      readText(audioMeta, "substancia_semantica") ||
      readText(audioMeta, "semantic_valence") ||
      ""
    ).toUpperCase();
    const devMfcc7 =
      readNumber(audioMeta, "desvio_mfcc7") ??
      calculateDeviation(
        readNumber(audioMeta, "mfcc7"),
        readNumber(audioMeta, "baseline_mfcc7"),
      );
    const devMfcc9 =
      readNumber(audioMeta, "desvio_mfcc9") ??
      calculateDeviation(
        readNumber(audioMeta, "mfcc9"),
        readNumber(audioMeta, "baseline_mfcc9"),
      );
    const hasSpectralBiopsy =
      valence === "NEGATIVO" ||
      valence === "NEUTRO" ||
      devMfcc7 !== null ||
      devMfcc9 !== null;
    const depressionSpectral =
      valence === "NEGATIVO" && devMfcc7 !== null
        ? clamp(35 + Math.max(0, devMfcc7) * 125, 0, 100)
        : null;
    const anxietySpectral =
      valence === "NEUTRO" && devMfcc9 !== null
        ? clamp(35 + Math.abs(Math.min(0, devMfcc9)) * 135, 0, 100)
        : null;
    const maskedDepression =
      valence === "NEGATIVO" &&
      (devMfcc7 ?? 0) > 0.35 &&
      (devMfcc9 ?? 0) < -0.3;

    const dissociationRaw =
      zonePressure(arr, [4, 9, 12]) * 0.8 +
      offsetLoad +
      (isEmbotamento ? 22 : 0);
    const traumaRaw =
      zonePressure(arr, [7, 8, 12]) + dissonanceLoad + peakLoad * 0.55;
    const depressionProxy =
      zonePressure(arr, [1, 3, 9, 10]) +
      (isEmbotamento ? 18 : 0) +
      offsetLoad * 0.45;
    const anxietyProxy =
      zonePressure(arr, [4, 8, 11]) +
      ipmLoad * 0.7 +
      (isCoherenceAlert ? 12 : 0);
    const stressProxy =
      zonePressure(arr, [2, 11, 12]) + ipmLoad * 0.6 + peakLoad * 0.45;

    const definitions = [
      {
        id: "depression",
        label: "Depressão",
        scale: "PHQ-9",
        pct: Math.max(depressionProxy, depressionSpectral ?? 0) + (maskedDepression ? 8 : 0),
        tooltip:
          depressionSpectral !== null
            ? `${TOOLTIP_TEXT.depression} Biópsia espectral ativa: substância=${valence}, desvio MFCC7=${devMfcc7?.toFixed(4)}.`
            : TOOLTIP_TEXT.depression,
        source: depressionSpectral !== null ? "bioacústico" : "proxy",
      },
      {
        id: "anxiety",
        label: "Ansiedade somática",
        scale: "HAMD",
        pct: Math.max(anxietyProxy, anxietySpectral ?? 0) + (maskedDepression ? 8 : 0),
        tooltip:
          anxietySpectral !== null
            ? `${TOOLTIP_TEXT.anxiety} Biópsia espectral ativa: substância=${valence}, desvio MFCC9=${devMfcc9?.toFixed(4)}.`
            : TOOLTIP_TEXT.anxiety,
        source: anxietySpectral !== null ? "bioacústico" : "proxy",
      },
      {
        id: "mania",
        label: "Ativação de mania",
        scale: "YMRS",
        pct: ipmLoad * 1.2 + zonePressure(arr, [2, 7]) * 0.55 + peakLoad * 0.35,
        tooltip: TOOLTIP_TEXT.mania,
        source: "proxy",
      },
      {
        id: "stress",
        label: "Estresse cognitivo",
        scale: "Workload",
        pct: stressProxy + (maskedDepression ? 10 : 0),
        tooltip:
          maskedDepression && hasSpectralBiopsy
            ? `${TOOLTIP_TEXT.stress} Risco dual ativo: MFCC7 elevado com MFCC9 em queda durante valência negativa.`
            : TOOLTIP_TEXT.stress,
        source: maskedDepression ? "bioacústico" : "proxy",
      },
      {
        id: "autonomic",
        label: "Dissociação / Trauma",
        scale: "SNA",
        pct:
          Math.max(traumaRaw, dissociationRaw) +
          Math.min(traumaRaw, dissociationRaw) * 0.25,
        tooltip: TOOLTIP_TEXT.autonomic,
        source: "proxy",
      },
    ];

    const normalized = definitions.map((risk) => ({
      ...risk,
      pct: Math.round(clamp(risk.pct)),
    }));
    const total = normalized.reduce((sum, risk) => sum + risk.pct, 0);
    const minPct = Math.min(...normalized.map((risk) => risk.pct));
    const maxPct = Math.max(...normalized.map((risk) => risk.pct));
    const range = maxPct - minPct;

    return normalized.map((risk) => {
      const relative = range > 0 ? (risk.pct - minPct) / range : risk.pct / 100;
      return {
        ...risk,
        sharePct: total > 0 ? Math.round((risk.pct / total) * 100) : 0,
        color: relativeRiskColor(relative),
      };
    });
  }, [zones, ipmScore, coherenceStatus, audioMeta]);
  const generalRiskIndex = Math.round(
    risks.reduce((sum, risk) => sum + risk.sharePct, 0) /
      Math.max(risks.length, 1),
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-[14px] border border-[#263a61] bg-[#050a1a] p-3 text-white shadow-sm">
      <div className="mb-3 flex shrink-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[14px] font-black text-white">
            Distribuicao dos riscos
          </h3>
          <p className="truncate text-[10px] font-medium text-[#9bc9ff]">
            Resumo percentual por categoria
            {typeof baseline === "number" && Number.isFinite(baseline)
              ? ` | IPM 60s ${baseline.toFixed(1)}`
              : ""}
          </p>
        </div>
        <div className="shrink-0 rounded-[14px] border border-[#4e7cff] bg-[#143b87] px-4 py-2 text-center text-white">
          <span className="block text-[8px] font-black uppercase tracking-wide">
            Indice geral
          </span>
          <strong className="font-mono text-[14px]">{generalRiskIndex}%</strong>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {risks.map((risk, index) => {
          const color = RISK_PIE_COLORS[risk.id] || risk.color;
          return (
            <FroidTooltip
              key={risk.id}
              content={
                <div className="max-w-[360px]">
                  <p className="font-bold">
                    {index + 1}. {risk.label} ({risk.scale})
                  </p>
                  <p className="mt-1 text-[10px] leading-relaxed">
                    {risk.tooltip}
                  </p>
                </div>
              }
              width={380}
            >
              <div className="cursor-help">
                <div className="mb-1 flex min-w-0 items-center gap-2">
                  <span
                    className="h-3.5 w-3.5 shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="min-w-0 flex-1 truncate text-[12px] font-black text-white">
                    {index + 1}. {risk.label}
                  </span>
                  <span className="font-mono text-[11px] font-black text-white">
                    {risk.sharePct}%
                  </span>
                </div>
                <div className="ml-5 h-2.5 overflow-hidden rounded-full bg-[#25314a]">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.max(3, Math.min(100, risk.sharePct))}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
              </div>
            </FroidTooltip>
          );
        })}
      </div>
    </div>
  );
};
