import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";

interface LiveSessionProps {
  user?: any;
}
import { useParams, useNavigate } from "react-router-dom";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import { RiskChart } from "../components/indicators/RiskChart";
import { SpectralBandsChart } from "../components/indicators/SpectralBandsChart";
import { SubharmonicChart } from "../components/indicators/SubharmonicChart";
import { MediaStatus } from "../components/indicators/MediaStatus";
import { SessionTimer } from "../components/indicators/SessionTimer";
import { AIInsights } from "../components/panels/AIInsights";
import { AudioTranscription } from "../components/panels/AudioTranscription";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import { FroidPayload, PerceptionZone } from "../lib/froid-engine";
import { getAUDetails, ZONE_CLINICAL_DESCRIPTIONS } from "../lib/froid-data";
import { apiUrl, wsUrl } from "../lib/api";
import {
  attachRemoteMedia,
  configureConferenceSender,
  createConferenceStream,
  loadRtcConfiguration,
} from "../lib/webrtc";
import {
  MetricSnapshot,
  loadSessionPatient,
  loadSessionReports,
  saveSessionReport,
  SessionReportRecord,
} from "../lib/session-report";

const SIMPLIFIED_METRIC_TOOLTIPS: Record<string, string> = {
  CORTE:
    "Intervalo temporal em análise desde o último corte semântico, seja automático ou executado pelo profissional.",
  IPM:
    "Índice de Potencia Motivacional. Funciona como o velocímetro emocional: indica a intensidade global da energia vocal, facial e semântica do paciente.",
  IDM:
    "Índice de Desvio Multimodal. Indica a direção e o grau de afastamento entre voz, face, semântica e zonas FROID.",
  ZONAS:
    "Zona FROID predominante no corte atual, calculada pela composição das métricas bioacústicas, semânticas e multimodais.",
  TOM:
    "Tom emocional predominante inferido pela composição entre fala transcrita, marcadores acústicos e contexto do corte.",
  "P/MIN":
    "Palavras por minuto no corte atual. Ajuda a identificar aceleração, lentificação, bloqueios ou mudancas de cadência.",
  "DISSO.":
    "Quantidade de dissonâncias confirmadas acima da métrica definida no corte atual. Exibe somente apontamentos efetivamente detectados.",
  MFCC7:
    "Coeficiente cepstral vocal associado ao timbre e a energia espectral. No FROID, ganha relevância quando cruza valencia semântica negativa e marcadores de retardo ou tensão.",
  MFCC9:
    "Coeficiente cepstral vocal usado como marcador complementar de tensão autônoma, especialmente quando observado em trechos semanticamente neutros.",
  DMFCC7:
    "Delta do MFCC7. Mede a variação de primeira ordem do coeficiente durante o corte.",
  DMFCC9:
    "Delta do MFCC9. Mede a variação de primeira ordem do coeficiente durante o corte.",
  DDMFCC7:
    "Delta-delta do MFCC7. Indica aceleração ou desaceleração da mudanca cepstral.",
  DDMFCC9:
    "Delta-delta do MFCC9. Indica aceleração ou desaceleração da mudanca cepstral.",
  "F0 MED.":
    "Frequência fundamental média da voz. Ajuda a observar elevação de pitch, queda vocal, tensão ou variações de ativação.",
  ZCR:
    "Taxa de cruzamento por zero. Aponta irregularidade acústica e componentes de aspereza, ruído ou tensão vocal.",
  JITTER:
    "Índice interno normalizado de perturbação de frequência, derivado para comparação longitudinal no FROID. Não e percentual acústico bruto.",
  SHIMMER:
    "Índice interno normalizado de variação de amplitude vocal, derivado para comparação longitudinal no FROID. Não e medida bruta em dB.",
  DELTA:
    "Energia de modulação vocal na faixa delta. No FROID, representa modulação bioacústica lenta, não atividade EEG direta.",
  THETA:
    "Energia de modulação vocal na faixa theta. Usada como marcador de oscilacao lenta da expressão vocal.",
  ALPHA:
    "Energia de modulação vocal na faixa alpha. Ajuda a compor estabilidade, ritmo e organização da emissao.",
  BETA:
    "Energia de modulação vocal na faixa beta. Ajuda a compor índices de ativação, esforco e tensão cognitiva.",
  GAMA:
    "Energia de modulação vocal na faixa gama. Ajuda a observar ativação rápida e instabilidade espectral fina.",
  "IND. ESPECTRAL":
    "Índice composto das bandas espectrais vocais, usado para sintetizar o perfil de modulação bioacústica do corte.",
  "SUB-H 5-12":
    "Energia sub-harmônica entre 5 e 12 Hz. No FROID, integra o nucleo de leitura autônoma e sinais de sobrecarga profunda.",
  "SUB-H 12-20":
    "Energia sub-harmônica entre 12 e 20 Hz. Complementa a leitura de tremor, tensão e modulação involuntária.",
  "SUB-H 20-40":
    "Energia sub-harmônica entre 20 e 40 Hz. Complementa a leitura de excitacao, instabilidade e microtremores vocais.",
  "VOCAL 85-165":
    "Banda basal de tensão vocal. Ajuda a identificar sustentacao, constricao e esforco na base da emissao.",
  "DNA INFRA":
    "Componente nuclear de infrassom vocal usado na matriz bioacústica do FROID.",
  "DNA LIMBICO":
    "Componente de modulação límbica estimado pela combinação de sub-harmônicos, voz e contexto emocional.",
  "DNA VOCAL":
    "Componente de tensão vocal basal usado para compor riscos, dissonâncias e estado de ativação.",
  "DNA FLOOD":
    "Indicador composto de flooding autonômico, sugerindo sobrecarga ou intensificacao fisiológica relevante.",
  "DNA SHUTDOWN":
    "Indicador composto de retraimento ou desligamento dissociativo, quando a assinatura bioacústica sugere queda defensiva.",
  "DNA NEURO":
    "Índice de ressonancia neurogenica estimado por combinações sub-harmônicas e estabilidade vocal.",
  "DNA SOMATO":
    "Índice de dissonância somatoafetiva, usado para cruzar expressão vocal, tensão e marcadores corporais inferidos.",
};

const SIMPLIFIED_CUT_TOOLTIP =
  "O corte organiza a sessão em janelas analisaveis. A cada fechamento, o FROID consolida tema, resumo da fala, métricas vocais, indicadores bioacústicos e dissonâncias relevantes.";

interface AggData {
  zones: PerceptionZone[];
  ipm: number;
  coherence: string;
  globalColor: string;
  globalDesc: string;
  alerts: string[];
  drValue: number;
  audioMeta: any;
  commitments: any[];
}

interface ConversationSummary {
  id: string;
  startSecond?: number;
  endSecond?: number;
  startMinute: number;
  endMinute: number;
  theme: string;
  summary: string;
  trigger?: "automatico_10min" | "manual" | "final";
}

type SpeakerRole = "PC" | "DR";
type SpeakerIdMode = "auto" | "manual";
type ClinicalUpdateMode = "realtime" | "1" | "3" | "5" | "7";

interface VoiceSignature {
  vector: number[];
  threshold: number;
  sampleCount: number;
  createdAt: string;
}

interface SessionState {
  connected: boolean;
  payload: FroidPayload | null;
  baselineIPM: number | null;
  elapsedSeconds: number;
  phase: "CALIBRATING" | "LIVE" | "ENDED";
  ipmHistory: number[];
  cameraOn: boolean;
  micOn: boolean;
  sessionStart: number;
  camError: string;
  aggregated: AggData | null;
  localIpm: number | null;
}

type Action =
  | { type: "WS_OPEN" }
  | { type: "WS_CLOSE" }
  | { type: "TICK" }
  | { type: "BASELINE_LOCK"; ipm: number }
  | { type: "PAYLOAD"; data: FroidPayload }
  | { type: "LOCAL_IPM"; ipm: number }
  | { type: "AGGREGATE"; agg: AggData }
  | {
      type: "MEDIA_STATUS";
      cameraOn: boolean;
      micOn: boolean;
      camError?: string;
    }
  | { type: "END_SESSION" };

const DISSONANCE_REPORT_THRESHOLD = 1.5;
const DISSONANCE_CRITICAL_THRESHOLD = 3.0;
const DISSONANCE_MFCC_DELTA_THRESHOLD = 0.35;
const DISSONANCE_DNA_THRESHOLD = 0.18;
const DISSONANCE_IPM_DELTA_THRESHOLD = 3.0;
const IPM_HISTORY_LIMIT = 1200;
const CLINICAL_MICRO_WINDOW_SECONDS = 60;
const CLINICAL_DEFAULT_UPDATE_MODE: ClinicalUpdateMode = "5";
const CLINICAL_UPDATE_STORAGE_KEY = "froid_clinical_update_mode";
const CLINICAL_UPDATE_OPTIONS: Array<{ value: ClinicalUpdateMode; label: string }> = [
  { value: "realtime", label: "Tempo real" },
  { value: "1", label: "1 min" },
  { value: "3", label: "3 min" },
  { value: "5", label: "5 min" },
  { value: "7", label: "7 min" },
];
const DR_VOICEPRINT_STORAGE_KEY = "froid_dr_voiceprint_v1";

function dissonanceScore(zone?: PerceptionZone | null) {
  return Math.abs(Number(zone?.deviation_score || 0));
}

function isReportableDissonance(zone?: PerceptionZone | null) {
  const activeAus = zone?.dissonance_details?.active_aus || [];
  return Boolean(
    zone?.facial_dissonance_detected &&
      zone?.dissonance_details &&
      activeAus.length > 0 &&
      dissonanceScore(zone) > DISSONANCE_REPORT_THRESHOLD,
  );
}

function hasConfirmedDissonanceEvidence(
  zone?: PerceptionZone | null,
  audioMeta?: Record<string, unknown>,
) {
  if (!isReportableDissonance(zone)) return false;
  const score = dissonanceScore(zone);
  const sub5 = Number(audioMeta?.subharmonic_energy_5_12hz || 0);
  const basal = Number(audioMeta?.energy_85_165hz || 0);
  const mfcc7 = Number(audioMeta?.mfcc7 || 0);
  const mfcc9 = Number(audioMeta?.mfcc9 || 0);
  const hasAcousticMarker =
    Math.abs(score) >= DISSONANCE_REPORT_THRESHOLD ||
    sub5 > 0.05 ||
    basal > 0.05 ||
    mfcc7 > 0 ||
    mfcc9 > 0;

  return hasAcousticMarker;
}

function dissonanceSeverity(zone?: PerceptionZone | null) {
  return dissonanceScore(zone) > DISSONANCE_CRITICAL_THRESHOLD
    ? "CRITICA"
    : "RELEVANTE";
}

function normalizeAuCode(code: string) {
  const match = String(code || "").toUpperCase().match(/AU?\s*(\d+)/);
  return match ? Number(match[1]) : null;
}

function hasAu(auSet: Set<number>, ...codes: number[]) {
  return codes.some((code) => auSet.has(code));
}

function readFiniteNumber(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function metricDelta(
  audioMeta: Record<string, unknown> | undefined,
  currentKey: string,
  baselineKey: string,
) {
  const current = readFiniteNumber(audioMeta?.[currentKey]);
  const baseline = readFiniteNumber(audioMeta?.[baselineKey]);
  if (current === null || baseline === null) return null;
  return current - baseline;
}

function classifyDissonance(zone?: PerceptionZone | null, audioMeta?: Record<string, unknown>) {
  const activeAus = zone?.dissonance_details?.active_aus || [];
  const auSet = new Set(
    activeAus
      .map(normalizeAuCode)
      .filter((code): code is number => typeof code === "number"),
  );
  const score = dissonanceScore(zone);
  const sub5 = Number(audioMeta?.subharmonic_energy_5_12hz || 0);
  const basal = Number(audioMeta?.energy_85_165hz || 0);
  const hasDeepSna = sub5 >= 0.35 || score >= DISSONANCE_CRITICAL_THRESHOLD;

  if (hasDeepSna && hasAu(auSet, 15) && hasAu(auSet, 20)) {
    return {
      title: "Risco de retraumatizacao / flooding autonômico",
      summary:
        "O motor de dissonâncias cruzou tremor sub-harmônico de 5-12 Hz, tensão basal e AUs 15/20, indicando vazamento extrapiramidal de dor/panico acima do relato consciente.",
      action:
        "Mitigar reduzindo intensidade, desacelerando a exploracao, usando aterramento, orientacao ao presente, respiracao ritmada e checagem da janela de tolerância antes de prosseguir.",
    };
  }
  if (hasDeepSna && hasAu(auSet, 15) && basal < 0.25) {
    return {
      title: "Shutdown psíquico / dissociacao",
      summary:
        "A combinação de tremor autonômico profundo, AU15 e baixa energia vocal basal sugere queda de disponibilidade, congelamento ou supressão defensiva da expressão emocional.",
      action:
        "Mitigar pausando confronto direto, reduzindo demanda cognitiva, restaurando orientacao corporal e confirmando se o paciente permanece presente e responsivo.",
    };
  }
  if (hasAu(auSet, 12) && !hasAu(auSet, 6)) {
    return {
      title: "Sorriso falso / falsa calma",
      summary:
        "AU12 sem AU6 indica sorriso voluntário sem marcador Duchenne; quando o IDM também sobe, o FROID interpreta possível mascara social cobrindo tensão interna.",
      action:
        "Mitigar validando a fala sem confrontar bruscamente, investigando com perguntas abertas a diferença entre calma relatada e carga corporal observada.",
    };
  }
  if (hasAu(auSet, 23, 24) || (zone?.zone === 7 && score > DISSONANCE_REPORT_THRESHOLD)) {
    return {
      title: "Raiva contida / resposta verbal suprimida",
      summary:
        "AUs 23/24 ou pico na Zona 7 indicam contencao mecanica dos labios diante de energia vocal de conflito, sugerindo resposta verbal freada ou agressividade reprimida.",
      action:
        "Mitigar abrindo espaço seguro para nomear irritacao, limite ou injustica percebida, preservando contencao e evitando escalada confrontativa.",
    };
  }
  if (hasAu(auSet, 1) && hasAu(auSet, 4) && hasAu(auSet, 15)) {
    return {
      title: "Tristeza mascarada",
      summary:
        "A conjuncao AU1+AU4+AU15 sugere vazamento involuntário de tristeza ou dor profunda, especialmente quando a fala aparenta neutralidade, controle ou bem-estar.",
      action:
        "Mitigar desacelerando o ritmo, explorando perdas e desamparo com linguagem permissiva e evitando insistencia caso surjam sinais de retraimento.",
    };
  }
  if (hasAu(auSet, 12, 14) && activeAus.some((au) => /^[LR]/i.test(String(au)))) {
    return {
      title: "Desprezo unilateral",
      summary:
        "Ativação unilateral de AU12/AU14 aponta assimetria expressiva compatível com desprezo, resistência ou defesa de superioridade em contexto relacional.",
      action:
        "Mitigar observando o contexto interpessoal, investigando julgamentos, vergonha ou rivalidade com neutralidade fenomenologica e sem rotular o paciente.",
    };
  }
  if (hasAu(auSet, 5, 20, 25, 26, 27) || hasAu(auSet, 4, 5, 7)) {
    return {
      title: "Microexpressao contraditoria",
      summary:
        "O FROID detectou vazamento facial breve de medo, panico, raiva ou foco defensivo contradizendo a neutralidade aparente em janela temporal curta.",
      action:
        "Mitigar registrando o instante clínico, checando o tema que precedeu o vazamento e testando a hipótese com pergunta aberta, sem assumir diagnóstico isolado.",
    };
  }
  return {
    title: "Dissonância facial-vocal relevante",
    summary:
      zone?.dissonance_details?.report ||
      "O rosto, a voz e/ou a semântica apresentaram incongruencia acima do limiar configurado do IDM, indicando possível desalinhamento entre intencao consciente e expressão involuntária.",
    action:
      "Mitigar usando o achado apenas como marcador de investigacao, cruzando relato, contexto, biomarcadores, AUs, mapa zonal e resposta do paciente.",
  };
}

function formatMetricValue(value: unknown, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

function dissonanceTechnicalFactors(
  zone?: PerceptionZone | null,
  audioMeta?: Record<string, unknown>,
  currentIpm?: number | null,
  baselineIpm?: number | null,
) {
  const aus = zone?.dissonance_details?.active_aus || [];
  const score = dissonanceScore(zone);
  const severity = dissonanceSeverity(zone).toLowerCase();
  const semantic =
    String(
      audioMeta?.semantic_valence ||
        audioMeta?.semantic_tone ||
        audioMeta?.substancia_semantica ||
        "",
    ).trim() || "não informada";
  const mfcc7Delta = metricDelta(audioMeta, "mfcc7", "baseline_mfcc7");
  const mfcc9Delta = metricDelta(audioMeta, "mfcc9", "baseline_mfcc9");
  const dnaInfrasound = readFiniteNumber(audioMeta?.dna_infrasound_nuclear);
  const dnaBasal = readFiniteNumber(audioMeta?.dna_vocal_basal_tension);
  const dnaFlooding = readFiniteNumber(audioMeta?.dna_autonomic_flooding);
  const dnaShutdown = readFiniteNumber(audioMeta?.dna_dissociative_shutdown);
  const dnaSomato = readFiniteNumber(audioMeta?.dna_somatoaffective_dissonance);
  const dnaNeurogenic = readFiniteNumber(audioMeta?.dna_neurogenic_resonance);
  const jitter = readFiniteNumber(audioMeta?.jitter);
  const shimmer = readFiniteNumber(audioMeta?.shimmer);
  const ipmDelta =
    typeof currentIpm === "number" && typeof baselineIpm === "number"
      ? currentIpm - baselineIpm
      : null;

  const factors = [
    `IDM ${score.toFixed(2)} (${severity}) acima do limiar ${DISSONANCE_REPORT_THRESHOLD.toFixed(2)}: o desvio energético compara E_vocal contra E_baseline e aplica M_fac quando há contradição facial-vocal.`,
    `Morfodinamica facial/FACS: AUs ativas ${aus.length ? aus.join(", ") : "sem AU específica reportada"}; a leitura exige coerencia temporal entre neutral, onset, apex e offset para reduzir falso positivo.`,
    `Zona ${zone?.zone ?? "--"} (${zone?.tema || "tema em apuração"}): ${ZONE_CLINICAL_DESCRIPTIONS[zone?.zone || 0] || "sem descricao zonal."}`,
  ];

  if (mfcc7Delta !== null && Math.abs(mfcc7Delta) >= DISSONANCE_MFCC_DELTA_THRESHOLD) {
    factors.push(
      `MFCC7 divergente: ${formatMetricValue(audioMeta?.mfcc7)} contra baseline ${formatMetricValue(audioMeta?.baseline_mfcc7)} (delta ${mfcc7Delta.toFixed(2)}), marcador acústico associado a valencia negativa quando sustentado em fala emocionalmente carregada.`,
    );
  }
  if (mfcc9Delta !== null && Math.abs(mfcc9Delta) >= DISSONANCE_MFCC_DELTA_THRESHOLD) {
    factors.push(
      `MFCC9 divergente: ${formatMetricValue(audioMeta?.mfcc9)} contra baseline ${formatMetricValue(audioMeta?.baseline_mfcc9)} (delta ${mfcc9Delta.toFixed(2)}), sugerindo tensão autônoma latente quando cruza discurso neutro ou controlado.`,
    );
  }
  if (dnaInfrasound !== null && dnaInfrasound >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Sub-harmônicos 5-12 Hz acima da métrica (${dnaInfrasound.toFixed(2)}): indicam tremor autonômico vocal detectado na trilha bruta do paciente.`,
    );
  }
  if (dnaBasal !== null && dnaBasal >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Tensão basal 85-165 Hz acima da métrica (${dnaBasal.toFixed(2)}): aponta carga laríngea/respiratoria sustentada sob a fala.`,
    );
  }
  if (dnaFlooding !== null && dnaFlooding >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Flooding autonômico acima da métrica (${dnaFlooding.toFixed(2)}): combinação de energia sub-harmônica, tensão basal e multiplicador facial.`,
    );
  }
  if (dnaShutdown !== null && dnaShutdown >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Shutdown/dissociacao acima da métrica (${dnaShutdown.toFixed(2)}): queda relativa de disponibilidade expressiva com tremor autonômico residual.`,
    );
  }
  if (dnaSomato !== null && dnaSomato >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Dissonância somatoafetiva acima da métrica (${dnaSomato.toFixed(2)}): contraste corpo-voz-face suficiente para registro clínico.`,
    );
  }
  if (dnaNeurogenic !== null && dnaNeurogenic >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Ressonancia neurogenica acima da métrica (${dnaNeurogenic.toFixed(2)}): alteração sub-harmônica em faixa superior compatível com ativação corporal não verbalizada.`,
    );
  }
  if (jitter !== null && jitter >= VOICE_PERTURBATION_PROXY_ALERT_THRESHOLD) {
    factors.push(
      `Jitter proxy elevado (${jitter.toFixed(2)}): índice interno normalizado derivado de ZCR escalado, usado como sinal de instabilidade vocal relativa; não equivale diretamente a jitter percentual normativo.`,
    );
  }
  if (shimmer !== null && shimmer >= VOICE_PERTURBATION_PROXY_ALERT_THRESHOLD) {
    factors.push(
      `Shimmer proxy elevado (${shimmer.toFixed(2)}): índice interno normalizado da variação relativa do envelope RMS, usado como sinal de instabilidade energética; não equivale diretamente a shimmer em dB.`,
    );
  }
  if (ipmDelta !== null && Math.abs(ipmDelta) >= DISSONANCE_IPM_DELTA_THRESHOLD) {
    factors.push(
      `IPM divergiu da baseline inicial em ${ipmDelta.toFixed(1)} pontos: a intensidade global mudou o suficiente para compor o alerta multimodal.`,
    );
  }
  if (semantic && !/^não informada$/i.test(semantic) && !/^neutro$/i.test(semantic)) {
    factors.push(
      `Semântica verbal considerada ${semantic}: o FROID cruza o conteúdo transcrito com face e voz para detectar contradição entre relato e expressão involuntária.`,
    );
  }

  return factors;
}

function buildDissonanceReportText(
  zone: PerceptionZone,
  audioMeta?: Record<string, unknown>,
  currentIpm?: number | null,
  baselineIpm?: number | null,
) {
  const score = dissonanceScore(zone);
  const interpretation = classifyDissonance(zone, audioMeta);
  const factors = dissonanceTechnicalFactors(zone, audioMeta, currentIpm, baselineIpm);
  return [
    `IDM ${score.toFixed(2)} | ${dissonanceSeverity(zone)} | Zona ${zone.zone}`,
    `${interpretation.title}: ${interpretation.summary}`,
    `Itens divergentes apurados: ${factors.join(" ")}`,
    `Sugestão técnica ao profissional: ${interpretation.action}`,
  ].join(" ");
}

