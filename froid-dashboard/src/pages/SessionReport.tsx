import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import { apiUrl } from "../lib/api";
import {
  formatDuration,
  loadSessionReport,
  MetricsAnalysis,
  MetricSnapshot,
  SessionReportRecord,
} from "../lib/session-report";
import { dashboardText, loadSessionLanguagePreferences, normalizeSessionLocale, type SessionLocale } from "../lib/localization";
import { tooltipText } from "../lib/tooltip-i18n";
import { InstrumentScorePrompt } from "../components/validation/InstrumentScorePrompt";
import { activeOrganizationId } from "../lib/validation";
import {
  buildReport,
  openPrintable,
  type ReportAudience,
} from "../lib/report-pdf";

interface Props {
  user?: any;
}

const DEFAULT_SECTIONS = {
  evolution: true,
  statistics: true,
  baseline: true,
  averages: true,
  cuts: true,
  summaries: true,
  notes: true,
  dissonances: true,
};

type SectionKey = keyof typeof DEFAULT_SECTIONS;
const SESSION_SUMMARY_MAX_WORDS = 300;

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return Number(value).toFixed(digits);
}

function fmtPct(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function limitWords(text: string, maxWords: number) {
  return String(text || "").trim().split(/\s+/).filter(Boolean).slice(0, maxWords).join(" ");
}

function limitThemeWords(text: string, maxWords = 6) {
  const dangling = new Set(["e", "ou", "de", "da", "do", "das", "dos", "com", "em", "para"]);
  const words = cleanSummaryText(text).split(/\s+/).filter(Boolean).slice(0, maxWords);
  while (words.length > 1 && dangling.has(words[words.length - 1].toLowerCase())) {
    words.pop();
  }
  return words.join(" ");
}

function cleanSummaryText(text: string) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();
}

function hasSubstantiveSummary(text: string) {
  const normalized = cleanSummaryText(text).toLowerCase();
  if (!normalized) return false;
  return ![
    "nenhuma fala foi transcrita",
    "sem fala transcrita",
    "resumo geral indisponível",
    "ausência de transcrição",
  ].some((token) => normalized.includes(token));
}

const TITLE_TOOLTIPS: Record<string, string> = {
  "Linha comparativa da sessão":
    "Compara o baseline inicial de 60 segundos com a média consolidada da sessão.",
  "Evolução FROID":
    "Gráfico normalizado pelo baseline inicial. A linha 100 representa o ponto de partida da sessão.",
  "Leitura estatística das métricas":
    "Resume baseline, média, último corte, delta e escore-z das métricas evolutivas do FROID.",
  "Composição do relatório":
    "Permite escolher quais blocos entram na visualização e no relatório da consulta.",
  "Parâmetros iniciais - 60 segundos":
    "Primeira fotografia bioacústica e multimodal da sessão, tomada após a ativação do áudio do paciente.",
  "Média das métricas da sessão":
    "Média consolidada dos marcadores coletados durante todo o período analisado da sessão.",
  "Cortes da sessão":
    "Cortes temporais da sessão, incluindo cortes manuais do profissional e cortes automáticos obrigatórios a cada 10 minutos após o último corte.",
  "Resumo geral da sessão":
    "Síntese analítica final da sessão, limitada a 300 palavras, com tema predominante de até 6 palavras.",
  "Transcrição da sessão":
    "Fala literal captada na sessão, em ordem cronológica, com o falante identificado por canal de áudio: DR para o profissional, PC para o paciente.",
  "Temas e Resumos por Cortes":
    "Resumo e métricas de cada corte temporal, alinhando tema, síntese semântica e marcadores multimodais do mesmo período.",
  "Observações do profissional":
    "Anotações clínicas registradas manualmente pelo profissional durante a sessão.",
  "Dissonâncias registradas":
    "Lista apenas dissonâncias persistentes acima do limiar clínico configurado.",
  "Relatório Descritivo":
    "Campo editável para o profissional montar texto a copiar, enviar ou futuramente imprimir.",
};

const METRIC_TOOLTIPS: Record<string, string> = {
  Corte: "Intervalo temporal efetivamente analisado no corte da sessão.",
  IPM: "Índice de Potência Multimodal: intensidade global ou energia emocional empregada.",
  IDM: "Índice de Desvio Multimodal: direção e grau do desequilíbrio multimodal.",
  ZONAS: "Zona FROID dominante no período analisado.",
  Tema: "Tema predominante consolidado da sessão ou do bloco analisado.",
  Tom: "Tom emocional inferido pela combinação vocal e semântica.",
  "P/min": "Palavras por minuto no período analisado.",
  "Disso.": "Quantidade de dissonâncias facial-vocais persistentes registradas.",
  MFCC7: "Biomarcador acústico associado a conteúdo de valência negativa e risco depressivo quando combinado a outros sinais.",
  MFCC9: "Biomarcador acústico acompanhado em fala neutra, relevante para tensão autonômica e ansiedade somática.",
  "F0 Med.": "Frequência fundamental média da voz no período.",
  ZCR: "Taxa de cruzamento por zero, relacionada a textura/ruído e dinâmica acústica.",
  "Jitter idx.": "Índice proxy interno normalizado de instabilidade vocal relativa; não equivale diretamente a jitter percentual normativo.",
  "Shimmer idx.": "Índice proxy interno normalizado de variação relativa do envelope RMS; não equivale diretamente a shimmer em dB.",
  Jitter: "Índice proxy interno normalizado de instabilidade vocal relativa.",
  Shimmer: "Índice proxy interno normalizado de variação relativa do envelope RMS.",
  "Sub-H 5-12Hz": "Energia sub-harmônica baixa, usada no cruzamento com sinais autonômicos.",
  "Sub-H 12-20Hz": "Energia sub-harmônica complementar para leitura bioacústica.",
  Metrica: "Nome da métrica estatística analisada pelo motor evolutivo.",
  Baseline: "Valor inicial de referência, apurado no baseline da sessão.",
  Media: "Média consolidada da sessão para a métrica.",
  "Último corte": "Valor mais recente observado nos cortes temporais.",
  "Delta último": "Variação percentual do último corte em relação ao baseline.",
  "Z último": "Desvio padronizado do último corte em relação ao comportamento de referência.",
  Alertas: "Alertas estatísticos ou clínicos levantados para a métrica.",
  ipm: "Índice de Potência Multimodal no motor estatístico.",
  idm: "Índice de Desvio Multimodal no motor estatístico.",
  words_per_minute: "Velocidade média de fala em palavras por minuto.",
  facial_vocal_dissonance: "Dissonância entre expressão facial e trilha vocal.",
  "Palavras/min": "Velocidade média de fala em palavras por minuto.",
  Dissonancia: "Dissonância entre expressão facial e trilha vocal.",
  "Delta 0.5-4Hz": "Modulação lenta do envelope vocal, associada a carga vegetativa basal.",
  "Theta 4-8Hz": "Faixa de modulação lenta relacionada a flutuação afetiva e organização narrativa.",
  "Alpha 8-12Hz": "Faixa intermediária de estabilização autônoma e transição rítmica.",
  "Beta 12-30Hz": "Beta (12-30 Hz): energia nessa faixa de modulacao da envoltoria vocal. Nao corresponde a ritmo cortical de EEG — a homonimia e coincidencia de nomenclatura de faixa. Picos indicam elevacao contra a referencia do paciente. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
  "Gama 30-80Hz": "Faixa alta de energia espectral, interpretada como tensão fina, aspereza ou descarga rápida.",
  "Ind. espectral": "Índice ponderado das bandas Delta, Theta, Alpha, Beta e Gama.",
  "DMFCC7": "Derivada temporal do MFCC7, comparando a janela atual com a anterior.",
  "DMFCC9": "Derivada temporal do MFCC9, comparando a janela atual com a anterior.",
  "DDMFCC7": "Aceleração cepstral do MFCC7, usada para detectar mudanças abruptas no marcador.",
  "DDMFCC9": "Aceleração cepstral do MFCC9, usada para detectar mudanças abruptas no marcador.",
  // Chaves do motor estatístico usadas na tabela de evolução. Faltavam, e a
  // tabela inteira caía no texto genérico — ver `descricaoDaMetrica`.
  spectral_beta:
    "Energia na faixa 12-30 Hz da modulação da envoltória vocal. Não corresponde a ritmo cortical de EEG: a homonímia é coincidência de nomenclatura de faixa.",
  spectral_gamma:
    "Energia na faixa alta do espectro de modulação, lida como tensão fina, aspereza ou descarga rápida.",
  spectral_band_index:
    "Índice ponderado das bandas Delta, Theta, Alpha, Beta e Gama num único número.",
  mfcc7_delta:
    "Derivada temporal do MFCC7: quanto o marcador mudou entre a janela atual e a anterior.",
  mfcc9_delta_delta:
    "Aceleração cepstral do MFCC9: mudanças abruptas no marcador, e não seu nível.",
  Dissonância: "Dissonância entre expressão facial e trilha vocal.",
};

