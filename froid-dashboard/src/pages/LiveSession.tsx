import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";

interface LiveSessionProps {
  user?: any;
}
import { useParams, useNavigate } from "react-router-dom";
import {
  incorporarRelatorioRemoto,
  observarConexao,
  registrarEnvio,
  registrarNegociacao,
  registrarFalha,
  registrarRtc,
  relatorioRtc,
} from "../lib/diagnostico-rtc";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import { RiskChart } from "../components/indicators/RiskChart";
import { SpectralBandsChart } from "../components/indicators/SpectralBandsChart";
import { SubharmonicChart } from "../components/indicators/SubharmonicChart";
import { MediaStatus } from "../components/indicators/MediaStatus";
import { AvisoVozSimulada } from "../components/indicators/AvisoVozSimulada";
import { SessionTimer } from "../components/indicators/SessionTimer";
import { AIInsights } from "../components/panels/AIInsights";
import { AudioTranscription } from "../components/panels/AudioTranscription";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import {
  FroidPayload,
  PerceptionZone,
  DissonanceEvent,
  EvidentMarker,
} from "../lib/froid-engine";
import { getAUDetails, ZONE_CLINICAL_DESCRIPTIONS } from "../lib/froid-data";
import {
  STATUS_CLASSES,
  countOutOfBounds,
  statusLabel,
  withBounds,
} from "../lib/metric-bounds";
import { apiUrl, wsUrl } from "../lib/api";
import {
  criarFreioDeRenegociacao,
  eDesalinhamentoDeMlines,
  activateRtcRelayFallback,
  motivoDaRecusaDeSinalizacao,
  adoptRemoteTrack,
  attachRemoteMedia,
  configureConferenceSender,
  createConferenceStream,
  evaluateInboundFlow,
  loadRtcConfiguration,
  readRtcMediaFlowStats,
  requestScreenWakeLock,
  shouldReconnectRtcSignaling,
  type RtcMediaFlowStats,
  type ScreenWakeLock,
} from "../lib/webrtc";
import {
  MetricSnapshot,
  loadSessionPatient,
  loadSessionReports,
  rememberSessionPatient,
  saveSessionReport,
  SessionReportRecord,
} from "../lib/session-report";
import { countSpokenUnits, normalizeSessionLocale, SESSION_LOCALES } from "../lib/localization";
import { tooltipText } from "../lib/tooltip-i18n";

const SIMPLIFIED_METRIC_TOOLTIPS: Record<string, string> = {
  CORTE:
    "Intervalo temporal em análise desde o último corte semântico, seja automático ou executado pelo profissional.",
  IPM:
    "Índice de Potência Multimodal. Funciona como o velocímetro emocional: indica a intensidade global da energia vocal, facial e semântica do paciente.",
  IDM:
    "Índice de Desvio Multimodal. Indica a direção e o grau de afastamento entre voz, face, semântica e zonas FROID.",
  ZONAS:
    "Zona FROID predominante no corte atual, calculada pela composição das métricas bioacústicas, semânticas e multimodais.",
  TOM:
    "Tom emocional predominante inferido pela composição entre fala transcrita, marcadores acústicos e contexto do corte.",
  "P/MIN":
    "Palavras por minuto no corte atual. Ajuda a identificar aceleração, lentificação, bloqueios ou mudanças de cadência.",
  "DISSO.":
    "Quantidade de dissonâncias confirmadas acima da métrica definida no corte atual. Exibe somente apontamentos efetivamente detectados.",
  MFCC7:
    "Coeficiente cepstral vocal associado ao timbre e à energia espectral. No FROID, ganha relevância quando cruza valência semântica negativa e marcadores de retardo ou tensão.",
  MFCC9:
    "Coeficiente cepstral vocal usado como marcador complementar de tensão autônoma, especialmente quando observado em trechos semanticamente neutros.",
  DMFCC7:
    "Delta do MFCC7. Mede a variação de primeira ordem do coeficiente durante o corte.",
  DMFCC9:
    "Delta do MFCC9. Mede a variação de primeira ordem do coeficiente durante o corte.",
  DDMFCC7:
    "Delta-delta do MFCC7. Indica aceleração ou desaceleração da mudança cepstral.",
  DDMFCC9:
    "Delta-delta do MFCC9. Indica aceleração ou desaceleração da mudança cepstral.",
  "F0 MED.":
    "Frequência fundamental média da voz. Ajuda a observar elevação de pitch, queda vocal, tensão ou variações de ativação.",
  ZCR:
    "Taxa de cruzamento por zero. Aponta irregularidade acústica e componentes de aspereza, ruído ou tensão vocal.",
  JITTER:
    "Índice interno normalizado de perturbação de frequência, derivado para comparação longitudinal no FROID. Não é percentual acústico bruto.",
  SHIMMER:
    "Índice interno normalizado de variação de amplitude vocal, derivado para comparação longitudinal no FROID. Não é medida bruta em dB.",
  DELTA:
    "Energia de modulação vocal na faixa delta. No FROID, representa modulação bioacústica lenta, não atividade EEG direta.",
  THETA:
    "Energia de modulação vocal na faixa theta. Usada como marcador de oscilação lenta da expressão vocal.",
  ALPHA:
    "Energia de modulação vocal na faixa alpha. Ajuda a compor estabilidade, ritmo e organização da emissão.",
  BETA:
    "Energia de modulação vocal na faixa beta. Ajuda a compor índices de ativação, esforço e tensão cognitiva.",
  GAMA:
    "Energia de modulação vocal na faixa gama. Ajuda a observar ativação rápida e instabilidade espectral fina.",
  "IND. ESPECTRAL":
    "Índice composto das bandas espectrais vocais, usado para sintetizar o perfil de modulação bioacústica do corte.",
  "SUB-H 5-12":
    "Energia sub-harmônica entre 5 e 12 Hz. No FROID, integra o núcleo de leitura autônoma e sinais de sobrecarga profunda.",
  "SUB-H 12-20":
    "Energia sub-harmônica entre 12 e 20 Hz. Complementa a leitura de tremor, tensão e modulação involuntária.",
  "SUB-H 20-40":
    "Energia sub-harmônica entre 20 e 40 Hz. Complementa a leitura de excitação, instabilidade e microtremores vocais.",
  "VOCAL 85-165":
    "Banda basal de tensão vocal. Ajuda a identificar sustentação, constrição e esforço na base da emissão.",
  "DNA INFRA":
    "Componente nuclear de infrassom vocal usado na matriz bioacústica do FROID.",
  "DNA LIMBICO":
    "Componente de modulação límbica estimado pela combinação de sub-harmônicos, voz e contexto emocional.",
  "DNA VOCAL":
    "Componente de tensão vocal basal usado para compor riscos, dissonâncias e estado de ativação.",
  "DNA FLOOD":
    "Indicador composto de elevacao multimodal simultanea: varios canais medidos sobem juntos na mesma janela.",
  "DNA SHUTDOWN":
    "Indicador composto de queda multimodal sustentada: varios canais medidos caem juntos, com reducao de coerencia entre eles.",
  "DNA NEURO":
    "Índice de ressonância neurogênica estimado por combinações sub-harmônicas e estabilidade vocal.",
  "DNA SOMATO":
    "Índice de dissonância somatoafetiva, usado para cruzar expressão vocal, tensão e marcadores corporais inferidos.",
};

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
// Tolerância de silêncio do paciente: o fluxo de áudio RTP é amostrado a cada
// 2s, então uma pausa natural na fala zera o delta de bytes. Manter a trilha
// válida por 20s após o último fluxo observado evita que silêncio clínico —
// que é dado, não ausência de sinal — descarte as métricas do tick.
const PATIENT_AUDIO_GRACE_MS = 20_000;
const CLINICAL_MICRO_WINDOW_SECONDS = 60;
// Teto de caracteres da transcrição enviada ao FROID Explica por consulta,
// preservando o trecho mais recente sem estourar o contexto do modelo.
const FROID_EXPLICA_TRANSCRIPT_CHAR_LIMIT = 8000;
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
      title: "Shutdown psíquico / dissociação",
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
  // `Number(null)` e `Number("")` valem ZERO, nao NaN. Sem esta guarda, uma
  // metrica que nunca foi medida aparecia como `0.000` — indistinguivel de uma
  // medida que deu zero — e ainda era classificada contra os limites da faixa.
  // Ausencia de medida nao e medida de ausencia.
  if (value === null || value === undefined || value === "") return "--";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