function reducer(state: SessionState, action: Action): SessionState {
  try {
    switch (action.type) {
      case "WS_OPEN":
        return { ...state, connected: true };
      case "WS_CLOSE":
        return {
          ...state,
          connected: false,
          phase: state.phase,
        };
      case "TICK":
        return state.phase !== "ENDED" && state.micOn
          ? { ...state, elapsedSeconds: state.elapsedSeconds + 1 }
          : state;
      case "BASELINE_LOCK":
        return { ...state, baselineIPM: action.ipm, phase: "LIVE" };
      case "PAYLOAD": {
        const p = action.data || {};
        const nextHistory =
          state.phase === "LIVE"
            ? [
                ...state.ipmHistory,
                typeof p.ipm_score === "number" ? p.ipm_score : 0,
              ].slice(-IPM_HISTORY_LIMIT)
            : state.ipmHistory;
        return { ...state, payload: p, ipmHistory: nextHistory };
      }
      case "LOCAL_IPM": {
        const ipm = clamp(action.ipm, 0, 100);
        const shouldAppend = state.phase !== "ENDED" && state.micOn;
        return {
          ...state,
          localIpm: ipm,
          ipmHistory: shouldAppend
            ? [...state.ipmHistory, ipm].slice(-IPM_HISTORY_LIMIT)
            : state.ipmHistory,
        };
      }
      case "AGGREGATE":
        return { ...state, aggregated: action.agg };
      case "MEDIA_STATUS":
        return {
          ...state,
          cameraOn: action.cameraOn,
          micOn: action.micOn,
          sessionStart:
            action.micOn &&
            !state.micOn &&
            state.phase === "CALIBRATING" &&
            state.elapsedSeconds === 0
              ? Date.now()
              : state.sessionStart,
          camError: action.camError || "",
        };
      case "END_SESSION":
        return { ...state, phase: "ENDED", connected: false };
      default:
        return state;
    }
  } catch {
    return state;
  }
}

const createInitialState = (): SessionState => ({
  connected: false,
  payload: null,
  baselineIPM: null,
  elapsedSeconds: 0,
  phase: "CALIBRATING",
  ipmHistory: [],
  cameraOn: false,
  micOn: false,
  sessionStart: 0,
  camError: "",
  aggregated: null,
  localIpm: null,
});

class ErrorGuard extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; err: string }
> {
  constructor(p: any) {
    super(p);
    this.state = { hasError: false, err: "" };
  }
  static getDerivedStateFromError(err: any) {
    return { hasError: true, err: String(err?.message || err) };
  }
  componentDidCatch(err: any, info: any) {
    console.error("FROID Crash:", err, info);
  }
  render() {
    if (this.state.hasError)
      return (
        <div
          style={{
            padding: 40,
            background: "#fff",
            color: "#b91c1c",
            fontFamily: "system-ui",
            minHeight: "100vh",
          }}
        >
          <h1 style={{ fontSize: 20, fontWeight: 800, marginBottom: 12 }}>
            🚨 ERRO FROID
          </h1>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              fontSize: 13,
              background: "#fef2f2",
              padding: 16,
              borderRadius: 8,
              border: "1px solid #fecaca",
            }}
          >
            {this.state.err}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: 16,
              padding: "8px 16px",
              background: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            Recarregar
          </button>
        </div>
      );
    return this.props.children;
  }
}

const SimulatedCamera: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf = 0;
    const draw = () => {
      const t = Date.now() / 1000;
      ctx!.fillStyle = `hsl(${(t * 20) % 360}, 35%, 10%)`;
      ctx!.fillRect(0, 0, canvas.width, canvas.height);
      ctx!.strokeStyle = "rgba(255,255,255,0.06)";
      for (let i = 0; i < 12; i++) {
        ctx!.beginPath();
        ctx!.moveTo(0, i * 40 + Math.sin(t + i) * 10);
        for (let x = 0; x < canvas.width; x += 20)
          ctx!.lineTo(x, i * 40 + Math.sin(t + x * 0.01 + i) * 12);
        ctx!.stroke();
      }
      ctx!.fillStyle = "rgba(255,255,255,0.9)";
      ctx!.font = "bold 16px sans-serif";
      ctx!.fillText("FROID — Simulação Facial Ativa", 20, 32);
      ctx!.fillStyle = "rgba(160, 255, 200, 0.8)";
      ctx!.font = "12px sans-serif";
      ctx!.fillText(
        `Bioacústica sincronizada | ${new Date().toLocaleTimeString("pt-BR")}`,
        20,
        56,
      );
      ctx!.beginPath();
      ctx!.arc(
        canvas.width / 2,
        canvas.height / 2 + 10,
        55 + Math.sin(t * 1.5) * 14,
        0,
        Math.PI * 2,
      );
      ctx!.strokeStyle = "rgba(74, 222, 128, 0.5)";
      ctx!.lineWidth = 3;
      ctx!.stroke();
      ctx!.beginPath();
      ctx!.arc(
        canvas.width / 2 - 28,
        canvas.height / 2 - 5,
        10 + Math.sin(t * 2.3) * 3,
        0,
        Math.PI * 2,
      );
      ctx!.fillStyle = "rgba(96, 165, 250, 0.8)";
      ctx!.fill();
      ctx!.beginPath();
      ctx!.arc(
        canvas.width / 2 + 28,
        canvas.height / 2 - 5,
        10 + Math.cos(t * 2.3) * 3,
        0,
        Math.PI * 2,
      );
      ctx!.fillStyle = "rgba(96, 165, 250, 0.8)";
      ctx!.fill();
      ctx!.beginPath();
      ctx!.arc(
        canvas.width / 2,
        canvas.height / 2 + 38,
        20 + Math.sin(t * 4) * 6,
        0,
        Math.PI,
      );
      ctx!.strokeStyle = "rgba(250, 204, 21, 0.4)";
      ctx!.lineWidth = 2;
      ctx!.stroke();
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <canvas
      ref={canvasRef}
      width={640}
      height={480}
      className="w-full h-full object-cover"
    />
  );
};

function selectAudioMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionFromMimeType(mimeType: string) {
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("mpeg") || mimeType.includes("mp3")) return "mp3";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function measureAudioActivity(blob: Blob) {
  if (typeof window === "undefined") {
    return { active: true, rms: 1, peak: 1 };
  }

  const AudioContextCtor =
    (window as any).AudioContext || (window as any).webkitAudioContext;
  if (!AudioContextCtor) {
    return { active: true, rms: 1, peak: 1 };
  }

  const context = new AudioContextCtor();
  try {
    const buffer = await blob.arrayBuffer();
    const decoded = await context.decodeAudioData(buffer.slice(0));
    let sumSquares = 0;
    let peak = 0;
    let samples = 0;

    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const data = decoded.getChannelData(channel);
      for (let index = 0; index < data.length; index += 64) {
        const value = Math.abs(data[index]);
        sumSquares += value * value;
        peak = Math.max(peak, value);
        samples += 1;
      }
    }

    const rms = samples > 0 ? Math.sqrt(sumSquares / samples) : 0;
    return {
      active: peak >= 0.006 && rms >= 0.0006,
      rms,
      peak,
    };
  } catch {
    return { active: true, rms: 1, peak: 1 };
  } finally {
    void context.close?.();
  }
}

function clamp(value: number, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value));
}

function getSemanticAudioConstraints(): MediaTrackConstraints {
  return {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    channelCount: { ideal: 1 },
  };
}

function frequencyBandEnergy(
  data: Uint8Array,
  sampleRate: number,
  fftSize: number,
  minHz: number,
  maxHz: number,
) {
  const binHz = sampleRate / fftSize;
  const start = Math.max(0, Math.floor(minHz / binHz));
  const end = Math.min(data.length - 1, Math.ceil(maxHz / binHz));
  if (end <= start) return 0;

  let sum = 0;
  for (let index = start; index <= end; index += 1) {
    sum += data[index] / 255;
  }

  return clamp(sum / (end - start + 1));
}

function voiceFeatureVector(
  timeData: Float32Array,
  frequencyData: Uint8Array,
  sampleRate: number,
  fftSize: number,
) {
  let sumSquares = 0;
  let peak = 0;
  let zeroCrossings = 0;
  let previous = timeData[0] || 0;
  for (let index = 0; index < timeData.length; index += 1) {
    const value = timeData[index] || 0;
    const abs = Math.abs(value);
    sumSquares += value * value;
    peak = Math.max(peak, abs);
    if ((previous >= 0 && value < 0) || (previous < 0 && value >= 0)) {
      zeroCrossings += 1;
    }
    previous = value;
  }
  const rms = Math.sqrt(sumSquares / Math.max(1, timeData.length));
  if (peak < 0.006 || rms < 0.0006) return null;

  let weighted = 0;
  let total = 0;
  const binHz = sampleRate / fftSize;
  for (let index = 0; index < frequencyData.length; index += 1) {
    const energy = frequencyData[index] / 255;
    weighted += energy * index * binHz;
    total += energy;
  }
  const centroid = total > 0 ? weighted / total : 0;
  const low = frequencyBandEnergy(frequencyData, sampleRate, fftSize, 85, 255);
  const mid = frequencyBandEnergy(frequencyData, sampleRate, fftSize, 255, 900);
  const high = frequencyBandEnergy(frequencyData, sampleRate, fftSize, 900, 3200);
  const upper = frequencyBandEnergy(frequencyData, sampleRate, fftSize, 3200, 7000);
  return [
    clamp(rms * 12),
    clamp(peak * 3),
    clamp(zeroCrossings / timeData.length / 0.25),
    clamp(centroid / 5000),
    low,
    mid,
    high,
    upper,
  ];
}

function meanVector(samples: number[][]) {
  if (!samples.length) return [];
  const length = samples[0].length;
  return Array.from({ length }, (_, index) =>
    samples.reduce((sum, sample) => sum + (sample[index] || 0), 0) /
    samples.length,
  );
}

function voiceDistance(a: number[] | undefined, b: number[] | undefined) {
  if (!a?.length || !b?.length || a.length !== b.length) return Number.POSITIVE_INFINITY;
  const sum = a.reduce((total, value, index) => {
    const diff = value - b[index];
    return total + diff * diff;
  }, 0);
  return Math.sqrt(sum / a.length);
}

function buildVoiceSignature(samples: number[][]): VoiceSignature | null {
  if (samples.length < 18) return null;
  const vector = meanVector(samples);
  const distances = samples.map((sample) => voiceDistance(sample, vector));
  const avgDistance = distances.reduce((sum, value) => sum + value, 0) / distances.length;
  const variance =
    distances.reduce((sum, value) => sum + (value - avgDistance) ** 2, 0) /
    distances.length;
  const threshold = clamp(avgDistance + Math.sqrt(variance) * 3 + 0.045, 0.09, 0.26);
  return {
    vector,
    threshold,
    sampleCount: samples.length,
    createdAt: new Date().toISOString(),
  };
}

function loadDrVoiceSignature(): VoiceSignature | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(DR_VOICEPRINT_STORAGE_KEY) || "null");
    if (
      parsed &&
      Array.isArray(parsed.vector) &&
      parsed.vector.every((value: unknown) => typeof value === "number")
    ) {
      return parsed as VoiceSignature;
    }
  } catch {}
  return null;
}

function saveDrVoiceSignature(signature: VoiceSignature) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DR_VOICEPRINT_STORAGE_KEY, JSON.stringify(signature));
}

function envelopeBandEnergy(
  envelope: number[],
  frameRate: number,
  minHz: number,
  maxHz: number,
) {
  const n = Math.min(envelope.length, 128);
  if (n < 32 || frameRate <= 0) return 0;

  const values = envelope.slice(-n);
  const mean = values.reduce((total, value) => total + value, 0) / n;
  const centered = values.map((value) => value - mean);
  const nyquist = frameRate / 2;
  const minBin = Math.max(1, Math.ceil((minHz * n) / frameRate));
  const maxBin = Math.min(
    Math.floor((Math.min(maxHz, nyquist) * n) / frameRate),
    Math.floor(n / 2),
  );
  if (maxBin < minBin) return 0;

  let sum = 0;
  let bins = 0;
  for (let bin = minBin; bin <= maxBin; bin += 1) {
    let real = 0;
    let imaginary = 0;
    for (let index = 0; index < n; index += 1) {
      const angle = (2 * Math.PI * bin * index) / n;
      real += centered[index] * Math.cos(angle);
      imaginary -= centered[index] * Math.sin(angle);
    }
    sum += Math.sqrt(real * real + imaginary * imaginary) / n;
    bins += 1;
  }

  return clamp((sum / Math.max(1, bins)) * 18);
}

type DnaBandSample = {
  sub5_12: number;
  sub12_20: number;
  sub20_40: number;
  energy85_165: number;
  zcr: number;
};

type DnaBaselineState = {
  startedAtMs: number;
  samples: DnaBandSample[];
  baseline: DnaBandSample | null;
  locked: boolean;
  limbicRatioEma: number | null;
};

type CepstralSample = {
  mfcc7: number;
  mfcc9: number;
  mfcc7Delta: number;
  mfcc9Delta: number;
  mfcc7DeltaDelta: number;
  mfcc9DeltaDelta: number;
  baselineMfcc7: number | null;
  baselineMfcc9: number | null;
  desvioMfcc7: number | null;
  desvioMfcc9: number | null;
};

type CepstralBaselineState = {
  startedAtMs: number;
  samples: Array<{ mfcc7: number; mfcc9: number }>;
  baseline: { mfcc7: number; mfcc9: number } | null;
  previous: { mfcc7: number; mfcc9: number } | null;
  previousDelta: { mfcc7: number; mfcc9: number } | null;
  locked: boolean;
};

const DNA_EPSILON = 1e-9;
const DNA_BASELINE_MS = 60_000;
const BIOACOUSTIC_WINDOW_MS = 1000;
const VOICE_PERTURBATION_PROXY_ALERT_THRESHOLD = 0.45;
const JITTER_PROXY_UNIT = "internal_proxy_0_1_zcr_scaled";
const SHIMMER_PROXY_UNIT = "internal_proxy_0_1_envelope_cv";
const VOCAL_SPECTRAL_BAND_CONTEXT = "voice_modulation_not_eeg";

const meanDnaSample = (samples: DnaBandSample[]): DnaBandSample => {
  const safe = samples.length
    ? samples
    : [{ sub5_12: 0, sub12_20: 0, sub20_40: 0, energy85_165: 0, zcr: 0 }];
  return {
    sub5_12: safe.reduce((sum, item) => sum + item.sub5_12, 0) / safe.length,
    sub12_20: safe.reduce((sum, item) => sum + item.sub12_20, 0) / safe.length,
    sub20_40: safe.reduce((sum, item) => sum + item.sub20_40, 0) / safe.length,
    energy85_165: safe.reduce((sum, item) => sum + item.energy85_165, 0) / safe.length,
    zcr: safe.reduce((sum, item) => sum + item.zcr, 0) / safe.length,
  };
};

const positiveDeviation = (current: number, baseline: number) =>
  clamp((current - baseline) / (baseline + DNA_EPSILON));

function computeCepstralCoefficients(
  frequencyData: Uint8Array,
  sampleRate: number,
  fftSize: number,
) {
  const bandCount = 20;
  const minHz = 65;
  const maxHz = Math.min(8000, sampleRate / 2);
  const logMin = Math.log(minHz);
  const logMax = Math.log(maxHz);
  const bands: number[] = [];

  for (let band = 0; band < bandCount; band += 1) {
    const lower = Math.exp(logMin + (band / bandCount) * (logMax - logMin));
    const upper = Math.exp(logMin + ((band + 1) / bandCount) * (logMax - logMin));
    const energy = frequencyBandEnergy(frequencyData, sampleRate, fftSize, lower, upper);
    bands.push(Math.log(Math.max(1e-6, energy)));
  }

  const coefficients: number[] = [];
  for (let k = 0; k < bandCount; k += 1) {
    let sum = 0;
    for (let n = 0; n < bandCount; n += 1) {
      sum += bands[n] * Math.cos((Math.PI * k * (n + 0.5)) / bandCount);
    }
    coefficients.push(sum / bandCount);
  }
  return coefficients;
}

function meanCepstral(samples: Array<{ mfcc7: number; mfcc9: number }>) {
  const safe = samples.length ? samples : [{ mfcc7: 0, mfcc9: 0 }];
  return {
    mfcc7: safe.reduce((sum, item) => sum + item.mfcc7, 0) / safe.length,
    mfcc9: safe.reduce((sum, item) => sum + item.mfcc9, 0) / safe.length,
  };
}

function computeCepstralDynamics(
  frequencyData: Uint8Array,
  sampleRate: number,
  fftSize: number,
  state: CepstralBaselineState,
  now: number,
  voicePresence: boolean,
): CepstralSample {
  if (!voicePresence) {
    const baseline = state.baseline || (state.samples.length ? meanCepstral(state.samples) : null);
    return {
      mfcc7: 0,
      mfcc9: 0,
      mfcc7Delta: 0,
      mfcc9Delta: 0,
      mfcc7DeltaDelta: 0,
      mfcc9DeltaDelta: 0,
      baselineMfcc7: baseline ? rounded(baseline.mfcc7, 4) : null,
      baselineMfcc9: baseline ? rounded(baseline.mfcc9, 4) : null,
      desvioMfcc7: null,
      desvioMfcc9: null,
    };
  }

  if (!state.startedAtMs) state.startedAtMs = now;
  const coeffs = computeCepstralCoefficients(frequencyData, sampleRate, fftSize);
  const mfcc7 = rounded(coeffs[7] || 0, 4) || 0;
  const mfcc9 = rounded(coeffs[9] || 0, 4) || 0;
  const previous = state.previous || { mfcc7, mfcc9 };
  const mfcc7Delta = rounded(mfcc7 - previous.mfcc7, 4) || 0;
  const mfcc9Delta = rounded(mfcc9 - previous.mfcc9, 4) || 0;
  const previousDelta = state.previousDelta || { mfcc7: mfcc7Delta, mfcc9: mfcc9Delta };
  const mfcc7DeltaDelta = rounded(mfcc7Delta - previousDelta.mfcc7, 4) || 0;
  const mfcc9DeltaDelta = rounded(mfcc9Delta - previousDelta.mfcc9, 4) || 0;

  state.samples.push({ mfcc7, mfcc9 });
  if (state.samples.length > 600) state.samples.shift();
  if (!state.locked && state.samples.length > 0 && now - state.startedAtMs >= DNA_BASELINE_MS) {
    state.baseline = meanCepstral(state.samples);
    state.locked = true;
  }

  state.previous = { mfcc7, mfcc9 };
  state.previousDelta = { mfcc7: mfcc7Delta, mfcc9: mfcc9Delta };
  const baseline = state.baseline || meanCepstral(state.samples);
  const desvioMfcc7 =
    baseline.mfcc7 === 0 ? null : rounded((mfcc7 - baseline.mfcc7) / Math.abs(baseline.mfcc7), 4);
  const desvioMfcc9 =
    baseline.mfcc9 === 0 ? null : rounded((mfcc9 - baseline.mfcc9) / Math.abs(baseline.mfcc9), 4);

  return {
    mfcc7,
    mfcc9,
    mfcc7Delta,
    mfcc9Delta,
    mfcc7DeltaDelta,
    mfcc9DeltaDelta,
    baselineMfcc7: rounded(baseline.mfcc7, 4),
    baselineMfcc9: rounded(baseline.mfcc9, 4),
    desvioMfcc7,
    desvioMfcc9,
  };
}

function hasSuppressionAu(zones: PerceptionZone[]) {
  return zones.some((zone) =>
    (zone.dissonance_details?.active_aus || []).some((code) => {
      const normalized = normalizeAuCode(String(code));
      return normalized === 23 || normalized === 24;
    }),
  );
}

function computeDnaSubharmonics(
  frame: DnaBandSample,
  state: DnaBaselineState,
  now: number,
  zones: PerceptionZone[],
  ipm: number,
) {
  const hasSignal =
    frame.sub5_12 > 0 ||
    frame.sub12_20 > 0 ||
    frame.sub20_40 > 0 ||
    frame.energy85_165 > 0;
  if (hasSignal && !state.startedAtMs) state.startedAtMs = now;
  if (hasSignal) {
    state.samples.push(frame);
    if (state.samples.length > 3600) state.samples.shift();
  }
  if (
    state.startedAtMs &&
    !state.locked &&
    state.samples.length > 0 &&
    now - state.startedAtMs >= DNA_BASELINE_MS
  ) {
    state.baseline = meanDnaSample(state.samples);
    state.locked = true;
  }

  const baseline = state.baseline || meanDnaSample(state.samples);
  const dSub = positiveDeviation(frame.sub5_12, baseline.sub5_12);
  const dBasal = positiveDeviation(frame.energy85_165, baseline.energy85_165);
  const resNeuro = positiveDeviation(frame.sub20_40, baseline.sub20_40);
  const currentLimbicRatio =
    frame.sub12_20 / (frame.sub5_12 + frame.sub12_20 + DNA_EPSILON);
  const baselineLimbicRatio =
    baseline.sub12_20 / (baseline.sub5_12 + baseline.sub12_20 + DNA_EPSILON);
  state.limbicRatioEma =
    state.limbicRatioEma === null
      ? currentLimbicRatio
      : state.limbicRatioEma * 0.85 + currentLimbicRatio * 0.15;
  const ratioEma = currentLimbicRatio / (state.limbicRatioEma + DNA_EPSILON);
  const limbicModulation = clamp(
    Math.max(
      0,
      (currentLimbicRatio - baselineLimbicRatio) /
        (baselineLimbicRatio + DNA_EPSILON),
    ) * ratioEma,
  );

  const facialMultiplier = zones.some((zone) => zone.facial_dissonance_detected)
    ? 2.5
    : 1.0;
  const au2324 = hasSuppressionAu(zones) ? 1 : 0;
  const zcrDropRatio = clamp((baseline.zcr - frame.zcr) / (baseline.zcr + DNA_EPSILON));
  const ipmRatio = clamp(ipm / 100);
  const flooding = clamp((dSub * 0.55 + dBasal * 0.45) * (facialMultiplier / 2.5));
  const shutdown = clamp(dSub * (1 - ipmRatio) * zcrDropRatio);
  const somatoaffective = clamp(
    ((dSub + dBasal) / 2) *
      (1 + (facialMultiplier - 1) * au2324) /
      2.5,
  );
  const index = clamp(
    (dSub +
      limbicModulation +
      resNeuro +
      dBasal +
      flooding +
      shutdown +
      somatoaffective) /
      7,
  );

  return {
    dna_infrasound_nuclear: dSub,
    dna_limbic_modulation: limbicModulation,
    dna_neurogenic_resonance: resNeuro,
    dna_vocal_basal_tension: dBasal,
    dna_autonomic_flooding: flooding,
    dna_dissociative_shutdown: shutdown,
    dna_somatoaffective_dissonance: somatoaffective,
    dna_subharmonic_index: index,
    dna_baseline_locked: state.locked,
    dna_facial_multiplier: facialMultiplier,
  };
}