/**
 * Encontra a descrição de uma métrica pelo rótulo OU pela chave.
 *
 * A busca era `METRIC_TOOLTIPS[label]`, casamento exato. Dois problemas reais,
 * que o Fábio viu em 02/09/2026 como "o tooltip não informa a descrição":
 *
 * 1. A tabela de evolução passa o rótulo do SERVIDOR ("Elevação multimodal
 *    (IPM)", "Desvio de ZCR vs. baseline"), que nunca esteve neste dicionário —
 *    então TODAS as linhas dela caíam no texto genérico.
 * 2. "Dissonância" existia como "Dissonancia": um acento separava a métrica da
 *    sua descrição.
 *
 * Aqui a busca tenta o rótulo, depois o rótulo normalizado (sem acento, caixa
 * ou pontuação), depois a chave, depois a chave normalizada. Normalizar resolve
 * a classe inteira do problema 2; aceitar a chave resolve o 1.
 */
const INDICE_NORMALIZADO: Record<string, string> = (() => {
  const indice: Record<string, string> = {};
  for (const [chave, texto] of Object.entries(METRIC_TOOLTIPS)) {
    const normal = chave
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
    if (normal && !indice[normal]) indice[normal] = texto;
  }
  return indice;
})();

export function descricaoDaMetrica(rotulo: string, chave?: string): string {
  const normalizar = (texto: string) =>
    String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  const candidatos = [
    METRIC_TOOLTIPS[rotulo],
    INDICE_NORMALIZADO[normalizar(rotulo)],
    chave ? METRIC_TOOLTIPS[chave] : undefined,
    chave ? INDICE_NORMALIZADO[normalizar(chave)] : undefined,
  ];
  const achado = candidatos.find((texto) => typeof texto === "string" && texto.length > 0);
  // Sem descrição, dizer isso é melhor do que "Métrica FROID." — que ocupava o
  // lugar da explicação e fazia parecer que a explicação era aquela.
  return achado || "Esta métrica ainda não tem descrição cadastrada.";
}

// Locale do relatório disponibilizado aos rótulos de ajuda sem precisar
// passar prop em cada um dos ~14 pontos de uso.
const ReportLocaleContext = React.createContext<SessionLocale>("pt-BR");

const HelpTitle: React.FC<{ title: string; className?: string }> = ({
  title,
  className = "text-sm font-bold text-slate-100",
}) => {
  const locale = React.useContext(ReportLocaleContext);
  return (
    <FroidTooltip
      width={320}
      content={
        <div>
          <p className="font-bold text-slate-100">{title}</p>
          <p className="mt-1">{tooltipText(locale, TITLE_TOOLTIPS[title] || "Informação do bloco.")}</p>
        </div>
      }
    >
      <span className={`${className} cursor-help border-b border-dashed border-slate-300`}>
        {title}
      </span>
    </FroidTooltip>
  );
};

const HelpMetric: React.FC<{ label: string; chave?: string }> = ({ label, chave }) => {
  const locale = React.useContext(ReportLocaleContext);
  return (
    <FroidTooltip
      width={300}
      content={
        <div>
          <p className="font-bold text-slate-100">{label}</p>
          <p className="mt-1">{tooltipText(locale, descricaoDaMetrica(label, chave))}</p>
        </div>
      }
    >
      <span className="cursor-help border-b border-dashed border-slate-300">
        {label}
      </span>
    </FroidTooltip>
  );
};

function dominantReportTheme(report: SessionReportRecord) {
  const ordered = [...(report.conversationSummaries || [])].sort(
    (a, b) => a.startMinute - b.startMinute,
  );
  const candidates = [
    ...ordered
      .filter((item) => hasSubstantiveSummary(item.summary))
      .map((item) => item.theme),
    report.sessionSummary?.theme || "",
    report.sessionAverage.theme || "",
    report.baseline.theme || "",
  ]
    .map((theme) => limitThemeWords(theme, 6))
    .filter(Boolean);
  return candidates[0] || "Tema em apuração";
}

function metricDeltaSentence(label: string, baseline: number, average: number, digits = 2) {
  if (!Number.isFinite(baseline) || !Number.isFinite(average)) return "";
  const delta = average - baseline;
  const direction =
    Math.abs(delta) < 0.01
      ? "permaneceu estável"
      : delta > 0
        ? "aumentou"
        : "reduziu";
  return `${label} ${direction} de ${baseline.toFixed(digits)} para ${average.toFixed(digits)}`;
}

function derivedSessionSummary(report: SessionReportRecord) {
  const ordered = [...(report.conversationSummaries || [])].sort(
    (a, b) => a.startMinute - b.startMinute,
  );
  const substantiveCuts = ordered.filter((item) => hasSubstantiveSummary(item.summary));
  const theme = dominantReportTheme(report);
  const savedSummary =
    report.sessionSummary?.summary && hasSubstantiveSummary(report.sessionSummary.summary)
      ? report.sessionSummary.summary
      : "";
  const progressionSource = substantiveCuts.length
    ? substantiveCuts
        .map(
          (item) =>
            `${item.startMinute}-${item.endMinute}min, ${limitThemeWords(item.theme, 6)}: ${item.summary}`,
        )
        .join(" ")
    : savedSummary || report.transcript || "";
  const metricSentences = [
    metricDeltaSentence("IPM", report.baseline.ipmAvg, report.sessionAverage.ipmAvg, 1),
    metricDeltaSentence("IDM", report.baseline.idmAvg, report.sessionAverage.idmAvg, 2),
  ].filter(Boolean);
  const metricText = [
    metricSentences.join("; "),
    report.sessionAverage.dominantZone
      ? `zona dominante ${report.sessionAverage.dominantZone} (${report.sessionAverage.dominantTheme || report.sessionAverage.theme || "tema em apuração"})`
      : "",
    report.sessionAverage.emotionalTone
      ? `tom predominante ${report.sessionAverage.emotionalTone}`
      : "",
    Number.isFinite(report.sessionAverage.wordsPerMinute)
      ? `${report.sessionAverage.wordsPerMinute.toFixed(1)} palavras/min em média`
      : "",
    report.sessionAverage.dissonanceCount
      ? `${report.sessionAverage.dissonanceCount} dissonância(s) média(s) acima do limiar`
      : "sem dissonâncias médias relevantes registradas",
  ]
    .filter(Boolean)
    .join("; ");

  const body = progressionSource
    ? limitWords(cleanSummaryText(progressionSource), 185)
    : "";
  const analyticalClose = body
    ? `A sequência dos cortes indica que a substância central da sessão se organizou em torno de ${theme.toLowerCase()}, com progressão narrativa observável entre os blocos registrados. ${body}. Na leitura multimodal, ${metricText}. Em conclusão, o registro recomenda que o profissional leia o conteúdo verbal em conjunto com a variação bioacústica e zonal, usando os próximos encontros para comparar se o tema se estabiliza, se desloca ou se intensifica em relação ao baseline desta consulta.`
    : `A sessão teve tema predominante ${theme}, mas não reuniu transcrição ou cortes semanticos suficientes para uma conclusão textual completa. Na leitura multimodal, ${metricText}. Em conclusão, o relatório deve ser utilizado principalmente como linha de base comparativa, aguardando próximas sessões com maior densidade verbal para consolidar a substância clínica do processo.`;

  return {
    theme,
    summary:
      limitWords(cleanSummaryText(analyticalClose), SESSION_SUMMARY_MAX_WORDS) ||
      "Resumo geral indisponível para esta sessão.",
    generatedAt: report.sessionSummary?.generatedAt || report.createdAt,
  };
}