function dissonanceTechnicalFactors(
  zone?: PerceptionZone | null,
  audioMeta?: Record<string, unknown>,
  currentIpm?: number | null,
  baselineIpm?: number | null,
) {
  // PORTAO DE PROCEDENCIA.
  //
  // Todos os fatores abaixo derivam do sinal acustico — jitter, shimmer, os
  // indices DNA, a aceleracao cepstral. Sem PCM real do paciente, o motor os
  // calcula sobre um espectro GERADO, e esta funcao os transformava em prosa
  // clinica afirmativa. A pior delas dizia "pico persistente compativel com
  // contracao espastica involuntaria das cordas vocais por ativacao simpatica"
  // — e sem audio ela dispara em cerca de um quarto dos ticks.
  //
  // O motor sempre declarou a origem em `voice_features_source`. Nenhuma tela
  // consultava. Este e o portao que faltava: sem medida, o profissional le que
  // nao ha medida, em vez de ler um achado que ninguem observou.
  const vozMedida = audioMeta?.voice_features_source === "real_pcm";
  if (audioMeta && !vozMedida) {
    return [
      "Sem áudio medido do paciente nesta janela: os índices acústicos foram "
      + "gerados pelo modo de simulação e não sustentam leitura clínica.",
    ];
  }
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
    `Morfodinâmica facial/FACS: AUs ativas ${aus.length ? aus.join(", ") : "sem AU específica reportada"}; a leitura exige coerência temporal entre neutral, onset, apex e offset para reduzir falso positivo.`,
    `Zona ${zone?.zone ?? "--"} (${zone?.tema || "tema em apuração"}): ${ZONE_CLINICAL_DESCRIPTIONS[zone?.zone || 0] || "sem descrição zonal."}`,
  ];

  if (mfcc7Delta !== null && Math.abs(mfcc7Delta) >= DISSONANCE_MFCC_DELTA_THRESHOLD) {
    factors.push(
      `MFCC7 divergente: ${formatMetricValue(audioMeta?.mfcc7)} contra baseline ${formatMetricValue(audioMeta?.baseline_mfcc7)} (delta ${mfcc7Delta.toFixed(2)}), marcador acústico associado a valência negativa quando sustentado em fala emocionalmente carregada.`,
    );
  }
  if (mfcc9Delta !== null && Math.abs(mfcc9Delta) >= DISSONANCE_MFCC_DELTA_THRESHOLD) {
    factors.push(
      `MFCC9 divergente: ${formatMetricValue(audioMeta?.mfcc9)} contra baseline ${formatMetricValue(audioMeta?.baseline_mfcc9)} (delta ${mfcc9Delta.toFixed(2)}), sugerindo tensão autônoma latente quando cruza discurso neutro ou controlado.`,
    );
  }
  if (audioMeta?.mfcc9_delta_delta_spastic_alert === true) {
    const spasticThreshold =
      typeof audioMeta?.mfcc9_delta_delta_spastic_threshold === "number"
        ? audioMeta.mfcc9_delta_delta_spastic_threshold
        : 1.8;
    factors.push(
      `Aceleração cepstral ΔΔMFCC9 = ${formatMetricValue(audioMeta?.mfcc9_delta_delta)} acima do limiar ${spasticThreshold.toFixed(1)}: pico persistente compatível com contração espástica involuntária das cordas vocais por ativação simpática.`,
    );
  }
  if (dnaInfrasound !== null && dnaInfrasound >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Sub-harmônicos 5-12 Hz acima da métrica (${dnaInfrasound.toFixed(2)}): indicam tremor autonômico vocal detectado na trilha bruta do paciente.`,
    );
  }
  if (dnaBasal !== null && dnaBasal >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Tensão basal 85-165 Hz acima da métrica (${dnaBasal.toFixed(2)}): aponta carga laríngea/respiratória sustentada sob a fala.`,
    );
  }
  if (dnaFlooding !== null && dnaFlooding >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Flooding autonômico acima da métrica (${dnaFlooding.toFixed(2)}): combinação de energia sub-harmônica, tensão basal e multiplicador facial.`,
    );
  }
  if (dnaShutdown !== null && dnaShutdown >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Shutdown/dissociação acima da métrica (${dnaShutdown.toFixed(2)}): queda relativa de disponibilidade expressiva com tremor autonômico residual.`,
    );
  }
  if (dnaSomato !== null && dnaSomato >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Dissonância somatoafetiva acima da métrica (${dnaSomato.toFixed(2)}): contraste corpo-voz-face suficiente para registro clínico.`,
    );
  }
  if (dnaNeurogenic !== null && dnaNeurogenic >= DISSONANCE_DNA_THRESHOLD) {
    factors.push(
      `Ressonância neurogênica acima da métrica (${dnaNeurogenic.toFixed(2)}): alteração sub-harmônica em faixa superior compatível com ativação corporal não verbalizada.`,
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
        // Tick sem apuracao NAO entra no historico.
        //
        // O `: 0` empilhava zero para cada janela sem medida, e zero e um valor
        // legitimo de IPM — o grafico passava a mostrar uma queda a zero que
        // ninguem observou, e a media da sessao a dividia por um denominador
        // que incluia os ticks vazios.
        const semApuracao = (p as { apuracao_disponivel?: boolean }).apuracao_disponivel === false;
        const nextHistory =
          state.phase === "LIVE" && !semApuracao && typeof p.ipm_score === "number"
            ? [...state.ipmHistory, p.ipm_score].slice(-IPM_HISTORY_LIMIT)
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
  ) || latestAudio.emotional_tone || "";
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
    // A janela clínica desliza a cada micro-janela (1 min), consolidando as
    // últimas N — não a cada janela cheia, que congelava o painel por 5-7 min.
    nextUpdateSecond: endSecond + CLINICAL_MICRO_WINDOW_SECONDS,
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
  // IDM como bússola: média COM SINAL dos desvios (positivo = hiperativação,
  // negativo = hipoativação). O valor absoluto usado antes descartava a
  // direção do desequilíbrio. Consumidores que só querem magnitude aplicam
  // Math.abs no ponto de uso.
  const idmAvg =
    zones.length > 0
      ? zones.reduce(
          (total, zone) => total + Number(zone.deviation_score || 0),
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
    // Sem `|| "neutro"`: o padrao transformava campo NAO APURADO numa
    // afirmacao de que o tom era neutro — exatamente a fabricacao que a
    // remocao do sorteio veio acabar. Vazio sobe vazio, e a tela mostra "--".
    emotionalTone:
      String(audioMetas.find((meta) => meta.emotional_tone)?.emotional_tone || ""),
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
  spokenLanguage = normalizeSessionLocale(undefined),
  analysisLanguage = spokenLanguage,
  reportLocale = analysisLanguage,
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
    spokenLanguage,
    analysisLanguage,
    reportLocale,
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
        // "sem_mudanca_tom" com os dois campos vazios seria AFIRMAR que o tom
        // nao mudou — sobre algo que nao foi apurado. Duas ausencias iguais
        // nao sao uma constancia observada.
        emotionalToneShift:
          !previousCut?.emotionalTone || !cut.emotionalTone
            ? "nao_apurado"
            : previousCut.emotionalTone !== cut.emotionalTone
              ? "mudanca_tom"
              : "sem_mudanca_tom",
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
  const [sessionPatient, setSessionPatient] = useState(() =>
    loadSessionPatient(sessionId || ""),
  );
  const spokenLanguage = normalizeSessionLocale(sessionPatient?.spokenLanguage);
  const analysisLanguage = normalizeSessionLocale(
    sessionPatient?.analysisLanguage,
    spokenLanguage,
  );
  const reportLocale = normalizeSessionLocale(sessionPatient?.reportLocale, analysisLanguage);
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
  // Registro das dissonâncias EVIDENTES múltiplas (>= 2 marcadores fora da
  // métrica base simultaneamente), vindas do motor de dissonância do backend.
  const [multiDissonanceLog, setMultiDissonanceLog] = useState<
    Array<{
      id: string;
      timestamp: string;
      elapsedSeconds: number;
      count: number;
      categories: string[];
      markers: EvidentMarker[];
      summary: string;
      severity?: number;
      isMulti?: boolean;
      peakZone?: number;
      peakZoneTema?: string;
      source: string;
    }>
  >([]);
  const lastMultiDissonanceSig = useRef<string>("");
  const [liveTranscription, setLiveTranscription] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [conversationSummaries, setConversationSummaries] = useState<
    ConversationSummary[]
  >([]);
  // Espelho em ref dos cortes.
  //
  // createSessionReport monta o relatório lendo sessionSamplesRef e
  // transcriptSegmentsRef — refs, porque precisa do valor DAQUELE instante, e
  // não do que o React já tinha renderizado. Os cortes eram a única peça que
  // vinha do estado, e por isso um corte fechado no mesmo tique do
  // encerramento não entrava no relatório: a atualização de estado só chega no
  // render seguinte, que nunca acontece porque a sessão acabou.
  const conversationSummariesRef = useRef<ConversationSummary[]>([]);
  const [sessionLayout, setSessionLayout] = useState<
    "detailed" | "simplified" | "indices"
  >(() =>
    // As layouts "Detalhada" e "Índices" exigem grades com largura mínima
    // fixa (1620px/1500px) pensadas para monitor de consultório; abertas
    // num celular do profissional (sessão celular-para-celular) ficariam
    // ilegíveis por padrão. "Simplificada" é a única responsiva de fato.
    typeof window !== "undefined" && window.innerWidth < 1024
      ? "simplified"
      : "detailed",
  );
  const [clinicalUpdateMode, setClinicalUpdateMode] = useState<ClinicalUpdateMode>(
    loadClinicalUpdateMode,
  );
  const [clinicalSnapshot, setClinicalSnapshot] =
    useState<ClinicalPresentationSnapshot | null>(null);
  const [semanticCutStartSecond, setSemanticCutStartSecond] = useState(0);
  const [rtcStatus, setRtcStatus] = useState("Aguardando paciente");
  // Onde o paciente esta ANTES de existir conexao. Separado de `rtcStatus` de
  // proposito: aquele descreve a negociacao WebRTC, este descreve a pessoa. Um
  // nao pode sobrescrever o outro.
  const [presencaDoPaciente, setPresencaDoPaciente] = useState("");
  // Acumula entre as voltas do polling: cada volta so traz os eventos novos.
  const aberturasRef = useRef(0);
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
  // Instante da última mensagem recebida no WS de análise — usado pelo
  // watchdog que detecta conexão "zumbi" (socket parece aberto mas parou de
  // entregar payloads; a queda de rede às vezes não dispara onclose).
  const wsLastMessageAtRef = useRef<number>(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  // Numa sessão pelo próprio celular do profissional, o bloqueio automático
  // de tela pausa a captura de câmera/microfone sem aviso nenhum na
  // interface. Mantemos a tela acordada enquanto a mídia estiver ativa.
  const wakeLockRef = useRef<ScreenWakeLock | null>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcRemoteStreamRef = useRef<MediaStream | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  const rtcMakingOfferRef = useRef(false);
  // Sobrevive a reconstrucao do peer, porque e ela que este numero conta.
  const reconstrucoesRtcRef = useRef(0);
  // Por que a analise acustica nao esta recebendo voz real, na palavra do
  // proprio navegador do paciente. Vazio quando esta tudo certo.
  const [motivoAcustico, setMotivoAcustico] = useState("");
  const rtcReconnectTimerRef = useRef<number | null>(null);
  const rtcDisconnectTimerRef = useRef<number | null>(null);
  const rtcMediaHealthTimerRef = useRef<number | null>(null);
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
  const transcriptLinesRef = useRef<string[]>([]);
  const transcriptSegmentsRef = useRef<Array<{ elapsedSeconds: number; text: string }>>([]);
  const froidExplicaConversationRef = useRef<Array<{ role: string; content: string }>>([]);
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
  const patientRemoteAudioTrackIdRef = useRef("");
  const transcriptionQueueRef = useRef<Promise<void>>(Promise.resolve());
  const transcriptionStatsRef = useRef<{
    totalWords: number;
    windows: Array<{ timestamp: number; words: number }>;
    successfulSegments: number;
    emptySegments: number;
    silentSegments: number;
    failedSegments: number;
    undersizedSegments: number;
    latenciesMs: number[];
  }>({
    totalWords: 0,
    windows: [],
    successfulSegments: 0,
    emptySegments: 0,
    silentSegments: 0,
    failedSegments: 0,
    undersizedSegments: 0,
    latenciesMs: [],
  });
  const lastDissonanceSig = useRef("");
  const attributedSpeakerRef = useRef<SpeakerRole>("DR");
  const forcedLocalSegmentSpeakerRef = useRef<SpeakerRole | null>(null);
  const remotePatientOnRef = useRef(false);
  // Último instante em que se observou fluxo RTP de áudio do paciente. O
  // detector compara bytes entre amostras de 2s, então SILÊNCIO CLÍNICO (uma
  // pausa natural do paciente) zera o delta e derrubava remotePatientOn — o
  // que descartava as métricas do tick. Silêncio não é desconexão: mantemos a
  // trilha válida por PATIENT_AUDIO_GRACE_MS após o último fluxo observado.
  const lastPatientAudioMsRef = useRef(0);
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

  // ONDE O PACIENTE ESTA, antes de existir qualquer conexao.
  //
  // O servidor ja registra os quatro passos do paciente — invite_opened,
  // invite_accepted, patient_joined — e ja os publica em /api/session-events.
  // Dashboard.tsx e NewPatient.tsx consomem isso ha meses. Esta tela, que e o
  // unico lugar onde a informacao decide alguma coisa, nao consumia.
  //
  // O efeito apareceu numa consulta real: o profissional via "Aguardando
  // paciente..." e nao tinha como distinguir quatro situacoes completamente
  // diferentes — o paciente nao abriu o link; abriu e nao tocou "Ativar camera
  // e microfone"; tocou e esta olhando o pedido de permissao do navegador; ou
  // negou a permissao. Nas quatro a tela dizia a mesma coisa, e em tres delas
  // a acao certa era falar com o paciente, nao esperar.
  //
  // Estado SEPARADO de `rtcStatus` por decisao: aquele descreve a negociacao
  // WebRTC e tem maquina propria; este descreve a pessoa. Misturar os dois
  // faria uma corrida entre quem escreve por ultimo.
  useEffect(() => {
    if (!sessionId) return;
    const token = localStorage.getItem("froid_token") || "";
    if (!token) return;
    // Para de perguntar assim que a midia do paciente chega: dai em diante
    // quem descreve a sessao e o proprio video.
    if (remotePatientOn || remotePatientVideoOn) return;
    let ativo = true;
    let cursor = 0;
    const FRASES: Record<string, string> = {
      invite_opened: "O paciente abriu o link do convite.",
      invite_accepted: "O paciente confirmou o cadastro e os consentimentos.",
      patient_joined:
        "O paciente está na sala. Falta ele liberar câmera e microfone no próprio aparelho.",
    };
    const perguntar = async () => {
      try {
        const resposta = await fetch(
          apiUrl(`/api/session-events?after=${cursor}`),
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!resposta.ok || !ativo) return;
        const dados = await resposta.json();
        const eventos: Array<Record<string, unknown>> = Array.isArray(dados?.events)
          ? dados.events
          : [];
        cursor = Math.max(
          cursor,
          Number(dados?.latest_id || 0),
          ...eventos.map((evento) => Number(evento.id || 0)),
        );
        // Só os desta sessão: o profissional pode ter outros convites abertos,
        // e presença de outro paciente nesta tela seria pior que silêncio.
        const desta = eventos.filter(
          (evento) => String(evento.session_id || "") === sessionId,
        );
        const relevantes = desta.filter((evento) => FRASES[String(evento.type)]);
        const ultimo = relevantes.pop();
        // Cada `patient_joined` e uma abertura do link. Mais de uma quase
        // sempre significa aparelho ou aba a mais — e o servidor guarda UM
        // socket por papel, entao quem entra por ultimo desconecta o anterior.
        // Sem este aviso o profissional via a chamada cair e nao tinha como
        // saber que a causa estava do outro lado, num segundo aparelho.
        const entradas = desta.filter(
          (evento) => String(evento.type) === "patient_joined",
        ).length;
        if (entradas > 0) {
          aberturasRef.current += entradas;
        }
        if (ultimo && ativo) {
          const base = FRASES[String(ultimo.type)];
          setPresencaDoPaciente(
            aberturasRef.current > 1
              ? `${base} (abriu o link ${aberturasRef.current} vezes — se estiver aberto em outro aparelho, peça para fechar lá)`
              : base,
          );
        }
      } catch {
        // Presença é informação auxiliar: falha ao buscá-la nunca pode
        // atrapalhar a sessão que está acontecendo.
      }
    };
    void perguntar();
    const relogio = window.setInterval(perguntar, 3_000);
    return () => {
      ativo = false;
      window.clearInterval(relogio);
    };
  }, [sessionId, remotePatientOn, remotePatientVideoOn]);

  useEffect(() => {
    if (!sessionId) return;
    const token = localStorage.getItem("froid_token") || "";
    if (!token) return;
    const controller = new AbortController();
    fetch(apiUrl(`/api/sessions/${encodeURIComponent(sessionId)}/configuration`), {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json();
      })
      .then((configuration) => {
        if (!configuration) return;
        const patient = {
          ...(configuration.patient || {}),
          sessionMode: configuration.session_mode,
          patientUiLocale: normalizeSessionLocale(configuration.patient_ui_locale),
          spokenLanguage: normalizeSessionLocale(configuration.spoken_language),
          analysisLanguage: normalizeSessionLocale(
            configuration.analysis_language,
            normalizeSessionLocale(configuration.spoken_language),
          ),
          reportLocale: normalizeSessionLocale(
            configuration.report_locale,
            normalizeSessionLocale(configuration.analysis_language),
          ),
        };
        rememberSessionPatient(sessionId, patient);
        setSessionPatient((current) => ({ ...(current || {}), ...patient }));
      })
      .catch((error) => {
        if (error?.name !== "AbortError") {
          console.warn("FROID session configuration:", error);
        }
      });
    return () => controller.abort();
  }, [sessionId]);

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

  // Trilha do paciente considerada válida: fluxo de áudio agora OU dentro da
  // janela de tolerância desde o último fluxo (silêncio clínico não invalida a
  // trilha). Usado pelos dois gates de métricas — payload do servidor e IPM local.
  const patientTrackUsable = useCallback(() => {
    if (remotePatientOnRef.current) return true;
    const last = lastPatientAudioMsRef.current;
    return last > 0 && Date.now() - last <= PATIENT_AUDIO_GRACE_MS;
  }, []);

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
    // O wake lock é liberado automaticamente pelo navegador quando a aba
    // perde visibilidade (troca de app no celular, por exemplo); ao voltar,
    // se a mídia ainda estiver ativa, pedimos de volta.
    const reacquireWakeLock = () => {
      if (document.visibilityState !== "visible") return;
      if (!state.cameraOn && !state.micOn) return;
      if (wakeLockRef.current) return;
      requestScreenWakeLock().then((lock) => {
        wakeLockRef.current = lock;
      });
    };
    document.addEventListener("visibilitychange", reacquireWakeLock);
    return () => document.removeEventListener("visibilitychange", reacquireWakeLock);
  }, [state.cameraOn, state.micOn]);

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
    if (rtcMediaHealthTimerRef.current) {
      window.clearInterval(rtcMediaHealthTimerRef.current);
      rtcMediaHealthTimerRef.current = null;
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
    patientRemoteAudioTrackIdRef.current = "";
    setRemotePatientOn(false);
    setRemotePatientVideoOn(false);
    setRtcStatus("Aguardando paciente");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  }, []);

  const unlockPatientAudio = useCallback(async () => {
    const audio = remoteAudioRef.current;
    if (!audio || !(audio.srcObject instanceof MediaStream)) {
      setRtcStatus("O áudio do paciente ainda não chegou.");
      return;
    }
    audio.muted = false;
    audio.volume = 1;
    try {
      await audio.play();
      setRtcStatus("Áudio do paciente liberado.");
    } catch {
      setRtcStatus("O navegador bloqueou o áudio. Clique novamente para ouvir.");
    }
  }, []);

  // Contexto vivo entregue ao FROID Explica no ato da pergunta (lê refs, para
  // não recriar a transcrição a cada render). Transcrição já vem com o locutor
  // embutido: "DR. -" é o profissional, "PC -"/"PAC -" é o paciente.
  const getFroidExplicaContext = useCallback((): Record<string, unknown> => {
    const segments = transcriptSegmentsRef.current || [];
    const transcriptLines = segments.map((segment) => segment.text);
    // Limita ao final da transcrição para não estourar o contexto do modelo.
    let transcript = transcriptLines.join("\n");
    if (transcript.length > FROID_EXPLICA_TRANSCRIPT_CHAR_LIMIT) {
      transcript = transcript.slice(-FROID_EXPLICA_TRANSCRIPT_CHAR_LIMIT);
    }
    const patientLines = transcriptLines.filter((line) =>
      /^(PC|PAC)\b/i.test(line),
    );
    const professionalLines = transcriptLines.filter((line) =>
      /^DR\b/i.test(line),
    );
    const latestPayload =
      sessionSamplesRef.current[sessionSamplesRef.current.length - 1]?.payload;
    const latestAudio =
      ((latestPayload as any)?.audio_meta as Record<string, unknown>) || {};
    const biomarkers: Record<string, number> = {};
    REPORT_AUDIO_KEYS.forEach((key) => {
      const value = latestAudio[key];
      if (typeof value === "number" && Number.isFinite(value)) {
        biomarkers[key] = Number(value.toFixed(4));
      }
    });
    return {
      patient_id: sessionPatient?.id || "",
      patient_name: sessionPatient?.name || "",
      transcript_available: transcriptLines.length > 0,
      transcript_speaker_legend:
        "DR = profissional/terapeuta; PC ou PAC = paciente.",
      session_transcript: transcript,
      patient_speech: patientLines.slice(-80).join("\n"),
      professional_speech: professionalLines.slice(-80).join("\n"),
      transcript_line_count: transcriptLines.length,
      session_biomarkers: biomarkers,
      session_elapsed_seconds: Math.max(0, elapsedSecondsRef.current),
    };
  }, [sessionPatient?.id, sessionPatient?.name]);

  const handleFroidExplicaConversation = useCallback(
    (conversation: Array<{ role: string; content: string }>) => {
      froidExplicaConversationRef.current = conversation;
    },
    [],
  );

  const startProfessionalRtcCall = useCallback(
    async (localSource: MediaStream) => {
      if (!sessionId || typeof RTCPeerConnection === "undefined") {
        setRtcStatus("WebRTC indisponível neste navegador.");
        return;
      }

      cleanupRtcCall();
      rtcClosingRef.current = false;
      const localConferenceStream = createConferenceStream(localSource);
      if (!localConferenceStream.getTracks().length && !isPresentialMobileSession) {
        setRtcStatus("Áudio e vídeo locais indisponíveis para chamada.");
        return;
      }

      const token = localStorage.getItem("froid_token") || "";
      const peer = new RTCPeerConnection(
        await loadRtcConfiguration({ sessionId, professionalToken: token }),
      );
      observarConexao(peer, "profissional");
      // Sem freio, a recuperacao de erro vira o proprio erro: ver
      // `criarFreioDeRenegociacao` em lib/webrtc.ts.
      const freioRenegociacao = criarFreioDeRenegociacao();
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
      // Fora do `else` de proposito: em sessao presencial-movel o profissional
      // so recebe, e saber que ele NAO envia e informacao — nao silencio.
      registrarEnvio(peer);

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

      const resetPatientAudioPipeline = (markDisconnected: boolean) => {
        if (patientSttRestartTimerRef.current) {
          window.clearTimeout(patientSttRestartTimerRef.current);
          patientSttRestartTimerRef.current = null;
        }
        if (patientSttSegmentTimerRef.current) {
          window.clearTimeout(patientSttSegmentTimerRef.current);
          patientSttSegmentTimerRef.current = null;
        }
        patientIntentionalRecorderStopRef.current = true;
        if (
          patientRecorderRef.current
          && patientRecorderRef.current.state !== "inactive"
        ) {
          patientRecorderRef.current.stop();
        }
        patientRecorderRef.current = null;
        patientBioacousticStreamRef.current?.getTracks().forEach((track) => track.stop());
        patientTranscriptStreamRef.current?.getTracks().forEach((track) => track.stop());
        patientBioacousticStreamRef.current = null;
        patientTranscriptStreamRef.current = null;
        patientRemoteAudioTrackIdRef.current = "";
        if (markDisconnected) setPatientAudioVersion(0);
      };

      let offerWatchdogTimer: number | null = null;
      const clearOfferWatchdog = () => {
        if (offerWatchdogTimer) window.clearTimeout(offerWatchdogTimer);
        offerWatchdogTimer = null;
      };
      // `forcar` desfaz uma oferta pendente antes de refazer, e existe por um
      // impasse real observado em consulta (26/08/2026):
      //
      //   1. o paciente cai; o peer do profissional vai para `failed`
      //   2. o tratamento de `failed` chama makeOffer, que fica em
      //      `have-local-offer` — e essa oferta vai para uma sala VAZIA
      //   3. o paciente volta; o servidor manda `peer-joined`
      //   4. o profissional chama makeOffer... que desiste em silencio,
      //      porque `signalingState !== "stable"`
      //
      // Os dois ficavam esperando: "Reconectando midia do paciente..." de um
      // lado, "Aguardando chamada do profissional..." do outro. A guarda de
      // estado esta certa para evitar colisao de ofertas; o que faltava era
      // distinguir a oferta que ainda pode ser respondida daquela que foi
      // entregue a ninguem. Quando o par ACABA de entrar, a pendente e sempre
      // do segundo tipo.
      // Leitura fresca do estado, por uma limitacao do compilador: lido
      // direto, `peer.signalingState` ja foi estreitado pela condicao anterior
      // e o TypeScript conclui que a segunda comparacao e impossivel. Ela nao
      // e: o estado muda entre as duas leituras. (O motivo original citava o
      // rollback; ele saiu do codigo em 02/09/2026 por embaralhar as m-lines,
      // mas a limitacao de tipo continua.)
      const estadoDaSinalizacao = (): RTCSignalingState => peer.signalingState;
      // Cada oferta leva um numero, e a resposta traz o numero de volta. A
      // resposta de uma oferta ja superada e descartada em vez de aplicada —
      // aplicar era o que produzia o desalinhamento de m-lines.
      let ofertaSeq = 0;
      const reenviarOfertaPendente = () => {
        const pendente = peer.localDescription;
        if (!pendente) return false;
        sendSignal({ type: "offer", offer: pendente, seq: ofertaSeq });
        return true;
      };
      const makeOffer = async (forcar = false) => {
        if (rtcMakingOfferRef.current) return;
        if (estadoDaSinalizacao() !== "stable") {
          if (!forcar || estadoDaSinalizacao() !== "have-local-offer") return;
          // Aqui havia um rollback, e era ELE que quebrava a chamada.
          //
          // 02/09/2026, no log: rollback e oferta nova no mesmo segundo. A
          // resposta do paciente — feita para a oferta anterior — chegou
          // depois, e o navegador recusou com "the order of m-lines in answer
          // doesn't match order in offer". O peer do paciente, ja negociado
          // com a ordem antiga, passou a recusar TODA oferta seguinte.
          //
          // O impasse que o rollback tentava resolver (uma oferta entregue a
          // sala vazia) se resolve sem ele: a sala agora tem alguem, entao
          // basta reenviar a MESMA oferta. Ela continua valida, e reenviar nao
          // reordena coisa nenhuma.
          clearOfferWatchdog();
          reenviarOfertaPendente();
          return;
        }
        rtcMakingOfferRef.current = true;
        try {
          const offer = await peer.createOffer();
          await peer.setLocalDescription(offer);
          ofertaSeq += 1;
          sendSignal({ type: "offer", offer: peer.localDescription, seq: ofertaSeq });
          setRtcStatus("Chamando paciente...");
          // Sem resposta dentro do prazo a conexão ficaria presa em
          // have-local-offer. Reenviar a MESMA oferta e o caminho de volta;
          // refazer com rollback era o que embaralhava as m-lines.
          clearOfferWatchdog();
          offerWatchdogTimer = window.setTimeout(() => {
            offerWatchdogTimer = null;
            if (
              peer.signalingState !== "have-local-offer"
              || peer.connectionState === "closed"
            ) return;
            reenviarOfertaPendente();
          }, 8_000);
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
        if (!media.audio) setRemotePatientOn(false);
        if (!media.video) setRemotePatientVideoOn(false);
        setRtcStatus(
          media.audio || media.video
            ? "Trilhas negociadas; validando fluxo real do paciente..."
            : "Conectado, aguardando trilhas reais do paciente.",
        );
      };

      const bindPatientAudioTrack = () => {
        const patientAudioTrack = remoteStream
          .getAudioTracks()
          .find(
            (track) =>
              track.readyState === "live"
              && track.enabled
              && !track.muted,
          );
        if (
          patientAudioTrack
          && patientRemoteAudioTrackIdRef.current !== patientAudioTrack.id
        ) {
          resetPatientAudioPipeline(false);
          patientBioacousticStreamRef.current = new MediaStream([
            patientAudioTrack.clone(),
          ]);
          patientTranscriptStreamRef.current = new MediaStream([
            patientAudioTrack.clone(),
          ]);
          patientRemoteAudioTrackIdRef.current = patientAudioTrack.id;
          setPatientAudioVersion((value) => value + 1);
          applyAttributedSpeaker("PC", "Trilha remota do paciente recebida por WebRTC.");
        }
      };

      const mutedTrackRecoveryTimers = new Map<string, number>();
      const clearMutedTrackRecovery = (track: MediaStreamTrack) => {
        const timer = mutedTrackRecoveryTimers.get(track.id);
        if (timer) window.clearTimeout(timer);
        mutedTrackRecoveryTimers.delete(track.id);
      };
      const scheduleMutedTrackRecovery = (track: MediaStreamTrack) => {
        clearMutedTrackRecovery(track);
        refreshRemoteTracks();
        const timer = window.setTimeout(() => {
          mutedTrackRecoveryTimers.delete(track.id);
          if (
            track.readyState !== "live"
            || !track.muted
            || peer.connectionState === "closed"
          ) return;
          if (track.kind === "audio") {
            resetPatientAudioPipeline(true);
            setRemotePatientOn(false);
          } else {
            setRemotePatientVideoOn(false);
          }
          setRtcStatus(
            `${track.kind === "video" ? "Vídeo" : "Áudio"} do paciente sem dados; reconectando...`,
          );
          if (peer.signalingState === "stable") {
            peer.restartIce();
            void makeOffer();
          }
        }, 2_500);
        mutedTrackRecoveryTimers.set(track.id, timer);
      };

      peer.ontrack = (event) => {
        const incomingTracks = event.streams[0]?.getTracks() || [event.track];
        incomingTracks.forEach((track) => {
          adoptRemoteTrack(remoteStream, track);
          track.onended = () => {
            clearMutedTrackRecovery(track);
            remoteStream.removeTrack(track);
            refreshRemoteTracks();
            // Só derruba o pipeline de áudio se a trilha encerrada for a que
            // está vinculada; uma trilha obsoleta não pode matar a atual.
            if (
              track.kind === "audio"
              && patientRemoteAudioTrackIdRef.current === track.id
            ) {
              resetPatientAudioPipeline(true);
            }
          };
          track.onmute = () => scheduleMutedTrackRecovery(track);
          track.onunmute = () => {
            clearMutedTrackRecovery(track);
            refreshRemoteTracks();
            if (track.kind === "audio") bindPatientAudioTrack();
          };
          if (track.muted) scheduleMutedTrackRecovery(track);
        });
        refreshRemoteTracks();
        bindPatientAudioTrack();
      };

      let previousFlowStats: RtcMediaFlowStats | null = null;
      let stalledFlowChecks = 0;
      const monitorInboundPatientMedia = async () => {
        if (peer.connectionState === "closed") return;
        const current = await readRtcMediaFlowStats(peer).catch(() => null);
        if (!current) return;
        const inbound = evaluateInboundFlow(previousFlowStats, current);
        previousFlowStats = current;
        if (!inbound) return;
        const { audioFlowing, videoFlowing } = inbound;
        if (audioFlowing) lastPatientAudioMsRef.current = Date.now();
        setRemotePatientOn(audioFlowing);
        setRemotePatientVideoOn(videoFlowing);
        const route = current.candidateType
          ? ` · rota ${current.candidateType}`
          : "";
        if (audioFlowing && videoFlowing) {
          stalledFlowChecks = 0;
          setRtcStatus(`Paciente conectado: áudio e vídeo recebidos${route}.`);
          return;
        }
        if (audioFlowing || videoFlowing) {
          stalledFlowChecks = 0;
          setRtcStatus(
            audioFlowing
              ? `Áudio recebido; vídeo sem quadros${route}.`
              : `Vídeo recebido; áudio sem pacotes${route}.`,
          );
          return;
        }
        if (peer.connectionState !== "connected") return;
        stalledFlowChecks += 1;
        // Registra os contadores RTP reais de entrada para separar "sem mídia"
        // de uma janela sem delta (paciente com câmera/microfone parados).
        console.debug(
          `FROID mídia sem entrada: audioBytesReceived=${current.audioBytesReceived} videoFramesDecoded=${current.videoFramesDecoded}`,
        );
        setRtcStatus(
          `WebRTC conectado sem transportar mídia (${stalledFlowChecks}/3)${route}.`,
        );
        if (stalledFlowChecks < 3 || peer.signalingState !== "stable") return;
        stalledFlowChecks = 0;
        const relayActivated = activateRtcRelayFallback(peer);
        if (relayActivated) {
          setRtcStatus("Rota direta sem mídia; alternando para o relay TURN protegido...");
        }
        peer.restartIce();
        await makeOffer();
      };
      if (rtcMediaHealthTimerRef.current) {
        window.clearInterval(rtcMediaHealthTimerRef.current);
      }
      rtcMediaHealthTimerRef.current = window.setInterval(
        () => void monitorInboundPatientMedia(),
        2_000,
      );

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
          freioRenegociacao.liberar();
          reconstrucoesRtcRef.current = 0;
          registrarNegociacao(peer);
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
          await makeOffer(true);
        } else if (data.type === "peer-joined") {
          // O par ACABOU de entrar: qualquer oferta pendente foi para a sala
          // vazia e nunca sera respondida. Forcar aqui e o que desfaz o
          // impasse — sem isso, quem reentra fica esperando uma chamada que o
          // outro lado ja desistiu de refazer.
          await makeOffer(true);
        } else if (data.type === "answer" && data.answer) {
          if (peer.signalingState !== "have-local-offer") return;
          if (typeof data.seq === "number" && data.seq !== ofertaSeq) {
            registrarRtc(
              `resposta atrasada descartada (era da oferta ${data.seq}, atual ${ofertaSeq})`,
            );
            return;
          }
          clearOfferWatchdog();
          await peer.setRemoteDescription(data.answer);
          await flushIceQueue();
        } else if (data.type === "renegotiate-request") {
          // O pedido do paciente chegava aqui sem limite nenhum. Quando a
          // oferta seguinte falhava do lado dele, ele pedia de novo, e o par
          // girava na velocidade da rede — enquanto o ICE, que precisa de
          // segundos, era reiniciado antes de tentar uma unica vez.
          if (!freioRenegociacao.permite()) {
            if (freioRenegociacao.esgotado()) {
              setRtcStatus(
                "O paciente pediu para refazer a chamada varias vezes sem sucesso. "
                + "Abra o diagnostico da chamada para ver o motivo.",
              );
              registrarNegociacao(peer);
              sendSignal({ type: "pedir-diagnostico" });
            }
            return;
          }
          peer.restartIce();
          await makeOffer(true);
        } else if (data.type === "acustica") {
          const status = String(data.status || "");
          registrarRtc(`analise acustica no paciente: ${status}`);
          setMotivoAcustico(status === "enviando" ? "" : status);
        } else if (data.type === "diagnostico" && data.texto) {
          // O relatorio do outro lado, que ate agora nunca atravessou.
          incorporarRelatorioRemoto(String(data.texto));
        } else if (data.type === "ice" && data.candidate) {
          if (peer.remoteDescription) {
            await peer.addIceCandidate(data.candidate).catch(() => undefined);
          } else {
            rtcIceQueueRef.current.push(data.candidate);
          }
        } else if (data.type === "error") {
          // O servidor emite isto e ninguem lia. Ate agora so acontece com
          // papel invalido na URL, que e defeito de programacao — mas
          // mensagem de erro que se perde e como o `peer-waiting` comecou.
          setRtcStatus(
            `A sala recusou a conexão: ${String(data.detail || "motivo não informado")}.`,
          );
        } else if (data.type === "peer-waiting") {
          // O servidor responde isto quando a oferta chega e o socket do
          // paciente NAO esta na sala. Ele sempre respondeu; nenhum cliente
          // nunca leu.
          //
          // O efeito no consultorio: a tela ficava em "Chamando paciente..."
          // indefinidamente, com o watchdog reofertando a cada 8 segundos,
          // enquanto o servidor repetia a cada volta que nao havia ninguem
          // para receber. O profissional esperava uma conexao que nao tinha
          // como acontecer, sem nada na tela que o dissesse — aconteceu numa
          // consulta real em 26/08/2026.
          //
          // Parar o watchdog aqui e parte da correcao: reofertar para uma sala
          // vazia nao aproxima a conexao, so mantem a mentira na tela. A
          // proxima oferta sai quando chegar `peer-joined`, que e o evento que
          // significa que existe alguem do outro lado.
          clearOfferWatchdog();
          setRemotePatientOn(false);
          setRemotePatientVideoOn(false);
          setRtcStatus(
            "O paciente não está na sala. Peça que ele abra novamente o link do convite — a chamada conecta sozinha assim que ele entrar.",
          );
        } else if (data.type === "peer-left") {
          remoteStream.getTracks().forEach((track) => {
            track.stop();
            remoteStream.removeTrack(track);
          });
          resetPatientAudioPipeline(true);
          setRemotePatientOn(false);
          setRemotePatientVideoOn(false);
          setRtcStatus("Paciente saiu da chamada.");
          if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
          if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
        }
      };

      let signalQueue: Promise<void> = Promise.resolve();
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
        socket.onmessage = (event) => {
          signalQueue = signalQueue
            .then(() => handleSignal(event))
            .catch((erro) => {
              // O erro era descartado aqui, e com ele a unica informacao que
              // dizia por que a chamada nao subia.
              registrarFalha("tratar sinal recebido", erro);
              if (eDesalinhamentoDeMlines(erro)) {
                if (reconstrucoesRtcRef.current >= 2) {
                  registrarRtc("desalinhamento persistente — parei de reconstruir");
                  setRtcStatus(
                    "Não foi possível estabelecer a chamada. Recarregue a página.",
                  );
                  return;
                }
                reconstrucoesRtcRef.current += 1;
                registrarRtc("reconstruindo a conexao do zero");
                setRtcStatus("Refazendo a conexão da chamada...");
                void startProfessionalRtcCall(localSource);
                return;
              }
              if (!freioRenegociacao.permite()) {
                if (freioRenegociacao.esgotado()) {
                  sendSignal({ type: "pedir-diagnostico" });
                }
                return;
              }
              setRtcStatus("Sincronizando novamente áudio e vídeo do paciente...");
              if (peer.signalingState === "stable") void makeOffer();
            });
        };
        socket.onerror = () => socket.close();
        socket.onclose = (event) => {
          if (rtcClosingRef.current || peer.connectionState === "closed") return;
          if (!shouldReconnectRtcSignaling(event.code, reconnectAttempt, peer.connectionState)) {
            // Era uma frase so para quatro causas diferentes, e nenhuma delas
            // se resolvia com "atualize a sessao". Quem le esta com um
            // paciente esperando: a frase precisa carregar a acao.
            setRtcStatus(motivoDaRecusaDeSinalizacao(event.code));
            return;
          }
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
            patientTrackUsable() ||
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

    const words = countSpokenUnits(text, spokenLanguage);
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
      emotional_tone: (prev?.emotional_tone as string) || "",
      transcription_status: "ok",
      transcription_error: "",
    }));
  }, [spokenLanguage]);

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
    intentionalRecorderStopRef.current = true;
    segmentingRecorderStopRef.current = false;
    patientIntentionalRecorderStopRef.current = true;
    patientSegmentingRecorderStopRef.current = false;
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
    void wakeLockRef.current?.release().catch(() => undefined);
    wakeLockRef.current = null;
  }, [cleanupRtcCall, refreshMediaStatus, stopRawBioacousticPipeline, stopVoiceIdentification]);

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
        // O ref primeiro, e de forma sincrona: quem encerra a sessao precisa
        // enxergar este corte imediatamente, sem esperar o proximo render.
        conversationSummariesRef.current = [
          ...conversationSummariesRef.current.filter((item) => item.id !== entry.id),
          entry,
        ].sort((a, b) => a.startMinute - b.startMinute);
        setConversationSummaries(conversationSummariesRef.current);
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
            spoken_language: spokenLanguage,
            analysis_language: analysisLanguage,
            report_locale: reportLocale,
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
          summary: limitWords(String(data?.summary || "").trim(), 80),
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
          summary: limitWords(transcript, 80),
          trigger,
        });
      }
    },
    [analysisLanguage, reportLocale, sessionId, spokenLanguage],
  );

  const closeSemanticCut = useCallback(
    async (trigger: "automatico_10min" | "manual" | "final") => {
      if (semanticCutClosingRef.current) {
        // Um corte automático pode estar em voo justamente quando o
        // profissional clica em encerrar. Desistir aqui devolveria o defeito
        // que este corte final existe para fechar, então o "final" ESPERA a
        // vez dele em vez de sair calado.
        if (trigger !== "final") return;
        const limite = Date.now() + 15000;
        while (semanticCutClosingRef.current && Date.now() < limite) {
          await new Promise((resolve) => setTimeout(resolve, 120));
        }
        // Se mesmo assim não liberou, segue: o corte em voo vai gravar o
        // trecho dele, e travar o encerramento seria pior do que um corte a
        // menos.
        if (semanticCutClosingRef.current) return;
      }
      const endSecond = Math.max(
        elapsedSecondsRef.current || state.elapsedSeconds,
        semanticCutStartSecondRef.current,
      );
      const startSecond = semanticCutStartSecondRef.current;
      const duration = endSecond - startSecond;

      if (trigger === "manual" && duration < 10) {
        return;
      }
      // Sem trecho residual não há o que fechar: um corte de duração zero
      // entraria no relatório como "sem fala transcrita" e sujaria a linha do
      // tempo. Só vale quando sobrou tempo desde o último corte.
      if (trigger === "final" && duration < 1) {
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
        transcriptionStatsRef.current.undersizedSegments += 1;
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
        transcriptionStatsRef.current.silentSegments += 1;
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
            spoken_language: spokenLanguage,
            previous_context: previousContext,
          }),
        });

        const data = await response.json();
        const latencyMs = Number(data?.latency_ms);
        if (Number.isFinite(latencyMs) && latencyMs >= 0) {
          transcriptionStatsRef.current.latenciesMs = [
            ...transcriptionStatsRef.current.latenciesMs,
            latencyMs,
          ].slice(-500);
        }
        const text = String(data?.text || "").trim();
        if (!response.ok) {
          transcriptionStatsRef.current.failedSegments += 1;
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
          transcriptionStatsRef.current.emptySegments += 1;
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
        transcriptionStatsRef.current.successfulSegments += 1;

        setLiveTranscription((prev) => ({
          ...(prev || {}),
          emotional_tone: (prev?.emotional_tone as string) || "",
          provider: data?.provider || "openai-gpt-4o-transcribe",
          transcription_status: data?.status || "ok",
          transcription_error: "",
          last_audio_bytes: audioBlob.size,
          last_transcription_latency_ms: Number.isFinite(latencyMs) ? latencyMs : null,
        }));
      } catch (err) {
        transcriptionStatsRef.current.failedSegments += 1;
        console.error("FROID speech-to-text:", err);
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "error",
          transcription_error:
            err instanceof Error ? err.message : "Falha ao enviar áudio.",
        }));
      }
    },
    [appendTranscriptText, sessionId, spokenLanguage],
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

    return () => {
      if (patientSttRestartTimerRef.current) {
        window.clearTimeout(patientSttRestartTimerRef.current);
        patientSttRestartTimerRef.current = null;
      }
      if (patientSttSegmentTimerRef.current) {
        window.clearTimeout(patientSttSegmentTimerRef.current);
        patientSttSegmentTimerRef.current = null;
      }
      patientIntentionalRecorderStopRef.current = true;
      if (
        patientRecorderRef.current
        && patientRecorderRef.current.state !== "inactive"
      ) {
        patientRecorderRef.current.stop();
      }
      patientRecorderRef.current = null;
      if (bioacousticStreamRef.current === patientBioacousticStream) {
        stopRawBioacousticPipeline();
      }
      patientBioacousticStream.getTracks().forEach((track) => track.stop());
      patientTranscriptStream.getTracks().forEach((track) => track.stop());
    };
  }, [
    patientAudioVersion,
    startRawBioacousticPipeline,
    startSpeechToText,
    stopRawBioacousticPipeline,
    stopVoiceIdentification,
  ]);

  useEffect(() => {
    if (remotePatientOn) return;

    if (!isPresentialSession) {
      directLocalMetricsActiveRef.current = false;
      stopRawBioacousticPipeline();
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        bioacoustic_status: "waiting_patient",
        bioacoustic_pipeline: "remote-patient-required",
        bioacoustic_track: "patient-webrtc",
        bioacoustic_warning: isPresentialMobileSession
          ? "Aguardando exclusivamente o áudio do celular do paciente. O microfone do profissional não será usado como PC."
          : "Aguardando exclusivamente o áudio remoto do paciente. O microfone do profissional não será usado como PC.",
        transcription_sources: "captura-semantica-por-cortes",
      }));
      return;
    }

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
    isPresentialMobileSession,
    isPresentialSession,
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
    if (cameraOn || micOn) {
      requestScreenWakeLock().then((lock) => {
        wakeLockRef.current = lock;
      });
    }
  }, [
    cleanupRtcCall,
    isPresentialSession,
    sessionId,
    refreshMediaStatus,
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
          if (wsRef.current === socket) {
            dispatch({ type: "WS_OPEN" });
            wsLastMessageAtRef.current = Date.now();
          }
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
          wsLastMessageAtRef.current = Date.now();
          try {
            const data: FroidPayload = JSON.parse(event.data);
            const elapsedSeconds = elapsedSecondsRef.current;
            const shouldUseForMetrics =
              patientTrackUsable() ||
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

    // Watchdog: o tick do servidor é ~1/s. Se o socket "parece" aberto mas
    // nenhuma mensagem chega há muito tempo (ex.: queda de rede que não
    // dispara onclose, deixando uma conexão zumbi), força o fechamento para
    // acionar a reconexão — em vez do painel ficar congelado em silêncio.
    const WATCHDOG_TIMEOUT_MS = 8000;
    const watchdog = window.setInterval(() => {
      if (cancelled || !ws) return;
      if (ws.readyState !== WebSocket.OPEN) return;
      const silentFor = Date.now() - wsLastMessageAtRef.current;
      if (silentFor > WATCHDOG_TIMEOUT_MS) {
        console.warn(
          `FROID: WS de análise sem dados há ${Math.round(silentFor / 1000)}s — forçando reconexão.`,
        );
        try {
          ws.close();
        } catch {}
      }
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(watchdog);
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (wsRef.current === ws) wsRef.current = null;
      try {
        ws?.close();
      } catch {}
    };
  }, [sessionId]);

  useEffect(() => {
    // Agrega a cada 3s sobre os frames acumulados desde a última agregação.
    // Antes rodava a cada 10s enquanto o buffer guardava só 6 frames (6s), o
    // que DESCARTAVA os frames mais antigos de cada janela e adicionava até
    // 10s de atraso à apresentação. Com 3s, nenhum frame é perdido (buffer de
    // 6 comporta a janela) e a latência do painel cai para ~1/3.
    const id = setInterval(() => {
      if (frameBuffer.current.length === 0) return;
      const agg = aggregatePayloads([...frameBuffer.current]);
      dispatch({ type: "AGGREGATE", agg });
      frameBuffer.current = [];
    }, 3000);
    return () => clearInterval(id);
  }, []);

  const agg = state.aggregated;
  const raw = state.payload;
  const clinicalPresentationActive =
    clinicalUpdateMode !== "realtime" && clinicalSnapshot;
  const presentationAgg = clinicalPresentationActive ? clinicalSnapshot.agg : agg;
  // SEM APURACAO, OS GRAFICOS DERIVADOS NAO RECEBEM NADA.
  //
  // O motor passou a declarar a ausencia, e nenhuma tela consumia a declaracao:
  // `apuracao_disponivel` existia so no tipo. O resultado seria pior que o
  // estado anterior — cada consumidor tem o proprio valor de queda, e todos
  // eles AFIRMAM. O RiskChart trata qualquer coerencia diferente de NEUTRO e
  // COERENTE como alerta, entao "SEM_APURACAO" viraria uma barra cheia de
  // "tensao laringea sustentada"; o SubharmonicChart cairia num proxy proprio
  // e escreveria "Sistema Nervoso Autonomo estavel"; as bandas espectrais
  // imprimiriam 0.0000; o Mapa Zonal desenharia doze zonas em equilibrio.
  //
  // Fome e melhor que mentira: sem medida eles recebem vazio e o aviso ocupa a
  // tela.
  const semApuracaoAgora =
    (raw as { apuracao_disponivel?: boolean } | undefined)?.apuracao_disponivel === false;
  const displayZones = semApuracaoAgora
    ? []
    : presentationAgg?.zones || raw?.perception_zones || [];
  const displayIpm = semApuracaoAgora
    ? null
    : presentationAgg?.ipm ?? raw?.ipm_score ?? state.localIpm ?? 0;
  const displayDrValue = presentationAgg?.drValue ?? (raw as any)?.dr_value ?? null;
  // "NEUTRO" seria uma AFIRMACAO de coerencia neutra sobre nada medido. Vazio
  // e o unico valor honesto, e os consumidores ja sabem tratar ausencia.
  const displayCoherence = semApuracaoAgora
    ? ""
    : presentationAgg?.coherence || raw?.coherence_status || "NEUTRO";
  const displayAlerts = presentationAgg?.alerts || raw?.realtime_alerts || [];
  const baseDisplayAudio = semApuracaoAgora ? {} : presentationAgg?.audioMeta ||
    (raw as any)?.audio_meta || {
      words_per_window: 0,
      total_words_session: 0,
      // Vazio, nao "neutro": o estado inicial nao observou nada ainda, e
      // dizer "neutro" seria uma leitura que ninguem fez.
      emotional_tone: "",
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
  // Detalhe diagnóstico (bandas, sub-harmônicos, biomarcadores e timeline do
  // IPM) é sempre AO VIVO: a estabilização clínica se aplica ao painel de
  // risco/zonas, não a estes gráficos, que devem acompanhar o sinal real.
  const liveAudioMeta =
    (agg?.audioMeta as Record<string, unknown> | undefined) ||
    ((raw as any)?.audio_meta as Record<string, unknown> | undefined) ||
    displayAudio;
  const liveZones = agg?.zones || raw?.perception_zones || displayZones;
  // Sem apuracao, `liveIpm` tambem e nulo: cair no IPM local aqui reintroduziria
  // um numero na tela exatamente onde a medida falta.
  const liveIpm = semApuracaoAgora
    ? null
    : agg?.ipm ?? raw?.ipm_score ?? state.localIpm ?? displayIpm;
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
  // Leitura de TODOS os índices com métrica base definida (rompida ou não) —
  // alimenta o layout "Sessão Detalhada · Índices" (Coluna 1).
  const allMarkerReadings: EvidentMarker[] = Array.isArray(
    (raw as any)?.dissonance_event?.all_markers,
  )
    ? (raw as any).dissonance_event.all_markers
    : [];
  // A origem e autoridade do MOTOR, nao do navegador: e ela que diz o que de
  // fato entrou no calculo. O relato do paciente so explica o porque.
  const origemDaVoz = String(
    (raw as any)?.dissonance_event?.voice_features_source || "",
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

  // As metricas da tabela cruzadas com os limites do servidor. Deriva da
  // MESMA lista do layout Simplificado de proposito: dois catalogos
  // divergiriam na primeira metrica nova.
  const metricasComLimite = withBounds(simplifiedMetricEntries, allMarkerReadings);
  const metricasForaDaFaixa = countOutOfBounds(metricasComLimite);


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
      // Do ref, e não do estado: o corte final é fechado no mesmo tique do
      // encerramento e precisa estar aqui.
      conversationSummariesRef.current,
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
      spokenLanguage,
      analysisLanguage,
      reportLocale,
    );
    const summarySourceTranscript = transcriptSegmentsRef.current
      .map((segment) => segment.text)
      .join("\n");
    const transcriptionStats = transcriptionStatsRef.current;
    const sortedLatencies = [...transcriptionStats.latenciesMs].sort((a, b) => a - b);
    const percentile = (ratio: number) => {
      if (!sortedLatencies.length) return null;
      const index = Math.max(0, Math.ceil(sortedLatencies.length * ratio) - 1);
      return Math.round(sortedLatencies[index]);
    };

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
      conversationSummaries: conversationSummariesRef.current,
      froidExplicaConversation: froidExplicaConversationRef.current,
      sessionSummary: buildSessionSummary(
        conversationSummariesRef.current,
        summarySourceTranscript,
      ),
      dissonances: dissonanceLog,
      evidentDissonances: multiDissonanceLog,
      transcript: summarySourceTranscript,
      // A base probatoria do documento, contada amostra a amostra. O motor
      // declara a origem em cada leitura; aqui ela para de se perder.
      procedenciaDosDados: {
        amostras: samples.length,
        amostrasComVozReal: samples.filter(
          (amostra) =>
            (amostra.payload as any)?.dissonance_event?.voice_features_source
            === "real_pcm",
        ).length,
        amostrasComFaceReal: samples.filter(
          (amostra) =>
            (amostra.payload as any)?.dissonance_event?.facs_source === "real_facs",
        ).length,
      },
      transcriptionQuality: {
        successfulSegments: transcriptionStats.successfulSegments,
        emptySegments: transcriptionStats.emptySegments,
        silentSegments: transcriptionStats.silentSegments,
        failedSegments: transcriptionStats.failedSegments,
        undersizedSegments: transcriptionStats.undersizedSegments,
        latencyP50Ms: percentile(0.5),
        latencyP95Ms: percentile(0.95),
      },
      spokenLanguage,
      analysisLanguage,
      reportLocale,
      transcriptRetention: "enabled",
      anonymizedContext,
    };
  }, [
    conversationSummaries,
    dissonanceLog,
    multiDissonanceLog,
    raw,
    analysisLanguage,
    reportLocale,
    sessionId,
    sessionPatient?.sessionMode,
    spokenLanguage,
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
    // Sinal explícito e deliberado de fim de sessão ao paciente (distinto do
    // "peer-left" passivo, que também dispara em blips transitórios de rede) —
    // habilita o encaminhamento do paciente à área restrita dele.
    if (rtcSignalRef.current?.readyState === WebSocket.OPEN) {
      try {
        rtcSignalRef.current.send(JSON.stringify({ type: "session-ended" }));
      } catch {}
    }

    // Corte final, obrigatório, antes de montar o relatório.
    //
    // O corte automático fecha a cada dez minutos. O trecho falado DEPOIS do
    // último corte automático nunca era fechado: o gatilho "final" existia no
    // tipo e no relatório, e nada o chamava. Numa sessão de 50 minutos isso
    // descartava os últimos dez; numa de 8 minutos, a sessão inteira. Conteúdo
    // clínico perdido em silêncio, sem erro na tela.
    //
    // O try/catch não é decoração. Se a sumarização falhar — rede, provedor
    // fora do ar —, a sessão TEM de fechar assim mesmo: o relatório carrega a
    // transcrição completa em `transcript`, e perder o corte é ruim, mas perder
    // o atendimento inteiro por causa dele seria pior. É a mesma regra que já
    // vale para crédito: sessão realizada nunca é recusada nem descartada.
    try {
      await closeSemanticCut("final");
    } catch (error) {
      console.error("Corte final falhou; a sessão será arquivada assim mesmo.", error);
    }

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
    navigate(`/session/${report.sessionId}/report`, { replace: true });
  }, [archiveSessionReport, closeSemanticCut, createSessionReport, navigate]);

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
          // O TITULO precisa ser gravado separado do texto.
          //
          // `report-pdf.ts` chama patientViewFor(d.title || d.report) para
          // traduzir o sinal antes de mostrar ao paciente. Mas `title` nunca
          // foi persistido: o tipo so tinha id/timestamp/elapsedSeconds/zone/
          // report. A busca e por chave EXATA, entao ela recebia o paragrafo
          // inteiro, nunca casava, e o `.filter(visao !== null)` apagava tudo.
          // Resultado: a secao de sinais do PDF do paciente sempre saiu VAZIA,
          // enquanto a tela do portal — que nao usa a salvaguarda — mostrava o
          // texto do profissional inteiro.
          title: classifyDissonance(z, displayAudio).title,
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
          title: entry.title,
          report: entry.report,
        };
      })
      .filter((entry) => Number.isFinite(entry.zone));

    setDissonanceLog((prev) => [...prev, ...nextEntries].slice(-18));
  }, [confirmedDissonanceZones, displayAudio, state.elapsedSeconds]);

  // Captura, AO VIVO, TODA dissonância evidente emitida pelo motor do backend
  // (>= 1 marcador ultrapassando a métrica base). Quando >= 2 marcadores em
  // >= 2 categorias ocorrem juntos, o evento também vem marcado como
  // is_multi_dissonance — destacado na listagem, não é mais o critério de entrada.
  useEffect(() => {
    const event = (raw as any)?.dissonance_event as DissonanceEvent | undefined;
    // Confirmação temporal: registra só a dissonância sustentada (>= 2 dos
    // últimos 3 ticks). Para payloads antigos sem o campo, recai no sinal
    // instantâneo. Sem dissonância ativa, zera a assinatura para que um novo
    // episódio (mesmo com os mesmos marcadores) volte a ser registrado.
    const confirmed = event
      ? (event.confirmed ?? event.has_dissonance ?? event.is_multi_dissonance)
      : false;
    if (!event || !confirmed) {
      lastMultiDissonanceSig.current = "";
      return;
    }
    const markers = Array.isArray(event.evident_markers)
      ? event.evident_markers
      : [];
    // Deduplica pelo CONJUNTO de marcadores (não pela severidade, que oscila a
    // cada tick): um mesmo episódio sustentado gera um único registro.
    const signature = markers
      .map((m) => m.key)
      .sort()
      .join("|");
    if (!signature || signature === lastMultiDissonanceSig.current) return;
    lastMultiDissonanceSig.current = signature;
    setMultiDissonanceLog((prev) => [
      ...prev,
      {
        id: `md-${Date.now()}`,
        timestamp: new Date().toLocaleString("pt-BR"),
        elapsedSeconds: state.elapsedSeconds,
        count: event.evident_count,
        categories: Array.isArray(event.categories) ? event.categories : [],
        markers,
        summary: event.summary || "",
        severity: typeof event.severity === "number" ? event.severity : undefined,
        isMulti: Boolean(event.is_multi_dissonance),
        peakZone: event.peak_zone,
        peakZoneTema: event.peak_zone_tema,
        source: event.voice_features_source || "mock",
      },
    ].slice(-30));
  }, [raw, state.elapsedSeconds]);

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
    <select
      value={sessionLayout}
      onChange={(event) =>
        setSessionLayout(event.target.value as "detailed" | "simplified" | "indices")
      }
      aria-label="Layout da sessão"
      className="w-full rounded-lg border border-blue-700 bg-blue-950 px-3 py-2 text-[9px] font-black uppercase tracking-wide text-blue-100 outline-none transition-colors hover:bg-blue-900"
    >
      <option value="detailed">Sessão Detalhada</option>
      <option value="indices">Sessão Detalhada · Índices</option>
      <option value="simplified">Sessão Simplificada</option>
    </select>
  );

  // Painel "Dissonâncias Evidentes" — extraído para ser reutilizado tanto na
  // Coluna 3 do layout Detalhado quanto na Coluna 2 do layout de Índices.
  function renderEvidentDissonancePanel() {
    if (multiDissonanceLog.length === 0) return null;
    return (
      <div className="mt-3 rounded-lg border border-red-700/70 bg-red-950/30 p-2">
        <div className="mb-2 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-red-200">
              Dissonâncias Evidentes
            </p>
            <p className="text-[9px] text-red-300/70">
              Cada marcador fora da métrica base é registrado com valor,
              limiar e interpretação. Ocorrências com 2+ marcadores em 2+
              categorias são destacadas como múltiplas.
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-red-800/60 px-2 py-0.5 text-[9px] font-bold text-red-100">
            {multiDissonanceLog.length}
          </span>
        </div>
        <div className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
          {multiDissonanceLog
            .slice()
            .reverse()
            .map((entry) => (
              <div
                key={entry.id}
                className="rounded border border-red-800/70 bg-red-950/40 p-2 text-[10px] text-slate-200"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 font-bold text-red-100">
                    {entry.isMulti && (
                      <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[8px] font-black uppercase tracking-wide text-white">
                        múltipla
                      </span>
                    )}
                    {entry.count} marcador{entry.count === 1 ? "" : "es"} ·{" "}
                    {entry.categories.length} categoria
                    {entry.categories.length === 1 ? "" : "s"}
                  </span>
                  <span className="flex items-center gap-1.5">
                    {typeof entry.severity === "number" && (
                      <span className="rounded bg-red-800/60 px-1.5 py-0.5 text-[8px] font-bold text-red-100">
                        int. {Math.round(entry.severity * 100)}%
                      </span>
                    )}
                    <span className="text-[9px] text-slate-400">
                      {entry.elapsedSeconds}s
                    </span>
                  </span>
                </div>
                <div className="mt-0.5 flex items-center justify-between gap-2">
                  <p className="text-[9px] text-slate-400">{entry.timestamp}</p>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                      entry.source === "real_pcm"
                        ? "bg-emerald-900/60 text-emerald-200"
                        : "bg-slate-700/60 text-slate-300"
                    }`}
                  >
                    {entry.source === "real_pcm" ? "voz real" : "voz simulada"}
                  </span>
                </div>
                {entry.peakZone && (
                  <p className="mt-0.5 text-[9px] text-red-300/80">
                    Zona de maior desvio: {entry.peakZone}
                    {entry.peakZoneTema ? ` — ${entry.peakZoneTema}` : ""}
                  </p>
                )}
                <div className="mt-1 space-y-1">
                  {entry.markers.map((m, mi) => (
                    <div
                      key={`${entry.id}-${m.key}-${mi}`}
                      className="rounded border border-red-900/50 bg-black/20 px-1.5 py-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-red-100">
                          {m.label}
                        </span>
                        <span className="text-[8px] uppercase text-slate-400">
                          {m.category}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[9px] text-slate-300">
                        Valor {Number(m.value).toFixed(3)} {m.direction} do
                        limiar {m.direction === "acima" ? m.band[1] : m.band[0]}{" "}
                        · {m.interpretation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
        </div>
      </div>
    );
  }

  const clinicalStabilizationControl = (
    <div className="flex flex-wrap items-center gap-1.5 text-[9px] text-slate-200">
      <strong className="uppercase tracking-wide text-cyan-200">Gráficos:</strong>
      <select
        value={clinicalUpdateMode}
        onChange={(event) => setClinicalUpdateMode(event.target.value as ClinicalUpdateMode)}
        aria-label="Tempo de atualização dos gráficos"
        className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-[9px] font-bold text-slate-100 outline-none focus:border-cyan-500"
      >
        {CLINICAL_UPDATE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <span className="text-slate-400">
        {clinicalWindowLabel}
        {clinicalUpdateMode !== "realtime"
          ? ` · próxima ${formatCutClock(clinicalNextUpdateSeconds)}`
          : " · contínuo"}
      </span>
      <button
        type="button"
        onClick={() => refreshClinicalPresentation()}
        disabled={clinicalUpdateMode === "realtime"}
        className="rounded border border-cyan-800 bg-cyan-950 px-2 py-1.5 font-black uppercase text-cyan-100 hover:bg-cyan-900 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Atualizar
      </button>
    </div>
  );

  if (sessionLayout === "simplified") {
    return (
      <div className="flex h-screen min-w-0 flex-col overflow-hidden bg-slate-950 text-slate-100">
        <header className="shrink-0 overflow-x-auto border-b border-slate-800 bg-slate-900 px-3 py-2">
          <div className="flex min-w-max items-center gap-3 whitespace-nowrap">
            <h1 className="text-sm font-black">Sessão Simplificada</h1>
            <span className="rounded border border-cyan-800 bg-cyan-950 px-2 py-1 text-[9px] font-black text-cyan-100">
              Voz {SESSION_LOCALES[spokenLanguage].shortLabel} · relatório {SESSION_LOCALES[reportLocale].shortLabel}
            </span>
            <div className="w-[220px] shrink-0">{layoutSelector}</div>
            {clinicalStabilizationControl}
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
                  content={tooltipText(
                    reportLocale,
                    SIMPLIFIED_METRIC_TOOLTIPS[label] ||
                      "Métrica do corte atual da sessão simplificada.",
                  )}
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

        <main className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-y-auto p-2 lg:grid-cols-[minmax(0,3fr)_minmax(360px,2fr)] lg:overflow-hidden">
          <section className="relative flex aspect-video min-h-[220px] shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-700 bg-slate-900 lg:aspect-auto lg:h-full lg:min-h-0 lg:shrink">
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
              {presencaDoPaciente && !remotePatientVideoOn && (
                <span className="ml-2 font-normal normal-case tracking-normal opacity-90">
                  · {presencaDoPaciente}
                </span>
              )}
            </div>
            {remotePatientOn && !isPresentialMobileSession && (
              <button
                type="button"
                onClick={() => void unlockPatientAudio()}
                className="absolute right-3 top-3 z-30 rounded-full border border-blue-300/60 bg-blue-700 px-3 py-1 text-[10px] font-black uppercase tracking-wide text-white shadow hover:bg-blue-600"
              >
                Ouvir paciente
              </button>
            )}
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

          <div className="flex min-h-0 flex-col gap-2 lg:overflow-y-auto">
            <section className="shrink-0 overflow-hidden rounded-xl border border-cyan-800 bg-slate-950 p-2 shadow-sm">
              <AudioTranscription
                audioMeta={displayAudio}
                conversationSummaries={conversationSummaries}
                section="summary"
                locale={reportLocale}
                cutElapsedLabel={formatCutClock(semanticCutElapsed)}
                cutRemainingLabel={formatCutClock(semanticCutRemaining)}
                cutProgress={semanticCutProgress}
                onCloseCut={() => void closeSemanticCut("manual")}
                closeCutDisabled={semanticCutElapsed < 10 || semanticCutClosingRef.current}
              />
            </section>

            <section className="min-h-[320px] flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2">
              <AIInsights
                responseLocale={reportLocale}
                zones={displayZones}
                ipmScore={displayIpm}
                coherenceStatus={displayCoherence}
                baselineEstablished={state.phase === "LIVE"}
                sessionId={sessionId || ""}
                getLiveContext={getFroidExplicaContext}
                onConversationChange={handleFroidExplicaConversation}
                initialMessages={froidExplicaConversationRef.current}
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

  if (sessionLayout === "indices") {
    return (
      <div className="grid h-screen min-w-[1500px] grid-cols-[minmax(200px,15%)_minmax(680px,49%)_minmax(500px,36%)] overflow-x-auto overflow-y-hidden bg-slate-950 text-slate-100">
        {/* COLUNA 1 — mínima: índices com métrica base, valor ao lado, um embaixo do outro */}
        <div className="order-1 min-w-0 flex flex-col gap-2 overflow-y-auto border-x border-slate-800 bg-slate-950 p-2 text-slate-100">
          <div className="flex min-w-max items-center justify-between gap-2 overflow-x-auto">
            <h1 className="text-[11px] font-bold text-slate-100">
              Índices
            </h1>
            <button
              onClick={endSession}
              className="rounded bg-red-600 px-2 py-1 text-[9px] font-bold text-white hover:bg-red-700"
            >
              Encerrar
            </button>
          </div>

          {layoutSelector}

          <SessionTimer startTime={state.sessionStart} onEndSession={endSession} />

          <AvisoVozSimulada origem={origemDaVoz} motivo={motivoAcustico} />

          {/* Grade de indices: TODAS as metricas do layout Simplificado, com a
              situacao de cada uma contra os limites que o servidor calcula.

              Antes, este painel mostrava so os marcadores COM metrica base, e o
              Simplificado mostrava todas em faixa rolante sem cor nenhuma. Quem
              quisesse o conjunto inteiro com indicacao de ruptura alternava
              entre os dois layouts e comparava de cabeca.

              Grade de duas colunas em vez de lista: cabe sem rolagem, que era o
              pedido. `content-start` impede as celulas de esticarem para
              preencher a altura quando ha poucas metricas. */}
          <div className="shrink-0 pb-1">
            <div className="flex items-center justify-between px-0.5 pb-1">
              <span className="text-[9px] font-black uppercase tracking-wider text-slate-400">
                Índices
              </span>
              {metricasForaDaFaixa > 0 && (
                <span className="rounded bg-red-950 px-1.5 py-0.5 text-[8px] font-black text-red-200">
                  {metricasForaDaFaixa} fora da faixa
                </span>
              )}
            </div>
            {/* As cores existiam e ninguem sabia le-las. Acima e abaixo pedem
                leituras opostas, e a distincao so serve se estiver dita. */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 px-0.5 text-[7px] font-bold uppercase tracking-wide text-slate-500">
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-1.5 rounded-sm border border-red-600 bg-red-950" />
                acima do limite
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-1.5 rounded-sm border border-amber-600 bg-amber-950" />
                abaixo do limite
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-1.5 rounded-sm border border-slate-800 bg-slate-900" />
                dentro / sem regua
              </span>
            </div>
          </div>
          <div className="flex-1 min-h-0 grid grid-cols-2 content-start gap-1 overflow-y-auto">
            {metricasComLimite.map((m) => {
              const cor = STATUS_CLASSES[m.status];
              return (
                <div
                  key={m.label}
                  title={`${statusLabel(m.status)}${
                    m.band ? ` · faixa ${m.band[0] ?? "—"} a ${m.band[1] ?? "—"}` : ""
                  }${m.interpretation ? ` · ${m.interpretation}` : ""}`}
                  className={`rounded border px-1.5 py-1 transition-colors ${cor.box}`}
                >
                  <span className={`block truncate text-[8px] font-bold uppercase tracking-wide ${cor.label}`}>
                    {m.label}
                  </span>
                  <span className={`block truncate font-mono text-[10px] font-black ${cor.value}`}>
                    {m.value}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* COLUNA 2 — vídeo + resumo/corte + FROID Explica (reduzido) + dissonâncias */}
        <div className="order-2 min-w-0 flex flex-col gap-2 overflow-y-auto bg-slate-950 p-2 shadow-inner">
          <div className="relative flex min-h-[280px] flex-[0.8] items-center justify-center overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
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
              {presencaDoPaciente && !remotePatientVideoOn && (
                <span className="ml-2 font-normal normal-case tracking-normal opacity-90">
                  · {presencaDoPaciente}
                </span>
              )}
            </div>
            {remotePatientOn && !isPresentialMobileSession && (
              <button
                type="button"
                onClick={() => void unlockPatientAudio()}
                className="absolute right-3 top-3 z-30 rounded-full border border-blue-300/60 bg-blue-700 px-3 py-1 text-[10px] font-black uppercase tracking-wide text-white shadow hover:bg-blue-600"
              >
                Ouvir paciente
              </button>
            )}
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

          <section className="shrink-0 overflow-hidden rounded-xl border border-cyan-800 bg-slate-950 p-2 shadow-sm">
            <AudioTranscription
              audioMeta={displayAudio}
              conversationSummaries={conversationSummaries}
              section="summary"
              locale={reportLocale}
              cutElapsedLabel={formatCutClock(semanticCutElapsed)}
              cutRemainingLabel={formatCutClock(semanticCutRemaining)}
              cutProgress={semanticCutProgress}
              onCloseCut={() => void closeSemanticCut("manual")}
              closeCutDisabled={semanticCutElapsed < 10 || semanticCutClosingRef.current}
            />
          </section>

          {/* FROID Explica — reduzido para abrir espaço às dissonâncias */}
          <div className="min-h-[150px] max-h-[220px] shrink-0 overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2">
            <AIInsights
              responseLocale={reportLocale}
              zones={displayZones}
              ipmScore={displayIpm}
              coherenceStatus={displayCoherence}
              baselineEstablished={state.phase === "LIVE"}
              sessionId={sessionId || ""}
              getLiveContext={getFroidExplicaContext}
              onConversationChange={handleFroidExplicaConversation}
              initialMessages={froidExplicaConversationRef.current}
              controlsSticky
              rootClassName="h-full border-0 bg-transparent p-0 text-slate-100"
              messagesClassName="min-h-[90px] bg-slate-800/80 text-slate-200"
            />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-2">
            {renderEvidentDissonancePanel()}
            {multiDissonanceLog.length === 0 && (
              <p className="p-2 text-[10px] leading-relaxed text-slate-500">
                Nenhuma dissonância evidente confirmada neste instante.
              </p>
            )}
          </div>
        </div>

        {/* COLUNA 3 — apenas IPM e Mapa Zonal, aproveitando o espaço da Coluna 1 */}
        <div className="order-3 grid min-w-0 grid-rows-2 gap-2 overflow-hidden bg-slate-950 p-3">
          {raw ? (
            <>
              <div className="min-h-0 overflow-hidden">
                <IPMLineChart
                  data={state.ipmHistory}
                  current={liveIpm}
                  baseline={state.baselineIPM || undefined}
                  locale={reportLocale}
                />
              </div>

              <div className="min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-900 p-1">
                <MapaZonalFroid
                  className="h-full"
                  zones={displayZones}
                  baselineIpm={state.baselineIPM}
                  drValue={displayDrValue}
                  isCalibrating={state.phase === "CALIBRATING"}
                  locale={reportLocale}
                />
              </div>
            </>
          ) : (
            <div className="row-span-2 flex items-center justify-center text-sm text-slate-400">
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

  return (
    <div className="grid h-screen min-w-[1620px] grid-cols-[minmax(500px,28%)_minmax(620px,44%)_minmax(500px,28%)] overflow-x-auto overflow-y-hidden bg-slate-950 text-slate-100">
      {/* COLUNA 1 — 30% */}
      <div className="order-1 min-w-0 flex flex-col gap-2 overflow-y-auto border-x border-slate-800 bg-slate-950 p-2 text-slate-100">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-base font-bold text-slate-100">
            Sessão Detalhada
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded border border-cyan-800 bg-cyan-950 px-2 py-0.5 text-[9px] font-black text-cyan-100">
              {SESSION_LOCALES[spokenLanguage].shortLabel} → {SESSION_LOCALES[reportLocale].shortLabel}
            </span>
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

        <div className="flex flex-wrap items-center gap-2">
          {clinicalStabilizationControl}
        </div>

        {layoutSelector}

        <AvisoVozSimulada origem={origemDaVoz} motivo={motivoAcustico} />

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
              locale={reportLocale}
            />
          </div>

          <div className="min-h-[300px]">
            <SpectralBandsChart audioMeta={liveAudioMeta} locale={reportLocale} />
          </div>

          <div className="min-h-[390px]">
            <SubharmonicChart zones={liveZones} audioMeta={liveAudioMeta} locale={reportLocale} />
          </div>

          <AudioTranscription
            audioMeta={liveAudioMeta}
            conversationSummaries={conversationSummaries}
            section="biomarkers"
            locale={reportLocale}
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
            {presencaDoPaciente && !remotePatientVideoOn && (
              <span className="ml-2 font-normal normal-case tracking-normal opacity-90">
                · {presencaDoPaciente}
              </span>
            )}
            {/* Aparece só quando a mídia do paciente não chegou — que é
                exatamente quando alguém precisa saber o porquê. Copia o
                histórico da negociação para colar num chamado. */}
            {!remotePatientVideoOn && !remotePatientOn && (
              <button
                type="button"
                onClick={() => {
                  const texto = relatorioRtc();
                  void navigator.clipboard?.writeText(texto);
                  window.alert(
                    "Diagnóstico copiado. Cole no chamado:" + texto.slice(0, 1200),
                  );
                }}
                title="Copia o histórico da conexão para enviar ao suporte"
                className="ml-2 rounded-full bg-slate-800/90 px-2 py-0.5 text-[9px] font-black normal-case tracking-normal text-slate-200 hover:bg-slate-700"
              >
                copiar diagnóstico
              </button>
            )}
          </div>
          {remotePatientOn && !isPresentialMobileSession && (
            <button
              type="button"
              onClick={() => void unlockPatientAudio()}
              className="absolute right-3 top-3 z-30 rounded-full border border-blue-300/60 bg-blue-700 px-3 py-1 text-[10px] font-black uppercase tracking-wide text-white shadow hover:bg-blue-600"
            >
              Ouvir paciente
            </button>
          )}
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

        <section className="shrink-0 overflow-hidden rounded-xl border border-cyan-800 bg-slate-950 p-2 shadow-sm">
          <AudioTranscription
            audioMeta={displayAudio}
            conversationSummaries={conversationSummaries}
            section="summary"
            locale={reportLocale}
            cutElapsedLabel={formatCutClock(semanticCutElapsed)}
            cutRemainingLabel={formatCutClock(semanticCutRemaining)}
            cutProgress={semanticCutProgress}
            onCloseCut={() => void closeSemanticCut("manual")}
            closeCutDisabled={semanticCutElapsed < 10 || semanticCutClosingRef.current}
          />
        </section>

        <div className="min-h-[320px] flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2">
          <AIInsights
            responseLocale={reportLocale}
            zones={displayZones}
            ipmScore={displayIpm}
            coherenceStatus={displayCoherence}
            baselineEstablished={state.phase === "LIVE"}
            sessionId={sessionId || ""}
            getLiveContext={getFroidExplicaContext}
            onConversationChange={handleFroidExplicaConversation}
            initialMessages={froidExplicaConversationRef.current}
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
                data={state.ipmHistory}
                current={liveIpm}
                baseline={state.baselineIPM || undefined}
                locale={reportLocale}
              />
            </div>

            <div className="min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-900 p-1">
              <MapaZonalFroid
                className="h-full"
                zones={displayZones}
                baselineIpm={state.baselineIPM}
                drValue={displayDrValue}
                isCalibrating={state.phase === "CALIBRATING"}
                locale={reportLocale}
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

              {renderEvidentDissonancePanel()}

              {dissonanceLog.length > 0 && (
                <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900 p-2">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-300">
                      Registro de Dissonâncias (por zona)
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