function calculateRawBioacousticFrame(
  timeData: Float32Array,
  frequencyData: Uint8Array,
  sampleRate: number,
  fftSize: number,
  envelope: number[],
  frameRate: number,
) {
  let sumSquares = 0;
  let peak = 0;
  let zeroCrossings = 0;
  let previous = timeData[0] || 0;

  for (let index = 0; index < timeData.length; index += 1) {
    const value = timeData[index];
    const abs = Math.abs(value);
    sumSquares += value * value;
    peak = Math.max(peak, abs);
    if ((previous < 0 && value >= 0) || (previous >= 0 && value < 0)) {
      zeroCrossings += 1;
    }
    previous = value;
  }

  const rms = Math.sqrt(sumSquares / Math.max(1, timeData.length));
  const zcr = zeroCrossings / Math.max(1, timeData.length - 1);
  envelope.push(rms);
  if (envelope.length > 180) envelope.shift();

  const voicePresence = rms >= 0.003 && peak >= 0.018;
  const voiceGain = voicePresence ? clamp((rms - 0.002) * 30) : 0;
  const meanEnvelope =
    envelope.reduce((total, value) => total + value, 0) /
    Math.max(1, envelope.length);
  const envelopeVariance =
    envelope.reduce((total, value) => {
      const diff = value - meanEnvelope;
      return total + diff * diff;
    }, 0) / Math.max(1, envelope.length);
  const shimmerProxyIndex = voicePresence
    ? clamp(Math.sqrt(envelopeVariance) / Math.max(0.0001, meanEnvelope))
    : 0;
  const jitterProxyIndex = voicePresence ? clamp(zcr * 45) : 0;
  const spectralDelta = envelopeBandEnergy(envelope, frameRate, 0.5, 4) * voiceGain;
  const spectralTheta = envelopeBandEnergy(envelope, frameRate, 4, 8) * voiceGain;
  const spectralAlpha = envelopeBandEnergy(envelope, frameRate, 8, 12) * voiceGain;
  const spectralBeta =
    Math.max(
      envelopeBandEnergy(envelope, frameRate, 12, 30),
      frequencyBandEnergy(frequencyData, sampleRate, fftSize, 12, 30),
    ) * voiceGain;
  const spectralGamma =
    frequencyBandEnergy(frequencyData, sampleRate, fftSize, 30, 80) * voiceGain;
  const spectralBandIndex = clamp(
    spectralDelta * 0.16 +
      spectralTheta * 0.18 +
      spectralAlpha * 0.16 +
      spectralBeta * 0.25 +
      spectralGamma * 0.25,
  );

  return {
    rms,
    peak,
    zcr,
    jitter: jitterProxyIndex,
    shimmer: shimmerProxyIndex,
    jitter_proxy_index: jitterProxyIndex,
    shimmer_proxy_index: shimmerProxyIndex,
    voicePresence,
    energy85_165: frequencyBandEnergy(
      frequencyData,
      sampleRate,
      fftSize,
      85,
      165,
    ) * voiceGain,
    sub5_12: envelopeBandEnergy(envelope, frameRate, 5, 12) * voiceGain,
    sub12_20: envelopeBandEnergy(envelope, frameRate, 12, 20) * voiceGain,
    sub20_40:
      Math.max(
        envelopeBandEnergy(envelope, frameRate, 20, 40),
        frequencyBandEnergy(frequencyData, sampleRate, fftSize, 20, 40),
      ) * voiceGain,
    spectralDelta,
    spectralTheta,
    spectralAlpha,
    spectralBeta,
    spectralGamma,
    spectralBandIndex,
  };
}

function computeLocalIpmFromBioacoustics(
  metrics: ReturnType<typeof calculateRawBioacousticFrame>,
  dnaMetrics: ReturnType<typeof computeDnaSubharmonics>,
) {
  if (!metrics.voicePresence) return null;

  const acousticDrive = metrics.rms * 650 + metrics.peak * 90;
  const perturbationDrive = (metrics.jitter + metrics.shimmer) * 8;
  const basalDrive = metrics.energy85_165 * 14;
  const subharmonicDrive = Number(dnaMetrics.dna_subharmonic_index || 0) * 24;

  return clamp(
    50 + acousticDrive + perturbationDrive + basalDrive + subharmonicDrive,
    0,
    100,
  );
}

const STT_CHUNK_MS = 7000;
const MIN_STT_AUDIO_BYTES = 1200;
const MAX_VISIBLE_TRANSCRIPT_LINES = 12;
const TRANSCRIPT_SUMMARY_WINDOW_MS = 10 * 60 * 1000;
const ENABLE_BROWSER_LIVE_STT = false;
const FROID_ALGORITHM_VERSION = "3.1.0-dashboard-bioacoustic-units";

function speakerPrefix(speaker: SpeakerRole) {
  return speaker === "DR" ? "DR. - " : "PC - ";
}

function formatCutClock(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60)
    .toString()
    .padStart(2, "0");
  const rest = (safeSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
}

function normalizeTranscriptText(text: string) {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function aggregatePayloads(payloads: FroidPayload[]): AggData {
  if (!payloads.length)
    return {
      zones: [],
      ipm: 0,
      coherence: "NEUTRO",
      globalColor: "CINZA",
      globalDesc: "Aguardando...",
      alerts: [],
      drValue: 5.0,
      audioMeta: {},
      commitments: [],
    };
  const last = payloads[payloads.length - 1];
  const zonesMap = new Map<number, PerceptionZone[]>();
  payloads.forEach((p) => {
    if (!Array.isArray(p.perception_zones)) return;
    p.perception_zones.forEach((z) => {
      if (!zonesMap.has(z.zone)) zonesMap.set(z.zone, []);
      zonesMap.get(z.zone)!.push(z);
    });
  });
  const zones: PerceptionZone[] = [];
  zonesMap.forEach((arr, _zoneId) => {
    const avgDev =
      arr.reduce(
        (s, z) =>
          s + (typeof z.deviation_score === "number" ? z.deviation_score : 0),
        0,
      ) / arr.length;
    const lastZ = arr[arr.length - 1];
    const dissCount = arr.filter((z) => !!z.facial_dissonance_detected).length;
    zones.push({
      ...lastZ,
      deviation_score: avgDev,
      facial_dissonance_detected: dissCount / arr.length >= 0.25,
    });
  });
  const allAlerts = payloads
    .flatMap((p) => p.realtime_alerts || [])
    .slice(0, 6);
  const avgIpm =
    payloads.reduce(
      (s, p) => s + (typeof p.ipm_score === "number" ? p.ipm_score : 0),
      0,
    ) / payloads.length;
  const dr = (last as any).dr_value ?? 5.0;
  return {
    zones: zones.sort((a, b) => a.zone - b.zone),
    ipm: avgIpm,
    coherence: last.coherence_status || "NEUTRO",
    globalColor: last.global_energy?.cor_plot || "CINZA",
    globalDesc: last.global_energy?.descricao || "Aguardando...",
    alerts: Array.from(new Set(allAlerts)),
    drValue: dr,
    audioMeta: (last as any).audio_meta || {},
    commitments: (last as any).commitment_models || [],
  };
}

type SessionSample = { elapsedSeconds: number; payload: FroidPayload };
type TranscriptSegment = { elapsedSeconds: number; text: string };

const REPORT_AUDIO_KEYS = [
  "mfcc7",
  "mfcc9",
  "mfcc7_delta",
  "mfcc9_delta",
  "mfcc7_delta_delta",
  "mfcc9_delta_delta",
  "f0_mean",
  "zcr",
  "jitter",
  "shimmer",
  "jitter_proxy_index",
  "shimmer_proxy_index",
  "spectral_delta_0_4hz",
  "spectral_theta_4_8hz",
  "spectral_alpha_8_12hz",
  "spectral_beta_12_30hz",
  "spectral_gamma_30_80hz",
  "spectral_band_index",
  "subharmonic_energy_5_12hz",
  "subharmonic_energy_12_20hz",
  "subharmonic_energy_20_40hz",
  "energy_85_165hz",
  "dna_infrasound_nuclear",
  "dna_limbic_modulation",
  "dna_vocal_basal_tension",
  "dna_autonomic_flooding",
  "dna_dissociative_shutdown",
  "dna_neurogenic_resonance",
  "dna_somatoaffective_dissonance",
  "dna_subharmonic_index",
] as const;

const CLINICAL_AUDIO_KEYS = [
  ...REPORT_AUDIO_KEYS,
  "raw_rms",
  "raw_peak",
  "audio_rms",
  "audio_peak",
  "jitter_proxy_index",
  "shimmer_proxy_index",
  "words_per_minute_10m",
] as const;

type ClinicalPresentationSnapshot = {
  mode: ClinicalUpdateMode;
  generatedAtSecond: number;
  nextUpdateSecond: number;
  windowStartSecond: number;
  windowEndSecond: number;
  microWindowCount: number;
  agg: AggData;
  metricSnapshot: MetricSnapshot;
  ipmHistory: number[];
};

function clinicalModeToMinutes(mode: ClinicalUpdateMode) {
  if (mode === "realtime") return 0;
  const parsed = Number(mode);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 5;
}

function loadClinicalUpdateMode(): ClinicalUpdateMode {
  if (typeof window === "undefined") return CLINICAL_DEFAULT_UPDATE_MODE;
  const stored = window.localStorage.getItem(CLINICAL_UPDATE_STORAGE_KEY);
  return CLINICAL_UPDATE_OPTIONS.some((option) => option.value === stored)
    ? (stored as ClinicalUpdateMode)
    : CLINICAL_DEFAULT_UPDATE_MODE;
}

function clinicalWeights(count: number) {
  if (count <= 1) return [1];
  if (count === 3) return [0.2, 0.3, 0.5];
  if (count === 5) return [0.1, 0.15, 0.2, 0.25, 0.3];
  if (count === 7) return [0.05, 0.07, 0.09, 0.12, 0.16, 0.21, 0.3];
  const raw = Array.from({ length: count }, (_, index) => index + 1);
  const total = raw.reduce((sum, value) => sum + value, 0);
  return raw.map((value) => value / total);
}

function weightedAverage(values: Array<{ value: number | null; weight: number }>) {
  const valid = values.filter((item) => typeof item.value === "number" && Number.isFinite(item.value));
  const totalWeight = valid.reduce((sum, item) => sum + item.weight, 0);
  if (!valid.length || totalWeight <= 0) return null;
  return (
    valid.reduce((sum, item) => sum + Number(item.value) * item.weight, 0) /
    totalWeight
  );
}

function latestString(values: Array<string | undefined | null>) {
  return [...values].reverse().find((value) => String(value || "").trim()) || "";
}

function buildClinicalPresentationSnapshot(
  mode: ClinicalUpdateMode,
  samples: SessionSample[],
  transcriptSegments: TranscriptSegment[],
  elapsedSeconds: number,
): ClinicalPresentationSnapshot | null {
  const minutes = clinicalModeToMinutes(mode);
  if (!minutes || !samples.length) return null;
  const endSecond = Math.max(1, elapsedSeconds);
  const windowSeconds = minutes * CLINICAL_MICRO_WINDOW_SECONDS;
  const windowStartSecond = Math.max(0, endSecond - windowSeconds);
  const weights = clinicalWeights(minutes);
  const microAggs = Array.from({ length: minutes }, (_, index) => {
    const microStart = Math.max(
      windowStartSecond,
      endSecond - (minutes - index) * CLINICAL_MICRO_WINDOW_SECONDS,
    );
    const microEnd = Math.min(
      endSecond,
      microStart + CLINICAL_MICRO_WINDOW_SECONDS,
    );
    const payloads = samples
      .filter((sample) => sample.elapsedSeconds >= microStart && sample.elapsedSeconds < microEnd)
      .map((sample) => sample.payload);
    if (!payloads.length) return null;
    return {
      weight: weights[index] || 0,
      startSecond: microStart,
      endSecond: microEnd,
      agg: aggregatePayloads(payloads),
    };
  }).filter(Boolean) as Array<{
    weight: number;
    startSecond: number;
    endSecond: number;
    agg: AggData;
  }>;

  if (!microAggs.length) return null;

  const zoneBuckets = new Map<number, Array<{ zone: PerceptionZone; weight: number }>>();
  microAggs.forEach(({ agg, weight }) => {
    (agg.zones || []).forEach((zone) => {
      if (!zoneBuckets.has(zone.zone)) zoneBuckets.set(zone.zone, []);
      zoneBuckets.get(zone.zone)!.push({ zone, weight });
    });
  });
  const zones: PerceptionZone[] = [];
  zoneBuckets.forEach((items) => {
    const last = items[items.length - 1]?.zone;
    if (!last) return;
    const totalWeight = items.reduce((sum, item) => sum + item.weight, 0) || 1;
    const deviation =
      items.reduce(
        (sum, item) => sum + Number(item.zone.deviation_score || 0) * item.weight,
        0,
      ) / totalWeight;
    const dissonanceWeight = items
      .filter((item) => hasConfirmedDissonanceEvidence(item.zone, (microAggs[microAggs.length - 1]?.agg.audioMeta || {}) as Record<string, unknown>))
      .reduce((sum, item) => sum + item.weight, 0);
    zones.push({
      ...last,
      deviation_score: deviation,
      facial_dissonance_detected:
        Boolean(last.facial_dissonance_detected) || dissonanceWeight / totalWeight >= 0.35,
    });
  });

  const audioMeta: Record<string, unknown> = {};
  CLINICAL_AUDIO_KEYS.forEach((key) => {
    const value = weightedAverage(
      microAggs.map(({ agg, weight }) => ({
        value:
          typeof agg.audioMeta?.[key] === "number"
            ? Number(agg.audioMeta[key])
            : null,
        weight,
      })),
    );
    if (value !== null) audioMeta[key] = rounded(value, 4);
  });
  const latestAudio = microAggs[microAggs.length - 1]?.agg.audioMeta || {};
  audioMeta.emotional_tone = latestString(
    microAggs.map(({ agg }) => String(agg.audioMeta?.emotional_tone || "")),
  ) || latestAudio.emotional_tone || "neutro";
  audioMeta.clinical_presentation_mode = mode;
  audioMeta.clinical_presentation_window_seconds = windowSeconds;
  audioMeta.clinical_micro_window_seconds = CLINICAL_MICRO_WINDOW_SECONDS;
  audioMeta.clinical_presentation_generated_at_second = endSecond;

  const agg: AggData = {
    zones: zones.sort((a, b) => a.zone - b.zone),
    ipm:
      weightedAverage(microAggs.map(({ agg, weight }) => ({ value: agg.ipm, weight }))) ??
      microAggs[microAggs.length - 1].agg.ipm,
    coherence: microAggs[microAggs.length - 1].agg.coherence,
    globalColor: microAggs[microAggs.length - 1].agg.globalColor,
    globalDesc: microAggs[microAggs.length - 1].agg.globalDesc,
    alerts: Array.from(new Set(microAggs.flatMap(({ agg }) => agg.alerts || []))).slice(0, 8),
    drValue:
      weightedAverage(microAggs.map(({ agg, weight }) => ({ value: agg.drValue, weight }))) ??
      microAggs[microAggs.length - 1].agg.drValue,
    audioMeta,
    commitments: microAggs[microAggs.length - 1].agg.commitments,
  };

  return {
    mode,
    generatedAtSecond: endSecond,
    nextUpdateSecond: endSecond + windowSeconds,
    windowStartSecond,
    windowEndSecond: endSecond,
    microWindowCount: microAggs.length,
    agg,
    metricSnapshot: buildMetricSnapshot(
      `Janela clínica ${minutes}min`,
      samples,
      windowStartSecond,
      endSecond,
      transcriptSegments,
    ),
    ipmHistory: microAggs.map(({ agg }) => rounded(agg.ipm, 2) || 0),
  };
}

function transcriptOverlay(meta: Record<string, unknown> | null) {
  if (!meta) return {};
  const allowed = [
    "transcription_snippet",
    "transcription_interim",
    "transcription_status",
    "transcription_error",
    "transcription_provider",
    "provider",
    "attributed_speaker",
    "speaker_identification",
    "semantic_stt_pipeline",
    "realtime_transcription_ready",
  ];
  return Object.fromEntries(
    allowed
      .filter((key) => key in meta)
      .map((key) => [key, meta[key]]),
  );
}

const THEME_STOPWORDS = new Set([
  "para",
  "como",
  "com",
  "que",
  "uma",
  "por",
  "dos",
  "das",
  "estou",
  "esta",
  "isso",
  "mais",
  "muito",
  "sobre",
  "pc",
  "pac",
  "dr",
  "você",
  "também",
]);

function makeReportId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
}

function averageNumeric(values: Array<number | null | undefined>) {
  const valid = values.filter((value): value is number => Number.isFinite(value));
  if (!valid.length) return null;
  return valid.reduce((total, value) => total + value, 0) / valid.length;
}

function rounded(value: number | null, digits = 2) {
  if (value === null || !Number.isFinite(value)) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function limitWords(text: string, maxWords: number) {
  return String(text || "").trim().split(/\s+/).filter(Boolean).slice(0, maxWords).join(" ");
}

function limitTheme(text: string, maxWords = 6) {
  const clean = limitWords(text, maxWords);
  return clean || "Tema em apuração";
}

function inferThemeFromTranscript(text: string) {
  const clean = text
    .replace(/^DR\.\s*-\s*|^PC\s*-\s*|^PAC\s*-\s*/gim, " ")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\w\s]/g, " ");
  const counts = new Map<string, number>();
  clean
    .split(/\s+/)
    .filter((word) => word.length >= 4 && !THEME_STOPWORDS.has(word))
    .forEach((word) => counts.set(word, (counts.get(word) || 0) + 1));
  const top = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([word]) => word);
  return top.length ? limitTheme(top.join(" "), 6) : "Tema em apuração";
}

function collectTranscript(
  segments: TranscriptSegment[],
  startSecond: number,
  endSecond: number,
) {
  return segments
    .filter(
      (segment) =>
        segment.elapsedSeconds >= startSecond &&
        segment.elapsedSeconds < endSecond,
    )
    .map((segment) => segment.text)
    .join(" ")
    .trim();
}

function buildMetricSnapshot(
  label: string,
  samples: SessionSample[],
  startSecond: number,
  endSecond: number,
  transcriptSegments: TranscriptSegment[],
): MetricSnapshot {
  const scoped = samples.filter(
    (sample) =>
      sample.elapsedSeconds >= startSecond && sample.elapsedSeconds < endSecond,
  );
  const payloads = scoped.map((sample) => sample.payload);
  const aggregate = aggregatePayloads(payloads);
  const zones = aggregate.zones || [];
  const dominant = [...zones].sort(
    (a, b) =>
      Math.abs(b?.deviation_score || 0) - Math.abs(a?.deviation_score || 0),
  )[0];
  const transcript = collectTranscript(transcriptSegments, startSecond, endSecond);
  const minutes = Math.max(1 / 60, (endSecond - startSecond) / 60);
  const wordCount = transcript
    .replace(/^DR\.\s*-\s*|^PC\s*-\s*|^PAC\s*-\s*/gim, " ")
    .split(/\s+/)
    .filter(Boolean).length;
  const audioMetas = payloads.map((payload) => (payload as any).audio_meta || {});
  const audioAverage = (key: (typeof REPORT_AUDIO_KEYS)[number]) =>
    rounded(
      averageNumeric(
        audioMetas.map((meta) =>
          typeof meta[key] === "number" ? Number(meta[key]) : null,
        ),
      ),
    );
  const idmAvg =
    zones.length > 0
      ? zones.reduce(
          (total, zone) => total + Math.abs(Number(zone.deviation_score || 0)),
          0,
        ) / zones.length
      : 0;

  return {
    label,
    startSecond,
    endSecond,
    sampleCount: payloads.length,
    ipmAvg: rounded(aggregate.ipm, 2) || 0,
    idmAvg: rounded(idmAvg, 3) || 0,
    dominantZone: dominant?.zone || null,
    dominantTheme: dominant?.tema || "Sem zona dominante",
    coherenceStatus: aggregate.coherence || "NEUTRO",
    emotionalTone:
      String(audioMetas.find((meta) => meta.emotional_tone)?.emotional_tone || "") ||
      "neutro",
    wordsPerMinute: rounded(wordCount / minutes, 1) || 0,
    theme: inferThemeFromTranscript(transcript),
    dissonanceCount: zones.filter(isReportableDissonance).length,
    mfcc7: audioAverage("mfcc7"),
    mfcc9: audioAverage("mfcc9"),
    mfcc7Delta: audioAverage("mfcc7_delta"),
    mfcc9Delta: audioAverage("mfcc9_delta"),
    mfcc7DeltaDelta: audioAverage("mfcc7_delta_delta"),
    mfcc9DeltaDelta: audioAverage("mfcc9_delta_delta"),
    f0Mean: audioAverage("f0_mean"),
    zcr: audioAverage("zcr"),
    jitter: audioAverage("jitter"),
    shimmer: audioAverage("shimmer"),
    spectralDelta0_4: audioAverage("spectral_delta_0_4hz"),
    spectralTheta4_8: audioAverage("spectral_theta_4_8hz"),
    spectralAlpha8_12: audioAverage("spectral_alpha_8_12hz"),
    spectralBeta12_30: audioAverage("spectral_beta_12_30hz"),
    spectralGamma30_80: audioAverage("spectral_gamma_30_80hz"),
    spectralBandIndex: audioAverage("spectral_band_index"),
    subharmonic5_12: audioAverage("subharmonic_energy_5_12hz"),
    subharmonic12_20: audioAverage("subharmonic_energy_12_20hz"),
    subharmonic20_40: audioAverage("subharmonic_energy_20_40hz"),
    vocalBasal85_165: audioAverage("energy_85_165hz"),
    dnaInfrasoundNuclear: audioAverage("dna_infrasound_nuclear"),
    dnaLimbicModulation: audioAverage("dna_limbic_modulation"),
    dnaVocalBasalTension: audioAverage("dna_vocal_basal_tension"),
    dnaAutonomicFlooding: audioAverage("dna_autonomic_flooding"),
    dnaDissociativeShutdown: audioAverage("dna_dissociative_shutdown"),
    dnaNeurogenicResonance: audioAverage("dna_neurogenic_resonance"),
    dnaSomatoaffectiveDissonance: audioAverage("dna_somatoaffective_dissonance"),
    dnaSubharmonicIndex: audioAverage("dna_subharmonic_index"),
    zones,
  };
}

function buildTenMinuteCuts(
  samples: SessionSample[],
  transcriptSegments: TranscriptSegment[],
  durationSeconds: number,
) {
  const windowSize = 10 * 60;
  const count = Math.max(1, Math.ceil(Math.max(durationSeconds, 1) / windowSize));
  return Array.from({ length: count }, (_, index) => {
    const startSecond = index * windowSize;
    const endSecond = Math.min((index + 1) * windowSize, Math.max(durationSeconds, windowSize));
    return buildMetricSnapshot(
      `${startSecond / 60}-${Math.ceil(endSecond / 60)}min`,
      samples,
      startSecond,
      endSecond,
      transcriptSegments,
    );
  }).filter((snapshot) => snapshot.sampleCount > 0);
}