function metricRows(snapshot: MetricSnapshot) {
  return [
    ["IPM", fmt(snapshot.ipmAvg, 1)],
    ["IDM", fmt(snapshot.idmAvg, 2)],
    ["ZONAS", snapshot.dominantZone ? `Zona ${snapshot.dominantZone}` : "--"],
    ["Tom", snapshot.emotionalTone || "--"],
    ["P/min", fmt(snapshot.wordsPerMinute, 1)],
    ["Disso.", String(snapshot.dissonanceCount || 0)],
    ["MFCC7", fmt(snapshot.mfcc7, 3)],
    ["MFCC9", fmt(snapshot.mfcc9, 3)],
    ["DMFCC7", fmt(snapshot.mfcc7Delta, 4)],
    ["DMFCC9", fmt(snapshot.mfcc9Delta, 4)],
    ["DDMFCC7", fmt(snapshot.mfcc7DeltaDelta, 4)],
    ["DDMFCC9", fmt(snapshot.mfcc9DeltaDelta, 4)],
    ["F0 Med.", fmt(snapshot.f0Mean, 2)],
    ["ZCR", fmt(snapshot.zcr, 3)],
    ["Jitter idx.", fmt(snapshot.jitter, 3)],
    ["Shimmer idx.", fmt(snapshot.shimmer, 3)],
    ["Delta 0.5-4Hz", fmt(snapshot.spectralDelta0_4, 3)],
    ["Theta 4-8Hz", fmt(snapshot.spectralTheta4_8, 3)],
    ["Alpha 8-12Hz", fmt(snapshot.spectralAlpha8_12, 3)],
    ["Beta 12-30Hz", fmt(snapshot.spectralBeta12_30, 3)],
    ["Gama 30-80Hz", fmt(snapshot.spectralGamma30_80, 3)],
    ["Ind. espectral", fmt(snapshot.spectralBandIndex, 3)],
    ["Sub-H 5-12Hz", fmt(snapshot.subharmonic5_12, 3)],
    ["Sub-H 12-20Hz", fmt(snapshot.subharmonic12_20, 3)],
  ];
}

type ConversationCutSummary = SessionReportRecord["conversationSummaries"][number];

function secondsForSummary(summary: ConversationCutSummary) {
  return {
    start: Math.max(0, Math.floor(summary.startSecond ?? summary.startMinute * 60)),
    end: Math.max(
      Math.floor(summary.startSecond ?? summary.startMinute * 60) + 1,
      Math.ceil(summary.endSecond ?? summary.endMinute * 60),
    ),
  };
}

function overlapSeconds(
  leftStart: number,
  leftEnd: number,
  rightStart: number,
  rightEnd: number,
) {
  return Math.max(0, Math.min(leftEnd, rightEnd) - Math.max(leftStart, rightStart));
}

function findCutForSummary(
  summary: ConversationCutSummary,
  cuts: MetricSnapshot[],
) {
  const interval = secondsForSummary(summary);
  const best = [...cuts]
    .map((cut) => ({
      cut,
      overlap: overlapSeconds(
        interval.start,
        interval.end,
        cut.startSecond,
        cut.endSecond,
      ),
    }))
    .sort((a, b) => b.overlap - a.overlap)[0];
  return best?.overlap ? best.cut : undefined;
}

function findSummaryForCut(
  cut: MetricSnapshot,
  summaries: ConversationCutSummary[],
) {
  const best = [...summaries]
    .map((summary) => {
      const interval = secondsForSummary(summary);
      return {
        summary,
        overlap: overlapSeconds(
          cut.startSecond,
          cut.endSecond,
          interval.start,
          interval.end,
        ),
      };
    })
    .sort((a, b) => b.overlap - a.overlap)[0];
  return best?.overlap ? best.summary : undefined;
}

function cutTimeLabel(cut: MetricSnapshot, summary?: ConversationCutSummary) {
  if (summary) {
    return `${summary.startMinute}-${summary.endMinute}min`;
  }
  return `${Math.floor(cut.startSecond / 60)}-${Math.ceil(cut.endSecond / 60)}min`;
}

function summaryMetricLine(cut?: MetricSnapshot) {
  if (!cut) return "";
  return [
    `IPM ${fmt(cut.ipmAvg, 1)}`,
    `IDM ${fmt(cut.idmAvg, 2)}`,
    `Zona ${cut.dominantZone || "--"}`,
    `Tom ${cut.emotionalTone || "--"}`,
    `${fmt(cut.wordsPerMinute, 1)} p/min`,
    `Disson. ${cut.dissonanceCount || 0}`,
    `MFCC7 ${fmt(cut.mfcc7, 3)}`,
    `MFCC9 ${fmt(cut.mfcc9, 3)}`,
    `Beta ${fmt(cut.spectralBeta12_30, 3)}`,
    `Gama ${fmt(cut.spectralGamma30_80, 3)}`,
    `DMFCC7 ${fmt(cut.mfcc7Delta, 4)}`,
  ].join(" | ");
}

function buildDescriptiveReportText(
  report: SessionReportRecord,
  sessionSummary: { theme: string; summary: string },
) {
  return [
    `Relatório descritivo da sessão ${report.sessionId}`,
    `Data: ${new Date(report.createdAt).toLocaleString("pt-BR")}`,
    `Duracao: ${formatDuration(report.durationSeconds)}`,
    `Tema predominante: ${limitThemeWords(sessionSummary.theme || report.sessionAverage.theme, 6)}`,
    "",
    `Resumo geral: ${limitWords(sessionSummary.summary, SESSION_SUMMARY_MAX_WORDS)}`,
    "",
    `Linha comparativa: IPM ${fmt(report.baseline.ipmAvg, 1)} -> ${fmt(report.sessionAverage.ipmAvg, 1)}; IDM ${fmt(report.baseline.idmAvg, 2)} -> ${fmt(report.sessionAverage.idmAvg, 2)}; Zona ${report.sessionAverage.dominantZone || "--"}; Tom ${report.sessionAverage.emotionalTone || "--"}; ${fmt(report.sessionAverage.wordsPerMinute, 1)} palavras/min.`,
    `Linha bioacustica: Beta ${fmt(report.baseline.spectralBeta12_30, 3)} -> ${fmt(report.sessionAverage.spectralBeta12_30, 3)}; Gama ${fmt(report.baseline.spectralGamma30_80, 3)} -> ${fmt(report.sessionAverage.spectralGamma30_80, 3)}; DMFCC7 medio ${fmt(report.sessionAverage.mfcc7Delta, 4)}; DDMFCC9 medio ${fmt(report.sessionAverage.mfcc9DeltaDelta, 4)}.`,
    "",
    `Observações clínicas registradas: ${report.clinicalNotes.length}. Dissonâncias persistentes registradas: ${report.dissonances.length}.`,
  ].join("\n");
}

