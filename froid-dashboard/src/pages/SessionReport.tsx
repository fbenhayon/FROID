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
    "resumo geral indisponivel",
    "ausencia de transcricao",
  ].some((token) => normalized.includes(token));
}

const TITLE_TOOLTIPS: Record<string, string> = {
  "Linha comparativa da sessao":
    "Compara o baseline inicial de 60 segundos com a media consolidada da sessao.",
  "Evolucao FROID":
    "Grafico normalizado pelo baseline inicial. A linha 100 representa o ponto de partida da sessao.",
  "Leitura estatistica das metricas":
    "Resume baseline, media, ultimo corte, delta e escore-z das metricas evolutivas do FROID.",
  "Composicao do relatorio":
    "Permite escolher quais blocos entram na visualizacao e no relatorio da consulta.",
  "Parametros iniciais - 60 segundos":
    "Primeira fotografia bioacustica e multimodal da sessao, tomada apos a ativacao do audio do paciente.",
  "Media das metricas da sessao":
    "Media consolidada dos marcadores coletados durante todo o periodo analisado da sessao.",
  "Cortes de 10 minutos":
    "Janelas temporais da sessao com as mesmas metricas da media, permitindo comparar a evolucao corte a corte.",
  "Resumo geral da sessao":
    "Sintese analitica final da sessao, limitada a 300 palavras, com tema predominante de ate 6 palavras.",
  "Temas e resumos por janela":
    "Resumo de cada janela temporal, limitado a 60 palavras, com tema de ate 6 palavras.",
  "Observacoes do profissional":
    "Anotacoes clinicas registradas manualmente pelo profissional durante a sessao.",
  "Dissonancias registradas":
    "Lista apenas dissonancias persistentes acima do limiar clinico configurado.",
  "Relatorio Descritivo":
    "Campo editavel para o profissional montar texto a copiar, enviar ou futuramente imprimir.",
};

const METRIC_TOOLTIPS: Record<string, string> = {
  Corte: "Janela temporal analisada na sessao.",
  IPM: "Indice de Potencia Multimodal: intensidade global ou energia emocional empregada.",
  IDM: "Indice de Desvio Multimodal: direcao e grau do desequilibrio multimodal.",
  "Z Domin.": "Zona FROID dominante no periodo analisado.",
  Tema: "Tema predominante consolidado da sessao ou do bloco analisado.",
  Tom: "Tom emocional inferido pela combinacao vocal e semantica.",
  "P/min": "Palavras por minuto no periodo analisado.",
  "Disso.": "Quantidade de dissonancias facial-vocais persistentes registradas.",
  MFCC7: "Biomarcador acustico associado a conteudo de valencia negativa e risco depressivo quando combinado a outros sinais.",
  MFCC9: "Biomarcador acustico acompanhado em fala neutra, relevante para tensao autonomica e ansiedade somatica.",
  "F0 Med.": "Frequencia fundamental media da voz no periodo.",
  ZCR: "Taxa de cruzamento por zero, relacionada a textura/ruido e dinamica acustica.",
  Jitter: "Microvariacao ciclo a ciclo da frequencia vocal.",
  Shimmer: "Microvariacao ciclo a ciclo da amplitude vocal.",
  "Sub-H 5-12Hz": "Energia sub-harmonica baixa, usada no cruzamento com sinais autonomicos.",
  "Sub-H 12-20Hz": "Energia sub-harmonica complementar para leitura bioacustica.",
  Metrica: "Nome da metrica estatistica analisada pelo motor evolutivo.",
  Baseline: "Valor inicial de referencia, apurado no baseline da sessao.",
  Media: "Media consolidada da sessao para a metrica.",
  "Ultimo corte": "Valor mais recente observado nos cortes temporais.",
  "Delta ultimo": "Variacao percentual do ultimo corte em relacao ao baseline.",
  "Z ultimo": "Desvio padronizado do ultimo corte em relacao ao comportamento de referencia.",
  Alertas: "Alertas estatisticos ou clinicos levantados para a metrica.",
  ipm: "Indice de Potencia Multimodal no motor estatistico.",
  idm: "Indice de Desvio Multimodal no motor estatistico.",
  words_per_minute: "Velocidade media de fala em palavras por minuto.",
  facial_vocal_dissonance: "Dissonancia entre expressao facial e trilha vocal.",
  clinical_risk: "Risco clinico agregado calculado pelo motor FROID.",
  "Palavras/min": "Velocidade media de fala em palavras por minuto.",
  Dissonancia: "Dissonancia entre expressao facial e trilha vocal.",
  "Risco clinico": "Risco clinico agregado calculado pelo motor FROID.",
};