function buildReportCuts(
  samples: SessionSample[],
  transcriptSegments: TranscriptSegment[],
  durationSeconds: number,
  conversationSummaries: ConversationSummary[],
) {
  const orderedSummaries = [...conversationSummaries]
    .filter((summary) => summary.endMinute > summary.startMinute)
    .sort((a, b) => {
      const aStart = a.startSecond ?? a.startMinute * 60;
      const bStart = b.startSecond ?? b.startMinute * 60;
      return aStart - bStart;
    });

  if (!orderedSummaries.length) {
    return buildTenMinuteCuts(samples, transcriptSegments, durationSeconds);
  }

  return orderedSummaries
    .map((summary) => {
      const startSecond = Math.max(
        0,
        Math.floor(summary.startSecond ?? summary.startMinute * 60),
      );
      const endSecond = Math.min(
        Math.max(durationSeconds, startSecond + 1),
        Math.max(
          startSecond + 1,
          Math.ceil(summary.endSecond ?? summary.endMinute * 60),
        ),
      );
      const triggerLabel =
        summary.trigger === "manual"
          ? "manual"
          : summary.trigger === "final"
            ? "final"
            : "10min";
      return buildMetricSnapshot(
        `${summary.startMinute}-${summary.endMinute}min (${triggerLabel})`,
        samples,
        startSecond,
        endSecond,
        transcriptSegments,
      );
    })
    .filter((snapshot) => snapshot.sampleCount > 0);
}

function buildSessionSummary(
  summaries: ConversationSummary[],
  transcript: string,
): SessionReportRecord["sessionSummary"] {
  const ordered = [...summaries].sort((a, b) => a.startMinute - b.startMinute);
  const source = ordered.length
    ? ordered
        .map(
          (item) =>
            `${item.startMinute}-${item.endMinute}min ${item.theme}: ${item.summary}`,
        )
        .join(" ")
    : transcript;
  const theme = limitTheme(
    ordered.length
      ? ordered.map((item) => item.theme).join(" ")
      : inferThemeFromTranscript(transcript),
    6,
  );
  const cleanSource = source.replace(/\s+/g, " ").trim();
  const summary = cleanSource
    ? `A sessão teve como eixo predominante ${theme}. A sequência dos cortes indica a seguinte progressão clínica e semântica: ${cleanSource}. Em conclusão, este resumo deve ser lido como síntese da substância verbal registrada nos cortes, servindo de base para comparar conteúdo, ritmo e deslocamentos temáticos com as métricas multimodais do relatório.`
    : "";
  return {
    theme,
    summary:
      limitWords(summary, 300) ||
      "Resumo geral indisponível por ausência de transcrição suficiente.",
    generatedAt: new Date().toISOString(),
  };
}

function transcriptWordCount(text: string, speakerPrefixText?: string) {
  const source = speakerPrefixText
    ? String(text || "")
        .split(/\n+/)
        .filter((line) => line.trim().startsWith(speakerPrefixText))
        .join(" ")
    : String(text || "");
  return source
    .replace(/^DR\.\s*-\s*|^PC\s*-\s*|^PAC\s*-\s*/gim, " ")
    .split(/\s+/)
    .filter(Boolean).length;
}

function inferInterventionCategory(text: string) {
  const clean = normalizeTranscriptText(text);
  if (!clean) return "nao_classificada";
  const buckets: Array<[string, string[]]> = [
    ["acolhimento", ["estou aqui", "vamos com calma", "pode falar", "te escuto", "acolho"]],
    ["silencio_terapeutico", ["pausa", "silêncio", "podemos esperar", "sem pressa"]],
    ["grounding_regulacao", ["respira", "corpo", "observe", "presença", "aterrar"]],
    ["psicoeducacao", ["explicar", "entenda", "funciona", "modelo", "sistema nervoso"]],
    ["reestruturacao_cognitiva", ["pensamento", "crenca", "evidência", "alternativa"]],
    ["validacao_emocional", ["faz sentido", "compreendo", "válido", "acolho"]],
    ["pergunta_aberta", ["como", "quando", "qual", "conte", "fale"]],
    ["orientacao_pratica", ["exercicio", "praticar", "anotar", "combinado", "tarefa"]],
    ["confrontacao_terapeutica", ["percebe", "padrão", "evita", "resistência"]],
    ["encerramento_sintese", ["resumindo", "síntese", "próxima sessão", "encerrar"]],
  ];
  const ranked = buckets
    .map(([category, words]) => ({
      category,
      score: words.filter((word) => clean.includes(word)).length,
    }))
    .sort((a, b) => b.score - a.score);
  return ranked[0]?.score ? ranked[0].category : "intervencao_geral";
}

function inferPatientResponse(
  cut: MetricSnapshot,
  previousCut: MetricSnapshot | null,
  baseline: MetricSnapshot,
) {
  const reference = previousCut || baseline;
  const ipmDelta = cut.ipmAvg - reference.ipmAvg;
  const dissonanceDelta = cut.dissonanceCount - reference.dissonanceCount;
  if (ipmDelta <= -0.5 && dissonanceDelta <= 0) return "melhora_regulacao";
  if (ipmDelta >= 0.5 || dissonanceDelta > 0) return "aumento_ativacao";
  return "estabilidade";
}

function cutQualityConfidence(cut: MetricSnapshot) {
  const duration = Math.max(1, cut.endSecond - cut.startSecond);
  const coverage = Math.min(1, cut.sampleCount / Math.max(1, duration / 10));
  const speech = Math.min(1, cut.wordsPerMinute / 80);
  return Math.round(((coverage * 0.65 + speech * 0.35) || 0) * 1000) / 1000;
}

function samePatientReport(report: SessionReportRecord, patient?: { id?: string; name?: string; document?: string }) {
  if (!patient) return false;
  const currentId = patient.id || "";
  const currentDocument = patient.document || "";
  const currentName = normalizeTranscriptText(patient.name || "");
  const reportPatient = report.patient || {};
  return Boolean(
    (currentId && reportPatient.id === currentId) ||
      (currentDocument && reportPatient.document === currentDocument) ||
      (currentName && normalizeTranscriptText(reportPatient.name || "") === currentName),
  );
}

function anonymizeForResearch(text: string, maxWords = 80) {
  return limitWords(
    String(text || "")
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
      .replace(/\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g, "[documento]")
      .replace(/\b(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}\b/g, "[telefone]")
      .replace(/\b\d{5,}\b/g, "[número]")
      .replace(/\s+/g, " ")
      .trim(),
    maxWords,
  );
}

function scopedSpeakerText(transcript: string, speaker: SpeakerRole) {
  const prefix = speakerPrefix(speaker);
  return String(transcript || "")
    .split(/\n+/)
    .filter((line) => line.trim().startsWith(prefix))
    .map((line) => line.replace(prefix, "").trim())
    .join(" ");
}

function reportsMetricAverage(
  reports: SessionReportRecord[],
  selector: (report: SessionReportRecord) => number | null | undefined,
) {
  return rounded(averageNumeric(reports.map(selector)), 3);
}

function recurringFromReports<T>(values: T[], maxItems = 5) {
  const counts = new Map<string, { value: T; count: number }>();
  values
    .filter((value) => value !== null && value !== undefined && String(value).trim() !== "")
    .forEach((value) => {
      const key = String(value);
      const current = counts.get(key) || { value, count: 0 };
      counts.set(key, { value, count: current.count + 1 });
    });
  return [...counts.values()]
    .sort((a, b) => b.count - a.count)
    .slice(0, maxItems)
    .map((item) => item.value);
}

function deltaDirection(delta: number | null | undefined, threshold = 0.05) {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return "nao_apurado";
  if (delta > threshold) return "aumento";
  if (delta < -threshold) return "redução";
  return "estabilidade";
}

function aggregatedClinicalRisk(cut: MetricSnapshot) {
  const idm = Math.min(40, Math.abs(cut.idmAvg || 0) * 20);
  const dissonance = Math.min(35, (cut.dissonanceCount || 0) * 12);
  const vocal = Math.min(
    25,
    Math.max(0, cut.subharmonic5_12 || 0) * 15 + Math.max(0, cut.jitter || 0) * 12,
  );
  return Math.round((idm + dissonance + vocal) * 10) / 10;
}

function buildAnonymizedContext(
  sessionId: string,
  durationSeconds: number,
  baseline: MetricSnapshot,
  sessionAverage: MetricSnapshot,
  cuts: MetricSnapshot[],
  transcriptSegments: TranscriptSegment[],
  conversationSummaries: ConversationSummary[],
  remotePatientOn: boolean,
  sessionMode?: "remote" | "presential" | "presential_mobile",
): SessionReportRecord["anonymizedContext"] {
  const patient = loadSessionPatient(sessionId || "");
  const previousReports = loadSessionReports()
    .filter(
      (report) =>
        report.sessionId !== sessionId && samePatientReport(report, patient || undefined),
    )
    .sort(
      (a, b) =>
        new Date(b.createdAt || 0).getTime() -
        new Date(a.createdAt || 0).getTime(),
    );
  const last3Reports = previousReports.slice(0, 3);
  const previousEnd = previousReports[0]?.createdAt
    ? new Date(previousReports[0].createdAt).getTime()
    : 0;
  const now = Date.now();
  const intervalDays =
    previousEnd > 0 ? Math.max(0, (now - previousEnd) / 86400000) : null;
  const fullTranscript = transcriptSegments.map((segment) => segment.text).join("\n");
  const previousSessionsCount = previousReports.length;
  const last3Ipm = reportsMetricAverage(last3Reports, (report) => report.sessionAverage?.ipmAvg);
  const last3Idm = reportsMetricAverage(last3Reports, (report) => report.sessionAverage?.idmAvg);
  const historicalIpm = reportsMetricAverage(previousReports, (report) => report.sessionAverage?.ipmAvg);
  const historicalIdm = reportsMetricAverage(previousReports, (report) => report.sessionAverage?.idmAvg);
  const deltaIpmVsLast3 = last3Ipm === null ? null : rounded(sessionAverage.ipmAvg - last3Ipm, 3);
  const deltaIdmVsLast3 = last3Idm === null ? null : rounded(sessionAverage.idmAvg - last3Idm, 3);
  const deltaIpmVsHistorical = historicalIpm === null ? null : rounded(sessionAverage.ipmAvg - historicalIpm, 3);
  const deltaIdmVsHistorical = historicalIdm === null ? null : rounded(sessionAverage.idmAvg - historicalIdm, 3);
  const longitudinalTrend =
    deltaIdmVsLast3 === null
      ? "sem_historico"
      : deltaIdmVsLast3 < -0.05
        ? "melhora"
        : deltaIdmVsLast3 > 0.05
          ? "piora"
          : "estabilidade";
  const emotionalStability =
    (sessionAverage.dissonanceCount || 0) <= (baseline.dissonanceCount || 0) &&
    Math.abs(sessionAverage.idmAvg - baseline.idmAvg) < 0.25
      ? "estável"
      : "oscilante";

  return {
    schemaVersion: "anonymous_datamart_v3",
    sessionModality:
      sessionMode === "presential_mobile"
        ? "presential_mobile"
        : remotePatientOn
          ? "remote"
          : "presential",
    sessionKind: previousReports.length ? "seguimento" : "primeira_sessao",
    sessionType: previousReports.length ? "seguimento" : "primeira_sessao",
    treatmentPhase:
      previousReports.length < 3
        ? "início"
        : previousReports.length < 12
          ? "meio"
          : "manutencao",
    sessionOrdinal: previousReports.length + 1,
    previousSessionsCount,
    intervalSincePreviousDays: intervalDays,
    sttModel: "gpt-4o-transcribe",
    llmModel: "gpt-4o/gemini-froid-explica",
    algorithmVersion: FROID_ALGORITHM_VERSION,
    metricsVersion: "froid-metrics-v4-bioacoustic-proxy-units",
    weightsVersion: "froid-weights-v1",
    audioQuality:
      transcriptWordCount(fullTranscript) > 20 || cuts.some((cut) => cut.sampleCount > 0)
        ? "suficiente"
        : "baixa_amostragem",
    mediaInterruptions: 0,
    mediaLossEvents: 0,
    consentAnonymousResearch: true,
    privacyTier: "anonymous_research_datamart",
    piiExcluded: true,
    rawAudioRetained: false,
    literalTranscriptRetained: false,
    deltaIpmFromSessionBaseline: rounded(sessionAverage.ipmAvg - baseline.ipmAvg, 3),
    deltaIdmFromSessionBaseline: rounded(sessionAverage.idmAvg - baseline.idmAvg, 3),
    deltaIpmVsLast3,
    deltaIdmVsLast3,
    deltaIpmVsHistorical,
    deltaIdmVsHistorical,
    longitudinalTrend,
    emotionalStability,
    recurringThemes: recurringFromReports(
      previousReports.map((report) => report.sessionSummary?.theme || report.sessionAverage?.theme || ""),
    ) as string[],
    recurringZones: recurringFromReports(
      previousReports.map((report) => report.sessionAverage?.dominantZone || null),
    ) as number[],
    recurringRisks: recurringFromReports(
      previousReports.map((report) => report.sessionAverage?.coherenceStatus || ""),
    ) as string[],
    cuts: cuts.map((cut, index) => {
      const scopedTranscript = transcriptSegments
        .filter(
          (segment) =>
            segment.elapsedSeconds >= cut.startSecond &&
            segment.elapsedSeconds < cut.endSecond,
        )
        .map((segment) => segment.text)
        .join("\n");
      const summary = conversationSummaries.find(
        (item) =>
          item.startMinute === Math.floor(cut.startSecond / 60) &&
          item.endMinute === Math.max(item.startMinute + 1, Math.ceil(cut.endSecond / 60)),
      );
      const previousCut = cuts[index - 1] || null;
      const nextCut = cuts[index + 1] || null;
      const drText = scopedSpeakerText(scopedTranscript, "DR");
      const pcText = scopedSpeakerText(scopedTranscript, "PC");
      const reference = previousCut || baseline;
      const nextReference = nextCut || cut;
      return {
        cutIndex: index,
        cutTrigger:
          cut.endSecond >= durationSeconds ? "final" : "automatico_10min",
        startSecond: cut.startSecond,
        endSecond: cut.endSecond,
        themePredominant: limitTheme(summary?.theme || cut.theme, 6),
        patientSummaryAnon: anonymizeForResearch(pcText || summary?.summary || cut.theme, 80),
        professionalSummaryAnon: anonymizeForResearch(drText || "intervencao profissional sem texto suficiente", 80),
        qualityConfidence: cutQualityConfidence(cut),
        interventionCategory: inferInterventionCategory(drText),
        patientResponse: inferPatientResponse(cut, previousCut, baseline),
        ipmDeltaFromBaseline: rounded(cut.ipmAvg - baseline.ipmAvg, 3),
        idmDeltaFromBaseline: rounded(cut.idmAvg - baseline.idmAvg, 3),
        dissonanceDeltaFromBaseline: rounded(cut.dissonanceCount - baseline.dissonanceCount, 3),
        ipmDeltaPreviousCut: rounded(cut.ipmAvg - reference.ipmAvg, 3),
        idmDeltaPreviousCut: rounded(cut.idmAvg - reference.idmAvg, 3),
        dissonanceDeltaPreviousCut: rounded(cut.dissonanceCount - reference.dissonanceCount, 3),
        ipmDeltaAfterIntervention: rounded(nextReference.ipmAvg - cut.ipmAvg, 3),
        idmDeltaAfterIntervention: rounded(nextReference.idmAvg - cut.idmAvg, 3),
        dissonanceDeltaAfterIntervention: rounded(nextReference.dissonanceCount - cut.dissonanceCount, 3),
        dominantZoneShift:
          previousCut && previousCut.dominantZone !== cut.dominantZone ? "mudanca_zona" : "sem_mudanca_zona",
        emotionalToneShift:
          previousCut && previousCut.emotionalTone !== cut.emotionalTone ? "mudanca_tom" : "sem_mudanca_tom",
        cadenceShift: deltaDirection(cut.wordsPerMinute - reference.wordsPerMinute, 5),
        responseIpmDirection: deltaDirection(nextReference.ipmAvg - cut.ipmAvg, 0.5),
        responseIdmDirection: deltaDirection(nextReference.idmAvg - cut.idmAvg, 0.05),
        responseDissonanceDirection: deltaDirection(nextReference.dissonanceCount - cut.dissonanceCount, 0.5),
        semanticCoherenceShift:
          previousCut && previousCut.coherenceStatus !== cut.coherenceStatus
            ? "mudanca_coerencia"
            : "sem_mudanca_coerencia",
        relevantDissonances:
          cut.dissonanceCount > 0
            ? `dissonancias_relevantes_${cut.dissonanceCount}_zona_${cut.dominantZone || "nao_apurada"}`
            : "sem_dissonancia_relevante",
        aggregatedClinicalRisk: aggregatedClinicalRisk(cut),
        spectralDelta0_4: cut.spectralDelta0_4,
        spectralTheta4_8: cut.spectralTheta4_8,
        spectralAlpha8_12: cut.spectralAlpha8_12,
        spectralBeta12_30: cut.spectralBeta12_30,
        spectralGamma30_80: cut.spectralGamma30_80,
        spectralBandIndex: cut.spectralBandIndex,
        mfcc7Delta: cut.mfcc7Delta,
        mfcc9Delta: cut.mfcc9Delta,
        mfcc7DeltaDelta: cut.mfcc7DeltaDelta,
        mfcc9DeltaDelta: cut.mfcc9DeltaDelta,
      };
    }),
  };
}

