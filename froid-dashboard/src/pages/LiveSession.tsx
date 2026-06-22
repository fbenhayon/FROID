import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";

interface LiveSessionProps {
  user?: any;
}
import { useParams, useNavigate } from "react-router-dom";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import { RiskChart } from "../components/indicators/RiskChart";
import { SubharmonicChart } from "../components/indicators/SubharmonicChart";
import { MediaStatus } from "../components/indicators/MediaStatus";
import { SessionTimer } from "../components/indicators/SessionTimer";
import { ClinicalNotes } from "../components/panels/ClinicalNotes";
import { AIInsights } from "../components/panels/AIInsights";
import { AudioTranscription } from "../components/panels/AudioTranscription";
import { COMMITMENT_TEXTS } from "../components/panels/CommitmentPanel";
import { FroidPayload, PerceptionZone } from "../lib/froid-engine";
import { getAUDetails, ZONE_CLINICAL_DESCRIPTIONS } from "../lib/froid-data";
import { apiUrl, wsUrl } from "../lib/api";
import { createConferenceStream, RTC_CONFIG } from "../lib/webrtc";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import {
  ClinicalNote,
  MetricSnapshot,
  saveSessionReport,
  SessionReportRecord,
} from "../lib/session-report";

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
  startMinute: number;
  endMinute: number;
  theme: string;
  summary: string;
}

type SpeakerRole = "PC" | "DR";

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
}

type Action =
  | { type: "WS_OPEN" }
  | { type: "WS_CLOSE" }
  | { type: "TICK" }
  | { type: "BASELINE_LOCK"; ipm: number }
  | { type: "PAYLOAD"; data: FroidPayload }
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

function dissonanceScore(zone?: PerceptionZone | null) {
  return Math.abs(Number(zone?.deviation_score || 0));
}

function isReportableDissonance(zone?: PerceptionZone | null) {
  return Boolean(
    zone?.facial_dissonance_detected &&
      zone?.dissonance_details &&
      dissonanceScore(zone) > DISSONANCE_REPORT_THRESHOLD,
  );
}

function dissonanceSeverity(zone?: PerceptionZone | null) {
  return dissonanceScore(zone) > DISSONANCE_CRITICAL_THRESHOLD
    ? "CRITICA"
    : "RELEVANTE";
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
              ].slice(-120)
            : state.ipmHistory;
        return { ...state, payload: p, ipmHistory: nextHistory };
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
      active: peak >= 0.012 && rms >= 0.0012,
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
  const shimmer = voicePresence
    ? clamp(Math.sqrt(envelopeVariance) / Math.max(0.0001, meanEnvelope))
    : 0;
  const jitter = voicePresence ? clamp(zcr * 45) : 0;

  return {
    rms,
    peak,
    zcr,
    jitter,
    shimmer,
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
  };
}

const STT_CHUNK_MS = 7000;
const MIN_STT_AUDIO_BYTES = 1200;
const MAX_VISIBLE_TRANSCRIPT_LINES = 12;
const TRANSCRIPT_SUMMARY_WINDOW_MS = 10 * 60 * 1000;
const ENABLE_BROWSER_LIVE_STT = false;

function speakerPrefix(speaker: SpeakerRole) {
  return speaker === "DR" ? "DR. - " : "PC - ";
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
  "f0_mean",
  "zcr",
  "jitter",
  "shimmer",
  "subharmonic_energy_5_12hz",
  "subharmonic_energy_12_20hz",
] as const;

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
  "voce",
  "tambem",
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
    .slice(0, 5)
    .map(([word]) => word);
  return top.length ? top.join(" ") : "Tema em apuracao";
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
    f0Mean: audioAverage("f0_mean"),
    zcr: audioAverage("zcr"),
    jitter: audioAverage("jitter"),
    shimmer: audioAverage("shimmer"),
    subharmonic5_12: audioAverage("subharmonic_energy_5_12hz"),
    subharmonic12_20: audioAverage("subharmonic_energy_12_20hz"),
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

