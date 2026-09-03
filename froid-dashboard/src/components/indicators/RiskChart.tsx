import React, { useMemo } from "react";
import { AcousticBiomarkers, PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

interface Props {
  zones: PerceptionZone[];
  /** Nulo quando nao houve apuracao — ver o portao em LiveSession. */
  ipmScore: number | null;
  coherenceStatus: string;
  baseline?: number | null;
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
  locale?: SessionLocale;
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

// Padrões de sinal, não condições clínicas.
//
// Estes cinco itens exibiam percentuais para "Depressão", "Ansiedade
// somática", "Ativação de mania" e "Dissociação / trauma", cada um crachado
// com o nome de um instrumento validado — PHQ-9, HAMD, YMRS. O FROID não
// aplica nenhum desses questionários e não foi validado contra nenhum deles: o
// cálculo é composição de pressão zonal com constantes ajustadas à mão. A
// procedência declarada não correspondia à implementação, e exibir o nome de
// um instrumento de terceiros empresta uma credibilidade que não pode ser
// conferida.
//
// A literatura por trás das associações é real e continua citada — agora no
// lugar certo: como associação observada em nível de grupo, e não como
// inferência sobre a pessoa na tela. A função de indicação para o profissional
// não se perde. Ele lê o padrão medido e forma a hipótese, que é o que o
// registro dele exige de qualquer forma.
//
// Ver knowledge/approved/Notas_tecnicas_FROID/FROID_Fronteira_Medida_Interpretacao.md
const RESSALVA =
  "Associação observada em nível de grupo na literatura; não constitui inferência sobre este paciente. A leitura clínica é do profissional.";

export const TOOLTIP_TEXT = {
  depression: `Lentificação psicomotora vocal: composto de MFCC7, ZCR, pausas e variação de F0, lido contra a linha de base deste paciente. O componente sobe quando o MFCC7 se eleva durante fala de valência negativa junto a fala mais lenta, pausas mais longas e menor variação de altura. A literatura associa esse padrão acústico à lentificação psicomotora descrita em quadros depressivos. ${RESSALVA}`,
  anxiety: `Tensão laríngea sustentada: acompanha o coeficiente MFCC9 em fala neutra, contra a referência do próprio paciente. Quedas sustentadas nesse coeficiente são descritas na literatura como correlato acústico de tensão na musculatura laríngea. ${RESSALVA}`,
  mania: `Ativação prosódica: composto de F0, loudness e taxa de fala, com fluxo espectral mais incisivo. Mede elevação simultânea de altura, intensidade e velocidade em relação à linha de base deste paciente. ${RESSALVA}`,
  stress: `Esforço vocal sustentado: composto de F0 sustentado, ZCR e os índices proxy de jitter e shimmer. Descreve carga articulatória contínua. Os índices são estimativas por quadros e não equivalem a medidas normativas de laboratório em % ou dB.`,
  autonomic: `Assinatura sub-harmônica com retração facial: cruzamento entre energia sub-harmônica de 5 a 12 Hz, as Unidades de Ação AU15 e AU20 e tensão vocal na faixa de 85 a 165 Hz. Mede co-ocorrência entre canais, não estado interno. ${RESSALVA}`,
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
  locale = "pt-BR",
}) => {
  const risks = useMemo<RiskItem[]>(() => {
    const arr = Array.isArray(zones)
      ? zones.filter((z) => z && typeof z.zone === "number")
      : [];

    const dissonanceCount = arr.filter(
      (z) => !!z.facial_dissonance_detected,
    ).length;
    const dissonanceLoad = clamp(dissonanceCount * 12, 0, 36);
    // Sem IPM medido nao ha carga de IPM. Tratar null como 0 daria
    // `clamp((0-50)*0.9, 0, 32)` = 0 por acidente, mas por caminho errado —
    // e qualquer mudanca no clamp passaria a somar risco sobre nada.
    const ipmLoad = ipmScore === null ? 0 : clamp((ipmScore - 50) * 0.9, 0, 32);
    const peakLoad = criticalPeak(arr);
    const offsetLoad = compensationLoad(arr);
    const isEmbotamento = coherenceStatus === "EMBOTAMENTO";
    // Ausencia de medida NAO e alerta.
    //
    // A condicao era "qualquer coisa que nao seja NEUTRO nem COERENTE", e o
    // motor passou a emitir "SEM_APURACAO" quando nao mede nada. Sem esta
    // guarda, a falta de audio somava +12 ao risco e, com todo o resto nulo,
    // virava 100% de "tensao laringea sustentada" — um alarme clinico
    // fabricado justamente pela mudanca que veio acabar com a fabricacao.
    const semApuracao = !coherenceStatus || coherenceStatus === "SEM_APURACAO";
    const isCoherenceAlert =
      !semApuracao
      && coherenceStatus !== "NEUTRO"
      && coherenceStatus !== "COERENTE";
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
        label: "Lentificação psicomotora vocal",
        scale: "MFCC7 + ZCR + pausas + F0",
        pct: Math.max(depressionProxy, depressionSpectral ?? 0) + (maskedDepression ? 8 : 0),
        tooltip:
          depressionSpectral !== null
            ? `${TOOLTIP_TEXT.depression} Biópsia espectral ativa: substância=${valence}, desvio MFCC7=${devMfcc7?.toFixed(4)}.`
            : TOOLTIP_TEXT.depression,
        source: depressionSpectral !== null ? "bioacústico" : "proxy",
      },
      {
        id: "anxiety",
        label: "Tensão laríngea sustentada",
        scale: "MFCC9 em fala neutra",
        pct: Math.max(anxietyProxy, anxietySpectral ?? 0) + (maskedDepression ? 8 : 0),
        tooltip:
          anxietySpectral !== null
            ? `${TOOLTIP_TEXT.anxiety} Biópsia espectral ativa: substância=${valence}, desvio MFCC9=${devMfcc9?.toFixed(4)}.`
            : TOOLTIP_TEXT.anxiety,
        source: anxietySpectral !== null ? "bioacústico" : "proxy",
      },
      {
        id: "mania",
        label: "Ativação prosódica",
        scale: "F0 + loudness + taxa",
        pct: ipmLoad * 1.2 + zonePressure(arr, [2, 7]) * 0.55 + peakLoad * 0.35,
        tooltip: TOOLTIP_TEXT.mania,
        source: "proxy",
      },
      {
        id: "stress",
        label: "Esforço vocal sustentado",
        scale: "F0 + ZCR + jitter/shimmer",
        pct: stressProxy + (maskedDepression ? 10 : 0),
        tooltip:
          maskedDepression && hasSpectralBiopsy
            ? `${TOOLTIP_TEXT.stress} Padrão duplo ativo: MFCC7 elevado com MFCC9 em queda durante fala de valência negativa.`
            : TOOLTIP_TEXT.stress,
        source: maskedDepression ? "bioacústico" : "proxy",
      },
      {
        id: "autonomic",
        label: "Assinatura sub-harmônica",
        scale: "5-12 Hz + AU15/AU20",
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
  const maxRiskShare = Math.max(...risks.map((risk) => risk.sharePct), 1);

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      <div className="mb-1.5 flex shrink-0 items-start justify-between gap-3">
        <FroidTooltip
          width={360}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Padrões de sinal")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Participação relativa de cinco padrões acústicos e faciais medidos, a partir do cruzamento entre voz, face e zonas, sempre contra a linha de base deste paciente. Nenhuma barra nomeia condição clínica nem constitui diagnóstico: passe o mouse em cada padrão para ver quais sinais o compõem e o que a literatura associa a ele.",
                )}
              </p>
            </div>
          }
        >
          <div className="min-w-0 cursor-help">
            <h3 className="text-[12px] font-black text-slate-100">
              Padrões de sinal
            </h3>
            <p className="truncate text-[9px] font-medium text-slate-400">
              Resumo percentual por categoria
              {typeof baseline === "number" && Number.isFinite(baseline)
                ? ` | IPM 60s ${baseline.toFixed(1)}`
                : ""}
            </p>
          </div>
        </FroidTooltip>
        <FroidTooltip
          width={300}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Intensidade agregada")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Média da participação relativa dos cinco padrões. Dá uma leitura rápida da carga de sinal do momento; para detalhar, observe qual padrão específico está elevado.",
                )}
              </p>
            </div>
          }
        >
          <div className="shrink-0 cursor-help rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
            <span className="block text-[7px] font-black uppercase">
              Índice geral
            </span>
            <strong className="font-mono text-[11px]">{generalRiskIndex}%</strong>
          </div>
        </FroidTooltip>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-hidden pr-1">
        {risks.map((risk, index) => {
          const color = RISK_PIE_COLORS[risk.id] || risk.color;
          return (
            <div key={risk.id} className="block w-full">
              <FroidTooltip
                fullWidth
                content={
                  <div className="max-w-[360px]">
                    <p className="font-bold">
                      {index + 1}. {risk.label} ({risk.scale})
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed">
                      {tooltipText(locale, risk.tooltip)}
                    </p>
                  </div>
                }
                width={380}
              >
                <div className="w-full cursor-help">
                  <div className="mb-1 grid min-w-0 grid-cols-[12px_minmax(0,1fr)_48px] items-center gap-2">
                    <span
                      className="h-5 w-3 rounded-sm"
                      style={{ backgroundColor: color }}
                    />
                    <span className="min-w-0 truncate text-[10px] font-black leading-tight text-slate-100">
                      {index + 1}. {risk.label}
                    </span>
                    <span className="text-right font-mono text-[10px] font-black text-white">
                      {risk.sharePct}%
                    </span>
                  </div>
                  <div className="ml-5 h-2.5 w-[calc(100%-1.25rem)] overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.max(3, (risk.sharePct / maxRiskShare) * 100)}%`,
                        backgroundColor: color,
                      }}
                    />
                  </div>
                </div>
              </FroidTooltip>
            </div>
          );
        })}
      </div>
    </div>
  );
};