const CompactMetricTable: React.FC<{
  title: string;
  rows: Array<{ label: string; metrics: string[][] }>;
}> = ({ title, rows }) => (
  <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
    <div className="mb-3">
      <HelpTitle title={title} />
    </div>
    <div className="overflow-x-auto">
      <table className="min-w-max table-auto text-left text-[10px] leading-tight">
        <thead className="text-[9px] uppercase tracking-normal text-slate-500">
          <tr>
            <th className="whitespace-nowrap py-1 pr-2">
              <HelpMetric label="Corte" />
            </th>
            {rows[0]?.metrics.map(([label]) => (
              <th
                key={label}
                className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold"
              >
                <HelpMetric label={label} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((row) => (
            <tr key={row.label} className="align-top">
              <td className="whitespace-nowrap py-1 pr-2 font-bold text-slate-300">
                {row.label}
              </td>
              {row.metrics.map(([label, value]) => (
                <td
                  key={`${row.label}-${label}`}
                  className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300"
                  title={value}
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
);

const MetricList: React.FC<{ title: string; snapshot: MetricSnapshot }> = ({
  title,
  snapshot,
}) => (
  <CompactMetricTable
    title={title}
    rows={[{ label: snapshot.label, metrics: metricRows(snapshot) }]}
  />
);

const METRIC_SUMMARY_KEYS = [
  "ipm",
  "idm",
  "spectral_beta",
  "spectral_gamma",
  "spectral_band_index",
  "mfcc7_delta",
  "mfcc9_delta_delta",
  "words_per_minute",
  "facial_vocal_dissonance",
];

function metricLabel(analysis: MetricsAnalysis | null, key: string) {
  return analysis?.metrics.find((metric) => metric.key === key)?.label || key;
}

const PREFIXO_DE_FALA = /^(DR\.\s*-\s*|PC\s*-\s*|PAC\s*-\s*)/i;

/** A fala da sessão, na ordem, com quem falou.
 *
 *  O sistema transcreve os dois canais separadamente e marca cada linha com
 *  `DR. - ` ou `PC - ` desde sempre. O texto era gravado no relatório — e
 *  nenhuma tela o mostrava, nem aqui nem no PDF. O profissional conduzia a
 *  leitura do documento sem poder conferir o que o sistema ouviu.
 *
 *  Isso importa porque os erros que um paciente aponta num relatório são, na
 *  maioria, da camada semântica: palavra trocada, frase incoerente, inferência
 *  que ninguém disse. Sem a transcrição ao lado, não há como localizar se o
 *  erro foi da escuta ou do resumo. */
const TranscricaoDaSessao: React.FC<{ transcript?: string }> = ({ transcript }) => {
  const linhas = String(transcript || "")
    .split(/\r?\n/)
    .map((linha) => linha.trim())
    .filter(Boolean);

  if (!linhas.length) return null;

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-100">
          <HelpTitle title="Transcrição da sessão" />
        </h2>
        <span className="flex items-center gap-3 text-[9px] font-bold uppercase tracking-wide">
          <span className="flex items-center gap-1 text-sky-300">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-400" />
            DR profissional
          </span>
          <span className="flex items-center gap-1 text-emerald-300">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
            PC paciente
          </span>
        </span>
      </div>
      <div className="max-h-96 space-y-1 overflow-y-auto pr-1">
        {linhas.map((linha, indice) => {
          const casa = linha.match(PREFIXO_DE_FALA);
          const doProfissional = (casa?.[1] || "").toUpperCase().startsWith("DR");
          const fala = linha.replace(PREFIXO_DE_FALA, "").trim();
          if (!fala) return null;
          return (
            <div
              key={`${indice}-${fala.slice(0, 24)}`}
              className={`rounded border-l-2 px-2 py-1 ${
                doProfissional
                  ? "border-sky-500 bg-sky-950/30"
                  : "border-emerald-500 bg-emerald-950/30"
              }`}
            >
              <span
                className={`mr-1.5 text-[9px] font-black uppercase ${
                  doProfissional ? "text-sky-300" : "text-emerald-300"
                }`}
              >
                {doProfissional ? "DR" : "PC"}
              </span>
              <span className="text-xs leading-5 text-slate-200">{fala}</span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-slate-800 pt-2 text-[10px] leading-4 text-slate-500">
        Ordem cronológica, como foi captada. Linha sem prefixo reconhecido é
        apresentada como fala do paciente — a atribuição vem do canal de áudio,
        não de suposição sobre o conteúdo.
      </p>
    </section>
  );
};

/** Evolução por índice, em painéis separados — um por grandeza.
 *
 *  Antes eram quatro séries num eixo só, normalizadas para base 100 contra o
 *  baseline. Normalizar não resolve escalas incomensuráveis quando o baseline é
 *  minúsculo: com IDM em 0.01 e dissonância em 0, uma variação irrelevante em
 *  valor absoluto vira centenas de pontos percentuais, o eixo se estica para
 *  acomodá-la, e IPM e palavras/min viram duas retas coladas no meio. Era o que
 *  o Fábio descreveu — impossível avaliar a escala.
 *
 *  Escala logarítmica não serve aqui: a dissonância vale 0 em sessões inteiras,
 *  e log(0) não existe. Painéis separados resolvem sem truque nenhum — cada
 *  índice na sua própria régua, com os valores REAIS escritos, e nenhuma
 *  comparação visual falsa entre grandezas que não se comparam.
 *
 *  E uma série sem leitura passa a DIZER isso, em vez de desenhar uma linha
 *  reta no zero. Uma reta no zero parece medida — e uma medida ausente que
 *  parece medida é a pior das duas.
 */

type SerieEvolucao = {
  key: string;
  label: string;
  color: string;
  valores: Array<number | null>;
  baseline: number | null;
  casas: number;
};

const PainelEvolucao: React.FC<{ serie: SerieEvolucao; rotulos: string[] }> = ({
  serie,
  rotulos,
}) => {
  const validos = serie.valores.filter(
    (v): v is number => typeof v === "number" && Number.isFinite(v),
  );

  if (!validos.length) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
        <div className="flex items-baseline justify-between gap-2">
          <HelpMetric label={serie.label} chave={serie.key} />
          <span className="text-[10px] text-slate-500">sem leitura</span>
        </div>
        <p className="mt-2 text-[10px] italic leading-4 text-slate-500">
          Nenhum corte deste período produziu valor para este índice. O gráfico
          fica vazio de propósito: uma linha no zero pareceria medição.
        </p>
      </div>
    );
  }

  const menor = Math.min(...validos);
  const maior = Math.max(...validos);
  const semVariacao = maior - menor < 1e-9;
  // Folga de 15% para a linha não encostar nas bordas; série constante ganha
  // uma janela artificial para não virar divisão por zero.
  const folga = semVariacao ? Math.max(1, Math.abs(maior) * 0.1) : (maior - menor) * 0.15;
  const min = menor - folga;
  const max = maior + folga;

  const W = 300;
  const H = 64;
  const x = (i: number) =>
    serie.valores.length <= 1 ? W / 2 : (i / (serie.valores.length - 1)) * W;
  const y = (v: number) => H - ((v - min) / Math.max(1e-9, max - min)) * H;

  const pontos = serie.valores
    .map((v, i) =>
      v === null || v === undefined || !Number.isFinite(v)
        ? null
        : `${x(i).toFixed(1)},${y(v).toFixed(1)}`,
    )
    .filter(Boolean)
    .join(" ");

  const atual = validos[validos.length - 1];
  const base = serie.baseline;
  const temBase = typeof base === "number" && Number.isFinite(base);
  const delta = temBase ? atual - (base as number) : null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <HelpMetric label={serie.label} chave={serie.key} />
        <span className="font-mono text-[13px] font-black" style={{ color: serie.color }}>
          {atual.toFixed(serie.casas)}
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[9px] text-slate-400">
        <span>
          baseline{" "}
          <strong className="font-mono text-slate-200">
            {temBase ? (base as number).toFixed(serie.casas) : "--"}
          </strong>
        </span>
        {delta !== null && (
          <span>
            delta{" "}
            <strong
              className={`font-mono ${delta > 0 ? "text-amber-300" : delta < 0 ? "text-cyan-300" : "text-slate-300"}`}
            >
              {delta > 0 ? "+" : ""}
              {delta.toFixed(serie.casas)}
            </strong>
          </span>
        )}
        <span>
          faixa{" "}
          <strong className="font-mono text-slate-200">
            {menor.toFixed(serie.casas)} a {maior.toFixed(serie.casas)}
          </strong>
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 h-16 w-full" preserveAspectRatio="none">
        {temBase && (base as number) >= min && (base as number) <= max && (
          <line
            x1={0}
            x2={W}
            y1={y(base as number)}
            y2={y(base as number)}
            stroke="#64748b"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
        )}
        <polyline
          points={pontos}
          fill="none"
          stroke={serie.color}
          strokeWidth={2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {serie.valores.map((v, i) =>
          v === null || v === undefined || !Number.isFinite(v) ? null : (
            <circle key={i} cx={x(i)} cy={y(v)} r={2.5} fill={serie.color} />
          ),
        )}
      </svg>

      <div className="mt-1 flex justify-between text-[8px] text-slate-500">
        <span>{rotulos[0]}</span>
        <span>{rotulos[rotulos.length - 1]}</span>
      </div>

      {semVariacao && (
        <p className="mt-1 text-[9px] italic text-slate-500">
          Sem variação entre os cortes.
        </p>
      )}
    </div>
  );
};

/** A base probatória do relatório, dita antes dos números.
 *
 *  Vem antes de propósito. Quem lê um índice acústico precisa saber, antes de
 *  interpretá-lo, se ele foi medido ou gerado — depois já é tarde, a leitura
 *  clínica já aconteceu.
 */
const ProcedenciaDoRelatorio: React.FC<{
  procedencia?: SessionReportRecord["procedenciaDosDados"];
}> = ({ procedencia }) => {
  if (!procedencia) {
    // Relatórios anteriores a 02/09/2026 não gravavam isso. Dizer "não sei" é
    // a única leitura honesta: nem afirma que foi medido, nem que não foi.
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-3">
        <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">
          Procedência dos dados
        </p>
        <p className="mt-1 text-xs text-slate-400">
          Este relatório é anterior ao registro de procedência. Não é possível
          afirmar, a partir dele, se os índices acústicos foram medidos sobre a
          voz do paciente ou gerados pelo modo de simulação.
        </p>
      </section>
    );
  }

  const { amostras, amostrasComVozReal, amostrasComFaceReal } = procedencia;
  const proporcao = amostras > 0 ? amostrasComVozReal / amostras : 0;
  const pct = (parte: number) =>
    amostras > 0 ? Math.round((parte / amostras) * 100) : 0;

  const nenhuma = amostrasComVozReal === 0;
  const parcial = !nenhuma && proporcao < 0.8;

  const cor = nenhuma
    ? "border-red-700 bg-red-950/50"
    : parcial
      ? "border-amber-700 bg-amber-950/40"
      : "border-emerald-800 bg-emerald-950/30";

  return (
    <section className={`rounded-lg border p-3 ${cor}`}>
      <p className="text-[10px] font-black uppercase tracking-wider text-slate-200">
        Procedência dos dados
      </p>
      {nenhuma ? (
        <p className="mt-1 text-xs font-bold leading-5 text-red-100">
          Os índices acústicos deste relatório <strong>não foram medidos</strong>.
          Nenhuma das {amostras} amostras da sessão recebeu voz real do paciente —
          o motor operou em modo de simulação. F0, ZCR, MFCC e os índices
          derivados deles não descrevem esta pessoa e não devem ser lidos como
          achado clínico.
        </p>
      ) : (
        <p className="mt-1 text-xs leading-5 text-slate-200">
          {amostrasComVozReal} de {amostras} amostras ({pct(amostrasComVozReal)}%)
          foram medidas sobre a voz real do paciente
          {parcial
            ? " — o restante veio do modo de simulação, e os índices representam uma mistura das duas fontes."
            : "."}
        </p>
      )}
      <p className="mt-1 text-[11px] leading-4 text-slate-400">
        Leitura facial real em {amostrasComFaceReal} de {amostras} amostras (
        {pct(amostrasComFaceReal)}%). A transcrição, os resumos e o registro da
        sessão não dependem desta origem e permanecem válidos.
      </p>
    </section>
  );
};

const EvolutionChart: React.FC<{ analysis: MetricsAnalysis }> = ({ analysis }) => {
  const rows = analysis.evolution || [];

  if (!rows.length) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-950 p-4 text-xs italic text-slate-500">
        Evolução estatística aguardando cortes com dados.
      </div>
    );
  }

  const rotulos = rows.map((row) =>
    // Arredondado: cortes nao caem em minuto exato, e sem isto o eixo escrevia
    // "20-33.28333333333333m".
    Number.isFinite(row.start_min) && Number.isFinite(row.end_min)
      ? `${Math.round(row.start_min)}-${Math.round(row.end_min)}m`
      : row.label,
  );

  const series: SerieEvolucao[] = [
    {
      key: "ipm",
      label: "IPM",
      color: "#60a5fa",
      valores: rows.map((row) => row.ipm ?? null),
      baseline: analysis.summary.ipm?.baseline ?? null,
      casas: 1,
    },
    {
      key: "idm",
      label: "IDM",
      color: "#4ade80",
      valores: rows.map((row) => row.idm ?? null),
      baseline: analysis.summary.idm?.baseline ?? null,
      casas: 2,
    },
    {
      key: "words_per_minute",
      label: "Palavras/min",
      color: "#fbbf24",
      valores: rows.map((row) => row.words_per_minute ?? null),
      baseline: analysis.summary.words_per_minute?.baseline ?? null,
      casas: 0,
    },
    {
      key: "facial_vocal_dissonance",
      label: "Dissonância",
      color: "#f87171",
      valores: rows.map((row) => row.facial_vocal_dissonance ?? null),
      baseline: analysis.summary.facial_vocal_dissonance?.baseline ?? null,
      casas: 2,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {series.map((serie) => (
        <PainelEvolucao key={serie.key} serie={serie} rotulos={rotulos} />
      ))}
    </div>
  );
};

export const SessionReport: React.FC<Props> = () => {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<SessionReportRecord | null>(() =>
    loadSessionReport(sessionId) || null,
  );
  const [metricsAnalysis, setMetricsAnalysis] = useState<MetricsAnalysis | null>(
    () => loadSessionReport(sessionId)?.metricsAnalysis || null,
  );
  const [metricsError, setMetricsError] = useState("");
  const [sections, setSections] = useState(DEFAULT_SECTIONS);
  const [descriptiveReport, setDescriptiveReport] = useState("");
  // Texto que o sistema pré-compôs. Guardado para saber se o profissional
  // chegou a escrever: enquanto o campo for idêntico ao gerado, o PDF fica
  // travado. Um documento assinado com texto de máquina é pior do que documento
  // nenhum — quem assina responde pelo que está escrito.
  const [autoDescriptive, setAutoDescriptive] = useState("");
  const descriptiveEdited =
    descriptiveReport.trim().length > 0
    && descriptiveReport.trim() !== autoDescriptive.trim();
  const [pdfAviso, setPdfAviso] = useState("");

  // ---------- Composição do documento do paciente ----------
  // Separado de `sections`, que governa o que o PROFISSIONAL vê e imprime. Aqui
  // se decide o que o PACIENTE recebe na área dele — outra audiência, outra
  // decisão. O catálogo vem do servidor: é a mesma lista que filtra o payload,
  // então a tela não consegue oferecer um item que o filtro desconhece.
  const [releaseCatalog, setReleaseCatalog] = useState<{ key: string; label: string }[]>([]);
  const [releaseItems, setReleaseItems] = useState<string[]>([]);
  const [releaseState, setReleaseState] = useState<{
    released: boolean;
    releasedAt: string;
    legacy: boolean;
  }>({ released: false, releasedAt: "", legacy: false });
  const [patientResultsEnabled, setPatientResultsEnabled] = useState(true);
  const [releaseSaving, setReleaseSaving] = useState(false);
  const [releaseAviso, setReleaseAviso] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    const token = localStorage.getItem("froid_token") || "";
    let active = true;
    fetch(apiUrl(`/api/session-reports/${sessionId}/patient-release`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active || !data) return;
        setReleaseCatalog(Array.isArray(data.catalog) ? data.catalog : []);
        const release = data.patientRelease || {};
        setReleaseState({
          released: Boolean(release.released),
          releasedAt: String(release.releasedAt || ""),
          legacy: Boolean(release.legacy),
        });
        // Sessão ainda não composta abre com tudo marcado: desmarcar o que não
        // cabe é mais rápido do que marcar oito itens do zero, e o profissional
        // ainda precisa clicar em liberar para que qualquer coisa saia daqui.
        const items = Array.isArray(release.items) ? release.items : [];
        setReleaseItems(
          items.length
            ? items
            : (Array.isArray(data.catalog) ? data.catalog : []).map(
                (item: { key: string }) => item.key,
              ),
        );
        setPatientResultsEnabled(data.patientResultsEnabled !== false);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [sessionId]);

  const toggleReleaseItem = (key: string) =>
    setReleaseItems((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key],
    );

  const salvarLiberacao = async (released: boolean) => {
    if (!sessionId) return;
    setReleaseSaving(true);
    setReleaseAviso("");
    try {
      const token = localStorage.getItem("froid_token") || "";
      const response = await fetch(
        apiUrl(`/api/session-reports/${sessionId}/patient-release`),
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          // O texto vai junto e fica congelado na liberação: é ele que preenche
          // "Anotações do seu profissional" na cópia que o paciente baixa.
          body: JSON.stringify({ released, items: releaseItems, descriptiveText: descriptiveReport }),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível salvar.");
      const release = data.patientRelease || {};
      setReleaseState({
        released: Boolean(release.released),
        releasedAt: String(release.releasedAt || ""),
        legacy: false,
      });
      setReleaseAviso(released ? "Relatório liberado ao paciente." : "Liberação revogada.");
    } catch (err) {
      setReleaseAviso(err instanceof Error ? err.message : "Falha ao salvar a liberação.");
    } finally {
      setReleaseSaving(false);
    }
  };

  const gerarPdf = (audience: ReportAudience) => {
    setPdfAviso("");
    if (!report) return;
    // O perfil vive no cadastro; aqui só se lê o que já existe. Nome ausente
    // não impede o documento — o gerador cai no título neutro.
    let perfil: Record<string, string> = {};
    try {
      perfil = JSON.parse(localStorage.getItem("froid_professional_profile") || "{}") || {};
    } catch {
      perfil = {};
    }
    const html = buildReport(
      audience,
      report,
      {
        clinicName: String(perfil.organization_name || perfil.trade_name || ""),
        professionalName: String(
          perfil.owner_name || report.professional?.name || report.professionalEmail || "",
        ),
        professionalRegistry: String(perfil.professional_registry || ""),
        contactEmail: String(
          perfil.email || report.professional?.email || report.professionalEmail || "",
        ),
      },
      descriptiveReport,
      undefined,
      // A seleção do checklist governa o documento do paciente. Sem passá-la
      // aqui, o "PDF paciente" saía do registro completo e marcar ou desmarcar
      // não mudava nada — que foi o defeito reportado em uso.
      audience === "patient" ? releaseItems : undefined,
    );
    if (!openPrintable(html)) {
      // Sem este aviso o profissional clica e nada acontece: o bloqueio de
      // pop-up é silencioso, e ele conclui que o botão está quebrado.
      setPdfAviso(
        "O navegador bloqueou a janela de impressão. Autorize pop-ups para este "
        + "endereço e tente de novo.",
      );
    }
  };
  const locale = normalizeSessionLocale(
    report?.reportLocale,
    loadSessionLanguagePreferences().reportLocale,
  );
  const tr = (text: string) => dashboardText(locale, text);

  useEffect(() => {
    let active = true;
    if (report || !sessionId) return;
    const token = localStorage.getItem("froid_token") || "";
    fetch(apiUrl(`/api/session-reports/${sessionId}`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (active && data?.sessionId) {
          setReport(data);
          if (data.metricsAnalysis) setMetricsAnalysis(data.metricsAnalysis);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [report, sessionId]);

  useEffect(() => {
    let active = true;
    if (!sessionId) return;
    const token = localStorage.getItem("froid_token") || "";
    fetch(apiUrl(`/api/session-reports/${sessionId}/metrics`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active) return;
        if (data?.schema) {
          setMetricsAnalysis(data);
          setMetricsError("");
        }
      })
      .catch((error) => {
        if (active) setMetricsError(error instanceof Error ? error.message : "Métricas indisponíveis");
      });
    return () => {
      active = false;
    };
  }, [sessionId]);

  const reportContext = useMemo(() => {
    if (!report) return {};
    const summary = derivedSessionSummary(report);
    const transcript = String(report.transcript || "");
    const transcriptLines = transcript.split("\n").filter((line) => line.trim());
    const patientLines = transcriptLines.filter((line) => /^(PC|PAC)\b/i.test(line));
    const professionalLines = transcriptLines.filter((line) => /^DR\b/i.test(line));
    return {
      report_baseline: report.baseline,
      report_session_average: report.sessionAverage,
      report_ten_minute_cuts: report.tenMinuteCuts,
      report_session_summary: summary,
      report_metrics_analysis: metricsAnalysis,
      report_notes_count: report.clinicalNotes.length,
      report_summaries: report.conversationSummaries,
      // Transcrição arquivada, no mesmo formato que o backend consome, para o
      // FROID Explica responder sobre falas e recomendações após a sessão.
      patient_id: report.patient?.id || (report as Record<string, any>).patientId || "",
      transcript_available: transcriptLines.length > 0,
      transcript_speaker_legend: "DR = profissional/terapeuta; PC ou PAC = paciente.",
      session_transcript: transcript.slice(-8000),
      patient_speech: patientLines.slice(-120).join("\n").slice(-4000),
      professional_speech: professionalLines.slice(-120).join("\n").slice(-4000),
    };
  }, [metricsAnalysis, report]);

  useEffect(() => {
    if (!report || descriptiveReport.trim()) return;
    const gerado = buildDescriptiveReportText(report, derivedSessionSummary(report));
    setAutoDescriptive(gerado);
    setDescriptiveReport(gerado);
  }, [descriptiveReport, report]);

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-300">
        <div className="max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 text-center shadow-sm">
          <h1 className="text-lg font-bold text-slate-100">
            {tr("Relatório não encontrado")}
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            O relatório da sessão ainda não foi gerado neste navegador.
          </p>
          <button
            onClick={() => navigate("/dashboard")}
            className="mt-4 rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800"
          >
            {tr("Voltar ao dashboard")}
          </button>
        </div>
      </div>
    );
  }

  const toggle = (key: SectionKey) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));
  const activeMetricsAnalysis = metricsAnalysis || report.metricsAnalysis || null;
  const sessionSummary = derivedSessionSummary(report);

  // A procedência decide se este par entra no estudo de validade convergente.
  //
  // Uma sessão analisada sobre voz simulada produz um IPM que o sistema
  // inventou. Pareado com um PHQ-9 verdadeiro, ele fabrica evidência: sai um
  // coeficiente, um intervalo e um gráfico, e nada por trás. Os filtros
  // antigos não pegavam isso — dado gerado tem cobertura e confiança
  // excelentes, justamente porque é gerado limpo.
  //
  // O piso espelha `migrations/030_procedencia_na_validade.sql`, que é a
  // fonte: quem decide a inclusão é a função de pares no banco. Aqui ele serve
  // só para avisar antes, em vez de o profissional descobrir que o par foi
  // descartado meses depois.
  const PISO_DE_PROCEDENCIA = 0.8;
  const procedencia = report.procedenciaDosDados;
  const fracaoDeVozMedida =
    procedencia && procedencia.amostras > 0
      ? procedencia.amostrasComVozReal / procedencia.amostras
      : null;
  const parEntraNoEstudo =
    fracaoDeVozMedida !== null && fracaoDeVozMedida >= PISO_DE_PROCEDENCIA;

  return (
    <ReportLocaleContext.Provider value={locale}>
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {report.patient?.id && activeOrganizationId() && (
        <div className="mx-auto max-w-7xl px-6 pt-4">
          {!parEntraNoEstudo && (
            <div className="mb-3 rounded-lg border border-amber-700 bg-amber-950/40 p-3">
              <p className="text-[10px] font-black uppercase tracking-wider text-amber-400">
                Este par não entra no estudo de validade
              </p>
              <p className="mt-1 text-xs leading-5 text-amber-100/90">
                {/* Tres estados, nao dois. `fracaoDeVozMedida` e nula tanto
                    quando a procedencia NAO foi registrada quanto quando ela
                    foi e nao houve amostra alguma — e dizer "nao registrou"
                    no segundo caso contradizia o bloco de procedencia logo
                    acima, que ja anunciava "nenhuma das 0 amostras". */}
                {!procedencia
                  ? "Esta sessão não registrou a procedência dos dados, e procedência desconhecida fica de fora do estudo."
                  : fracaoDeVozMedida === null
                    ? "Esta sessão não produziu amostra nenhuma, então não há o que parear."
                    : `Apenas ${Math.round(fracaoDeVozMedida * 100)}% das amostras desta sessão foram medidas sobre a voz real do paciente.`}{" "}
                O lado FROID do par seria um número gerado, e pareá-lo com um
                escore verdadeiro fabricaria evidência.
              </p>
              <p className="mt-1 text-[11px] leading-4 text-amber-100/70">
                Registrar o escore continua valendo clinicamente — o PHQ-9 é
                útil por si. Só o pareamento com os padrões é que fica de fora.
              </p>
            </div>
          )}
          <InstrumentScorePrompt
            organizationId={activeOrganizationId()}
            patientId={report.patient.id}
            sessionId={report.sessionId}
            observations={[
              {
                pattern_key: "psychomotor_slowing",
                pattern_value: report.sessionAverage?.wordsPerMinute ?? null,
                coverage: report.metricsAnalysis?.dashboard?.mean_coverage ?? null,
                confidence: report.metricsAnalysis?.dashboard?.mean_confidence ?? null,
                window_seconds: report.durationSeconds,
                voice_measured_ratio: fracaoDeVozMedida,
              },
              {
                pattern_key: "prosodic_activation",
                pattern_value: report.sessionAverage?.ipmAvg ?? null,
                coverage: report.metricsAnalysis?.dashboard?.mean_coverage ?? null,
                confidence: report.metricsAnalysis?.dashboard?.mean_confidence ?? null,
                window_seconds: report.durationSeconds,
                voice_measured_ratio: fracaoDeVozMedida,
              },
            ].filter((item) => item.pattern_value !== null)}
          />
        </div>
      )}
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              {tr("Relatório da Consulta")}
            </p>
            <h1 className="text-xl font-bold text-slate-100">
              {tr("Sessão")} {report.sessionId}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(report.createdAt).toLocaleString(locale)} | {tr("Duração")}{" "}
              {formatDuration(report.durationSeconds)}
            </p>
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl items-start gap-4 p-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-4">
          <section className="rounded-lg border border-blue-800 bg-blue-950 p-4">
            <div className="mb-3">
              <HelpTitle
                title={tr("Linha comparativa da sessão")}
                className="text-sm font-bold text-blue-100"
              />
            </div>
            <div className="grid gap-2 md:grid-cols-5">
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IPM baseline
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(report.baseline.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IPM medio
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(report.sessionAverage.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IDM baseline
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(report.baseline.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  IDM medio
                </p>
                <p className="text-lg font-black text-blue-100">
                  {fmt(report.sessionAverage.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-300">
                  Tema inicial
                </p>
                <p className="text-sm font-bold text-blue-100">
                  {report.baseline.theme}
                </p>
              </div>
            </div>
          </section>

          <ProcedenciaDoRelatorio procedencia={report.procedenciaDosDados} />

          {sections.evolution && activeMetricsAnalysis && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-100">
                    <HelpTitle title="Evolução FROID" />
                  </h2>
                  <p className="text-[11px] text-slate-500">
                    Curvas normalizadas pelo baseline inicial de 60 segundos.
                  </p>
                </div>
                <span
                  className={`rounded px-2 py-1 text-[10px] font-black uppercase ${
                    activeMetricsAnalysis.dashboard.data_status === "Adequado"
                      ? "bg-emerald-950/40 text-emerald-200"
                      : "bg-amber-950/40 text-amber-100"
                  }`}
                >
                  {activeMetricsAnalysis.dashboard.data_status}
                </span>
              </div>
              <div className="mb-3 grid gap-2 md:grid-cols-5">
                <div className="rounded border border-slate-700 bg-slate-950 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-500">
                    Cortes com dados
                  </p>
                  <p className="text-lg font-black text-slate-100">
                    {activeMetricsAnalysis.dashboard.populated_windows}
                  </p>
                </div>
                <div className="rounded border border-slate-700 bg-slate-950 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-500">
                    Cobertura média
                  </p>
                  <p className="text-lg font-black text-slate-100">
                    {fmtPct(activeMetricsAnalysis.dashboard.mean_coverage)}
                  </p>
                </div>
                <div className="rounded border border-slate-700 bg-slate-950 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-500">
                    Confiança média
                  </p>
                  <p className="text-lg font-black text-slate-100">
                    {fmtPct(activeMetricsAnalysis.dashboard.mean_confidence)}
                  </p>
                </div>
                <div className="rounded border border-slate-700 bg-slate-950 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-500">
                    Alertas
                  </p>
                  <p className="text-lg font-black text-slate-100">
                    {activeMetricsAnalysis.dashboard.alerts_count}
                  </p>
                </div>
                <div className="rounded border border-slate-700 bg-slate-950 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-500">
                    Críticos
                  </p>
                  <p className="text-lg font-black text-slate-100">
                    {activeMetricsAnalysis.dashboard.critical_alerts}
                  </p>
                </div>
              </div>
              <EvolutionChart analysis={activeMetricsAnalysis} />
            </section>
          )}

          {sections.evolution && !activeMetricsAnalysis && (
            <section className="rounded-lg border border-amber-700 bg-amber-950/40 p-4 text-xs text-amber-100">
              Motor evolutivo aguardando análise do servidor.
              {metricsError ? ` ${metricsError}` : ""}
            </section>
          )}

          {sections.statistics && activeMetricsAnalysis && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-100">
                <HelpTitle title="Leitura estatística das métricas" />
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-500">
                    <tr>
                      {[
                        "Métrica",
                        "Baseline",
                        "Média",
                        "Último corte",
                        "Delta último",
                        "Z último",
                        "Alertas",
                      ].map((label, index) => (
                        <th key={label} className={index === 0 ? "py-2" : ""}>
                          <HelpMetric label={label} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {METRIC_SUMMARY_KEYS.map((key) => {
                      const summary = activeMetricsAnalysis.summary[key] || {};
                      return (
                        <tr key={key}>
                          <td className="py-2 font-bold text-slate-300">
                            <HelpMetric
                              label={metricLabel(activeMetricsAnalysis, key)}
                              chave={key}
                            />
                          </td>
                          <td>{fmt(summary.baseline, 2)}</td>
                          <td>{fmt(summary.session_mean, 2)}</td>
                          <td>{fmt(summary.last, 2)}</td>
                          <td>{fmtPct(summary.delta_last)}</td>
                          <td>{fmt(summary.z_last, 2)}</td>
                          <td>
                            {(summary.alerts || []).length ? (
                              <span className="rounded bg-amber-950/40 px-2 py-1 text-[10px] font-bold text-amber-100">
                                {(summary.alerts || []).join(", ")}
                              </span>
                            ) : (
                              <span className="text-slate-500">Sem alerta</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h2 className="mb-3 text-sm font-bold text-slate-100">
              <HelpTitle title="Composição do relatório" />
            </h2>
            <div className="grid gap-2 md:grid-cols-4">
              {(Object.keys(sections) as SectionKey[]).map((key) => (
                <label
                  key={key}
                  className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs font-semibold text-slate-300"
                >
                  <input
                    type="checkbox"
                    checked={sections[key]}
                    onChange={() => toggle(key)}
                  />
                  {key}
                </label>
              ))}
            </div>
          </section>

          {sections.baseline && (
            <MetricList title="Parâmetros iniciais - 60 segundos" snapshot={report.baseline} />
          )}
          {sections.averages && (
            <MetricList title="Média das métricas da sessão" snapshot={report.sessionAverage} />
          )}

          {sections.cuts && (
            <CompactMetricTable
              title="Cortes da sessão"
              rows={report.tenMinuteCuts.map((cut) => {
                const summary = findSummaryForCut(
                  cut,
                  report.conversationSummaries || [],
                );
                return {
                  label: cutTimeLabel(cut, summary),
                  metrics: metricRows(cut),
                };
              })}
            />
          )}

          <TranscricaoDaSessao transcript={report.transcript} />

          {sections.summaries && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-100">
                <HelpTitle title="Resumo geral da sessão" />
              </h2>
              <div className="rounded border border-blue-800 bg-blue-950 p-3">
                <p className="text-xs font-bold text-blue-100">
                  Tema predominante:{" "}
                  {limitThemeWords(sessionSummary.theme || report.sessionAverage.theme, 6)}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-blue-100">
                  {limitWords(sessionSummary.summary, SESSION_SUMMARY_MAX_WORDS)}
                </p>
              </div>
            </section>
          )}

          {sections.summaries && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              {/* A conversa com o FROID Explica ja vinha sendo anexada ao
                  registro no encerramento, e nunca era mostrada aqui — que e
                  justamente onde o profissional escreve o relatorio descritivo
                  e precisa reler o que perguntou durante o atendimento. */}
              {!!(report.froidExplicaConversation || []).length && (
                <details className="mb-4 rounded-lg border border-cyan-900 bg-cyan-950/30">
                  <summary className="cursor-pointer list-none p-3 text-sm font-bold text-cyan-100">
                    FROID Explica nesta sessão —{" "}
                    {(report.froidExplicaConversation || []).length} mensagem(ns)
                    <span className="ml-2 text-[11px] font-normal text-cyan-300 underline">
                      abrir
                    </span>
                  </summary>
                  <div className="space-y-2 p-3 pt-0">
                    {(report.froidExplicaConversation || []).map((mensagem, indice) => (
                      <div
                        key={`${indice}-${mensagem.role}`}
                        className={`rounded border p-2 text-xs leading-5 ${
                          mensagem.role === "user"
                            ? "border-slate-700 bg-slate-950 text-slate-300"
                            : "border-cyan-900 bg-cyan-950/40 text-cyan-50"
                        }`}
                      >
                        <span className="mb-1 block text-[10px] font-black uppercase tracking-widest text-slate-400">
                          {mensagem.role === "user" ? "Você perguntou" : "FROID Explica"}
                        </span>
                        {mensagem.content}
                      </div>
                    ))}
                  </div>
                  <p className="px-3 pb-3 text-[11px] leading-5 text-slate-400">
                    Apoio à redação do relatório. O que o FROID Explica respondeu
                    não é conduta nem diagnóstico — a interpretação e a decisão
                    continuam sendo do profissional.
                  </p>
                </details>
              )}

              <h2 className="mb-3 text-sm font-bold text-slate-100">
                <HelpTitle title="Temas e Resumos por Cortes" />
              </h2>
              <div className="space-y-2">
                {!(report.conversationSummaries || []).length && (
                  <p className="rounded border border-slate-700 bg-slate-950 p-3 text-xs italic text-slate-500">
                    Nenhum corte semântico registrado para esta sessão.
                  </p>
                )}
                {[...(report.conversationSummaries || [])]
                  .sort((a, b) => {
                    const aStart = a.startSecond ?? a.startMinute * 60;
                    const bStart = b.startSecond ?? b.startMinute * 60;
                    // Do primeiro corte para o ultimo, como a sessao aconteceu.
                    return aStart - bStart;
                  })
                  .map((item) => {
                    const cut = findCutForSummary(item, report.tenMinuteCuts);
                    const metricLine = summaryMetricLine(cut);
                    return (
                      <div key={item.id} className="rounded border border-slate-700 bg-slate-950 p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="text-xs font-bold text-slate-200">
                              {item.startMinute}-{item.endMinute}min |{" "}
                              {limitThemeWords(item.theme, 6)}
                            </p>
                          </div>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-slate-300">
                          {limitWords(item.summary, 80)}
                        </p>
                        {metricLine && (
                          <p className="mt-2 rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-[10px] leading-relaxed text-slate-300">
                            <span className="font-bold text-slate-200">Metricas:</span>{" "}
                            {metricLine}
                          </p>
                        )}
                        {!cut && (
                          <p className="mt-2 text-[10px] italic text-amber-600">
                            Métricas deste corte indisponíveis no registro legado.
                          </p>
                        )}
                      </div>
                    );
                  })}
              </div>
            </section>
          )}

          {sections.notes && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-100">
                <HelpTitle title="Observações do profissional" />
              </h2>
              <div className="space-y-2">
                {report.clinicalNotes.length === 0 && (
                  <p className="text-xs italic text-slate-500">
                    Nenhuma anotação clínica registrada.
                  </p>
                )}
                {report.clinicalNotes.map((note) => (
                  <div key={note.id} className="rounded border border-slate-700 bg-slate-950 p-3">
                    <p className="whitespace-pre-wrap text-xs text-slate-300">
                      {note.text}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {new Date(note.timestamp).toLocaleString("pt-BR")}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.dissonances && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-100">
                <HelpTitle title="Dissonâncias registradas" />
              </h2>
              <div className="space-y-2">
                {report.dissonances.length === 0 && (
                  <p className="text-xs italic text-slate-500">
                    Nenhuma dissonância persistente registrada.
                  </p>
                )}
                {report.dissonances.map((item) => (
                  <div key={item.id} className="rounded border border-red-800 bg-red-950/40 p-3">
                    <p className="text-xs font-bold text-red-100">
                      Zona {item.zone} | {item.elapsedSeconds}s
                    </p>
                    <p className="mt-1 text-xs text-red-200">{item.report}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {(report.froidExplicaConversation?.length || 0) > 0 && (
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-100">
                Consultas ao FROID Explica na sessão
              </h2>
              <div className="space-y-2">
                {(report.froidExplicaConversation || []).map((message, index) => (
                  <div
                    key={index}
                    className={`rounded border p-3 text-xs ${
                      message.role === "user"
                        ? "border-blue-800 bg-blue-950/40 text-blue-100"
                        : "border-slate-700 bg-slate-950 text-slate-200"
                    }`}
                  >
                    <p className="mb-1 font-bold uppercase tracking-wide text-[10px] text-slate-400">
                      {message.role === "user" ? "Profissional" : "FROID Explica"}
                    </p>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        <aside className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <section className="min-h-[520px] rounded-lg border border-slate-700 bg-slate-900 p-3">
            <AIInsights
              zones={report.sessionAverage.zones || []}
              ipmScore={report.sessionAverage.ipmAvg}
              coherenceStatus={report.sessionAverage.coherenceStatus}
              baselineEstablished
              sessionId={report.sessionId}
              responseLocale={locale}
              extraContext={reportContext}
              controlsSticky
              messagesClassName="min-h-[300px]"
            />
          </section>

          <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-sm font-bold text-slate-100">
                <HelpTitle title="Relatório Descritivo" />
              </h2>
              <div className="flex items-center gap-1.5">
              <button
                onClick={() => gerarPdf("professional")}
                disabled={!descriptiveEdited}
                title={
                  descriptiveEdited
                    ? "Gera o documento do profissional para impressão ou PDF."
                    : "Escreva o relatório com as suas palavras antes de gerar o documento."
                }
                className="rounded border border-cyan-700 bg-cyan-950 px-2 py-1 text-[10px] font-bold text-cyan-100 hover:bg-cyan-900 disabled:cursor-not-allowed disabled:opacity-40"
              >
                PDF profissional
              </button>
              <button
                onClick={() => gerarPdf("patient")}
                title="Gera o documento que o paciente recebe, sem rótulo técnico."
                className="rounded border border-amber-700 bg-amber-950 px-2 py-1 text-[10px] font-bold text-amber-100 hover:bg-amber-900"
              >
                PDF paciente
              </button>
              <button
                onClick={() => navigator.clipboard?.writeText(descriptiveReport)}
                className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-bold text-slate-300 hover:bg-slate-900"
              >
                Copiar
              </button>
              </div>
            </div>

            {/* Composição e liberação do documento do paciente. Fica aqui, e não
                numa tela à parte, porque é a mesma decisão que o profissional
                está tomando ao redigir: o que este paciente deve ler. */}
            <div className="mb-3 rounded-lg border border-amber-900/60 bg-amber-950/20 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-black text-amber-100">
                  O que o paciente recebe na área dele
                </h3>
                <span
                  className={
                    releaseState.released
                      ? "rounded-full bg-emerald-900/60 px-2 py-0.5 text-[10px] font-black text-emerald-200"
                      : "rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-black text-slate-300"
                  }
                >
                  {releaseState.released ? "Liberado" : "Retido"}
                </span>
              </div>

              {!patientResultsEnabled && (
                <p className="mt-2 rounded border border-amber-800 bg-amber-950/50 p-2 text-[11px] leading-4 text-amber-200">
                  Este paciente está com o acesso aos resultados desligado na ficha.
                  Liberar aqui deixa o relatório pronto, mas ele só aparecerá para o
                  paciente quando o acesso for habilitado.
                </p>
              )}

              <p className="mt-2 text-[11px] leading-4 text-slate-400">
                Marque os blocos que entram no documento do paciente. O documento do
                profissional não depende desta escolha — ele sai sempre completo.
              </p>

              <div className="mt-2 grid gap-1 sm:grid-cols-2">
                {releaseCatalog.map((item) => (
                  <label
                    key={item.key}
                    className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-slate-900/60"
                  >
                    <input
                      type="checkbox"
                      checked={releaseItems.includes(item.key)}
                      onChange={() => toggleReleaseItem(item.key)}
                      className="h-3.5 w-3.5 shrink-0 accent-amber-500"
                    />
                    <span className="text-[11px] font-bold text-slate-200">{item.label}</span>
                  </label>
                ))}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  onClick={() => salvarLiberacao(true)}
                  disabled={releaseSaving || !releaseItems.length}
                  title={
                    releaseItems.length
                      ? "Publica o relatório na área do paciente, com os blocos marcados."
                      : "Marque ao menos um bloco para compor o relatório."
                  }
                  className="rounded border border-emerald-700 bg-emerald-950 px-2 py-1 text-[10px] font-bold text-emerald-100 hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {releaseState.released ? "Atualizar liberação" : "Liberar ao paciente"}
                </button>
                {releaseState.released && (
                  <button
                    onClick={() => salvarLiberacao(false)}
                    disabled={releaseSaving}
                    title="Retira o relatório da área do paciente imediatamente."
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-bold text-slate-300 hover:bg-slate-900 disabled:opacity-40"
                  >
                    Revogar
                  </button>
                )}
                {releaseState.legacy && !releaseSaving && (
                  <span className="text-[10px] font-bold text-slate-400">
                    Sessão anterior a este controle: visível ao paciente por
                    compatibilidade.
                  </span>
                )}
                {releaseAviso && (
                  <span className="text-[10px] font-bold text-amber-200">{releaseAviso}</span>
                )}
              </div>
            </div>

            {!descriptiveEdited && (
              <p className="mb-2 rounded border border-amber-800 bg-amber-950/50 px-2 py-1.5 text-[10px] leading-4 text-amber-100">
                O texto abaixo foi composto pelo sistema. Reescreva-o com as suas
                palavras para liberar o documento do profissional — quem assina
                responde pelo que está escrito.
              </p>
            )}
            {pdfAviso && (
              <p className="mb-2 rounded border border-red-800 bg-red-950/60 px-2 py-1.5 text-[10px] text-red-200">
                {pdfAviso}
              </p>
            )}
            <textarea
              value={descriptiveReport}
              onChange={(event) => setDescriptiveReport(event.target.value)}
              className="min-h-72 w-full resize-y rounded border border-slate-700 bg-slate-950 p-3 text-xs leading-relaxed text-slate-200 outline-none focus:border-cyan-500 focus:bg-slate-900"
              placeholder="Cole aqui os pontos relevantes que serão usados no relatório para paciente, pares ou impressão."
            />
            <p className="mt-2 text-[10px] text-slate-500">
              Campo fixo para edição, cópia e posterior composição do documento de impressão.
            </p>
          </section>
        </aside>
      </main>
    </div>
    </ReportLocaleContext.Provider>
  );
};