function LiveSessionInner({ user }: LiveSessionProps) {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const sessionPatient = loadSessionPatient(sessionId || "");
  const isPresentialSession = sessionPatient?.sessionMode === "presential";
  const isPresentialMobileSession = sessionPatient?.sessionMode === "presential_mobile";
  const [state, dispatch] = useReducer(reducer, undefined, createInitialState);
  const [dissonanceLog, setDissonanceLog] = useState<
    Array<{
      id: string;
      timestamp: string;
      elapsedSeconds: number;
      zone: number;
      report: string;
    }>
  >([]);
  const [liveTranscription, setLiveTranscription] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [conversationSummaries, setConversationSummaries] = useState<
    ConversationSummary[]
  >([]);
  const [sessionLayout, setSessionLayout] = useState<"detailed" | "simplified">(
    "detailed",
  );
  const [clinicalUpdateMode, setClinicalUpdateMode] = useState<ClinicalUpdateMode>(
    loadClinicalUpdateMode,
  );
  const [clinicalSnapshot, setClinicalSnapshot] =
    useState<ClinicalPresentationSnapshot | null>(null);
  const [semanticCutStartSecond, setSemanticCutStartSecond] = useState(0);
  const [rtcStatus, setRtcStatus] = useState("Aguardando paciente");
  const [remotePatientOn, setRemotePatientOn] = useState(false);
  const [remotePatientVideoOn, setRemotePatientVideoOn] = useState(false);
  const [attributedSpeaker, setAttributedSpeaker] = useState<SpeakerRole>("DR");
  const [speakerIdMode, setSpeakerIdMode] = useState<SpeakerIdMode>(() =>
    loadDrVoiceSignature() ? "auto" : "manual",
  );
  const [drVoiceSignature, setDrVoiceSignature] = useState<VoiceSignature | null>(() =>
    loadDrVoiceSignature(),
  );
  const [voiceIdStatus, setVoiceIdStatus] = useState(
    loadDrVoiceSignature()
      ? "Identificação automática pronta."
      : "Cadastre a voz do DR para identificação automática.",
  );
  const [isEnrollingDrVoice, setIsEnrollingDrVoice] = useState(false);
  const [patientAudioVersion, setPatientAudioVersion] = useState(0);
  const frameBuffer = useRef<FroidPayload[]>([]);
  const sessionSamplesRef = useRef<SessionSample[]>([]);
  const firstPatientMetricSecondRef = useRef<number | null>(null);
  const baselineSnapshotRef = useRef<MetricSnapshot | null>(null);
  const elapsedSecondsRef = useRef(0);
  const reportSavedRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcRemoteStreamRef = useRef<MediaStream | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  const rtcMakingOfferRef = useRef(false);
  const rtcReconnectTimerRef = useRef<number | null>(null);
  const rtcDisconnectTimerRef = useRef<number | null>(null);
  const rtcClosingRef = useRef(false);
  const bioacousticStreamRef = useRef<MediaStream | null>(null);
  const bioacousticContextRef = useRef<AudioContext | null>(null);
  const bioacousticRafRef = useRef<number | null>(null);
  const bioacousticEnvelopeRef = useRef<number[]>([]);
  const bioacousticClockRef = useRef({ lastTime: 0, frameRate: 60 });
  const lastBioacousticPublishMsRef = useRef(0);
  const bioacousticDnaRef = useRef<DnaBaselineState>({
    startedAtMs: 0,
    samples: [],
    baseline: null,
    locked: false,
    limbicRatioEma: null,
  });
  const bioacousticCepstralRef = useRef<CepstralBaselineState>({
    startedAtMs: 0,
    samples: [],
    baseline: null,
    previous: null,
    previousDelta: null,
    locked: false,
  });
  const recorderRef = useRef<MediaRecorder | null>(null);
  const patientRecorderRef = useRef<MediaRecorder | null>(null);
  const browserRecognitionRef = useRef<any>(null);
  const browserSttRestartTimerRef = useRef<number | null>(null);
  const browserSttAvailableRef = useRef(false);
  const transcriptLinesRef = useRef<string[]>([]);
  const transcriptSegmentsRef = useRef<Array<{ elapsedSeconds: number; text: string }>>([]);
  const semanticCutStartSecondRef = useRef(0);
  const semanticCutClosingRef = useRef(false);
  const manualCutCounterRef = useRef(0);
  const sttRestartTimerRef = useRef<number | null>(null);
  const sttSegmentTimerRef = useRef<number | null>(null);
  const patientSttRestartTimerRef = useRef<number | null>(null);
  const patientSttSegmentTimerRef = useRef<number | null>(null);
  const intentionalRecorderStopRef = useRef(false);
  const segmentingRecorderStopRef = useRef(false);
  const patientIntentionalRecorderStopRef = useRef(false);
  const patientSegmentingRecorderStopRef = useRef(false);
  const patientBioacousticStreamRef = useRef<MediaStream | null>(null);
  const patientTranscriptStreamRef = useRef<MediaStream | null>(null);
  const transcribingRef = useRef(false);
  const transcriptionQueueRef = useRef<Promise<void>>(Promise.resolve());
  const transcriptionStatsRef = useRef<{
    totalWords: number;
    windows: Array<{ timestamp: number; words: number }>;
  }>({ totalWords: 0, windows: [] });
  const lastDissonanceSig = useRef("");
  const attributedSpeakerRef = useRef<SpeakerRole>("DR");
  const forcedLocalSegmentSpeakerRef = useRef<SpeakerRole | null>(null);
  const remotePatientOnRef = useRef(false);
  const directLocalMetricsActiveRef = useRef(false);
  const speakerIdModeRef = useRef<SpeakerIdMode>(speakerIdMode);
  const drVoiceSignatureRef = useRef<VoiceSignature | null>(drVoiceSignature);
  const voiceIdRafRef = useRef<number | null>(null);
  const voiceIdContextRef = useRef<AudioContext | null>(null);
  const voiceIdHistoryRef = useRef<SpeakerRole[]>([]);
  const latestZonesRef = useRef<PerceptionZone[]>([]);
  const latestIpmRef = useRef(50);
  const lastLocalIpmDispatchMsRef = useRef(0);
  const lastCriticalClinicalRefreshSecondRef = useRef(0);

  useEffect(() => {
    const id = setInterval(() => dispatch({ type: "TICK" }), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    latestZonesRef.current =
      state.aggregated?.zones || state.payload?.perception_zones || [];
    latestIpmRef.current =
      state.aggregated?.ipm ?? state.payload?.ipm_score ?? state.localIpm ?? 50;
  }, [state.aggregated, state.payload, state.localIpm]);

  useEffect(() => {
    elapsedSecondsRef.current = state.elapsedSeconds;
  }, [state.elapsedSeconds]);

  useEffect(() => {
    semanticCutStartSecondRef.current = semanticCutStartSecond;
  }, [semanticCutStartSecond]);

  const refreshClinicalPresentation = useCallback(
    (mode: ClinicalUpdateMode = clinicalUpdateMode) => {
      if (mode === "realtime") {
        setClinicalSnapshot(null);
        return;
      }
      const snapshot = buildClinicalPresentationSnapshot(
        mode,
        sessionSamplesRef.current,
        transcriptSegmentsRef.current,
        elapsedSecondsRef.current || state.elapsedSeconds,
      );
      if (snapshot) setClinicalSnapshot(snapshot);
    },
    [clinicalUpdateMode],
  );

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(CLINICAL_UPDATE_STORAGE_KEY, clinicalUpdateMode);
    }
    refreshClinicalPresentation(clinicalUpdateMode);
  }, [clinicalUpdateMode, refreshClinicalPresentation]);

  useEffect(() => {
    if (clinicalUpdateMode === "realtime") return;
    if (!clinicalSnapshot) {
      refreshClinicalPresentation();
      return;
    }
    if (state.elapsedSeconds >= clinicalSnapshot.nextUpdateSecond) {
      refreshClinicalPresentation();
    }
  }, [
    clinicalSnapshot,
    clinicalUpdateMode,
    refreshClinicalPresentation,
    state.elapsedSeconds,
  ]);

  useEffect(() => {
    remotePatientOnRef.current = remotePatientOn;
  }, [remotePatientOn]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const localVideoTracks = mediaStreamRef.current
        ?.getVideoTracks()
        .filter((track) => track.readyState === "live");
      if (videoRef.current && localVideoTracks?.length) {
        videoRef.current.srcObject = new MediaStream(localVideoTracks);
        void videoRef.current.play().catch(() => undefined);
      }

      if (rtcRemoteStreamRef.current) {
        const media = attachRemoteMedia(
          rtcRemoteStreamRef.current,
          remoteVideoRef.current,
          remoteAudioRef.current,
        );
        setRemotePatientOn(media.audio);
        setRemotePatientVideoOn(media.video);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [sessionLayout]);

  useEffect(() => {
    speakerIdModeRef.current = speakerIdMode;
  }, [speakerIdMode]);

  useEffect(() => {
    drVoiceSignatureRef.current = drVoiceSignature;
  }, [drVoiceSignature]);

  const applyAttributedSpeaker = useCallback((speaker: SpeakerRole, reason = "") => {
    attributedSpeakerRef.current = speaker;
    setAttributedSpeaker((prev) => (prev === speaker ? prev : speaker));
    if (reason) {
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        speaker_identification: reason,
        attributed_speaker: speaker,
      }));
    }
  }, []);

  const refreshMediaStatus = useCallback((stream: MediaStream | null) => {
    const cameraOn =
      stream
        ?.getVideoTracks()
        .some((track) => track.enabled && track.readyState === "live") || false;
    const micOn =
      stream
        ?.getAudioTracks()
        .some((track) => track.enabled && track.readyState === "live") || false;
    dispatch({ type: "MEDIA_STATUS", cameraOn, micOn });
  }, []);

  const stopVoiceIdentification = useCallback(() => {
    if (voiceIdRafRef.current) {
      window.cancelAnimationFrame(voiceIdRafRef.current);
      voiceIdRafRef.current = null;
    }
    const context = voiceIdContextRef.current;
    voiceIdContextRef.current = null;
    if (context && context.state !== "closed") {
      void context.close().catch(() => undefined);
    }
    voiceIdHistoryRef.current = [];
  }, []);

  const startVoiceIdentification = useCallback(
    (stream: MediaStream) => {
      if (typeof window === "undefined" || remotePatientOnRef.current) return;
      const signature = drVoiceSignatureRef.current;
      if (!signature) {
        setVoiceIdStatus("Cadastre a voz do DR para identificação automática.");
        return;
      }
      const audioTrack = stream
        .getAudioTracks()
        .find((track) => track.readyState === "live");
      if (!audioTrack) return;

      const AudioContextCtor =
        (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextCtor) {
        setVoiceIdStatus("Identificação vocal indisponível neste navegador.");
        return;
      }

      stopVoiceIdentification();
      let context: AudioContext;
      try {
        context = new AudioContextCtor({ sampleRate: 48000 });
      } catch {
        context = new AudioContextCtor();
      }
      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      analyser.minDecibels = -95;
      analyser.maxDecibels = -15;
      analyser.smoothingTimeConstant = 0.18;
      const source = context.createMediaStreamSource(new MediaStream([audioTrack]));
      source.connect(analyser);
      voiceIdContextRef.current = context;
      const timeData = new Float32Array(analyser.fftSize);
      const frequencyData = new Uint8Array(analyser.frequencyBinCount);
      let frameCount = 0;

      const analyse = () => {
        if (voiceIdContextRef.current !== context) return;
        analyser.getFloatTimeDomainData(timeData);
        analyser.getByteFrequencyData(frequencyData);
        frameCount += 1;
        if (frameCount % 18 === 0 && speakerIdModeRef.current === "auto") {
          const currentSignature = drVoiceSignatureRef.current;
          const vector = voiceFeatureVector(
            timeData,
            frequencyData,
            context.sampleRate,
            analyser.fftSize,
          );
          if (currentSignature && vector) {
            const distance = voiceDistance(vector, currentSignature.vector);
            const speaker: SpeakerRole =
              distance <= currentSignature.threshold ? "DR" : "PC";
            voiceIdHistoryRef.current = [
              ...voiceIdHistoryRef.current.slice(-5),
              speaker,
            ];
            const drVotes = voiceIdHistoryRef.current.filter((item) => item === "DR").length;
            const pcVotes = voiceIdHistoryRef.current.length - drVotes;
            const stableSpeaker: SpeakerRole = drVotes >= pcVotes ? "DR" : "PC";
            applyAttributedSpeaker(
              stableSpeaker,
              `Auto voz DR: ${distance.toFixed(3)} / ${currentSignature.threshold.toFixed(3)}`,
            );
            setVoiceIdStatus(
              `Auto: ${stableSpeaker} (${distance.toFixed(3)} / ${currentSignature.threshold.toFixed(3)})`,
            );
          }
        }
        voiceIdRafRef.current = window.requestAnimationFrame(analyse);
      };

      void context.resume?.().catch(() => undefined);
      setVoiceIdStatus("Identificação automática ativa.");
      voiceIdRafRef.current = window.requestAnimationFrame(analyse);
    },
    [applyAttributedSpeaker, stopVoiceIdentification],
  );

  const enrollDrVoice = useCallback(async () => {
    if (isEnrollingDrVoice) return;
    const stream = mediaStreamRef.current;
    const audioTrack = stream
      ?.getAudioTracks()
      .find((track) => track.readyState === "live");
    if (!stream || !audioTrack || typeof window === "undefined") {
      setVoiceIdStatus("Microfone local indisponível para cadastrar voz do DR.");
      return;
    }
    const AudioContextCtor =
      (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextCtor) {
      setVoiceIdStatus("Cadastro vocal indisponível neste navegador.");
      return;
    }
    setIsEnrollingDrVoice(true);
    setSpeakerIdMode("manual");
    applyAttributedSpeaker("DR", "Cadastro da voz do DR em andamento.");

    let context: AudioContext;
    try {
      context = new AudioContextCtor({ sampleRate: 48000 });
    } catch {
      context = new AudioContextCtor();
    }
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    analyser.minDecibels = -95;
    analyser.maxDecibels = -15;
    analyser.smoothingTimeConstant = 0.12;
    const source = context.createMediaStreamSource(new MediaStream([audioTrack]));
    source.connect(analyser);
    const timeData = new Float32Array(analyser.fftSize);
    const frequencyData = new Uint8Array(analyser.frequencyBinCount);
    const samples: number[][] = [];
    const start = performance.now();

    await new Promise<void>((resolve) => {
      const collect = (now: number) => {
        analyser.getFloatTimeDomainData(timeData);
        analyser.getByteFrequencyData(frequencyData);
        const vector = voiceFeatureVector(
          timeData,
          frequencyData,
          context!.sampleRate,
          analyser.fftSize,
        );
        if (vector) samples.push(vector);
        const elapsed = Math.min(8, (now - start) / 1000);
        setVoiceIdStatus(`Cadastrando voz do DR: ${elapsed.toFixed(1)}s / 8s`);
        if (now - start >= 8000) {
          resolve();
          return;
        }
        window.requestAnimationFrame(collect);
      };
      void context?.resume?.().catch(() => undefined);
      window.requestAnimationFrame(collect);
    });

    const signature = buildVoiceSignature(samples);
    if (context.state !== "closed") {
      await context.close().catch(() => undefined);
    }
    setIsEnrollingDrVoice(false);
    if (!signature) {
      setVoiceIdStatus("Cadastro insuficiente. Fale novamente por 8 segundos em tom natural.");
      setSpeakerIdMode("manual");
      return;
    }
    saveDrVoiceSignature(signature);
    setDrVoiceSignature(signature);
    setSpeakerIdMode("auto");
    setVoiceIdStatus(
      `Voz do DR cadastrada (${signature.sampleCount} amostras). Identificação automática ativa.`,
    );
    startVoiceIdentification(stream);
  }, [applyAttributedSpeaker, isEnrollingDrVoice, startVoiceIdentification]);

  const cleanupRtcCall = useCallback(() => {
    rtcClosingRef.current = true;
    if (rtcReconnectTimerRef.current) {
      window.clearTimeout(rtcReconnectTimerRef.current);
      rtcReconnectTimerRef.current = null;
    }
    if (rtcDisconnectTimerRef.current) {
      window.clearTimeout(rtcDisconnectTimerRef.current);
      rtcDisconnectTimerRef.current = null;
    }
    rtcSignalRef.current?.close();
    rtcSignalRef.current = null;
    rtcPeerRef.current?.close();
    rtcPeerRef.current = null;
    rtcRemoteStreamRef.current = null;
    rtcIceQueueRef.current = [];
    rtcMakingOfferRef.current = false;
    if (patientSttRestartTimerRef.current) {
      window.clearTimeout(patientSttRestartTimerRef.current);
      patientSttRestartTimerRef.current = null;
    }
    if (patientSttSegmentTimerRef.current) {
      window.clearTimeout(patientSttSegmentTimerRef.current);
      patientSttSegmentTimerRef.current = null;
    }
    patientIntentionalRecorderStopRef.current = true;
    patientSegmentingRecorderStopRef.current = false;
    if (patientRecorderRef.current && patientRecorderRef.current.state !== "inactive") {
      patientRecorderRef.current.stop();
    }
    patientRecorderRef.current = null;
    patientBioacousticStreamRef.current
      ?.getTracks()
      .forEach((track) => track.stop());
    patientBioacousticStreamRef.current = null;
    patientTranscriptStreamRef.current
      ?.getTracks()
      .forEach((track) => track.stop());
    patientTranscriptStreamRef.current = null;
    setRemotePatientOn(false);
    setRemotePatientVideoOn(false);
    setRtcStatus("Aguardando paciente");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  }, []);

  const startProfessionalRtcCall = useCallback(
    async (localSource: MediaStream) => {
      if (!sessionId || typeof RTCPeerConnection === "undefined") {
        setRtcStatus("WebRTC indisponível neste navegador.");
        return;
      }

      cleanupRtcCall();
      rtcClosingRef.current = false;
      const localConferenceStream = createConferenceStream(localSource);
      if (!localConferenceStream.getTracks().length) {
        setRtcStatus("Áudio e vídeo locais indisponiveis para chamada.");
        return;
      }

      const token = localStorage.getItem("froid_token") || "";
      const peer = new RTCPeerConnection(
        await loadRtcConfiguration({ sessionId, professionalToken: token }),
      );
      const remoteStream = new MediaStream();
      rtcPeerRef.current = peer;
      rtcRemoteStreamRef.current = remoteStream;

      if (isPresentialMobileSession) {
        peer.addTransceiver("audio", { direction: "recvonly" });
        peer.addTransceiver("video", { direction: "recvonly" });
      } else {
        localConferenceStream.getTracks().forEach((track) => {
          const sender = peer.addTrack(track, localConferenceStream);
          void configureConferenceSender(sender);
        });
      }

      const sendSignal = (payload: Record<string, unknown>) => {
        const socket = rtcSignalRef.current;
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(payload));
        }
      };

      const flushIceQueue = async () => {
        const queued = [...rtcIceQueueRef.current];
        rtcIceQueueRef.current = [];
        for (const candidate of queued) {
          await peer.addIceCandidate(candidate).catch(() => undefined);
        }
      };

      const makeOffer = async () => {
        if (rtcMakingOfferRef.current || peer.signalingState !== "stable") return;
        rtcMakingOfferRef.current = true;
        try {
          const offer = await peer.createOffer();
          await peer.setLocalDescription(offer);
          sendSignal({ type: "offer", offer: peer.localDescription });
          setRtcStatus("Chamando paciente...");
        } finally {
          rtcMakingOfferRef.current = false;
        }
      };

      const refreshRemoteTracks = () => {
        const media = attachRemoteMedia(
          remoteStream,
          remoteVideoRef.current,
          isPresentialMobileSession ? null : remoteAudioRef.current,
        );
        setRemotePatientOn(media.audio);
        setRemotePatientVideoOn(media.video);
        setRtcStatus(
          media.audio && media.video
            ? "Paciente conectado: áudio e vídeo ativos."
            : media.audio
              ? "Paciente conectado: áudio ativo, aguardando vídeo."
              : media.video
                ? "Paciente conectado: vídeo ativo, aguardando áudio."
                : "Conectado, aguardando trilhas do paciente.",
        );
      };

      peer.ontrack = (event) => {
        const incomingTracks = event.streams[0]?.getTracks() || [event.track];
        incomingTracks.forEach((track) => {
          if (!remoteStream.getTracks().some((item) => item.id === track.id)) {
            remoteStream.addTrack(track);
          }
          track.onended = refreshRemoteTracks;
          track.onmute = refreshRemoteTracks;
          track.onunmute = refreshRemoteTracks;
        });
        refreshRemoteTracks();
        const patientAudioTrack = remoteStream
          .getAudioTracks()
          .find((track) => track.readyState === "live");
        if (patientAudioTrack && !patientTranscriptStreamRef.current) {
          patientBioacousticStreamRef.current = new MediaStream([
            patientAudioTrack.clone(),
          ]);
          patientTranscriptStreamRef.current = new MediaStream([
            patientAudioTrack.clone(),
          ]);
          setPatientAudioVersion((value) => value + 1);
        }
        applyAttributedSpeaker("PC", "Trilha remota do paciente recebida por WebRTC.");
      };

      peer.onicecandidate = (event) => {
        if (event.candidate) {
          sendSignal({
            type: "ice",
            candidate: event.candidate.toJSON(),
          });
        }
      };

      peer.onconnectionstatechange = () => {
        if (peer.connectionState === "connected") {
          if (rtcDisconnectTimerRef.current) {
            window.clearTimeout(rtcDisconnectTimerRef.current);
            rtcDisconnectTimerRef.current = null;
          }
          refreshRemoteTracks();
        } else if (peer.connectionState === "failed") {
          peer.restartIce();
          void makeOffer();
          setRtcStatus("Reconectando mídia do paciente...");
        } else if (peer.connectionState === "disconnected") {
          setRtcStatus("Mídia instável; tentando reconectar...");
          if (!rtcDisconnectTimerRef.current) {
            rtcDisconnectTimerRef.current = window.setTimeout(() => {
              rtcDisconnectTimerRef.current = null;
              if (peer.connectionState === "disconnected") {
                peer.restartIce();
                void makeOffer();
              }
            }, 3_000);
          }
        } else if (peer.connectionState === "connecting") {
          setRtcStatus("Conectando áudio e vídeo do paciente...");
        }
      };

      let reconnectAttempt = 0;
      const handleSignal = async (event: MessageEvent) => {
        const data = JSON.parse(String(event.data || "{}"));
        if (data.type === "signal-ready" && data.peer_connected) {
          await makeOffer();
        } else if (data.type === "peer-joined") {
          await makeOffer();
        } else if (data.type === "answer" && data.answer) {
          await peer.setRemoteDescription(data.answer);
          await flushIceQueue();
        } else if (data.type === "renegotiate-request") {
          peer.restartIce();
          await makeOffer();
        } else if (data.type === "ice" && data.candidate) {
          if (peer.remoteDescription) {
            await peer.addIceCandidate(data.candidate).catch(() => undefined);
          } else {
            rtcIceQueueRef.current.push(data.candidate);
          }
        } else if (data.type === "peer-left") {
          setRemotePatientOn(false);
          setRemotePatientVideoOn(false);
          setRtcStatus("Paciente saiu da chamada.");
          if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
          if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
        }
      };

      const connectSignaling = () => {
        if (rtcClosingRef.current || peer.connectionState === "closed") return;
        const socket = new WebSocket(
          wsUrl(
            `/ws/rtc/${sessionId}/professional?token=${encodeURIComponent(token)}`,
          ),
        );
        rtcSignalRef.current = socket;
        socket.onopen = () => {
          reconnectAttempt = 0;
          setRtcStatus("Aguardando paciente...");
        };
        socket.onmessage = (event) => void handleSignal(event);
        socket.onerror = () => socket.close();
        socket.onclose = () => {
          if (rtcClosingRef.current || peer.connectionState === "closed") return;
          const delay = Math.min(4_000, 500 * 2 ** reconnectAttempt);
          reconnectAttempt += 1;
          setRtcStatus("Reconectando sinalização da chamada...");
          rtcReconnectTimerRef.current = window.setTimeout(connectSignaling, delay);
        };
      };
      connectSignaling();
    },
    [
      applyAttributedSpeaker,
      cleanupRtcCall,
      isPresentialMobileSession,
      sessionId,
    ],
  );

  const stopRawBioacousticPipeline = useCallback(() => {
    if (bioacousticRafRef.current) {
      window.cancelAnimationFrame(bioacousticRafRef.current);
      bioacousticRafRef.current = null;
    }

    const context = bioacousticContextRef.current;
    bioacousticContextRef.current = null;
    if (context && context.state !== "closed") {
      void context.close().catch(() => undefined);
    }

    bioacousticStreamRef.current?.getTracks().forEach((track) => track.stop());
    bioacousticStreamRef.current = null;
    bioacousticEnvelopeRef.current = [];
    lastBioacousticPublishMsRef.current = 0;
    bioacousticClockRef.current = { lastTime: 0, frameRate: 60 };
    bioacousticDnaRef.current = {
      startedAtMs: 0,
      samples: [],
      baseline: null,
      locked: false,
      limbicRatioEma: null,
    };
    bioacousticCepstralRef.current = {
      startedAtMs: 0,
      samples: [],
      baseline: null,
      previous: null,
      previousDelta: null,
      locked: false,
    };
  }, []);

  const startRawBioacousticPipeline = useCallback(
    (
      stream: MediaStream,
      sourceMode:
        | "patient-webrtc"
        | "raw-independent"
        | "semantic-fallback"
        | "direct-local-patient",
    ) => {
      const liveTracks = stream
        .getAudioTracks()
        .filter((track) => track.readyState === "live");
      if (!liveTracks.length || typeof window === "undefined") return;

      const AudioContextCtor =
        (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextCtor) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          bioacoustic_status: "error",
          bioacoustic_error: "WebAudio indisponível para bioacústica bruta.",
        }));
        return;
      }

      stopRawBioacousticPipeline();

      let context: AudioContext;
      try {
        context = new AudioContextCtor({ sampleRate: 48000 });
      } catch {
        context = new AudioContextCtor();
      }

      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      analyser.minDecibels = -95;
      analyser.maxDecibels = -15;
      analyser.smoothingTimeConstant = 0.12;

      const source = context.createMediaStreamSource(stream);
      source.connect(analyser);

      const timeData = new Float32Array(analyser.fftSize);
      const frequencyData = new Uint8Array(analyser.frequencyBinCount);
      bioacousticStreamRef.current = stream;
      bioacousticContextRef.current = context;
      bioacousticEnvelopeRef.current = [];
      lastBioacousticPublishMsRef.current = 0;
      bioacousticClockRef.current = { lastTime: 0, frameRate: 60 };

      setLiveTranscription((prev) => ({
        ...(prev || {}),
        bioacoustic_status: "monitoring",
        bioacoustic_pipeline: "raw-webaudio",
        bioacoustic_track: sourceMode,
        bioacoustic_sample_rate: context.sampleRate,
        bioacoustic_fft_size: analyser.fftSize,
        semantic_stt_pipeline: "chunked-gpt-4o-transcribe",
        semantic_streaming_target: "openai-realtime-transcription",
        realtime_transcription_ready: false,
        dual_track_audio_ready: true,
        bioacoustic_error: "",
      }));

      const analyse = (now: number) => {
        if (bioacousticContextRef.current !== context) return;
        const clock = bioacousticClockRef.current;
        if (clock.lastTime > 0) {
          const deltaMs = Math.max(1, now - clock.lastTime);
          const instantFrameRate = clamp(1000 / deltaMs, 15, 90);
          clock.frameRate = clock.frameRate * 0.85 + instantFrameRate * 0.15;
        }
        clock.lastTime = now;

        analyser.getFloatTimeDomainData(timeData);
        analyser.getByteFrequencyData(frequencyData);

        const metrics = calculateRawBioacousticFrame(
          timeData,
          frequencyData,
          context.sampleRate,
          analyser.fftSize,
          bioacousticEnvelopeRef.current,
          clock.frameRate,
        );
        const dnaMetrics = computeDnaSubharmonics(
          {
            sub5_12: metrics.sub5_12,
            sub12_20: metrics.sub12_20,
            sub20_40: metrics.sub20_40,
            energy85_165: metrics.energy85_165,
            zcr: metrics.zcr,
          },
          bioacousticDnaRef.current,
          now,
          latestZonesRef.current,
          latestIpmRef.current,
        );
        const shouldPublishBioacoustic =
          lastBioacousticPublishMsRef.current === 0 ||
          now - lastBioacousticPublishMsRef.current >= BIOACOUSTIC_WINDOW_MS;
        if (shouldPublishBioacoustic) {
          lastBioacousticPublishMsRef.current = now;
          const cepstralMetrics = computeCepstralDynamics(
            frequencyData,
            context.sampleRate,
            analyser.fftSize,
            bioacousticCepstralRef.current,
            now,
            metrics.voicePresence,
          );
          const shouldFeedLocalIpm =
            remotePatientOnRef.current ||
            attributedSpeakerRef.current === "PC" ||
            directLocalMetricsActiveRef.current;
          const localIpm = computeLocalIpmFromBioacoustics(metrics, dnaMetrics);
          if (
            shouldFeedLocalIpm &&
            localIpm !== null &&
            now - lastLocalIpmDispatchMsRef.current >= BIOACOUSTIC_WINDOW_MS
          ) {
            lastLocalIpmDispatchMsRef.current = now;
            dispatch({ type: "LOCAL_IPM", ipm: localIpm });
          }

          setLiveTranscription((prev) => ({
            ...(prev || {}),
            bioacoustic_status: "monitoring",
            bioacoustic_pipeline: "raw-webaudio",
            bioacoustic_track: sourceMode,
            bioacoustic_sample_rate: context.sampleRate,
            bioacoustic_window_ms: BIOACOUSTIC_WINDOW_MS,
            bioacoustic_frame_rate: clock.frameRate,
            semantic_stt_pipeline: "chunked-gpt-4o-transcribe",
            semantic_streaming_target: "openai-realtime-transcription",
            realtime_transcription_ready: false,
            dual_track_audio_ready: true,
            raw_rms: metrics.rms,
            raw_peak: metrics.peak,
            audio_rms: metrics.rms,
            audio_peak: metrics.peak,
            zcr: metrics.zcr,
            jitter: metrics.jitter,
            shimmer: metrics.shimmer,
            jitter_proxy_index: metrics.jitter_proxy_index,
            shimmer_proxy_index: metrics.shimmer_proxy_index,
            jitter_unit: JITTER_PROXY_UNIT,
            shimmer_unit: SHIMMER_PROXY_UNIT,
            jitter_source: "zero_crossing_rate_scaled_x45",
            shimmer_source: "rms_envelope_coefficient_of_variation",
            spectral_band_context: VOCAL_SPECTRAL_BAND_CONTEXT,
            voice_presence: metrics.voicePresence,
            energy_85_165hz: metrics.energy85_165,
            subharmonic_energy_5_12hz: metrics.sub5_12,
            subharmonic_energy_12_20hz: metrics.sub12_20,
            subharmonic_energy_20_40hz: metrics.sub20_40,
            spectral_delta_0_4hz: metrics.spectralDelta,
            spectral_theta_4_8hz: metrics.spectralTheta,
            spectral_alpha_8_12hz: metrics.spectralAlpha,
            spectral_beta_12_30hz: metrics.spectralBeta,
            spectral_gamma_30_80hz: metrics.spectralGamma,
            spectral_band_index: metrics.spectralBandIndex,
            mfcc7: cepstralMetrics.mfcc7,
            mfcc9: cepstralMetrics.mfcc9,
            baseline_mfcc7: cepstralMetrics.baselineMfcc7,
            baseline_mfcc9: cepstralMetrics.baselineMfcc9,
            desvio_mfcc7: cepstralMetrics.desvioMfcc7,
            desvio_mfcc9: cepstralMetrics.desvioMfcc9,
            mfcc7_delta: cepstralMetrics.mfcc7Delta,
            mfcc9_delta: cepstralMetrics.mfcc9Delta,
            mfcc7_delta_delta: cepstralMetrics.mfcc7DeltaDelta,
            mfcc9_delta_delta: cepstralMetrics.mfcc9DeltaDelta,
            local_ipm_score: localIpm,
            ...dnaMetrics,
          }));
        }

        bioacousticRafRef.current = window.requestAnimationFrame(analyse);
      };

      void context.resume?.().catch(() => undefined);
      bioacousticRafRef.current = window.requestAnimationFrame(analyse);
    },
    [stopRawBioacousticPipeline],
  );

  const appendTranscriptText = useCallback((rawText: string, speakerOverride?: SpeakerRole) => {
    const text = rawText.replace(/\s+/g, " ").trim();
    if (!text) return;

    const speaker = speakerOverride || attributedSpeakerRef.current;
    const prefix = speakerPrefix(speaker);
    const line = `${prefix}${text}`;
    const normalized = normalizeTranscriptText(text);
    const recentLines = transcriptLinesRef.current.slice(-4);
    const isDuplicate = recentLines.some((recent) => {
      const normalizedRecent = normalizeTranscriptText(
        recent.replace(/^DR\.\s*-\s*|^PC\s*-\s*|^PAC\s*-\s*/i, ""),
      );
      return (
        normalizedRecent === normalized ||
        (normalized.length > 24 && normalizedRecent.includes(normalized)) ||
        (normalizedRecent.length > 24 && normalized.includes(normalizedRecent))
      );
    });

    if (isDuplicate) return;

    const nextLines = [...transcriptLinesRef.current];
    const lastIndex = nextLines.length - 1;
    const lastLine = lastIndex >= 0 ? nextLines[lastIndex] : "";
    if (lastLine.startsWith(prefix)) {
      nextLines[lastIndex] = `${lastLine} ${text}`.replace(/\s+/g, " ").trim();
    } else {
      nextLines.push(line);
    }
    transcriptLinesRef.current = nextLines.slice(-MAX_VISIBLE_TRANSCRIPT_LINES);

    const words = text.split(/\s+/).filter(Boolean).length;
    const now = Date.now();
    const elapsedSeconds = Math.max(0, elapsedSecondsRef.current);
    transcriptSegmentsRef.current = [
      ...transcriptSegmentsRef.current,
      { elapsedSeconds, text: line },
    ];

    const stats = transcriptionStatsRef.current;
    stats.totalWords += words;
    stats.windows = [...stats.windows, { timestamp: now, words }].filter(
      (entry) => now - entry.timestamp <= 10 * 60 * 1000,
    );
    const words10m = stats.windows.reduce(
      (total, entry) => total + entry.words,
      0,
    );
    const firstWindow = stats.windows[0]?.timestamp || now;
    const minutes = Math.max(1, (now - firstWindow) / 60000);

    setLiveTranscription((prev) => ({
      ...(prev || {}),
      transcription_snippet: "",
      transcription_interim: "",
      words_per_window: words,
      total_words_session: stats.totalWords,
      words_per_minute_10m: words10m / minutes,
      emotional_tone: (prev?.emotional_tone as string) || "neutro",
      transcription_status: "ok",
      transcription_error: "",
    }));
  }, []);

  const stopMedia = useCallback((reportStatus = true) => {
    if (sttRestartTimerRef.current) {
      window.clearTimeout(sttRestartTimerRef.current);
      sttRestartTimerRef.current = null;
    }
    if (sttSegmentTimerRef.current) {
      window.clearTimeout(sttSegmentTimerRef.current);
      sttSegmentTimerRef.current = null;
    }
    if (patientSttRestartTimerRef.current) {
      window.clearTimeout(patientSttRestartTimerRef.current);
      patientSttRestartTimerRef.current = null;
    }
    if (patientSttSegmentTimerRef.current) {
      window.clearTimeout(patientSttSegmentTimerRef.current);
      patientSttSegmentTimerRef.current = null;
    }
    if (browserSttRestartTimerRef.current) {
      window.clearTimeout(browserSttRestartTimerRef.current);
      browserSttRestartTimerRef.current = null;
    }
    intentionalRecorderStopRef.current = true;
    segmentingRecorderStopRef.current = false;
    patientIntentionalRecorderStopRef.current = true;
    patientSegmentingRecorderStopRef.current = false;
    if (browserRecognitionRef.current) {
      try {
        browserRecognitionRef.current.onend = null;
        browserRecognitionRef.current.stop();
      } catch {}
      browserRecognitionRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    if (patientRecorderRef.current && patientRecorderRef.current.state !== "inactive") {
      patientRecorderRef.current.stop();
    }
    patientRecorderRef.current = null;
    cleanupRtcCall();
    stopRawBioacousticPipeline();
    stopVoiceIdentification();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (reportStatus) refreshMediaStatus(null);
  }, [cleanupRtcCall, refreshMediaStatus, stopRawBioacousticPipeline, stopVoiceIdentification]);

  const startBrowserSpeechToText = useCallback((stream: MediaStream) => {
    if (typeof window === "undefined") return false;
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      browserSttAvailableRef.current = false;
      return false;
    }

    const micStillLive = () =>
      stream.getAudioTracks().some((track) => track.readyState === "live");

    try {
      if (browserRecognitionRef.current) {
        browserRecognitionRef.current.onend = null;
        browserRecognitionRef.current.stop();
      }

      const recognition = new SpeechRecognition();
      browserRecognitionRef.current = recognition;
      browserSttAvailableRef.current = true;
      recognition.lang = "pt-BR";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-live",
          transcription_status: "listening",
          transcription_error: "",
        }));
      };

      recognition.onresult = (event: any) => {
        let interim = "";
        let finalText = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = String(event.results[i]?.[0]?.transcript || "").trim();
          if (!transcript) continue;
          if (event.results[i].isFinal) finalText += ` ${transcript}`;
          else interim += ` ${transcript}`;
        }

        if (interim.trim()) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            provider: prev?.provider || "browser-live",
            transcription_status: "listening",
            transcription_interim: "",
            transcription_error: "",
          }));
        }

        if (finalText.trim()) {
          appendTranscriptText(finalText);
        }
      };

      recognition.onerror = (event: any) => {
        const error = String(event?.error || "");
        if (error === "no-speech" || error === "aborted") return;
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-live",
          transcription_status: "listening",
          transcription_error: `STT navegador: ${error || "erro desconhecido"}`,
        }));
      };

      recognition.onend = () => {
        if (!intentionalRecorderStopRef.current && micStillLive()) {
          browserSttRestartTimerRef.current = window.setTimeout(() => {
            browserSttRestartTimerRef.current = null;
            startBrowserSpeechToText(stream);
          }, 350);
        }
      };

      recognition.start();
      return true;
    } catch (err: any) {
      browserSttAvailableRef.current = false;
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        provider: prev?.provider || "browser-live",
        transcription_status: "listening",
        transcription_error:
          err?.message || "Reconhecimento de fala do navegador indisponível.",
      }));
      return false;
    }
  }, [appendTranscriptText]);

  const summarizeTranscriptRange = useCallback(
    async ({
      id,
      startSecond,
      endSecond,
      trigger,
    }: {
      id: string;
      startSecond: number;
      endSecond: number;
      trigger: "automatico_10min" | "manual" | "final";
    }) => {
      const safeStartSecond = Math.max(0, Math.floor(startSecond));
      const safeEndSecond = Math.max(safeStartSecond + 1, Math.ceil(endSecond));
      const startMinute = Math.floor(safeStartSecond / 60);
      const endMinute = Math.max(startMinute + 1, Math.ceil(safeEndSecond / 60));
      const transcript = transcriptSegmentsRef.current
        .filter(
          (segment) =>
            segment.elapsedSeconds >= safeStartSecond &&
            segment.elapsedSeconds < safeEndSecond,
        )
        .map((segment) => segment.text)
        .join(" ")
        .trim();

      const commitSummary = (entry: ConversationSummary) => {
        setConversationSummaries((prev) =>
          [...prev.filter((item) => item.id !== entry.id), entry].sort(
            (a, b) => b.startMinute - a.startMinute,
          ),
        );
      };


      if (!transcript) {
        commitSummary({
          id,
          startSecond: safeStartSecond,
          endSecond: safeEndSecond,
          startMinute,
          endMinute,
          theme: "Sem fala transcrita",
          summary: "Nenhuma fala foi transcrita neste intervalo.",
          trigger,
        });
        return;
      }

      try {
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(apiUrl("/api/session-summary"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            transcript,
            start_minute: startMinute,
            end_minute: endMinute,
            session_id: sessionId || "default",
          }),
        });
        const data = await response.json();
        commitSummary({
          id,
          startSecond: safeStartSecond,
          endSecond: safeEndSecond,
          startMinute,
          endMinute,
          theme: limitTheme(String(data?.theme || "Tema em apuração"), 6),
          summary: limitWords(String(data?.summary || "").trim(), 60),
          trigger,
        });
      } catch {
        commitSummary({
          id,
          startSecond: safeStartSecond,
          endSecond: safeEndSecond,
          startMinute,
          endMinute,
          theme: "Resumo indisponível",
          summary: limitWords(transcript, 60),
          trigger,
        });
      }
    },
    [sessionId],
  );

  const closeSemanticCut = useCallback(
    async (trigger: "automatico_10min" | "manual" | "final") => {
      if (semanticCutClosingRef.current) return;
      const endSecond = Math.max(
        elapsedSecondsRef.current || state.elapsedSeconds,
        semanticCutStartSecondRef.current,
      );
      const startSecond = semanticCutStartSecondRef.current;
      const duration = endSecond - startSecond;

      if (trigger === "manual" && duration < 10) {
        return;
      }

      semanticCutClosingRef.current = true;
      const cutId =
        trigger === "manual"
          ? `manual-${Date.now()}-${manualCutCounterRef.current++}`
          : `${trigger}-${Date.now()}`;

      try {
        await summarizeTranscriptRange({
          id: cutId,
          startSecond,
          endSecond,
          trigger,
        });
        semanticCutStartSecondRef.current = endSecond;
        setSemanticCutStartSecond(endSecond);
      } finally {
        semanticCutClosingRef.current = false;
      }
    },
    [state.elapsedSeconds, summarizeTranscriptRange],
  );

  const transcribeAudioBlob = useCallback(
    async (audioBlob: Blob, mimeType: string, speaker: SpeakerRole) => {
      if (!audioBlob || audioBlob.size < MIN_STT_AUDIO_BYTES) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "listening",
          transcription_error: "Áudio capturado ainda insuficiente.",
          last_audio_bytes: audioBlob?.size || 0,
        }));
        return;
      }

      const activity = await measureAudioActivity(audioBlob);
      if (!activity.active) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "listening",
          transcription_interim: "",
          transcription_error: "Aguardando fala detectavel.",
          last_audio_bytes: audioBlob.size,
          audio_rms: activity.rms,
          audio_peak: activity.peak,
        }));
        return;
      }

      transcribingRef.current = true;
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        provider: prev?.provider || "browser-recorder",
        transcription_status: "transcribing",
        transcription_error: "",
        last_audio_bytes: audioBlob.size,
        audio_rms: activity.rms,
        audio_peak: activity.peak,
      }));

      try {
        const chunkMime = audioBlob.type || mimeType || "audio/webm";
        const previousContext = transcriptLinesRef.current
          .slice(-3)
          .join("\n")
          .slice(-900);
        const audioBase64 = await blobToBase64(audioBlob);
        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(apiUrl("/api/transcribe"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            audio_base64: audioBase64,
            mime_type: chunkMime,
            filename: `froid-session-${Date.now()}.${extensionFromMimeType(
              chunkMime,
            )}`,
            session_id: sessionId || "default",
            prompt:
              "Sessão clínica FROID em português do Brasil. Transcreva literalmente somente a fala humana audível, com pontuação natural. Não traduza, não resuma, não complete frases e não invente palavras. Mantenha termos técnicos, nomes e siglas como falados. Se não houver fala humana clara, retorne vazio." +
              " Vocabulario obrigatorio: FROID deve ser grafado FROID, nunca Freud; IPM, IDM, biomarcadores, sub-harmônicos, bioacústica, dissonâncias, paciente e profissional." +
              (previousContext
                ? `\n\nContexto transcrito imediatamente anterior para continuidade e pontuação:\n${previousContext}`
                : ""),
          }),
        });

        const data = await response.json();
        const text = String(data?.text || "").trim();
        if (!response.ok) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            provider: data?.provider || "local-fallback",
            transcription_status: "error",
            transcription_error:
              data?.error || `Falha HTTP ${response.status} na transcrição.`,
          }));
          return;
        }
        if (!text) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            provider: data?.provider || "openai-gpt-4o-transcribe",
            transcription_status: "listening",
            transcription_interim: "",
            transcription_error:
              data?.error || "Áudio enviado, sem fala transcrita no bloco.",
          }));
          return;
        }

        appendTranscriptText(text, speaker);

        setLiveTranscription((prev) => ({
          ...(prev || {}),
          emotional_tone: (prev?.emotional_tone as string) || "neutro",
          provider: data?.provider || "openai-gpt-4o-transcribe",
          transcription_status: data?.status || "ok",
          transcription_error: "",
          last_audio_bytes: audioBlob.size,
        }));
      } catch (err) {
        console.error("FROID speech-to-text:", err);
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "error",
          transcription_error:
            err instanceof Error ? err.message : "Falha ao enviar áudio.",
        }));
      } finally {
        transcribingRef.current = false;
      }
    },
    [appendTranscriptText, sessionId],
  );

  const enqueueTranscriptionBlob = useCallback(
    (audioBlob: Blob, mimeType: string, speaker: SpeakerRole) => {
      const run = () => transcribeAudioBlob(audioBlob, mimeType, speaker);
      transcriptionQueueRef.current = transcriptionQueueRef.current.then(
        run,
        run,
      );
    },
    [transcribeAudioBlob],
  );

  const startSpeechToText = useCallback(
    (
      stream: MediaStream,
      speaker: SpeakerRole,
      source: "professional" | "patient",
      attempt = 0,
    ) => {
      const recorderBox = source === "patient" ? patientRecorderRef : recorderRef;
      const restartTimerBox =
        source === "patient" ? patientSttRestartTimerRef : sttRestartTimerRef;
      const segmentTimerBox =
        source === "patient" ? patientSttSegmentTimerRef : sttSegmentTimerRef;
      const intentionalStopBox =
        source === "patient"
          ? patientIntentionalRecorderStopRef
          : intentionalRecorderStopRef;
      const segmentingStopBox =
        source === "patient"
          ? patientSegmentingRecorderStopRef
          : segmentingRecorderStopRef;
      const audioTracks = stream
        .getAudioTracks()
        .filter((track) => track.readyState === "live");

      if (!audioTracks.length || typeof MediaRecorder === "undefined") {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: "browser-recorder",
          transcription_status: "error",
          transcription_error:
            typeof MediaRecorder === "undefined"
              ? "MediaRecorder indisponível neste navegador."
              : source === "patient"
                ? "Áudio do paciente ainda não chegou ao gravador."
                : "Microfone do profissional indisponível para gravação.",
        }));
        return;
      }

      if (recorderBox.current && recorderBox.current.state !== "inactive") {
        intentionalStopBox.current = true;
        recorderBox.current.stop();
      }

      const mimeType = selectAudioMimeType();
      const audioStream = new MediaStream(audioTracks);
      let recorder: MediaRecorder;

      try {
        recorder = new MediaRecorder(
          audioStream,
          mimeType ? { mimeType } : undefined,
        );
      } catch (err: any) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: "browser-recorder",
          transcription_status: "error",
          transcription_error:
            err?.message || "Não foi possível criar o gravador de áudio.",
        }));
        return;
      }

      intentionalStopBox.current = false;
      segmentingStopBox.current = false;
      const recordedChunks: Blob[] = [];

      recorder.onstart = () => {
        if (segmentTimerBox.current) {
          window.clearTimeout(segmentTimerBox.current);
        }
        segmentTimerBox.current = window.setTimeout(() => {
          if (recorderBox.current === recorder && recorder.state === "recording") {
            segmentingStopBox.current = true;
            recorder.stop();
          }
        }, STT_CHUNK_MS);

        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "listening",
          transcription_sources: "captura-semantica-por-cortes",
          active_stt_source: source,
          transcription_error: "",
        }));
      };

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunks.push(event.data);
        }
      };

      recorder.onerror = (event: Event) => {
        const error = (event as ErrorEvent)?.error;
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "error",
          transcription_error:
            error?.message || "Erro no gravador de áudio do navegador.",
        }));
      };

      recorder.onstop = () => {
        if (segmentTimerBox.current) {
          window.clearTimeout(segmentTimerBox.current);
          segmentTimerBox.current = null;
        }
        const wasSegmentStop = segmentingStopBox.current;
        segmentingStopBox.current = false;
        const micStillLive = stream
          .getAudioTracks()
          .some((track) => track.readyState === "live");
        const finishedBlob =
          recordedChunks.length > 0
            ? new Blob(recordedChunks, {
                type: recorder.mimeType || mimeType || "audio/webm",
              })
            : null;

        if (wasSegmentStop && !intentionalStopBox.current && micStillLive) {
          if (recorderBox.current === recorder) recorderBox.current = null;
          window.setTimeout(() => startSpeechToText(stream, speaker, source, 0), 0);
          if (finishedBlob) {
            const forcedSpeaker =
              source === "professional"
                ? forcedLocalSegmentSpeakerRef.current
                : null;
            const segmentSpeaker =
              forcedSpeaker ||
              (source === "professional" && !remotePatientOnRef.current
                ? attributedSpeakerRef.current
                : speaker);
            if (source === "professional") {
              forcedLocalSegmentSpeakerRef.current = null;
            }
            enqueueTranscriptionBlob(
              finishedBlob,
              finishedBlob.type || mimeType || "audio/webm",
              segmentSpeaker,
            );
          }
          return;
        }

        if (!intentionalStopBox.current && micStillLive) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            provider: prev?.provider || "browser-recorder",
            transcription_status: "restarting",
            transcription_error:
              "Gravador reiniciado automaticamente pelo FROID.",
          }));
          restartTimerBox.current = window.setTimeout(() => {
            restartTimerBox.current = null;
            startSpeechToText(stream, speaker, source, attempt + 1);
          }, Math.min(1200, 250 + attempt * 250));
          return;
        }

        if (!micStillLive) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            provider: prev?.provider || "browser-recorder",
            transcription_status: "error",
            transcription_error: "O microfone foi encerrado pelo navegador.",
          }));
        }
      };

      try {
        recorder.start();
      } catch (err: any) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: "browser-recorder",
          transcription_status: "error",
          transcription_error:
            err?.message || "Não foi possível iniciar o gravador de áudio.",
        }));
        return;
      }

      recorderBox.current = recorder;
    },
    [enqueueTranscriptionBlob],
  );

  useEffect(() => {
    const patientBioacousticStream = patientBioacousticStreamRef.current;
    const patientTranscriptStream = patientTranscriptStreamRef.current;
    const patientBioacousticTrack = patientBioacousticStream
      ?.getAudioTracks()
      .find((track) => track.readyState === "live");
    const patientTranscriptTrack = patientTranscriptStream
      ?.getAudioTracks()
      .find((track) => track.readyState === "live");

    if (
      !patientAudioVersion ||
      !patientBioacousticStream ||
      !patientBioacousticTrack ||
      !patientTranscriptStream ||
      !patientTranscriptTrack
    ) {
      return;
    }

    stopVoiceIdentification();
    startRawBioacousticPipeline(patientBioacousticStream, "patient-webrtc");
    startSpeechToText(patientTranscriptStream, "PC", "patient");
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "monitoring",
      bioacoustic_pipeline: "patient-webrtc",
      bioacoustic_track: "patient-webrtc",
      bioacoustic_warning:
        "Avaliação FROID usando exclusivamente a voz do paciente.",
      transcription_sources: "captura-semantica-por-cortes",
      bioacoustic_error: "",
    }));
  }, [patientAudioVersion, startRawBioacousticPipeline, startSpeechToText, stopVoiceIdentification]);

  useEffect(() => {
    if (remotePatientOn) return;
    const localAudioTrack = mediaStreamRef.current
      ?.getAudioTracks()
      .find((track) => track.readyState === "live");

    if (!localAudioTrack) {
      directLocalMetricsActiveRef.current = false;
      return;
    }

    const hasAutomaticVoiceGuard = speakerIdMode === "auto" && Boolean(drVoiceSignature);
    const metricSpeaker = hasAutomaticVoiceGuard ? attributedSpeaker : "PC";

    if (metricSpeaker === "PC") {
      directLocalMetricsActiveRef.current = true;
      if (!hasAutomaticVoiceGuard && attributedSpeakerRef.current !== "PC") {
        applyAttributedSpeaker(
          "PC",
          "Atendimento presencial: sem voz DR cadastrada, microfone local atribuido ao PC para métricas.",
        );
      }
      startRawBioacousticPipeline(
        new MediaStream([localAudioTrack.clone()]),
        hasAutomaticVoiceGuard ? "semantic-fallback" : "direct-local-patient",
      );
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        bioacoustic_status: "monitoring",
        bioacoustic_pipeline: "direct-local-patient",
        bioacoustic_track: hasAutomaticVoiceGuard
          ? "local-patient-selected"
          : "direct-local-patient",
        bioacoustic_warning:
          hasAutomaticVoiceGuard
            ? "Atendimento presencial: métricas calculadas a partir da voz local identificada como paciente."
            : "Atendimento presencial: microfone local alimentando a trilha PC para manter métricas e gráficos ativos.",
        transcription_sources: "captura-semantica-por-cortes",
        bioacoustic_error: "",
      }));
      return;
    }

    directLocalMetricsActiveRef.current = false;
    stopRawBioacousticPipeline();
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "waiting_patient",
      bioacoustic_pipeline: "direct-local-paused",
      bioacoustic_track: "local-professional-selected",
      bioacoustic_warning:
        "Aguardando trilha vocal de paciente para alimentar biomarcadores.",
      transcription_sources: "captura-semantica-por-cortes",
    }));
  }, [
    attributedSpeaker,
    applyAttributedSpeaker,
    drVoiceSignature,
    remotePatientOn,
    speakerIdMode,
    state.micOn,
    startRawBioacousticPipeline,
    stopRawBioacousticPipeline,
  ]);

  const activateMedia = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      dispatch({
        type: "MEDIA_STATUS",
        cameraOn: false,
        micOn: false,
        camError: "Navegador sem suporte a câmera e microfone.",
      });
      return;
    }

    stopMedia();

    const tracks: MediaStreamTrack[] = [];
    let semanticAudioStream: MediaStream | null = null;
    let audioError = "";
    let videoError = "";

    if (!isPresentialSession && sessionId) {
      void loadRtcConfiguration({
        sessionId,
        professionalToken: localStorage.getItem("froid_token") || "",
      });
    }

    const videoConstraints: MediaTrackConstraints = {
      width: { ideal: 1280 },
      height: { ideal: 720 },
      frameRate: { ideal: 24, max: 30 },
      facingMode: "user",
    };
    let audioCapture: PromiseSettledResult<MediaStream>;
    let videoCapture: PromiseSettledResult<MediaStream>;
    try {
      const combinedStream = await navigator.mediaDevices.getUserMedia({
        audio: getSemanticAudioConstraints(),
        video: videoConstraints,
      });
      audioCapture = { status: "fulfilled", value: combinedStream };
      videoCapture = { status: "fulfilled", value: combinedStream };
    } catch {
      [audioCapture, videoCapture] = await Promise.allSettled([
        navigator.mediaDevices.getUserMedia({
          audio: getSemanticAudioConstraints(),
          video: false,
        }),
        navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: false,
        }),
      ]);
    }

    if (audioCapture.status === "fulfilled") {
      semanticAudioStream = audioCapture.value;
      tracks.push(...semanticAudioStream.getAudioTracks());
    } else {
      const err = audioCapture.reason;
      audioError =
        err?.name === "NotAllowedError"
          ? "Permissão de microfone negada pelo navegador."
          : "Não foi possível ativar o microfone.";
    }

    if (videoCapture.status === "fulfilled") {
      const existingTrackIds = new Set(tracks.map((track) => track.id));
      tracks.push(
        ...videoCapture.value
          .getVideoTracks()
          .filter((track) => !existingTrackIds.has(track.id)),
      );
    } else {
      const err = videoCapture.reason;
      videoError =
        err?.name === "NotAllowedError"
          ? "Permissão de câmera negada pelo navegador."
          : "Não foi possível ativar a câmera.";
    }

    const stream = new MediaStream(tracks);
    mediaStreamRef.current = stream;
    startVoiceIdentification(stream);
    startSpeechToText(stream, "DR", "professional");
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "waiting_patient",
      bioacoustic_pipeline: "patient-webrtc",
      bioacoustic_track: "patient-webrtc",
      bioacoustic_warning:
        "Biomarcadores e gráficos aguardam exclusivamente o áudio do paciente.",
      bioacoustic_error: "",
    }));
    if (ENABLE_BROWSER_LIVE_STT) {
      startBrowserSpeechToText(stream);
    }

    const updateStatus = () => refreshMediaStatus(mediaStreamRef.current);
    stream.getTracks().forEach((track) => {
      track.onended = updateStatus;
      track.onmute = updateStatus;
      track.onunmute = updateStatus;
    });

    const cameraTracks = stream.getVideoTracks();
    if (videoRef.current && cameraTracks.length > 0) {
      videoRef.current.srcObject = new MediaStream(cameraTracks);
      await videoRef.current.play().catch(() => undefined);
    }

    const cameraOn = cameraTracks.some(
      (track) => track.enabled && track.readyState === "live",
    );
    const micOn = stream
      .getAudioTracks()
      .some((track) => track.enabled && track.readyState === "live");

    dispatch({
      type: "MEDIA_STATUS",
      cameraOn,
      micOn,
      camError: [audioError, videoError].filter(Boolean).join(" "),
    });
    if (isPresentialSession) {
      cleanupRtcCall();
      setRtcStatus("Sessão presencial: captura local ativa.");
    } else {
      void startProfessionalRtcCall(stream);
    }
  }, [
    cleanupRtcCall,
    isPresentialSession,
    sessionId,
    refreshMediaStatus,
    startBrowserSpeechToText,
    startProfessionalRtcCall,
    startVoiceIdentification,
    startRawBioacousticPipeline,
    startSpeechToText,
    stopMedia,
  ]);

  useEffect(() => {
    void activateMedia();
    return () => stopMedia(false);
  }, [activateMedia, stopMedia]);

  useEffect(() => {
    if (state.phase === "ENDED") return;
    const elapsedInCut = state.elapsedSeconds - semanticCutStartSecond;
    if (elapsedInCut >= TRANSCRIPT_SUMMARY_WINDOW_MS / 1000) {
      void closeSemanticCut("automatico_10min");
    }
  }, [
    closeSemanticCut,
    semanticCutStartSecond,
    state.elapsedSeconds,
    state.phase,
  ]);

  useEffect(() => {
    const baselineStart = firstPatientMetricSecondRef.current;
    if (
      baselineStart !== null &&
      state.elapsedSeconds >= baselineStart + 60 &&
      state.phase === "CALIBRATING"
    ) {
      const baseline = buildMetricSnapshot(
        "Baseline PC 60s",
        sessionSamplesRef.current,
        baselineStart,
        baselineStart + 60,
        transcriptSegmentsRef.current,
      );
      baselineSnapshotRef.current = baseline;
      dispatch({ type: "BASELINE_LOCK", ipm: baseline.ipmAvg });
    }
  }, [state.elapsedSeconds, state.phase]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;
    let reconnectTimer: number | null = null;

    const scheduleConnect = (attempt: number) => {
      const delay = attempt === 0 ? 50 : Math.min(5000, 600 + attempt * 700);
      reconnectTimer = window.setTimeout(() => connect(attempt), delay);
    };

    const connect = (attempt = 0) => {
      if (cancelled) return;
      try {
        const token = localStorage.getItem("froid_token") || "";
        const socket = new WebSocket(
          wsUrl(`/ws/fusion/${sessionId || "default"}?token=${encodeURIComponent(token)}`),
        );
        ws = socket;
        wsRef.current = socket;
        socket.onopen = () => {
          if (wsRef.current === socket) dispatch({ type: "WS_OPEN" });
        };
        socket.onclose = () => {
          if (wsRef.current === socket) {
            wsRef.current = null;
            dispatch({ type: "WS_CLOSE" });
          }
          if (!cancelled) scheduleConnect(attempt + 1);
        };
        socket.onerror = () => {
          try {
            socket.close();
          } catch {}
        };
        socket.onmessage = (event) => {
          if (cancelled) return;
          try {
            const data: FroidPayload = JSON.parse(event.data);
            const elapsedSeconds = elapsedSecondsRef.current;
            const shouldUseForMetrics =
              remotePatientOnRef.current ||
              attributedSpeakerRef.current === "PC" ||
              directLocalMetricsActiveRef.current;
            if (!shouldUseForMetrics) {
              setLiveTranscription((prev) => ({
                ...(prev || {}),
                bioacoustic_status: "waiting_patient",
                bioacoustic_track: "local-professional-selected",
                bioacoustic_warning:
                  "Áudio local fora da trilha de paciente: métricas multimodais pausadas.",
              }));
              return;
            }
            if (firstPatientMetricSecondRef.current === null) {
              firstPatientMetricSecondRef.current = elapsedSeconds;
            }
            sessionSamplesRef.current.push({ elapsedSeconds, payload: data });
            if (sessionSamplesRef.current.length > 22000) {
              sessionSamplesRef.current = sessionSamplesRef.current.slice(-22000);
            }
            dispatch({ type: "PAYLOAD", data });
            frameBuffer.current.push(data);
            if (frameBuffer.current.length > 6) frameBuffer.current.shift();
          } catch (err) {
            console.error("Parse WS:", err);
          }
        };
      } catch {
        dispatch({ type: "WS_CLOSE" });
        if (!cancelled) scheduleConnect(attempt + 1);
      }
    };

    scheduleConnect(0);

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (wsRef.current === ws) wsRef.current = null;
      try {
        ws?.close();
      } catch {}
    };
  }, [sessionId]);

  useEffect(() => {
    const id = setInterval(() => {
      if (frameBuffer.current.length === 0) return;
      const agg = aggregatePayloads([...frameBuffer.current]);
      dispatch({ type: "AGGREGATE", agg });
      frameBuffer.current = [];
    }, 10000); /* agrega a cada 10s usando média dos últimos 3s (6 frames) */
    return () => clearInterval(id);
  }, []);

  const agg = state.aggregated;
  const raw = state.payload;
  const clinicalPresentationActive =
    clinicalUpdateMode !== "realtime" && clinicalSnapshot;
  const presentationAgg = clinicalPresentationActive ? clinicalSnapshot.agg : agg;
  const displayZones = presentationAgg?.zones || raw?.perception_zones || [];
  const displayIpm = presentationAgg?.ipm ?? raw?.ipm_score ?? state.localIpm ?? 0;
  const displayDrValue = presentationAgg?.drValue ?? (raw as any)?.dr_value ?? null;
  const displayCoherence = presentationAgg?.coherence || raw?.coherence_status || "NEUTRO";
  const displayAlerts = presentationAgg?.alerts || raw?.realtime_alerts || [];
  const displayIpmHistory =
    clinicalPresentationActive && clinicalSnapshot.ipmHistory.length
      ? clinicalSnapshot.ipmHistory
      : state.ipmHistory;
  const baseDisplayAudio = presentationAgg?.audioMeta ||
    (raw as any)?.audio_meta || {
      words_per_window: 0,
      total_words_session: 0,
      emotional_tone: "neutro",
      transcription_snippet: "",
      session_theme: "",
      theme_minute_mark: 0,
      words_per_minute_10m: 0,
    };
  const realTranscriptAudio = {
    ...baseDisplayAudio,
    transcription_snippet: "",
    transcription_interim: "",
    words_per_window: 0,
    total_words_session: 0,
    words_per_minute_10m: 0,
    session_theme: "",
    theme_minute_mark: 0,
    provider: "browser-recorder",
    transcription_status: state.micOn ? "listening" : "",
    transcription_error: "",
  };
  const displayAudio = liveTranscription
    ? clinicalPresentationActive
      ? { ...realTranscriptAudio, ...transcriptOverlay(liveTranscription) }
      : { ...realTranscriptAudio, ...liveTranscription }
    : realTranscriptAudio;
  const clinicalWindowMinutes = clinicalModeToMinutes(clinicalUpdateMode);
  const clinicalNextUpdateSeconds =
    clinicalPresentationActive
      ? Math.max(0, clinicalSnapshot.nextUpdateSecond - state.elapsedSeconds)
      : 0;
  const clinicalWindowLabel =
    clinicalUpdateMode === "realtime"
      ? "Tempo real"
      : `${clinicalWindowMinutes}min`;
  useEffect(() => {
    if (clinicalUpdateMode === "realtime" || !raw) return;
    const rawZones = Array.isArray(raw.perception_zones) ? raw.perception_zones : [];
    const rawAudio = ((raw as any)?.audio_meta || liveTranscription || {}) as Record<string, unknown>;
    const hasCriticalSignal =
      Boolean(raw.realtime_alerts?.length) ||
      rawZones.some(
        (zone) =>
          hasConfirmedDissonanceEvidence(zone, rawAudio) &&
          Math.abs(Number(zone.deviation_score || 0)) >= DISSONANCE_REPORT_THRESHOLD,
      );
    if (!hasCriticalSignal) return;
    if (state.elapsedSeconds - lastCriticalClinicalRefreshSecondRef.current < 20) return;
    lastCriticalClinicalRefreshSecondRef.current = state.elapsedSeconds;
    refreshClinicalPresentation();
  }, [
    clinicalUpdateMode,
    liveTranscription,
    raw,
    refreshClinicalPresentation,
    state.elapsedSeconds,
  ]);
  const confirmedDissonanceZones = (Array.isArray(displayZones) ? displayZones : []).filter(
    (zone) => hasConfirmedDissonanceEvidence(zone, displayAudio),
  );
  const semanticCutElapsed = Math.max(0, state.elapsedSeconds - semanticCutStartSecond);
  const semanticCutWindowSeconds = TRANSCRIPT_SUMMARY_WINDOW_MS / 1000;
  const semanticCutProgress = Math.min(
    100,
    (semanticCutElapsed / semanticCutWindowSeconds) * 100,
  );
  const semanticCutRemaining = Math.max(
    0,
    semanticCutWindowSeconds - semanticCutElapsed,
  );
  const simplifiedSnapshot =
    clinicalPresentationActive && clinicalSnapshot.metricSnapshot
      ? clinicalSnapshot.metricSnapshot
      : buildMetricSnapshot(
          "Atual",
          sessionSamplesRef.current,
          semanticCutStartSecond,
          Math.max(semanticCutStartSecond + 1, state.elapsedSeconds),
          transcriptSegmentsRef.current,
        );
  const simplifiedMetricEntries: Array<[string, string]> = [
    [
      "CORTE",
      `${Math.floor(semanticCutStartSecond / 60)}-${Math.max(
        Math.floor(semanticCutStartSecond / 60) + 1,
        Math.ceil(state.elapsedSeconds / 60),
      )}min`,
    ],
    ["IPM", formatMetricValue(simplifiedSnapshot.ipmAvg, 1)],
    ["IDM", formatMetricValue(simplifiedSnapshot.idmAvg, 2)],
    ["ZONAS", simplifiedSnapshot.dominantZone ? `Zona ${simplifiedSnapshot.dominantZone}` : "--"],
    ["TOM", simplifiedSnapshot.emotionalTone || "--"],
    ["P/MIN", formatMetricValue(simplifiedSnapshot.wordsPerMinute, 1)],
    ["DISSO.", String(simplifiedSnapshot.dissonanceCount || 0)],
    ["MFCC7", formatMetricValue(simplifiedSnapshot.mfcc7, 3)],
    ["MFCC9", formatMetricValue(simplifiedSnapshot.mfcc9, 3)],
    ["DMFCC7", formatMetricValue(simplifiedSnapshot.mfcc7Delta, 4)],
    ["DMFCC9", formatMetricValue(simplifiedSnapshot.mfcc9Delta, 4)],
    ["DDMFCC7", formatMetricValue(simplifiedSnapshot.mfcc7DeltaDelta, 4)],
    ["DDMFCC9", formatMetricValue(simplifiedSnapshot.mfcc9DeltaDelta, 4)],
    ["F0 MED.", formatMetricValue(simplifiedSnapshot.f0Mean, 2)],
    ["ZCR", formatMetricValue(simplifiedSnapshot.zcr, 3)],
    ["JITTER", formatMetricValue(simplifiedSnapshot.jitter, 3)],
    ["SHIMMER", formatMetricValue(simplifiedSnapshot.shimmer, 3)],
    ["DELTA", formatMetricValue(simplifiedSnapshot.spectralDelta0_4, 3)],
    ["THETA", formatMetricValue(simplifiedSnapshot.spectralTheta4_8, 3)],
    ["ALPHA", formatMetricValue(simplifiedSnapshot.spectralAlpha8_12, 3)],
    ["BETA", formatMetricValue(simplifiedSnapshot.spectralBeta12_30, 3)],
    ["GAMA", formatMetricValue(simplifiedSnapshot.spectralGamma30_80, 3)],
    ["IND. ESPECTRAL", formatMetricValue(simplifiedSnapshot.spectralBandIndex, 3)],
    ["SUB-H 5-12", formatMetricValue(simplifiedSnapshot.subharmonic5_12, 3)],
    ["SUB-H 12-20", formatMetricValue(simplifiedSnapshot.subharmonic12_20, 3)],
    ["SUB-H 20-40", formatMetricValue(simplifiedSnapshot.subharmonic20_40, 3)],
    ["VOCAL 85-165", formatMetricValue(simplifiedSnapshot.vocalBasal85_165, 3)],
    ["DNA INFRA", formatMetricValue(simplifiedSnapshot.dnaInfrasoundNuclear, 3)],
    ["DNA LIMBICO", formatMetricValue(simplifiedSnapshot.dnaLimbicModulation, 3)],
    ["DNA VOCAL", formatMetricValue(simplifiedSnapshot.dnaVocalBasalTension, 3)],
    ["DNA FLOOD", formatMetricValue(simplifiedSnapshot.dnaAutonomicFlooding, 3)],
    ["DNA SHUTDOWN", formatMetricValue(simplifiedSnapshot.dnaDissociativeShutdown, 3)],
    ["DNA NEURO", formatMetricValue(simplifiedSnapshot.dnaNeurogenicResonance, 3)],
    ["DNA SOMATO", formatMetricValue(simplifiedSnapshot.dnaSomatoaffectiveDissonance, 3)],
  ];

  const createSessionReport = useCallback((): SessionReportRecord => {
    const durationSeconds = Math.max(1, elapsedSecondsRef.current || state.elapsedSeconds);
    const samples = sessionSamplesRef.current.length
      ? sessionSamplesRef.current
      : raw
        ? [{ elapsedSeconds: durationSeconds, payload: raw }]
        : [];
    const baseline =
      baselineSnapshotRef.current ||
      buildMetricSnapshot(
        "Baseline inicial",
        samples,
        0,
        Math.min(60, durationSeconds),
        transcriptSegmentsRef.current,
      );
    const sessionAverage = buildMetricSnapshot(
      "Média da sessão",
      samples,
      0,
      Math.max(durationSeconds, 1),
      transcriptSegmentsRef.current,
    );
    const tenMinuteCuts = buildReportCuts(
      samples,
      transcriptSegmentsRef.current,
      durationSeconds,
      conversationSummaries,
    );
    const anonymizedContext = buildAnonymizedContext(
      sessionId || "default",
      durationSeconds,
      baseline,
      sessionAverage,
      tenMinuteCuts,
      transcriptSegmentsRef.current,
      conversationSummaries,
      remotePatientOnRef.current,
      sessionPatient?.sessionMode,
    );
    const summarySourceTranscript = transcriptSegmentsRef.current
      .map((segment) => segment.text)
      .join("\n");

    return {
      id: makeReportId(),
      sessionId: sessionId || "default",
      patient: loadSessionPatient(sessionId || "") || undefined,
      professionalEmail: user?.email || "",
      professional: {
        email: user?.email || "",
        name: user?.name || user?.email || "Profissional FROID",
      },
      createdAt: new Date().toISOString(),
      durationSeconds,
      baseline,
      sessionAverage,
      tenMinuteCuts,
      clinicalNotes: [],
      conversationSummaries,
      sessionSummary: buildSessionSummary(conversationSummaries, summarySourceTranscript),
      dissonances: dissonanceLog,
      transcript: summarySourceTranscript,
      transcriptRetention: "enabled",
      anonymizedContext,
    };
  }, [
    conversationSummaries,
    dissonanceLog,
    raw,
    sessionId,
    sessionPatient?.sessionMode,
    state.elapsedSeconds,
  ]);

  const archiveSessionReport = useCallback(
    async (report: SessionReportRecord) => {
      saveSessionReport(report);
      const token = localStorage.getItem("froid_token") || "";
      const response = await fetch(apiUrl("/api/session-reports"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(report),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail || "Falha ao arquivar a sessão no servidor.");
      }
    },
    [],
  );

  const endSession = useCallback(async () => {
    if (reportSavedRef.current) return;
    reportSavedRef.current = true;
    const report = createSessionReport();
    try {
      await archiveSessionReport(report);
    } catch (error) {
      reportSavedRef.current = false;
      const message = error instanceof Error ? error.message : "Falha ao arquivar a sessão.";
      window.alert(
        `${message}\n\nA sessão permanecerá aberta para preservar a transcrição. Tente encerrar novamente.`,
      );
      return;
    }
    if (wsRef.current)
      try {
        wsRef.current.close();
      } catch {}
    dispatch({ type: "END_SESSION" });
    navigate(`/session/${report.sessionId}/report`);
  }, [archiveSessionReport, createSessionReport, navigate]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      (
        window as Window &
          typeof globalThis & { __froidAudioMeta?: Record<string, unknown> }
      ).__froidAudioMeta = displayAudio;
    }
  }, [displayAudio]);

  useEffect(() => {
    const currentEntries = confirmedDissonanceZones
      .map((z) => {
        const score = dissonanceScore(z);
        return {
          zone: z.zone,
          score,
          severity: dissonanceSeverity(z),
          report: buildDissonanceReportText(
            z,
            displayAudio,
            displayIpm,
            state.baselineIPM,
          ),
        };
      });
    const signature = currentEntries
      .map((entry) => `${entry.zone}:${entry.score.toFixed(3)}:${entry.report}`)
      .join("|");
    if (!signature || signature === lastDissonanceSig.current) return;
    lastDissonanceSig.current = signature;

    const nextEntries = currentEntries
      .map((entry) => {
        return {
          id: `${entry.zone}-${Date.now()}`,
          timestamp: new Date().toLocaleString("pt-BR"),
          elapsedSeconds: state.elapsedSeconds,
          zone: entry.zone,
          report: entry.report,
        };
      })
      .filter((entry) => Number.isFinite(entry.zone));

    setDissonanceLog((prev) => [...prev, ...nextEntries].slice(-18));
  }, [confirmedDissonanceZones, displayAudio, state.elapsedSeconds]);

  const connectionText = state.connected
    ? state.phase === "CALIBRATING"
      ? "Sincronia Inicial"
      : "Ao Vivo"
    : state.phase === "ENDED"
      ? "Encerrada"
      : "Desconectado";
  const patientBaselineStart = firstPatientMetricSecondRef.current;
  const patientBaselineElapsed =
    patientBaselineStart === null
      ? 0
      : clamp(state.elapsedSeconds - patientBaselineStart, 0, 60);

  if (state.phase === "ENDED") {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-700">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold text-slate-800">
            Sessão Encerrada
          </h1>
          <p className="text-sm text-slate-500">Dados arquivados.</p>
          <button
            onClick={() => navigate("/dashboard")}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700"
          >
            Voltar ao Dashboard
          </button>
        </div>
      </div>
    );
  }

  const layoutSelector = (
    <button
      type="button"
      onClick={() =>
        setSessionLayout((current) =>
          current === "detailed" ? "simplified" : "detailed",
        )
      }
      className="w-full rounded-lg border border-blue-700 bg-blue-950 px-3 py-2 text-[9px] font-black uppercase tracking-wide text-blue-100 transition-colors hover:bg-blue-900"
    >
      {sessionLayout === "detailed"
        ? "Abrir Sessão Simplificada"
        : "Voltar à Sessão Detalhada"}
    </button>
  );

  const clinicalStabilizationControl = (
    <div className="rounded-lg border border-slate-700 bg-slate-900/90 p-2 text-[10px] text-slate-200">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-black uppercase tracking-wide text-cyan-200">
            Estabilização clínica
          </p>
          <p className="truncate text-[9px] text-slate-400">
            Janela visual: {clinicalWindowLabel}
            {clinicalUpdateMode !== "realtime"
              ? ` | próxima em ${formatCutClock(clinicalNextUpdateSeconds)}`
              : " | sem congelamento"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshClinicalPresentation()}
          disabled={clinicalUpdateMode === "realtime"}
          className="shrink-0 rounded border border-cyan-800 bg-cyan-950 px-2 py-1 text-[9px] font-black uppercase text-cyan-100 hover:bg-cyan-900 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
        >
          Atualizar agora
        </button>
      </div>
      <select
        value={clinicalUpdateMode}
        onChange={(event) => setClinicalUpdateMode(event.target.value as ClinicalUpdateMode)}
        className="mt-2 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-[10px] font-bold text-slate-100 outline-none focus:border-cyan-500"
      >
        {CLINICAL_UPDATE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );

  if (sessionLayout === "simplified") {
    return (
      <div className="flex h-screen min-w-0 flex-col overflow-hidden bg-slate-950 text-slate-100">
        <header className="shrink-0 overflow-x-auto border-b border-slate-800 bg-slate-900 px-3 py-2">
          <div className="flex min-w-max items-center gap-3 whitespace-nowrap">
            <h1 className="text-sm font-black">Sessão Simplificada</h1>
            <span className="text-[9px] text-slate-400">
              Sessão {sessionId?.slice(0, 8) || "--"} · vídeo · corte semântico · resumo · métricas · FROID Explica
            </span>
            <div className="w-[220px] shrink-0">{layoutSelector}</div>
            <strong className="text-[9px] uppercase text-cyan-200">Estabilização:</strong>
            <select
              value={clinicalUpdateMode}
              onChange={(event) => setClinicalUpdateMode(event.target.value as ClinicalUpdateMode)}
              className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-[9px] font-bold text-slate-100 outline-none focus:border-cyan-500"
            >
              {CLINICAL_UPDATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <span className="text-[9px] text-slate-400">
              {clinicalWindowLabel}{clinicalUpdateMode !== "realtime" ? ` · próxima em ${formatCutClock(clinicalNextUpdateSeconds)}` : " · tempo real"}
            </span>
            <button
              type="button"
              onClick={() => refreshClinicalPresentation()}
              disabled={clinicalUpdateMode === "realtime"}
              className="rounded border border-cyan-800 bg-cyan-950 px-2 py-1.5 text-[9px] font-black uppercase text-cyan-100 disabled:opacity-40"
            >
              Atualizar
            </button>
            <button
              type="button"
              onClick={endSession}
              className="rounded bg-red-600 px-3 py-1.5 text-[10px] font-bold text-white hover:bg-red-700"
            >
              Encerrar
            </button>
          </div>
        </header>

        <div className="shrink-0 overflow-x-auto border-b border-slate-700 bg-slate-900">
          <div className="flex min-w-max divide-x divide-slate-700 px-2 py-1.5">
            {simplifiedMetricEntries.map(([label, value]) => (
              <div key={label} className="px-2 first:pl-1">
                <FroidTooltip
                  content={SIMPLIFIED_METRIC_TOOLTIPS[label] || "Métrica do corte atual da sessão simplificada."}
                  width={330}
                >
                  <span className="block cursor-help whitespace-nowrap text-[9px] font-black uppercase tracking-wide text-slate-500 underline decoration-slate-600 underline-offset-2">
                    {label}
                  </span>
                </FroidTooltip>
                <p className="mt-0.5 whitespace-nowrap font-mono text-[10px] text-slate-200">
                  {value}
                </p>
              </div>
            ))}
          </div>
        </div>

        <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,3fr)_minmax(360px,2fr)] gap-2 overflow-hidden p-2">
          <section className="relative flex min-h-0 items-center justify-center overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
            <MediaStatus
              cameraOn={state.cameraOn}
              micOn={state.micOn}
              simulated={!state.cameraOn}
            />
            <video
              ref={remoteVideoRef}
              autoPlay
              muted
              playsInline
              className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                remotePatientVideoOn ? "opacity-100" : "opacity-0"
              }`}
            />
            <audio ref={remoteAudioRef} autoPlay className="hidden" />
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
                remotePatientVideoOn
                  ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                  : "inset-0 h-full w-full"
              } ${state.cameraOn ? "opacity-100" : "opacity-0"}`}
            />
            <div
              className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
                remotePatientVideoOn
                  ? "bg-emerald-500/90 text-white"
                  : "bg-slate-950/70 text-slate-200"
              }`}
            >
              {rtcStatus}
            </div>
            {!state.cameraOn && <SimulatedCamera />}
            {(state.camError || !state.micOn) && (
              <div className="absolute bottom-3 left-3 right-3 z-20 rounded-lg border border-amber-300/50 bg-slate-950/75 px-3 py-2 text-[10px] font-semibold text-amber-100 backdrop-blur-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="min-w-0 flex-1">
                    {state.camError || "Áudio aguardando permissão do navegador."}
                  </span>
                  {!state.micOn && (
                    <button
                      type="button"
                      onClick={() => void activateMedia()}
                      className="shrink-0 rounded bg-amber-400 px-2 py-1 text-[10px] font-black text-slate-950 hover:bg-amber-300"
                    >
                      Ativar áudio
                    </button>
                  )}
                </div>
              </div>
            )}
          </section>

          <div className="flex min-h-0 flex-col gap-2 overflow-y-auto">
            <section className="shrink-0 overflow-hidden rounded-xl border border-cyan-800 bg-slate-950 shadow-sm">
              <div className="bg-cyan-950 p-3 text-[10px] text-cyan-100">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <p className="font-black uppercase tracking-wider">
                      <FroidTooltip content={SIMPLIFIED_CUT_TOOLTIP} width={360}>
                        <span className="cursor-help underline decoration-cyan-700 underline-offset-2">
                          Corte semântico + Resumo da Fala IA
                        </span>
                      </FroidTooltip>
                    </p>
                    <p className="mt-0.5 text-[9px] text-cyan-300">
                      Fechamento do corte e síntese complementar
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void closeSemanticCut("manual")}
                    className="shrink-0 rounded bg-cyan-700 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-cyan-200"
                    disabled={semanticCutElapsed < 10 || semanticCutClosingRef.current}
                    title="Fecha manualmente o corte atual e gera resumo IA do período."
                  >
                    Fechar corte
                  </button>
                </div>
                <div className="flex items-center justify-between font-mono text-[10px] text-cyan-200">
                  <span>Atual {formatCutClock(semanticCutElapsed)}</span>
                  <span>Auto em {formatCutClock(semanticCutRemaining)}</span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-cyan-900">
                  <div
                    className="h-full rounded-full bg-cyan-600 transition-all duration-1000"
                    style={{ width: `${semanticCutProgress}%` }}
                  />
                </div>
              </div>
              <div className="p-2">
                <AudioTranscription
                  audioMeta={displayAudio}
                  conversationSummaries={conversationSummaries}
                  section="summary"
                />
              </div>
            </section>

            <section className="min-h-[320px] flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2">
              <AIInsights
                zones={displayZones}
                ipmScore={displayIpm}
                coherenceStatus={displayCoherence}
                baselineEstablished={state.phase === "LIVE"}
                sessionId={sessionId || ""}
                controlsSticky
                rootClassName="h-full border-0 bg-transparent p-0 text-slate-100"
                messagesClassName="min-h-[190px] bg-slate-800/80 text-slate-200"
              />
            </section>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="grid h-screen min-w-[1620px] grid-cols-[minmax(500px,28%)_minmax(620px,44%)_minmax(500px,28%)] overflow-x-auto overflow-y-hidden bg-slate-950 text-slate-100">
      {/* COLUNA 1 — 30% */}
      <div className="order-1 min-w-0 flex flex-col gap-2 overflow-y-auto border-x border-slate-800 bg-slate-950 p-2 text-slate-100">
        <div className="flex items-center justify-between">
          <h1 className="text-base font-bold text-slate-100">
            Sessão Detalhada
          </h1>
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${state.connected ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}
            >
              {connectionText}
            </span>
            <button
              onClick={endSession}
              className="rounded bg-red-600 px-2 py-1 text-[10px] font-bold text-white hover:bg-red-700"
            >
              Encerrar
            </button>
          </div>
        </div>

        {layoutSelector}

        {clinicalStabilizationControl}

        <SessionTimer
          startTime={state.sessionStart}
          onEndSession={endSession}
        />

        {(isPresentialSession || isPresentialMobileSession) && (
          <div className="rounded-lg border border-emerald-800 bg-emerald-950 p-3 text-[10px] leading-relaxed text-emerald-100">
            <div className="flex items-center justify-between gap-2">
              <p className="font-black uppercase tracking-wide">
                {isPresentialMobileSession
                  ? "Presencial com celular do paciente"
                  : "Sessão presencial"}
              </p>
              <span className="rounded bg-slate-950/60 px-2 py-0.5 font-black">
                {speakerIdMode === "auto" ? "voz DR auto" : "captura PC prioritária"}
              </span>
            </div>
            <p className="mt-1">
              {isPresentialMobileSession
                ? "O celular do paciente deve ficar voltado ao rosto dele e funcionar como captura dedicada. Recomenda-se microfone de lapela no profissional para reduzir interferencia da voz do DR."
                : "Recomendado: câmera e microfone externos direcionados ao paciente. Cadastre a voz do DR antes da consulta para reduzir contaminação da trilha bioacústica."}
            </p>
            <div className="mt-2 grid grid-cols-1 gap-1.5">
              <button
                type="button"
                disabled={isEnrollingDrVoice || !state.micOn}
                onClick={() => void enrollDrVoice()}
                className="rounded border border-emerald-700 bg-slate-950/60 px-2 py-1 font-bold text-emerald-100 hover:bg-emerald-900 disabled:opacity-40"
              >
                Cadastrar voz do DR antes da sessão
              </button>
            </div>
            <p className="mt-2 text-[9px] text-emerald-200">{voiceIdStatus}</p>
          </div>
        )}

        <div className="rounded-xl border border-cyan-800 bg-cyan-950 p-3 text-[10px] text-cyan-100 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div>
              <p className="font-bold uppercase tracking-wider">
                Corte semântico da sessão
              </p>
            </div>
            <button
              type="button"
              onClick={() => void closeSemanticCut("manual")}
              className="shrink-0 rounded bg-cyan-700 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-cyan-200"
              disabled={semanticCutElapsed < 10 || semanticCutClosingRef.current}
              title="Fecha manualmente o corte atual e gera resumo IA do período."
            >
              Fechar corte
            </button>
          </div>
          <div className="flex items-center justify-between font-mono text-[10px] text-cyan-200">
            <span>Atual {formatCutClock(semanticCutElapsed)}</span>
            <span>Auto em {formatCutClock(semanticCutRemaining)}</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-cyan-900">
            <div
              className="h-full rounded-full bg-cyan-600 transition-all duration-1000"
              style={{ width: `${semanticCutProgress}%` }}
            />
          </div>
        </div>

        {state.phase === "CALIBRATING" && (
          <div className="shrink-0 rounded-lg border border-blue-800 bg-blue-950 p-3 text-xs text-blue-100">
            <p className="font-bold">Fase de Repouso Ativa</p>
            <p>
              {patientBaselineStart === null
                ? "Aguardando PC para iniciar baseline de métricas."
                : `Coletando baseline do PC: ${patientBaselineElapsed.toFixed(0)}s / 60s`}
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-900">
              <div
                className="h-full bg-blue-600 transition-all duration-1000"
                style={{ width: (patientBaselineElapsed / 60) * 100 + "%" }}
              />
            </div>
          </div>
        )}

        <div className="flex-1 min-h-0 flex flex-col gap-3">
          <div className="min-h-[270px]">
            <RiskChart
              zones={displayZones}
              ipmScore={displayIpm}
              coherenceStatus={displayCoherence}
              baseline={state.baselineIPM}
              audioMeta={displayAudio}
            />
          </div>

          <div className="min-h-[300px]">
            <SpectralBandsChart audioMeta={displayAudio} />
          </div>

          <div className="min-h-[390px]">
            <SubharmonicChart zones={displayZones} audioMeta={displayAudio} />
          </div>

          <AudioTranscription
            audioMeta={displayAudio}
            conversationSummaries={conversationSummaries}
            section="biomarkers"
          />
        </div>
      </div>

      {/* COLUNA 2 — 34%: Vídeo (50%) + Mapa Zonal (50%) */}
      <div className="order-2 min-w-0 flex flex-col gap-2 overflow-y-auto bg-slate-950 p-2 shadow-inner">
        {/* Vídeo — 50% do espaço */}
        <div className="relative flex min-h-[320px] flex-[0.9] items-center justify-center overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
          <MediaStatus
            cameraOn={state.cameraOn}
            micOn={state.micOn}
            simulated={!state.cameraOn}
          />
          <video
            ref={remoteVideoRef}
            autoPlay
            muted
            playsInline
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
              remotePatientVideoOn ? "opacity-100" : "opacity-0"
            }`}
          />
          <audio ref={remoteAudioRef} autoPlay className="hidden" />
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
              remotePatientVideoOn
                ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                : "inset-0 h-full w-full"
            } ${state.cameraOn ? "opacity-100" : "opacity-0"}`}
          />
          <div
            className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
              remotePatientVideoOn
                ? "bg-emerald-500/90 text-white"
                : "bg-slate-950/70 text-slate-200"
            }`}
          >
            {rtcStatus}
          </div>
          {!state.cameraOn && <SimulatedCamera />}
          {(state.camError || !state.micOn) && (
            <div className="absolute bottom-3 left-3 right-3 z-20 rounded-lg border border-amber-300/50 bg-slate-950/75 px-3 py-2 text-[10px] font-semibold text-amber-100 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="min-w-0 flex-1">
                  {state.camError || "Áudio aguardando permissão do navegador."}
                </span>
                {!state.micOn && (
                  <button
                    type="button"
                    onClick={() => void activateMedia()}
                    className="shrink-0 rounded bg-amber-400 px-2 py-1 text-[10px] font-black text-slate-950 hover:bg-amber-300"
                  >
                    Ativar áudio
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <AudioTranscription
          audioMeta={displayAudio}
          conversationSummaries={conversationSummaries}
          section="summary"
        />

        <div className="min-h-[320px] flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2">
          <AIInsights
            zones={displayZones}
            ipmScore={displayIpm}
            coherenceStatus={displayCoherence}
            baselineEstablished={state.phase === "LIVE"}
            sessionId={sessionId || ""}
            controlsSticky
            rootClassName="h-full border-0 bg-transparent p-0 text-slate-100"
            messagesClassName="min-h-[190px] bg-slate-800/80 text-slate-200"
          />
        </div>
      </div>

      {/* COLUNA 3 — 35%: IPM grande, Risco, Subharm, Coherence, Dissonâncias */}
      <div className="order-3 grid min-w-0 grid-rows-3 gap-2 overflow-hidden bg-slate-950 p-3">
        {raw ? (
          <>
            <div className="min-h-0 overflow-hidden">
              <IPMLineChart
                data={displayIpmHistory}
                current={displayIpm}
                baseline={state.baselineIPM || undefined}
              />
            </div>

            <div className="min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-900 p-1">
              <MapaZonalFroid
                className="h-full"
                zones={displayZones}
                baselineIpm={state.baselineIPM}
                drValue={displayDrValue}
                isCalibrating={state.phase === "CALIBRATING"}
              />
            </div>

            <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-100 shadow-sm">
              <div className="mb-3 flex items-start justify-between gap-3 border-b border-slate-800 pb-2">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-red-200">
                    Dissonâncias
                  </p>
                  <p className="mt-1 text-[10px] leading-snug text-slate-400">
                    Divergencias multimodais acima dos limiares FROID. Itens abaixo
                    das métricas configuradas são omitidos.
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded px-2 py-1 text-[9px] font-black uppercase ${
                    confirmedDissonanceZones.length
                      ? "bg-red-600 text-white"
                      : "bg-emerald-900/70 text-emerald-200"
                  }`}
                >
                  {confirmedDissonanceZones.length
                    ? `${confirmedDissonanceZones.length} ativa(s)`
                    : "sem alerta"}
                </span>
              </div>

              {confirmedDissonanceZones.length === 0 && (
                <div className="rounded-xl border border-emerald-900/70 bg-emerald-950/20 p-3 text-[11px] leading-relaxed text-emerald-100">
                  Nenhuma dissonância facial-vocal-semântica ultrapassou os
                  limiares definidos neste instante. O FROID segue monitorando
                  voz do paciente, FACS, IPM, IDM, sub-harmônicos, biomarcadores
                  acústicos e conteúdo transcrito.
                </div>
              )}

              {confirmedDissonanceZones.length > 0 &&
                confirmedDissonanceZones
                  .map((zone) => {
                    const aus = zone.dissonance_details?.active_aus || [];
                    const auDescs = getAUDetails(aus);
                    const score = dissonanceScore(zone);
                    const severity = dissonanceSeverity(zone);
                    const interpretation = classifyDissonance(zone, displayAudio);
                    const technicalFactors = dissonanceTechnicalFactors(
                      zone,
                      displayAudio,
                      displayIpm,
                      state.baselineIPM,
                    );
                    return (
                      <div
                        key={zone.zone}
                        className="mb-3 rounded-xl border border-red-800/70 bg-red-950/25 p-3 shadow-sm"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[11px] font-black uppercase tracking-wide text-red-200">
                              {interpretation.title}
                            </p>
                            <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                              Zona {zone.zone} - {zone.tema || "tema em apuração"}
                            </p>
                          </div>
                          <span className="shrink-0 rounded bg-red-600 px-1.5 py-0.5 text-[9px] font-black text-white">
                            IDM {score.toFixed(2)} | {severity}
                          </span>
                        </div>

                        <p className="mt-2 text-[11px] font-medium leading-relaxed text-slate-200">
                          {interpretation.summary}
                        </p>

                        <div className="mt-2 rounded-lg border border-slate-700 bg-slate-950/70 p-2">
                          <p className="text-[10px] font-black uppercase tracking-wider text-cyan-200">
                            Motivo técnico do apontamento
                          </p>
                          <p className="mt-1 text-[10px] leading-snug text-slate-300">
                            O FROID registrou este apontamento apenas porque a
                            composição entre face, voz, zona, IDM e/ou semântica
                            ultrapassou os limiares definidos após comparação com
                            a baseline de 60 segundos da sessão.
                          </p>
                          <p className="mt-2 text-[10px] font-black uppercase tracking-wider text-slate-400">
                            Itens divergentes apurados
                          </p>
                          <ul className="mt-1 space-y-1 text-[10px] leading-snug text-slate-300">
                            {technicalFactors.map((factor, i) => (
                              <li key={i} className="list-inside list-disc">
                                {factor}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {auDescs.length > 0 && (
                          <div className="mt-2 space-y-1 rounded-lg border border-slate-700 bg-slate-950/50 p-2">
                            <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                              Leitura FACS/AUs
                            </p>
                            {auDescs.map((d, i) => (
                              <p
                                key={i}
                                className="text-[10px] font-mono leading-tight text-slate-300"
                              >
                                {d}
                              </p>
                            ))}
                          </div>
                        )}

                        <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] font-bold leading-relaxed text-amber-100">
                          Fatores de mitigacao: {interpretation.action}
                        </p>
                      </div>
                    );
                  })}

              {dissonanceLog.length > 0 && (
                <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900 p-2">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-300">
                      Registro de Dissonâncias
                    </p>
                    <span className="text-[9px] text-slate-500">
                      {dissonanceLog.length} itens
                    </span>
                  </div>
                  <div className="max-h-32 space-y-1 overflow-y-auto pr-1">
                    {dissonanceLog
                      .slice()
                      .reverse()
                      .map((entry) => (
                        <div
                          key={entry.id}
                          className="rounded border border-red-900/60 bg-red-950/20 p-2 text-[10px] text-slate-300"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-bold text-red-200">
                              Zona {entry.zone}
                            </span>
                            <span className="text-[9px] text-slate-500">
                              {entry.elapsedSeconds}s
                            </span>
                          </div>
                          <p className="mt-0.5 text-[9px] text-slate-500">
                            {entry.timestamp}
                          </p>
                          <p className="mt-0.5 leading-snug">{entry.report}</p>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              <div className="mt-3 space-y-2">
                {displayAlerts.slice(0, 4).map((alert, i) => (
                  <div
                    key={`alert-${i}`}
                    className="rounded bg-amber-50 p-2 text-[11px] font-medium text-amber-800 border border-amber-100"
                  >
                    {alert}
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="row-span-3 flex items-center justify-center text-sm text-slate-400">
            <div className="text-center">
              <div className="mb-2 mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
              Aguardando pacote multimodal FROID...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function LiveSession({ user }: LiveSessionProps) {
  return (
    <ErrorGuard>
      <LiveSessionInner user={user} />
    </ErrorGuard>
  );
}