function LiveSessionInner(_: LiveSessionProps) {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
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
  const [clinicalNotes, setClinicalNotes] = useState<ClinicalNote[]>([]);
  const [rtcStatus, setRtcStatus] = useState("Aguardando paciente");
  const [remotePatientOn, setRemotePatientOn] = useState(false);
  const [localSpeaker, setLocalSpeaker] = useState<SpeakerRole>("DR");
  const [patientAudioVersion, setPatientAudioVersion] = useState(0);
  const frameBuffer = useRef<FroidPayload[]>([]);
  const sessionSamplesRef = useRef<SessionSample[]>([]);
  const baselineSnapshotRef = useRef<MetricSnapshot | null>(null);
  const elapsedSecondsRef = useRef(0);
  const reportSavedRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  const rtcMakingOfferRef = useRef(false);
  const bioacousticStreamRef = useRef<MediaStream | null>(null);
  const bioacousticContextRef = useRef<AudioContext | null>(null);
  const bioacousticRafRef = useRef<number | null>(null);
  const bioacousticEnvelopeRef = useRef<number[]>([]);
  const bioacousticFrameRef = useRef(0);
  const bioacousticClockRef = useRef({ lastTime: 0, frameRate: 60 });
  const recorderRef = useRef<MediaRecorder | null>(null);
  const patientRecorderRef = useRef<MediaRecorder | null>(null);
  const browserRecognitionRef = useRef<any>(null);
  const browserSttRestartTimerRef = useRef<number | null>(null);
  const browserSttAvailableRef = useRef(false);
  const transcriptLinesRef = useRef<string[]>([]);
  const transcriptSegmentsRef = useRef<Array<{ elapsedSeconds: number; text: string }>>([]);
  const summarizedWindowsRef = useRef<Set<number>>(new Set());
  const pendingSummaryWindowsRef = useRef<Set<number>>(new Set());
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
  const activeSpeakerRef = useRef<SpeakerRole>("DR");
  const forcedLocalSegmentSpeakerRef = useRef<SpeakerRole | null>(null);
  const remotePatientOnRef = useRef(false);

  useEffect(() => {
    const id = setInterval(() => dispatch({ type: "TICK" }), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    elapsedSecondsRef.current = state.elapsedSeconds;
  }, [state.elapsedSeconds]);

  useEffect(() => {
    remotePatientOnRef.current = remotePatientOn;
  }, [remotePatientOn]);

  const selectLocalSpeaker = useCallback((speaker: SpeakerRole) => {
    const previousSpeaker = activeSpeakerRef.current;
    if (previousSpeaker === speaker) return;
    const recorder = recorderRef.current;
    if (
      recorder &&
      recorder.state === "recording" &&
      !remotePatientOnRef.current
    ) {
      forcedLocalSegmentSpeakerRef.current = previousSpeaker;
      segmentingRecorderStopRef.current = true;
      try {
        recorder.stop();
      } catch {}
    }
    activeSpeakerRef.current = speaker;
    setLocalSpeaker(speaker);
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      local_session_speaker: speaker,
      local_session_mode:
        "Atendimento presencial: microfone local rotulado manualmente.",
    }));
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

  const cleanupRtcCall = useCallback(() => {
    rtcSignalRef.current?.close();
    rtcSignalRef.current = null;
    rtcPeerRef.current?.close();
    rtcPeerRef.current = null;
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
    setRtcStatus("Aguardando paciente");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
  }, []);

  const startProfessionalRtcCall = useCallback(
    async (localSource: MediaStream) => {
      if (!sessionId || typeof RTCPeerConnection === "undefined") {
        setRtcStatus("WebRTC indisponivel neste navegador.");
        return;
      }

      cleanupRtcCall();
      const localConferenceStream = createConferenceStream(localSource);
      if (!localConferenceStream.getTracks().length) {
        setRtcStatus("Audio e video locais indisponiveis para chamada.");
        return;
      }

      const peer = new RTCPeerConnection(RTC_CONFIG);
      const remoteStream = new MediaStream();
      rtcPeerRef.current = peer;

      localConferenceStream.getTracks().forEach((track) => {
        peer.addTrack(track, localConferenceStream);
      });

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

      peer.ontrack = (event) => {
        event.streams[0]?.getTracks().forEach((track) => {
          if (!remoteStream.getTracks().some((item) => item.id === track.id)) {
            remoteStream.addTrack(track);
          }
        });
        if (remoteVideoRef.current) {
          remoteVideoRef.current.srcObject = remoteStream;
          remoteVideoRef.current.play().catch(() => undefined);
        }
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
        setRemotePatientOn(true);
        setRtcStatus("Paciente conectado por audio e video.");
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
          setRtcStatus("Audio e video bidirecionais ativos.");
        } else if (["failed", "disconnected"].includes(peer.connectionState)) {
          setRemotePatientOn(false);
          setRtcStatus("Conexao com paciente interrompida.");
        } else if (peer.connectionState === "connecting") {
          setRtcStatus("Conectando audio e video do paciente...");
        }
      };

      const socket = new WebSocket(wsUrl(`/ws/rtc/${sessionId}/professional`));
      rtcSignalRef.current = socket;

      socket.onopen = () => setRtcStatus("Aguardando paciente...");
      socket.onclose = () => setRtcStatus("Sinalizacao de video encerrada.");
      socket.onerror = () => setRtcStatus("Falha na sinalizacao de video.");
      socket.onmessage = async (event) => {
        const data = JSON.parse(String(event.data || "{}"));
        if (data.type === "signal-ready" && data.peer_connected) {
          await makeOffer();
        } else if (data.type === "peer-joined") {
          await makeOffer();
        } else if (data.type === "answer" && data.answer) {
          await peer.setRemoteDescription(data.answer);
          await flushIceQueue();
        } else if (data.type === "ice" && data.candidate) {
          if (peer.remoteDescription) {
            await peer.addIceCandidate(data.candidate).catch(() => undefined);
          } else {
            rtcIceQueueRef.current.push(data.candidate);
          }
        } else if (data.type === "peer-left") {
          setRemotePatientOn(false);
          setRtcStatus("Paciente saiu da chamada.");
          if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
        }
      };
    },
    [cleanupRtcCall, sessionId],
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
    bioacousticFrameRef.current = 0;
    bioacousticClockRef.current = { lastTime: 0, frameRate: 60 };
  }, []);

  const startRawBioacousticPipeline = useCallback(
    (
      stream: MediaStream,
      sourceMode: "patient-webrtc" | "raw-independent" | "semantic-fallback",
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
          bioacoustic_error: "WebAudio indisponivel para bioacustica bruta.",
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
      bioacousticFrameRef.current = 0;
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

        bioacousticFrameRef.current += 1;
        if (bioacousticFrameRef.current % 8 === 0) {
          setLiveTranscription((prev) => ({
            ...(prev || {}),
            bioacoustic_status: "monitoring",
            bioacoustic_pipeline: "raw-webaudio",
            bioacoustic_track: sourceMode,
            bioacoustic_sample_rate: context.sampleRate,
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
            voice_presence: metrics.voicePresence,
            energy_85_165hz: metrics.energy85_165,
            subharmonic_energy_5_12hz: metrics.sub5_12,
            subharmonic_energy_12_20hz: metrics.sub12_20,
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

    const speaker = speakerOverride || activeSpeakerRef.current;
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
      transcription_snippet: transcriptLinesRef.current.slice().reverse().join("\n"),
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
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (reportStatus) refreshMediaStatus(null);
  }, [cleanupRtcCall, refreshMediaStatus, stopRawBioacousticPipeline]);

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
            transcription_interim: `${speakerPrefix(activeSpeakerRef.current)}${interim.trim()}`,
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
          err?.message || "Reconhecimento de fala do navegador indisponivel.",
      }));
      return false;
    }
  }, [appendTranscriptText]);

  const summarizeTranscriptWindow = useCallback(async (windowIndex: number) => {
    if (
      summarizedWindowsRef.current.has(windowIndex) ||
      pendingSummaryWindowsRef.current.has(windowIndex)
    ) {
      return;
    }

    pendingSummaryWindowsRef.current.add(windowIndex);
    const startMinute = windowIndex * 10;
    const endMinute = startMinute + 10;
    const startSeconds = windowIndex * 10 * 60;
    const endSeconds = startSeconds + 10 * 60;
    const transcript = transcriptSegmentsRef.current
      .filter(
        (segment) =>
          segment.elapsedSeconds >= startSeconds &&
          segment.elapsedSeconds < endSeconds,
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
      summarizedWindowsRef.current.add(windowIndex);
      pendingSummaryWindowsRef.current.delete(windowIndex);
    };

    if (!transcript) {
      commitSummary({
        id: `summary-${windowIndex}`,
        startMinute,
        endMinute,
        theme: "Sem fala transcrita",
        summary: "Nenhuma fala foi transcrita neste intervalo.",
      });
      return;
    }

    try {
      const response = await fetch(apiUrl("/api/session-summary"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript,
          start_minute: startMinute,
          end_minute: endMinute,
          session_id: sessionId || "default",
        }),
      });
      const data = await response.json();
      commitSummary({
        id: `summary-${windowIndex}`,
        startMinute,
        endMinute,
        theme: String(data?.theme || "Tema em apuracao"),
        summary: String(data?.summary || "").trim(),
      });
    } catch {
      commitSummary({
        id: `summary-${windowIndex}`,
        startMinute,
        endMinute,
        theme: "Resumo indisponivel",
        summary: transcript.split(/\s+/).slice(0, 200).join(" "),
      });
    }
  }, [sessionId]);

  const flushDueTranscriptSummaries = useCallback(() => {
    const currentWindowIndex = Math.floor(
      state.elapsedSeconds / (TRANSCRIPT_SUMMARY_WINDOW_MS / 1000),
    );
    for (let index = 0; index < currentWindowIndex; index += 1) {
      void summarizeTranscriptWindow(index);
    }
  }, [state.elapsedSeconds, summarizeTranscriptWindow]);

  const addClinicalNote = useCallback((text: string) => {
    setClinicalNotes((prev) => [
      {
        id: makeReportId(),
        text,
        timestamp: Date.now(),
      },
      ...prev,
    ]);
  }, []);

  const transcribeAudioBlob = useCallback(
    async (audioBlob: Blob, mimeType: string, speaker: SpeakerRole) => {
      if (!audioBlob || audioBlob.size < MIN_STT_AUDIO_BYTES) {
        setLiveTranscription((prev) => ({
          ...(prev || {}),
          provider: prev?.provider || "browser-recorder",
          transcription_status: "listening",
          transcription_error: "Audio capturado ainda insuficiente.",
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
        const response = await fetch(apiUrl("/api/transcribe"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_base64: audioBase64,
            mime_type: chunkMime,
            filename: `froid-session-${Date.now()}.${extensionFromMimeType(
              chunkMime,
            )}`,
            session_id: sessionId || "default",
            prompt:
              "Sessao clinica FROID em portugues do Brasil. Transcreva literalmente somente a fala humana audivel, com pontuacao natural. Nao traduza, nao resuma, nao complete frases e nao invente palavras. Mantenha termos tecnicos, nomes e siglas como falados. Se nao houver fala humana clara, retorne vazio." +
              " Vocabulario obrigatorio: FROID deve ser grafado FROID, nunca Freud; IPM, IDM, biomarcadores, sub-harmonicos, bioacustica, dissonancias, paciente e profissional." +
              (previousContext
                ? `\n\nContexto transcrito imediatamente anterior para continuidade e pontuacao:\n${previousContext}`
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
              data?.error || `Falha HTTP ${response.status} na transcricao.`,
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
              data?.error || "Audio enviado, sem fala transcrita no bloco.",
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
            err instanceof Error ? err.message : "Falha ao enviar audio.",
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
              ? "MediaRecorder indisponivel neste navegador."
              : source === "patient"
                ? "Audio do paciente ainda nao chegou ao gravador."
                : "Microfone do profissional indisponivel para gravacao.",
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
            err?.message || "Nao foi possivel criar o gravador de audio.",
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
          transcription_sources: "DR-profissional/PC-paciente",
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
            error?.message || "Erro no gravador de audio do navegador.",
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
                ? activeSpeakerRef.current
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
            err?.message || "Nao foi possivel iniciar o gravador de audio.",
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

    startRawBioacousticPipeline(patientBioacousticStream, "patient-webrtc");
    startSpeechToText(patientTranscriptStream, "PC", "patient");
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "monitoring",
      bioacoustic_pipeline: "patient-webrtc",
      bioacoustic_track: "patient-webrtc",
      bioacoustic_warning:
        "Avaliacao FROID usando exclusivamente a voz do paciente.",
      transcription_sources: "DR-profissional/PC-paciente",
      bioacoustic_error: "",
    }));
  }, [patientAudioVersion, startRawBioacousticPipeline, startSpeechToText]);

  useEffect(() => {
    if (remotePatientOn) return;
    const localAudioTrack = mediaStreamRef.current
      ?.getAudioTracks()
      .find((track) => track.readyState === "live");

    if (!localAudioTrack) return;

    if (localSpeaker === "PC") {
      startRawBioacousticPipeline(
        new MediaStream([localAudioTrack.clone()]),
        "semantic-fallback",
      );
      setLiveTranscription((prev) => ({
        ...(prev || {}),
        bioacoustic_status: "monitoring",
        bioacoustic_pipeline: "direct-local-patient",
        bioacoustic_track: "local-patient-selected",
        bioacoustic_warning:
          "Atendimento presencial: metricas calculadas somente enquanto PC esta selecionado.",
        transcription_sources:
          "Atendimento presencial com alternancia manual DR/PC.",
        bioacoustic_error: "",
      }));
      return;
    }

    stopRawBioacousticPipeline();
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "waiting_patient",
      bioacoustic_pipeline: "direct-local-paused",
      bioacoustic_track: "local-professional-selected",
      bioacoustic_warning:
        "Atendimento presencial: selecione PC quando o paciente estiver falando para alimentar os biomarcadores.",
      transcription_sources:
        "Atendimento presencial com alternancia manual DR/PC.",
    }));
  }, [
    localSpeaker,
    remotePatientOn,
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
        camError: "Navegador sem suporte a camera e microfone.",
      });
      return;
    }

    stopMedia();

    const tracks: MediaStreamTrack[] = [];
    let semanticAudioStream: MediaStream | null = null;
    let audioError = "";
    let videoError = "";

    try {
      semanticAudioStream = await navigator.mediaDevices.getUserMedia({
        audio: getSemanticAudioConstraints(),
        video: false,
      });
      tracks.push(...semanticAudioStream.getAudioTracks());
    } catch (err: any) {
      audioError =
        err?.name === "NotAllowedError"
          ? "Permissao de microfone negada pelo navegador."
          : "Nao foi possivel ativar o microfone.";
    }

    try {
      const videoStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: false,
      });
      tracks.push(...videoStream.getVideoTracks());
    } catch (err: any) {
      videoError =
        err?.name === "NotAllowedError"
          ? "Permissao de camera negada pelo navegador."
          : "Nao foi possivel ativar a camera.";
    }

    const stream = new MediaStream(tracks);
    mediaStreamRef.current = stream;
    startSpeechToText(stream, "DR", "professional");
    setLiveTranscription((prev) => ({
      ...(prev || {}),
      bioacoustic_status: "waiting_patient",
      bioacoustic_pipeline: "patient-webrtc",
      bioacoustic_track: "patient-webrtc",
      bioacoustic_warning:
        "Biomarcadores e graficos aguardam exclusivamente o audio do paciente.",
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
    void startProfessionalRtcCall(stream);
  }, [
    refreshMediaStatus,
    startBrowserSpeechToText,
    startProfessionalRtcCall,
    startRawBioacousticPipeline,
    startSpeechToText,
    stopMedia,
  ]);

  useEffect(() => {
    void activateMedia();
    return () => stopMedia(false);
  }, [activateMedia, stopMedia]);

  useEffect(() => {
    flushDueTranscriptSummaries();
  }, [flushDueTranscriptSummaries]);

  useEffect(() => {
    if (state.elapsedSeconds >= 60 && state.phase === "CALIBRATING") {
      const baseline = buildMetricSnapshot(
        "Baseline 0-60s",
        sessionSamplesRef.current,
        0,
        60,
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
        const socket = new WebSocket(wsUrl(`/ws/fusion/${sessionId || "default"}`));
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
    }, 10000); /* agrega a cada 10s usando media dos ultimos 3s (6 frames) */
    return () => clearInterval(id);
  }, []);

  const agg = state.aggregated;
  const raw = state.payload;
  const displayZones = agg?.zones || raw?.perception_zones || [];
  const displayIpm = agg?.ipm || raw?.ipm_score || 0;
  const displayDrValue = agg?.drValue ?? (raw as any)?.dr_value ?? null;
  const displayCoherence = agg?.coherence || raw?.coherence_status || "NEUTRO";
  const displayAlerts = agg?.alerts || raw?.realtime_alerts || [];
  const baseDisplayAudio = agg?.audioMeta ||
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
    ? { ...realTranscriptAudio, ...liveTranscription }
    : realTranscriptAudio;
  const displayCommitments =
    agg?.commitments || (raw as any)?.commitment_models || [];

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
      "Media da sessao",
      samples,
      0,
      Math.max(durationSeconds, 1),
      transcriptSegmentsRef.current,
    );
    const tenMinuteCuts = buildTenMinuteCuts(
      samples,
      transcriptSegmentsRef.current,
      durationSeconds,
    );

    return {
      id: makeReportId(),
      sessionId: sessionId || "default",
      createdAt: new Date().toISOString(),
      durationSeconds,
      baseline,
      sessionAverage,
      tenMinuteCuts,
      clinicalNotes,
      conversationSummaries,
      dissonances: dissonanceLog,
      transcript: transcriptSegmentsRef.current.map((segment) => segment.text).join("\n"),
    };
  }, [
    clinicalNotes,
    conversationSummaries,
    dissonanceLog,
    raw,
    sessionId,
    state.elapsedSeconds,
  ]);

  const archiveSessionReport = useCallback(
    async (report: SessionReportRecord) => {
      saveSessionReport(report);
      try {
        await fetch(apiUrl("/api/session-reports"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(report),
        });
      } catch {
        // Local report remains available even if server archival is offline.
      }
    },
    [],
  );

  const endSession = useCallback(() => {
    if (reportSavedRef.current) return;
    reportSavedRef.current = true;
    const report = createSessionReport();
    void archiveSessionReport(report);
    if (wsRef.current)
      try {
        wsRef.current.close();
      } catch {}
    dispatch({ type: "END_SESSION" });
    setTimeout(() => navigate(`/session/${report.sessionId}/report`), 400);
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
    const currentEntries = (displayZones || [])
      .filter(isReportableDissonance)
      .map((z) => {
        const score = dissonanceScore(z);
        return {
          zone: z.zone,
          score,
          severity: dissonanceSeverity(z),
          report:
            z.dissonance_details?.report ||
            "Dissonancia facial-vocal detectada",
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
          report: `IDM ${entry.score.toFixed(2)} | ${entry.severity}: ${
            entry.report
          }`,
        };
      })
      .filter((entry) => Number.isFinite(entry.zone));

    setDissonanceLog((prev) => [...prev, ...nextEntries].slice(-18));
  }, [displayZones, state.elapsedSeconds]);

  const connectionText = state.connected
    ? state.phase === "CALIBRATING"
      ? "Sincronia Inicial"
      : "Ao Vivo"
    : state.phase === "ENDED"
      ? "Encerrada"
      : "Desconectado";
  const baselineSnapshot = baselineSnapshotRef.current;

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

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden text-slate-800">
      {/* COLUNA 1 — 30% */}
      <div className="w-[28%] flex flex-col gap-2 border-r border-slate-200 bg-white p-3 overflow-y-auto">
        <div className="flex items-center justify-between">
          <h1 className="text-base font-bold text-slate-800">
            Sessão {sessionId?.slice(0, 8) || "--"}
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

        <SessionTimer
          startTime={state.sessionStart}
          onEndSession={endSession}
        />

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Fala presencial
            </span>
            <span className="text-[9px] font-semibold text-slate-400">
              {remotePatientOn ? "Remoto automatico" : "Alternancia manual"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {(["DR", "PC"] as SpeakerRole[]).map((speaker) => {
              const active = localSpeaker === speaker;
              const disabled = remotePatientOn;
              return (
                <button
                  key={speaker}
                  type="button"
                  disabled={disabled}
                  onClick={() => selectLocalSpeaker(speaker)}
                  className={`rounded-md border px-2 py-1.5 text-[11px] font-black transition ${
                    active
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:border-blue-300"
                  } ${disabled ? "cursor-not-allowed opacity-45" : ""}`}
                >
                  {speaker === "DR" ? "DR. falando" : "PC falando"}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-[10px] leading-snug text-slate-500">
            {remotePatientOn
              ? "Com paciente remoto, o FROID separa DR pela trilha local e PC pela trilha do paciente."
              : "Em consulta presencial, selecione PC durante a fala do paciente para transcricao e biomarcadores."}
          </p>
        </div>

        <AudioTranscription
          snippet={displayAudio.transcription_snippet}
          wordsCount={displayAudio.words_per_window}
          totalWords={displayAudio.total_words_session}
          tone={displayAudio.emotional_tone}
          wordsPerMinute10m={displayAudio.words_per_minute_10m || 0}
          sessionTheme={displayAudio.session_theme}
          themeMinuteMark={displayAudio.theme_minute_mark}
          audioMeta={displayAudio}
          conversationSummaries={conversationSummaries}
        />

        {state.phase === "CALIBRATING" && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-700 shrink-0">
            <p className="font-bold">Fase de Repouso Ativa</p>
            <p>Coletando baseline completo: {state.elapsedSeconds}s / 60s</p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
              <div
                className="h-full bg-blue-600 transition-all duration-1000"
                style={{ width: (state.elapsedSeconds / 60) * 100 + "%" }}
              />
            </div>
          </div>
        )}

        {state.phase === "LIVE" && baselineSnapshot && (
          <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-2 text-[10px] text-emerald-900">
            <div className="mb-1 font-bold uppercase tracking-wider">
              Baseline 60s registrado
            </div>
            <div className="grid grid-cols-3 gap-1">
              <span>IPM {baselineSnapshot.ipmAvg.toFixed(1)}</span>
              <span>IDM {baselineSnapshot.idmAvg.toFixed(2)}</span>
              <span>{baselineSnapshot.wordsPerMinute.toFixed(0)} ppm</span>
            </div>
            <p className="mt-1 truncate text-emerald-700">
              Tema: {baselineSnapshot.theme} | Zona{" "}
              {baselineSnapshot.dominantZone || "--"}
            </p>
          </div>
        )}

        <div className="flex-1 min-h-0 flex flex-col gap-3">
          <ClinicalNotes notes={clinicalNotes} onAddNote={addClinicalNote} />
          <div className="flex-1 min-h-[200px]">
            <AIInsights
              zones={displayZones}
              ipmScore={displayIpm}
              coherenceStatus={displayCoherence}
              baselineEstablished={state.phase === "LIVE"}
              sessionId={sessionId || ""}
            />
          </div>
        </div>
      </div>

      {/* COLUNA 2 — 34%: Vídeo (50%) + Mapa Zonal (50%) */}
      <div className="w-[34%] flex flex-col gap-0 bg-white shadow-inner overflow-hidden">
        {/* Vídeo — 50% do espaço */}
        <div className="h-1/2 relative rounded-xl bg-slate-900 overflow-hidden flex items-center justify-center border-b border-slate-200">
          <MediaStatus
            cameraOn={state.cameraOn}
            micOn={state.micOn}
            simulated={!state.cameraOn}
          />
          <video
            ref={remoteVideoRef}
            autoPlay
            playsInline
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
              remotePatientOn ? "opacity-100" : "opacity-0"
            }`}
          />
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
              remotePatientOn
                ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                : "inset-0 h-full w-full"
            } ${state.cameraOn ? "opacity-100" : "opacity-0"}`}
          />
          <div
            className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
              remotePatientOn
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
                  {state.camError || "Audio aguardando permissao do navegador."}
                </span>
                {!state.micOn && (
                  <button
                    type="button"
                    onClick={() => void activateMedia()}
                    className="shrink-0 rounded bg-amber-400 px-2 py-1 text-[10px] font-black text-slate-950 hover:bg-amber-300"
                  >
                    Ativar audio
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="h-1/2 flex flex-col gap-0 p-2 overflow-hidden">
          <MapaZonalFroid
            className="h-full"
            zones={displayZones}
            baselineIpm={state.baselineIPM}
            drValue={displayDrValue}
            isCalibrating={state.phase === "CALIBRATING"}
          />
        </div>
      </div>

      {/* COLUNA 3 — 35%: IPM grande, Risco, Subharm, Coherence, Dissonâncias */}
      <div className="grid flex-1 grid-rows-4 gap-2 overflow-visible bg-slate-50 p-3">
        {raw ? (
          <>
            <div className="min-h-0 overflow-visible">
              <IPMLineChart
                data={state.ipmHistory}
                current={displayIpm}
                baseline={state.baselineIPM || undefined}
              />
            </div>

            <div className="min-h-0 overflow-visible">
              <RiskChart
                zones={displayZones}
                ipmScore={displayIpm}
                coherenceStatus={displayCoherence}
                baseline={state.baselineIPM}
                audioMeta={displayAudio}
              />
            </div>

            <div className="min-h-0 overflow-hidden">
              <SubharmonicChart zones={displayZones} audioMeta={displayAudio} />
            </div>

            <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
              <h3 className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Dissonâncias Identificadas (Média 10s)
                {displayZones.some(isReportableDissonance) && (
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                )}
                <span className="text-[9px] font-semibold normal-case tracking-normal text-slate-400">
                  IDM &gt; {DISSONANCE_REPORT_THRESHOLD.toFixed(2)}
                </span>
              </h3>

              {(!Array.isArray(displayZones) ||
                displayZones.filter(isReportableDissonance).length === 0) && (
                <p className="text-xs italic text-slate-400">
                  Nenhuma dissonancia facial-vocal acima do limiar nos ultimos
                  10 segundos.
                </p>
              )}

              {Array.isArray(displayZones) &&
                displayZones
                  .filter(isReportableDissonance)
                  .map((zone) => {
                    const aus = zone.dissonance_details?.active_aus || [];
                    const auDescs = getAUDetails(aus);
                    const score = dissonanceScore(zone);
                    const severity = dissonanceSeverity(zone);
                    return (
                      <div
                        key={zone.zone}
                        className="mb-2 rounded-r-lg border-l-4 border-red-600 bg-red-50 p-3"
                      >
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-bold text-red-900">
                            Zona {zone.zone} — {zone.tema || ""}
                          </p>
                          <span className="text-[9px] font-bold text-white bg-red-600 px-1.5 py-0.5 rounded">
                            IDM {score.toFixed(2)} | {severity}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] font-medium leading-relaxed text-slate-700">
                          {ZONE_CLINICAL_DESCRIPTIONS[zone.zone] || ""}
                        </p>
                        <p className="mt-2 text-[11px] font-semibold leading-relaxed text-red-700">
                          {zone.dissonance_details?.report || ""}
                        </p>
                        <div className="mt-2 space-y-1">
                          {auDescs.map((d, i) => (
                            <p
                              key={i}
                              className="text-[10px] font-mono text-slate-600 leading-tight"
                            >
                              • {d}
                            </p>
                          ))}
                        </div>
                        <p className="mt-2 text-[10px] font-bold text-red-800">
                          Multiplicador facial 2.5x aplicado ao IDM.
                        </p>
                      </div>
                    );
                  })}

              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Registro de Dissonâncias
                  </p>
                  <span className="text-[9px] text-slate-500">
                    {dissonanceLog.length} itens
                  </span>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                  {dissonanceLog.length === 0 && (
                    <p className="text-[10px] text-slate-400">
                      Nenhuma dissonancia acima do limiar registrada ainda.
                    </p>
                  )}
                  {dissonanceLog
                    .slice()
                    .reverse()
                    .map((entry) => (
                      <div
                        key={entry.id}
                        className="rounded border border-red-100 bg-white p-2 text-[10px] text-slate-600"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-red-700">
                            Zona {entry.zone}
                          </span>
                          <span className="text-[9px] text-slate-400">
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

              <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50/40 p-2">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Compromissos Terapeuticos Sugeridos
                  </p>
                  <span className="text-[9px] text-slate-500">
                    {displayCommitments.slice(0, 3).length} itens
                  </span>
                </div>
                <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                  {displayCommitments.slice(0, 3).length === 0 && (
                    <p className="text-[10px] text-slate-400">
                      Coletando padroes para sugerir declaracoes de compromisso.
                    </p>
                  )}
                  {displayCommitments.slice(0, 3).map((commitment: any) => {
                    const model = COMMITMENT_TEXTS[Number(commitment.model_id)];
                    if (!model) return null;
                    return (
                      <div
                        key={`commitment-${commitment.model_id}`}
                        className="rounded border border-blue-100 bg-white p-2 text-[10px] text-slate-600"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-blue-800">
                            {model.title}
                          </span>
                          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[9px] font-bold text-blue-700">
                            Zonas: {(commitment.zones || []).join(", ")}
                          </span>
                        </div>
                        <p className="mt-0.5 leading-snug">
                          {model.lines[0]} {model.lines[1] || ""}
                        </p>
                        <FroidTooltip
                          content={
                            <div className="max-w-[340px] space-y-1">
                              <p className="text-xs font-bold text-slate-900">
                                {model.title}
                              </p>
                              {model.lines.map((line, index) => (
                                <p
                                  key={index}
                                  className="text-[11px] leading-snug text-slate-600"
                                >
                                  - {line}
                                </p>
                              ))}
                              <p className="border-t border-slate-100 pt-1 text-[10px] text-slate-400">
                                Baseado nas zonas: {(commitment.zones || []).join(", ")}
                              </p>
                            </div>
                          }
                          width={360}
                        >
                          <button className="mt-1 bg-transparent p-0 text-[9px] font-bold text-blue-600 hover:text-blue-800">
                            Ler declaracao completa
                          </button>
                        </FroidTooltip>
                      </div>
                    );
                  })}
                </div>
              </div>

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
          <div className="row-span-4 flex items-center justify-center text-sm text-slate-400">
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