const HelpTitle: React.FC<{ title: string; className?: string }> = ({
  title,
  className = "text-sm font-bold text-slate-900",
}) => (
  <FroidTooltip
    width={320}
    content={
      <div>
        <p className="font-bold text-slate-900">{title}</p>
        <p className="mt-1">{TITLE_TOOLTIPS[title] || "Informacao do bloco."}</p>
      </div>
    }
  >
    <span className={`${className} cursor-help border-b border-dashed border-slate-300`}>
      {title}
    </span>
  </FroidTooltip>
);

const HelpMetric: React.FC<{ label: string }> = ({ label }) => (
  <FroidTooltip
    width={300}
    content={
      <div>
        <p className="font-bold text-slate-900">{label}</p>
        <p className="mt-1">{METRIC_TOOLTIPS[label] || "Metrica FROID."}</p>
      </div>
    }
  >
    <span className="cursor-help border-b border-dashed border-slate-300">
      {label}
    </span>
  </FroidTooltip>
);

function dominantReportTheme(report: SessionReportRecord) {
  const ordered = [...(report.conversationSummaries || [])].sort(
    (a, b) => a.startMinute - b.startMinute,
  );
  const themeSource = [
    ...ordered
      .filter((item) => hasSubstantiveSummary(item.summary))
      .map((item) => item.theme),
    report.sessionSummary?.theme || "",
    report.sessionAverage.theme || "",
    report.baseline.theme || "",
  ].join(" ");
  return limitWords(themeSource || "Tema em apuracao", 6);
}

function metricDeltaSentence(label: string, baseline: number, average: number, digits = 2) {
  if (!Number.isFinite(baseline) || !Number.isFinite(average)) return "";
  const delta = average - baseline;
  const direction =
    Math.abs(delta) < 0.01
      ? "permaneceu estavel"
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
            `${item.startMinute}-${item.endMinute}min, ${limitWords(item.theme, 6)}: ${item.summary}`,
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
      ? `zona dominante ${report.sessionAverage.dominantZone} (${report.sessionAverage.dominantTheme || report.sessionAverage.theme || "tema em apuracao"})`
      : "",
    report.sessionAverage.emotionalTone
      ? `tom predominante ${report.sessionAverage.emotionalTone}`
      : "",
    Number.isFinite(report.sessionAverage.wordsPerMinute)
      ? `${report.sessionAverage.wordsPerMinute.toFixed(1)} palavras/min em media`
      : "",
    report.sessionAverage.dissonanceCount
      ? `${report.sessionAverage.dissonanceCount} dissonancia(s) media(s) acima do limiar`
      : "sem dissonancias medias relevantes registradas",
  ]
    .filter(Boolean)
    .join("; ");

  const body = progressionSource
    ? limitWords(cleanSummaryText(progressionSource), 185)
    : "";
  const analyticalClose = body
    ? `A sequencia dos cortes indica que a substancia central da sessao se organizou em torno de ${theme.toLowerCase()}, com progressao narrativa observavel entre os blocos registrados. ${body}. Na leitura multimodal, ${metricText}. Em conclusao, o registro recomenda que o profissional leia o conteudo verbal em conjunto com a variacao bioacustica e zonal, usando os proximos encontros para comparar se o tema se estabiliza, se desloca ou se intensifica em relacao ao baseline desta consulta.`
    : `A sessao teve tema predominante ${theme}, mas nao reuniu transcricao ou cortes semanticos suficientes para uma conclusao textual completa. Na leitura multimodal, ${metricText}. Em conclusao, o relatorio deve ser utilizado principalmente como linha de base comparativa, aguardando proximas sessoes com maior densidade verbal para consolidar a substancia clinica do processo.`;

  return {
    theme,
    summary:
      limitWords(cleanSummaryText(analyticalClose), SESSION_SUMMARY_MAX_WORDS) ||
      "Resumo geral indisponivel para esta sessao.",
    generatedAt: report.sessionSummary?.generatedAt || report.createdAt,
  };
}

