import React, { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { apiUrl, wsUrl } from "../lib/api";
import { createConferenceStream, RTC_CONFIG } from "../lib/webrtc";

type JoinState = "checking" | "joined" | "blocked";
type MediaState = "idle" | "requesting" | "active" | "failed";

export const PatientSessionPage: React.FC = () => {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") || "";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  const [joinState, setJoinState] = useState<JoinState>("checking");
  const [mediaState, setMediaState] = useState<MediaState>("idle");
  const [callStatus, setCallStatus] = useState("Aguardando profissional");
  const [remoteProfessionalOn, setRemoteProfessionalOn] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [error, setError] = useState("");

  const cleanupRtc = () => {
    rtcSignalRef.current?.close();
    rtcSignalRef.current = null;
    rtcPeerRef.current?.close();
    rtcPeerRef.current = null;
    rtcIceQueueRef.current = [];
    setRemoteProfessionalOn(false);
    setCallStatus("Aguardando profissional");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    let active = true;
    if (!sessionId || !inviteToken) {
      setJoinState("blocked");
      setError("Link de sessao incompleto.");
      return;
    }

    fetch(apiUrl(`/api/patient-sessions/${sessionId}/join`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_token: inviteToken }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Sessao indisponivel.");
        return data;
      })
      .then((data) => {
        if (!active) return;
        setPatientName(String(data?.patient_name || ""));
        setJoinState("joined");
      })
      .catch((err) => {
        if (!active) return;
        setJoinState("blocked");
        setError(err instanceof Error ? err.message : "Nao foi possivel entrar.");
      });

    return () => {
      active = false;
      cleanupRtc();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [inviteToken, sessionId]);

  const startPatientRtc = async (localSource: MediaStream) => {
    if (!sessionId || typeof RTCPeerConnection === "undefined") {
      setCallStatus("WebRTC indisponivel neste navegador.");
      return;
    }

    cleanupRtc();
    const localConferenceStream = createConferenceStream(localSource);
    if (!localConferenceStream.getTracks().length) {
      setCallStatus("Audio e video locais indisponiveis para chamada.");
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
      setRemoteProfessionalOn(true);
      setCallStatus("Profissional conectado por audio e video.");
    };

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal({ type: "ice", candidate: event.candidate.toJSON() });
      }
    };

    peer.onconnectionstatechange = () => {
      if (peer.connectionState === "connected") {
        setCallStatus("Audio e video bidirecionais ativos.");
      } else if (["failed", "disconnected"].includes(peer.connectionState)) {
        setRemoteProfessionalOn(false);
        setCallStatus("Conexao com profissional interrompida.");
      } else if (peer.connectionState === "connecting") {
        setCallStatus("Conectando audio e video do profissional...");
      }
    };

    const socket = new WebSocket(wsUrl(`/ws/rtc/${sessionId}/patient`));
    rtcSignalRef.current = socket;

    socket.onopen = () => setCallStatus("Aguardando chamada do profissional...");
    socket.onclose = () => setCallStatus("Sinalizacao de video encerrada.");
    socket.onerror = () => setCallStatus("Falha na sinalizacao de video.");
    socket.onmessage = async (event) => {
      const data = JSON.parse(String(event.data || "{}"));
      if (data.type === "offer" && data.offer) {
        await peer.setRemoteDescription(data.offer);
        await flushIceQueue();
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        sendSignal({ type: "answer", answer: peer.localDescription });
        setCallStatus("Respondendo ao profissional...");
      } else if (data.type === "ice" && data.candidate) {
        if (peer.remoteDescription) {
          await peer.addIceCandidate(data.candidate).catch(() => undefined);
        } else {
          rtcIceQueueRef.current.push(data.candidate);
        }
      } else if (data.type === "peer-left") {
        setRemoteProfessionalOn(false);
        setCallStatus("Profissional saiu da chamada.");
        if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
      }
    };
  };

  const activateMedia = async () => {
    setMediaState("requesting");
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setMediaState("active");
      await startPatientRtc(stream);
    } catch {
      setMediaState("failed");
      setError("Nao foi possivel ativar camera e microfone neste navegador.");
    }
  };

  const statusText =
    joinState === "checking"
      ? "Validando convite..."
      : joinState === "joined"
        ? "Paciente conectado"
        : "Entrada bloqueada";

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-4xl">
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-2xl font-bold">Sala do paciente</h1>
          <p className="mt-1 text-sm text-slate-400">
            {statusText}
            {patientName ? ` - ${patientName}` : ""}
          </p>
        </div>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
          <div className="relative aspect-video overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
            <video
              ref={remoteVideoRef}
              autoPlay
              playsInline
              className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                remoteProfessionalOn ? "opacity-100" : "opacity-0"
              }`}
            />
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
                remoteProfessionalOn
                  ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                  : "inset-0 h-full w-full"
              } ${mediaState === "active" ? "opacity-100" : "opacity-0"}`}
            />
            {mediaState !== "active" && (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-slate-400">
                Camera e microfone aguardando permissao.
              </div>
            )}
            <div
              className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
                remoteProfessionalOn
                  ? "bg-emerald-500/90 text-white"
                  : "bg-slate-950/70 text-slate-200"
              }`}
            >
              {callStatus}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-slate-100">
                Sessao {sessionId}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                O profissional conduz a sessao pelo painel clinico FROID.
              </p>
            </div>
            <button
              type="button"
              onClick={activateMedia}
              disabled={joinState !== "joined" || mediaState === "requesting"}
              className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mediaState === "requesting"
                ? "Ativando..."
                : mediaState === "active"
                  ? "Audio e video ativos"
                  : "Ativar audio e video"}
            </button>
          </div>

          {error && (
            <p className="mt-4 rounded-md border border-red-900/50 bg-red-950/50 px-3 py-2 text-xs font-semibold text-red-200">
              {error}
            </p>
          )}
        </section>
      </main>
    </div>
  );
};
