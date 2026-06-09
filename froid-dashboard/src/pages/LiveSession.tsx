import React, { useEffect, useReducer, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import { CoherenceLine } from "../components/indicators/CoherenceLine";
import { RiskChart } from "../components/indicators/RiskChart";
import { SubharmonicChart } from "../components/indicators/SubharmonicChart";
import { MediaStatus } from "../components/indicators/MediaStatus";
import { SessionTimer } from "../components/indicators/SessionTimer";
import { ClinicalNotes } from "../components/panels/ClinicalNotes";
import { AIInsights } from "../components/panels/AIInsights";
import { AudioTranscription } from "../components/panels/AudioTranscription";
import { CommitmentPanel } from "../components/panels/CommitmentPanel";
import { FroidPayload, PerceptionZone } from "../lib/froid-engine";
import { getAUDetails, ZONE_CLINICAL_DESCRIPTIONS } from "../lib/froid-data";

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
  | { type: "END_SESSION" };

function reducer(state: SessionState, action: Action): SessionState {
  try {
    switch (action.type) {
      case "WS_OPEN":
        return { ...state, connected: true };
      case "WS_CLOSE":
        return {
          ...state,
          connected: false,
          phase: state.phase === "ENDED" ? "ENDED" : "LIVE",
        };
      case "TICK":
        return state.phase === "CALIBRATING"
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
      case "END_SESSION":
        return { ...state, phase: "ENDED", connected: false };
      default:
        return state;
    }
  } catch {
    return state;
  }
}

const initialState: SessionState = {
  connected: false,
  payload: null,
  baselineIPM: null,
  elapsedSeconds: 0,
  phase: "CALIBRATING",
  ipmHistory: [],
  cameraOn: false,
  micOn: false,
  sessionStart: Date.now(),
  camError: "",
  aggregated: null,
};

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

function LiveSessionInner() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(reducer, initialState);
  const bufferRef = useRef<{ ipm: number[] }>({ ipm: [] });
  const frameBuffer = useRef<FroidPayload[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const id = setInterval(() => dispatch({ type: "TICK" }), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (state.elapsedSeconds >= 60 && state.phase === "CALIBRATING") {
      const avg =
        bufferRef.current.ipm.length > 0
          ? bufferRef.current.ipm.reduce((a, b) => a + b, 0) /
            bufferRef.current.ipm.length
          : 0;
      dispatch({ type: "BASELINE_LOCK", ipm: avg });
    }
  }, [state.elapsedSeconds, state.phase]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      const wsUrl =
        ((import.meta as any).env?.VITE_WS_URL ||
          "ws://localhost:8000" ||
          "ws://localhost:8000") +
        "/ws/fusion/" +
        (sessionId || "default");
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => dispatch({ type: "WS_OPEN" });
      ws.onclose = () => dispatch({ type: "WS_CLOSE" });
      ws.onerror = () => {};
      ws.onmessage = (event) => {
        try {
          const data: FroidPayload = JSON.parse(event.data);
          if (
            state.phase === "CALIBRATING" &&
            typeof data?.ipm_score === "number"
          )
            bufferRef.current.ipm.push(data.ipm_score);
          dispatch({ type: "PAYLOAD", data });
          frameBuffer.current.push(data);
          if (frameBuffer.current.length > 6) frameBuffer.current.shift();
        } catch (err) {
          console.error("Parse WS:", err);
        }
      };
    } catch {
      dispatch({ type: "END_SESSION" });
    }
    return () => {
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

  const endSession = () => {
    if (wsRef.current)
      try {
        wsRef.current.close();
      } catch {}
    dispatch({ type: "END_SESSION" });
    setTimeout(() => navigate("/dashboard"), 400);
  };

  const agg = state.aggregated;
  const raw = state.payload;
  const displayZones = agg?.zones || raw?.perception_zones || [];
  const displayIpm = agg?.ipm || raw?.ipm_score || 0;
  const displayDrValue = agg?.drValue ?? (raw as any)?.dr_value ?? null;
  const displayCoherence = agg?.coherence || raw?.coherence_status || "NEUTRO";
  const displayAlerts = agg?.alerts || raw?.realtime_alerts || [];
  const displayAudio = agg?.audioMeta ||
    (raw as any)?.audio_meta || {
      words_per_window: 0,
      total_words_session: 0,
      emotional_tone: "neutro",
      transcription_snippet: "",
      session_theme: "",
      theme_minute_mark: 0,
      words_per_minute_10m: 0,
    };
  const displayCommitments =
    agg?.commitments || (raw as any)?.commitment_models || [];

  const connectionText = state.connected
    ? state.phase === "CALIBRATING"
      ? "Sincronia Inicial"
      : "Ao Vivo"
    : state.phase === "ENDED"
      ? "Encerrada"
      : "Desconectado";

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

        <AudioTranscription
          snippet={displayAudio.transcription_snippet}
          wordsCount={displayAudio.words_per_window}
          totalWords={displayAudio.total_words_session}
          tone={displayAudio.emotional_tone}
          wordsPerMinute10m={displayAudio.words_per_minute_10m || 0}
          sessionTheme={displayAudio.session_theme}
          themeMinuteMark={displayAudio.theme_minute_mark}
        />

        <CommitmentPanel commitments={displayCommitments} />

        {state.phase === "CALIBRATING" && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-700 shrink-0">
            <p className="font-bold">Fase de Repouso Ativa</p>
            <p>Coletando baseline: {state.elapsedSeconds}s / 60s</p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
              <div
                className="h-full bg-blue-600 transition-all duration-1000"
                style={{ width: (state.elapsedSeconds / 60) * 100 + "%" }}
              />
            </div>
          </div>
        )}

        <div className="flex-1 min-h-0 flex flex-col gap-3">
          <ClinicalNotes />
          <div className="flex-1 min-h-[200px]">
            <AIInsights
              zones={displayZones}
              ipmScore={displayIpm}
              coherenceStatus={displayCoherence}
              baselineEstablished={state.phase === "LIVE"}
            />
          </div>
        </div>
      </div>

      {/* COLUNA 2 — 34%: Vídeo (50%) + Mapa Zonal (50%) */}
      <div className="w-[34%] flex flex-col gap-0 bg-white shadow-inner overflow-hidden">
        {/* Vídeo — 50% do espaço */}
        <div className="h-1/2 relative rounded-xl bg-slate-900 overflow-hidden flex items-center justify-center border-b border-slate-200">
          <MediaStatus
            cameraOn={true}
            micOn={state.connected}
            simulated={true}
          />
          <SimulatedCamera />
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
      <div className="flex-1 flex flex-col gap-2 bg-slate-50 p-3 overflow-y-auto">
        {raw ? (
          <>
            <IPMLineChart
              data={state.ipmHistory}
              current={displayIpm}
              baseline={state.baselineIPM || undefined}
            />
            <CoherenceLine status={displayCoherence} />
            <RiskChart
              zones={displayZones}
              ipmScore={displayIpm}
              coherenceStatus={displayCoherence}
            />
            <SubharmonicChart zones={displayZones} />

            <div className="flex-1 overflow-y-auto rounded-xl border border-slate-100 bg-white p-4 shadow-sm min-h-[140px]">
              <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                Dissonâncias Identificadas (Média 10s)
                {displayZones.some((z) => !!z?.facial_dissonance_detected) && (
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                )}
              </h3>

              {(!Array.isArray(displayZones) ||
                displayZones.filter((z) => !!z?.facial_dissonance_detected)
                  .length === 0) && (
                <p className="text-xs italic text-slate-400">
                  Nenhuma dissonância facial-vocal crítica persistente nos
                  últimos 10 segundos.
                </p>
              )}

              {Array.isArray(displayZones) &&
                displayZones
                  .filter(
                    (z) =>
                      !!z?.facial_dissonance_detected &&
                      !!z?.dissonance_details,
                  )
                  .map((zone) => {
                    const aus = zone.dissonance_details?.active_aus || [];
                    const auDescs = getAUDetails(aus);
                    return (
                      <div
                        key={zone.zone}
                        className="mb-3 rounded-r-lg border-l-4 border-red-600 bg-red-50 p-4"
                      >
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-bold text-red-900">
                            Zona {zone.zone} — {zone.tema || ""}
                          </p>
                          <span className="text-[9px] font-bold text-white bg-red-600 px-1.5 py-0.5 rounded">
                            IDM {zone.deviation_score?.toFixed(2)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-slate-700 font-medium">
                          {ZONE_CLINICAL_DESCRIPTIONS[zone.zone] || ""}
                        </p>
                        <p className="mt-2 text-xs leading-relaxed text-red-700 font-semibold">
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

              <div className="mt-4 space-y-2">
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
          <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
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

export function LiveSession() {
  return (
    <ErrorGuard>
      <LiveSessionInner />
    </ErrorGuard>
  );
}