function norm(value: number | null | undefined, baseline: number | null | undefined) {
  if (
    value === null ||
    value === undefined ||
    baseline === null ||
    baseline === undefined ||
    !Number.isFinite(value) ||
    !Number.isFinite(baseline) ||
    Number(baseline) === 0
  ) {
    return null;
  }
  return (Number(value) / Number(baseline)) * 100;
}

function metricRows(snapshot: MetricSnapshot) {
  return [
    ["IPM", fmt(snapshot.ipmAvg, 1)],
    ["IDM", fmt(snapshot.idmAvg, 2)],
    ["Z Domin.", snapshot.dominantZone ? `Zona ${snapshot.dominantZone}` : "--"],
    ["Tema", snapshot.theme || "--"],
    ["Tom", snapshot.emotionalTone || "--"],
    ["P/min", fmt(snapshot.wordsPerMinute, 1)],
    ["Disso.", String(snapshot.dissonanceCount || 0)],
    ["MFCC7", fmt(snapshot.mfcc7, 3)],
    ["MFCC9", fmt(snapshot.mfcc9, 3)],
    ["F0 Med.", fmt(snapshot.f0Mean, 2)],
    ["ZCR", fmt(snapshot.zcr, 3)],
    ["Jitter", fmt(snapshot.jitter, 3)],
    ["Shimmer", fmt(snapshot.shimmer, 3)],
    ["Sub-H 5-12Hz", fmt(snapshot.subharmonic5_12, 3)],
    ["Sub-H 12-20Hz", fmt(snapshot.subharmonic12_20, 3)],
  ];
}

function cutMetricRows(snapshot: MetricSnapshot, sessionTheme: string) {
  return metricRows(snapshot).map(([label, value]) =>
    label === "Tema" ? ["Tema", sessionTheme || "--"] : [label, value],
  );
}

function buildDescriptiveReportText(
  report: SessionReportRecord,
  sessionSummary: { theme: string; summary: string },
) {
  return [
    `Relatorio descritivo da sessao ${report.sessionId}`,
    `Data: ${new Date(report.createdAt).toLocaleString("pt-BR")}`,
    `Duracao: ${formatDuration(report.durationSeconds)}`,
    `Tema predominante: ${limitWords(sessionSummary.theme || report.sessionAverage.theme, 6)}`,
    "",
    `Resumo geral: ${limitWords(sessionSummary.summary, SESSION_SUMMARY_MAX_WORDS)}`,
    "",
    `Linha comparativa: IPM ${fmt(report.baseline.ipmAvg, 1)} -> ${fmt(report.sessionAverage.ipmAvg, 1)}; IDM ${fmt(report.baseline.idmAvg, 2)} -> ${fmt(report.sessionAverage.idmAvg, 2)}; Zona ${report.sessionAverage.dominantZone || "--"}; Tom ${report.sessionAverage.emotionalTone || "--"}; ${fmt(report.sessionAverage.wordsPerMinute, 1)} palavras/min.`,
    "",
    `Observacoes clinicas registradas: ${report.clinicalNotes.length}. Dissonancias persistentes registradas: ${report.dissonances.length}.`,
  ].join("\n");
}

const CompactMetricTable: React.FC<{
  title: string;
  rows: Array<{ label: string; metrics: string[][] }>;
}> = ({ title, rows }) => (
  <section className="rounded-lg border border-slate-200 bg-white p-4">
    <div className="mb-3">
      <HelpTitle title={title} />
    </div>
    <div className="overflow-x-auto">
      <table className="w-full table-auto text-left text-[10px] leading-tight">
        <thead className="text-[9px] uppercase tracking-normal text-slate-400">
          <tr>
            <th className="whitespace-nowrap py-1 pr-2">
              <HelpMetric label="Corte" />
            </th>
            {rows[0]?.metrics.map(([label]) => (
              <th
                key={label}
                className="max-w-28 whitespace-nowrap px-1 py-1 font-bold"
              >
                <HelpMetric label={label} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.label} className="align-top">
              <td className="whitespace-nowrap py-1 pr-2 font-bold text-slate-700">
                {row.label}
              </td>
              {row.metrics.map(([label, value]) => (
                <td
                  key={`${row.label}-${label}`}
                  className="max-w-28 truncate px-1 py-1 text-slate-700"
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
  "words_per_minute",
  "facial_vocal_dissonance",
  "clinical_risk",
];

function metricLabel(analysis: MetricsAnalysis | null, key: string) {
  return analysis?.metrics.find((metric) => metric.key === key)?.label || key;
}

const EvolutionChart: React.FC<{ analysis: MetricsAnalysis }> = ({ analysis }) => {
  const rows = analysis.evolution || [];
  const series = [
    {
      key: "ipm",
      label: "IPM",
      color: "#2563eb",
      values: rows.map((row) => norm(row.ipm, analysis.summary.ipm?.baseline)),
    },
    {
      key: "idm",
      label: "IDM",
      color: "#16a34a",
      values: rows.map((row) => norm(row.idm, analysis.summary.idm?.baseline)),
    },
    {
      key: "words_per_minute",
      label: "Palavras/min",
      color: "#d97706",
      values: rows.map((row) =>
        norm(row.words_per_minute, analysis.summary.words_per_minute?.baseline),
      ),
    },
    {
      key: "facial_vocal_dissonance",
      label: "Dissonancia",
      color: "#dc2626",
      values: rows.map((row) =>
        norm(
          row.facial_vocal_dissonance,
          analysis.summary.facial_vocal_dissonance?.baseline,
        ),
      ),
    },
  ];
  const values = series.flatMap((item) =>
    item.values.filter((value): value is number => Number.isFinite(value)),
  );
  const min = Math.min(80, ...values);
  const max = Math.max(120, ...values);
  const width = 640;
  const height = 220;
  const pad = { left: 42, right: 18, top: 20, bottom: 42 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (index: number) =>
    pad.left + (rows.length <= 1 ? plotW / 2 : (index / (rows.length - 1)) * plotW);
  const y = (value: number) =>
    pad.top + ((max - value) / Math.max(1, max - min)) * plotH;
  const points = (valuesForSeries: Array<number | null>) =>
    valuesForSeries
      .map((value, index) =>
        value === null || value === undefined || !Number.isFinite(value)
          ? null
          : `${x(index).toFixed(1)},${y(value).toFixed(1)}`,
      )
      .filter(Boolean)
      .join(" ");

  if (!rows.length) {
    return (
      <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-xs italic text-slate-400">
        Evolucao estatistica aguardando cortes com dados.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3">
      <div className="mb-2 flex flex-wrap items-center gap-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {series.map((item) => (
          <span key={item.key} className="inline-flex items-center gap-1">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            {item.label}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full">
        {rows.map((row, index) => (
          <g key={`x-grid-${row.label}-${index}`}>
            <line
              x1={x(index)}
              x2={x(index)}
              y1={pad.top}
              y2={height - pad.bottom}
              stroke="#e2e8f0"
              strokeDasharray="2 4"
            />
            <line
              x1={x(index)}
              x2={x(index)}
              y1={height - pad.bottom}
              y2={height - pad.bottom + 5}
              stroke="#94a3b8"
            />
          </g>
        ))}
        <line
          x1={pad.left}
          x2={width - pad.right}
          y1={height - pad.bottom}
          y2={height - pad.bottom}
          stroke="#94a3b8"
        />
        {[min, 100, max].map((tick) => (
          <g key={tick}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(tick)}
              y2={y(tick)}
              stroke={tick === 100 ? "#94a3b8" : "#e2e8f0"}
              strokeDasharray={tick === 100 ? "4 4" : "0"}
            />
            <text x={8} y={y(tick) + 4} fontSize="10" fill="#64748b">
              {tick.toFixed(0)}
            </text>
          </g>
        ))}
        {series.map((item) => (
          <g key={item.key}>
            <polyline
              points={points(item.values)}
              fill="none"
              stroke={item.color}
              strokeWidth="3"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {item.values.map((value, index) =>
              value === null || value === undefined || !Number.isFinite(value) ? null : (
                <circle
                  key={`${item.key}-${index}`}
                  cx={x(index)}
                  cy={y(value)}
                  r="3.5"
                  fill={item.color}
                />
              ),
            )}
          </g>
        ))}
        {rows.map((row, index) => (
          <text
            key={row.label}
            x={x(index)}
            y={height - 16}
            textAnchor="middle"
            fontSize="9"
            fill="#64748b"
          >
            {Number.isFinite(row.start_min) && Number.isFinite(row.end_min)
              ? `${row.start_min}-${row.end_min}m`
              : row.label}
          </text>
        ))}
      </svg>
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
        if (active) setMetricsError(error instanceof Error ? error.message : "Metricas indisponiveis");
      });
    return () => {
      active = false;
    };
  }, [sessionId]);

  const reportContext = useMemo(() => {
    if (!report) return {};
    const summary = derivedSessionSummary(report);
    return {
      report_baseline: report.baseline,
      report_session_average: report.sessionAverage,
      report_ten_minute_cuts: report.tenMinuteCuts,
      report_session_summary: summary,
      report_metrics_analysis: metricsAnalysis,
      report_notes_count: report.clinicalNotes.length,
      report_summaries: report.conversationSummaries,
    };
  }, [metricsAnalysis, report]);

  useEffect(() => {
    if (!report || descriptiveReport.trim()) return;
    setDescriptiveReport(buildDescriptiveReportText(report, derivedSessionSummary(report)));
  }, [descriptiveReport, report]);

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-700">
        <div className="max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <h1 className="text-lg font-bold text-slate-900">
            Relatorio nao encontrado
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            O relatorio da sessao ainda nao foi gerado neste navegador.
          </p>
          <button
            onClick={() => navigate("/dashboard")}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700"
          >
            Voltar ao dashboard
          </button>
        </div>
      </div>
    );
  }

  const toggle = (key: SectionKey) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));
  const activeMetricsAnalysis = metricsAnalysis || report.metricsAnalysis || null;
  const sessionSummary = derivedSessionSummary(report);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-600">
              Relatorio da Consulta
            </p>
            <h1 className="text-xl font-bold text-slate-900">
              Sessao {report.sessionId}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(report.createdAt).toLocaleString("pt-BR")} | Duracao{" "}
              {formatDuration(report.durationSeconds)}
            </p>
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
          >
            Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl items-start gap-4 p-6 lg:grid-cols-[1fr_390px]">
        <div className="space-y-4">
          <section className="rounded-lg border border-blue-100 bg-blue-50 p-4">
            <div className="mb-3">
              <HelpTitle
                title="Linha comparativa da sessao"
                className="text-sm font-bold text-blue-950"
              />
            </div>
            <div className="grid gap-2 md:grid-cols-5">
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IPM baseline
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.baseline.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IPM medio
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.sessionAverage.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IDM baseline
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.baseline.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IDM medio
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.sessionAverage.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  Tema inicial
                </p>
                <p className="text-sm font-bold text-blue-950">
                  {report.baseline.theme}
                </p>
              </div>
            </div>
          </section>

          {sections.evolution && activeMetricsAnalysis && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">
                    <HelpTitle title="Evolucao FROID" />
                  </h2>
                  <p className="text-[11px] text-slate-500">
                    Curvas normalizadas pelo baseline inicial de 60 segundos.
                  </p>
                </div>
                <span
                  className={`rounded px-2 py-1 text-[10px] font-black uppercase ${
                    activeMetricsAnalysis.dashboard.data_status === "Adequado"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {activeMetricsAnalysis.dashboard.data_status}
                </span>
              </div>
              <div className="mb-3 grid gap-2 md:grid-cols-5">
                <div className="rounded border border-slate-100 bg-slate-50 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-400">
                    Cortes com dados
                  </p>
                  <p className="text-lg font-black text-slate-900">
                    {activeMetricsAnalysis.dashboard.populated_windows}
                  </p>
                </div>
                <div className="rounded border border-slate-100 bg-slate-50 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-400">
                    Cobertura media
                  </p>
                  <p className="text-lg font-black text-slate-900">
                    {fmtPct(activeMetricsAnalysis.dashboard.mean_coverage)}
                  </p>
                </div>
                <div className="rounded border border-slate-100 bg-slate-50 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-400">
                    Confianca media
                  </p>
                  <p className="text-lg font-black text-slate-900">
                    {fmtPct(activeMetricsAnalysis.dashboard.mean_confidence)}
                  </p>
                </div>
                <div className="rounded border border-slate-100 bg-slate-50 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-400">
                    Alertas
                  </p>
                  <p className="text-lg font-black text-slate-900">
                    {activeMetricsAnalysis.dashboard.alerts_count}
                  </p>
                </div>
                <div className="rounded border border-slate-100 bg-slate-50 p-2">
                  <p className="text-[10px] font-bold uppercase text-slate-400">
                    Criticos
                  </p>
                  <p className="text-lg font-black text-slate-900">
                    {activeMetricsAnalysis.dashboard.critical_alerts}
                  </p>
                </div>
              </div>
              <EvolutionChart analysis={activeMetricsAnalysis} />
            </section>
          )}

          {sections.evolution && !activeMetricsAnalysis && (
            <section className="rounded-lg border border-amber-100 bg-amber-50 p-4 text-xs text-amber-800">
              Motor evolutivo aguardando analise do servidor.
              {metricsError ? ` ${metricsError}` : ""}
            </section>
          )}

          {sections.statistics && activeMetricsAnalysis && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                <HelpTitle title="Leitura estatistica das metricas" />
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                    <tr>
                      {[
                        "Metrica",
                        "Baseline",
                        "Media",
                        "Ultimo corte",
                        "Delta ultimo",
                        "Z ultimo",
                        "Alertas",
                      ].map((label, index) => (
                        <th key={label} className={index === 0 ? "py-2" : ""}>
                          <HelpMetric label={label} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {METRIC_SUMMARY_KEYS.map((key) => {
                      const summary = activeMetricsAnalysis.summary[key] || {};
                      return (
                        <tr key={key}>
                          <td className="py-2 font-bold text-slate-700">
                            <HelpMetric label={metricLabel(activeMetricsAnalysis, key)} />
                          </td>
                          <td>{fmt(summary.baseline, 2)}</td>
                          <td>{fmt(summary.session_mean, 2)}</td>
                          <td>{fmt(summary.last, 2)}</td>
                          <td>{fmtPct(summary.delta_last)}</td>
                          <td>{fmt(summary.z_last, 2)}</td>
                          <td>
                            {(summary.alerts || []).length ? (
                              <span className="rounded bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-700">
                                {(summary.alerts || []).join(", ")}
                              </span>
                            ) : (
                              <span className="text-slate-400">Sem alerta</span>
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

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-bold text-slate-900">
              <HelpTitle title="Composicao do relatorio" />
            </h2>
            <div className="grid gap-2 md:grid-cols-4">
              {(Object.keys(sections) as SectionKey[]).map((key) => (
                <label
                  key={key}
                  className="flex items-center gap-2 rounded border border-slate-100 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-600"
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
            <MetricList title="Parametros iniciais - 60 segundos" snapshot={report.baseline} />
          )}
          {sections.averages && (
            <MetricList title="Media das metricas da sessao" snapshot={report.sessionAverage} />
          )}

          {sections.cuts && (
            <CompactMetricTable
              title="Cortes de 10 minutos"
              rows={report.tenMinuteCuts.map((cut) => ({
                label: cut.label,
                metrics: cutMetricRows(
                  cut,
                  limitWords(sessionSummary.theme || report.sessionAverage.theme, 6),
                ),
              }))}
            />
          )}

          {sections.summaries && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                <HelpTitle title="Resumo geral da sessao" />
              </h2>
              <div className="rounded border border-blue-100 bg-blue-50 p-3">
                <p className="text-xs font-bold text-blue-950">
                  Tema predominante:{" "}
                  {limitWords(sessionSummary.theme || report.sessionAverage.theme, 6)}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-blue-900">
                  {limitWords(sessionSummary.summary, SESSION_SUMMARY_MAX_WORDS)}
                </p>
              </div>
            </section>
          )}

          {sections.summaries && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                <HelpTitle title="Temas e resumos por janela" />
              </h2>
              <div className="space-y-2">
                {report.conversationSummaries.map((item) => (
                  <div key={item.id} className="rounded border border-slate-100 bg-slate-50 p-3">
                    <p className="text-xs font-bold text-slate-800">
                      {item.startMinute}-{item.endMinute}min |{" "}
                      {limitWords(item.theme, 6)}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">
                      {limitWords(item.summary, 60)}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.notes && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                <HelpTitle title="Observacoes do profissional" />
              </h2>
              <div className="space-y-2">
                {report.clinicalNotes.length === 0 && (
                  <p className="text-xs italic text-slate-400">
                    Nenhuma anotacao clinica registrada.
                  </p>
                )}
                {report.clinicalNotes.map((note) => (
                  <div key={note.id} className="rounded border border-slate-100 bg-slate-50 p-3">
                    <p className="whitespace-pre-wrap text-xs text-slate-700">
                      {note.text}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      {new Date(note.timestamp).toLocaleString("pt-BR")}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.dissonances && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                <HelpTitle title="Dissonancias registradas" />
              </h2>
              <div className="space-y-2">
                {report.dissonances.length === 0 && (
                  <p className="text-xs italic text-slate-400">
                    Nenhuma dissonancia persistente registrada.
                  </p>
                )}
                {report.dissonances.map((item) => (
                  <div key={item.id} className="rounded border border-red-100 bg-red-50 p-3">
                    <p className="text-xs font-bold text-red-900">
                      Zona {item.zone} | {item.elapsedSeconds}s
                    </p>
                    <p className="mt-1 text-xs text-red-800">{item.report}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        <aside className="space-y-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <section className="min-h-[420px] rounded-lg border border-slate-200 bg-white p-4">
            <AIInsights
              zones={report.sessionAverage.zones || []}
              ipmScore={report.sessionAverage.ipmAvg}
              coherenceStatus={report.sessionAverage.coherenceStatus}
              baselineEstablished
              sessionId={report.sessionId}
              extraContext={reportContext}
            />
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-sm font-bold text-slate-900">
                <HelpTitle title="Relatorio Descritivo" />
              </h2>
              <button
                onClick={() => navigator.clipboard?.writeText(descriptiveReport)}
                className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-100"
              >
                Copiar
              </button>
            </div>
            <textarea
              value={descriptiveReport}
              onChange={(event) => setDescriptiveReport(event.target.value)}
              className="min-h-72 w-full resize-y rounded border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-800 outline-none focus:border-blue-400 focus:bg-white"
              placeholder="Cole aqui os pontos relevantes que serao usados no relatorio para paciente, pares ou impressao."
            />
            <p className="mt-2 text-[10px] text-slate-400">
              Campo fixo para edicao, copia e posterior composicao do documento de impressao.
            </p>
          </section>
        </aside>
      </main>
    </div>
  );
};
