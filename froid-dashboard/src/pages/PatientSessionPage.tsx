import React, { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { apiUrl, wsUrl } from "../lib/api";
import {
  activateRtcRelayFallback,
  attachRemoteMedia,
  configureConferenceSender,
  createConferenceStream,
  loadRtcConfiguration,
  readRtcMediaFlowStats,
  shouldReconnectRtcSignaling,
} from "../lib/webrtc";
import { normalizeSessionLocale, patientCopy, type SessionLocale } from "../lib/localization";

type JoinState = "checking" | "joined" | "blocked";
type MediaState = "idle" | "requesting" | "active" | "failed";

export const PatientSessionPage: React.FC = () => {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") || "";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcRemoteStreamRef = useRef<MediaStream | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  const rtcReconnectTimerRef = useRef<number | null>(null);
  const rtcDisconnectTimerRef = useRef<number | null>(null);
  const rtcMediaHealthTimerRef = useRef<number | null>(null);
  const rtcClosingRef = useRef(false);
  const [joinState, setJoinState] = useState<JoinState>("checking");
  const [mediaState, setMediaState] = useState<MediaState>("idle");
  const [callStatus, setCallStatus] = useState("Aguardando profissional");
  const [remoteProfessionalOn, setRemoteProfessionalOn] = useState(false);
  const [remoteProfessionalVideoOn, setRemoteProfessionalVideoOn] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [error, setError] = useState("");
  const [uiLocale, setUiLocale] = useState<SessionLocale>(() =>
    normalizeSessionLocale(typeof navigator === "undefined" ? "" : navigator.language),
  );
  const copy = patientCopy(uiLocale);

  const cleanupRtc = () => {
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
    setRemoteProfessionalOn(false);
    setRemoteProfessionalVideoOn(false);
    setCallStatus("Aguardando profissional");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  };

  useEffect(() => {
    let active = true;
    if (!sessionId || !inviteToken) {
      setJoinState("blocked");
      setError("Link de sessão incompleto.");
      return;
    }

    fetch(apiUrl(`/api/patient-sessions/${sessionId}/join`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_token: inviteToken }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Sessão indisponível.");
        return data;
      })
      .then((data) => {
        if (!active) return;
        setPatientName(String(data?.patient_name || ""));
        const nextLocale = normalizeSessionLocale(data?.patient_ui_locale, uiLocale);
        setUiLocale(nextLocale);
        document.documentElement.lang = nextLocale;
        setJoinState("joined");
      })
      .catch((err) => {
        if (!active) return;
        setJoinState("blocked");
        setError(err instanceof Error ? err.message : "Não foi possível entrar.");
      });

    return () => {
      active = false;
      cleanupRtc();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [inviteToken, sessionId]);

  const startPatientRtc = async (localSource: MediaStream) => {
    if (!sessionId || typeof RTCPeerConnection === "undefined") {
      setCallStatus("WebRTC indisponível neste navegador.");
      return;
    }

    cleanupRtc();
    rtcClosingRef.current = false;
    const localConferenceStream = createConferenceStream(localSource);
    if (!localConferenceStream.getTracks().length) {
      setCallStatus("Áudio e vídeo locais indisponiveis para chamada.");
      return;
    }

    const peer = new RTCPeerConnection(
      await loadRtcConfiguration({ sessionId, inviteToken }),
    );
    const remoteStream = new MediaStream();
    rtcPeerRef.current = peer;
    rtcRemoteStreamRef.current = remoteStream;

    localConferenceStream.getTracks().forEach((track) => {
      const sender = peer.addTrack(track, localConferenceStream);
      void configureConferenceSender(sender);
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

    const refreshRemoteTracks = () => {
      const media = attachRemoteMedia(
        remoteStream,
        remoteVideoRef.current,
        remoteAudioRef.current,
      );
      setRemoteProfessionalOn(media.audio);
      setRemoteProfessionalVideoOn(media.video);
      setCallStatus(
        media.audio && media.video
          ? "Profissional conectado: áudio e vídeo ativos."
          : media.audio
            ? "Profissional conectado: áudio ativo, aguardando vídeo."
            : media.video
              ? "Profissional conectado: vídeo ativo, aguardando áudio."
              : "Conectado, aguardando mídia do profissional.",
      );
    };

    peer.ontrack = (event) => {
      const incomingTracks = event.streams[0]?.getTracks() || [event.track];
      incomingTracks.forEach((track) => {
        if (!remoteStream.getTracks().some((item) => item.id === track.id)) {
          remoteStream.addTrack(track);
        }
        track.onended = () => {
          remoteStream.removeTrack(track);
          refreshRemoteTracks();
        };
        track.onmute = refreshRemoteTracks;
        track.onunmute = refreshRemoteTracks;
      });
      refreshRemoteTracks();
    };

    let previousFlowStats: Awaited<
      ReturnType<typeof readRtcMediaFlowStats>
    > | null = null;
    let stalledOutboundChecks = 0;
    const monitorPatientOutboundMedia = async () => {
      if (peer.connectionState === "closed") return;
      const current = await readRtcMediaFlowStats(peer).catch(() => null);
      if (!current) return;
      if (!previousFlowStats) {
        previousFlowStats = current;
        return;
      }
      const audioSending =
        current.audioBytesSent > previousFlowStats.audioBytesSent;
      const videoSending =
        current.videoFramesEncoded > previousFlowStats.videoFramesEncoded
        || (
          current.videoFramesEncoded === 0
          && current.videoBytesSent > previousFlowStats.videoBytesSent
        );
      previousFlowStats = current;
      const route = current.candidateType
        ? ` · rota ${current.candidateType}`
        : "";
      if (audioSending && videoSending) {
        stalledOutboundChecks = 0;
        setCallStatus(`Transmitindo áudio e vídeo ao profissional${route}.`);
        return;
      }
      if (peer.connectionState !== "connected") return;
      stalledOutboundChecks += 1;
      setCallStatus(
        `Conexão ativa, mas mídia sem saída (${stalledOutboundChecks}/3)${route}.`,
      );
      if (stalledOutboundChecks < 3) return;
      stalledOutboundChecks = 0;
      const relayActivated = activateRtcRelayFallback(peer);
      if (relayActivated) {
        peer.restartIce();
        setCallStatus("Rota direta sem mídia; ativando o relay TURN protegido...");
        sendSignal({ type: "renegotiate-request" });
        return;
      }
      setMediaState("failed");
      setError(
        "A chamada conectou sem transmitir câmera e microfone. Toque em Ativar câmera e microfone para reconstruir a conexão.",
      );
      sendSignal({ type: "renegotiate-request" });
    };
    if (rtcMediaHealthTimerRef.current) {
      window.clearInterval(rtcMediaHealthTimerRef.current);
    }
    rtcMediaHealthTimerRef.current = window.setInterval(
      () => void monitorPatientOutboundMedia(),
      2_000,
    );

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal({ type: "ice", candidate: event.candidate.toJSON() });
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
        sendSignal({ type: "renegotiate-request" });
        setRemoteProfessionalOn(false);
        setRemoteProfessionalVideoOn(false);
        setCallStatus("Reconectando áudio e vídeo do profissional...");
      } else if (peer.connectionState === "disconnected") {
        setCallStatus("Mídia instável; tentando reconectar...");
        if (!rtcDisconnectTimerRef.current) {
          rtcDisconnectTimerRef.current = window.setTimeout(() => {
            rtcDisconnectTimerRef.current = null;
            if (peer.connectionState === "disconnected") {
              peer.restartIce();
              sendSignal({ type: "renegotiate-request" });
            }
          }, 3_000);
        }
      } else if (peer.connectionState === "connecting") {
        setCallStatus("Conectando áudio e vídeo do profissional...");
      }
    };

    let reconnectAttempt = 0;
    const handleSignal = async (event: MessageEvent) => {
      const data = JSON.parse(String(event.data || "{}"));
      if (data.type === "offer" && data.offer) {
        if (peer.signalingState !== "stable") return;
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
        remoteStream.getTracks().forEach((track) => {
          track.stop();
          remoteStream.removeTrack(track);
        });
        setRemoteProfessionalOn(false);
        setRemoteProfessionalVideoOn(false);
        setCallStatus("Profissional saiu da chamada.");
        if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
        if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
      }
    };

    let signalQueue: Promise<void> = Promise.resolve();
    const connectSignaling = () => {
      if (rtcClosingRef.current || peer.connectionState === "closed") return;
      const socket = new WebSocket(
        wsUrl(
          `/ws/rtc/${sessionId}/patient?invite=${encodeURIComponent(inviteToken)}`,
        ),
      );
      rtcSignalRef.current = socket;
      socket.onopen = () => {
        reconnectAttempt = 0;
        setCallStatus("Aguardando chamada do profissional...");
      };
      socket.onmessage = (event) => {
        signalQueue = signalQueue
          .then(() => handleSignal(event))
          .catch(() => {
            setCallStatus("Sincronizando novamente a chamada...");
            sendSignal({ type: "renegotiate-request" });
          });
      };
      socket.onerror = () => socket.close();
      socket.onclose = (event) => {
        if (rtcClosingRef.current || peer.connectionState === "closed") return;
        if (!shouldReconnectRtcSignaling(event.code, reconnectAttempt, peer.connectionState)) {
          setCallStatus("Não foi possível manter a conexão. Atualize o link da sessão.");
          return;
        }
        const delay = Math.min(4_000, 500 * 2 ** reconnectAttempt);
        reconnectAttempt += 1;
        setCallStatus("Reconectando sinalização da chamada...");
        rtcReconnectTimerRef.current = window.setTimeout(connectSignaling, delay);
      };
    };
    connectSignaling();
  };

  const activateMedia = async () => {
    if (mediaState === "active" || mediaState === "requesting") return;
    setMediaState("requesting");
    setError("");
    try {
      void loadRtcConfiguration({ sessionId, inviteToken });
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const video = {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 24, max: 30 },
        facingMode: "user",
      } satisfies MediaTrackConstraints;
      const audio = {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      } satisfies MediaTrackConstraints;
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video, audio });
      } catch {
        const tracks: MediaStreamTrack[] = [];
        try {
          const audioCapture = await navigator.mediaDevices.getUserMedia({
            audio,
            video: false,
          });
          tracks.push(...audioCapture.getAudioTracks());
        } catch {
          // Continue para permitir diagnóstico e nova tentativa da câmera.
        }
        try {
          const videoCapture = await navigator.mediaDevices.getUserMedia({
            video,
            audio: false,
          });
          tracks.push(...videoCapture.getVideoTracks());
        } catch {
          // A interface informa exatamente qual trilha não foi liberada.
        }
        if (!tracks.length) throw new Error("camera-and-microphone-unavailable");
        stream = new MediaStream(tracks);
      }
      streamRef.current = stream;
      stream.getTracks().forEach((track) => {
        let muteTimer: number | null = null;
        const markCaptureUnavailable = () => {
          if (track.readyState !== "live" || track.muted) {
            setMediaState("failed");
            setError(
              track.kind === "video"
                ? "A câmera parou de transmitir. Toque em Ativar câmera e microfone para reconectar."
                : "O microfone parou de transmitir. Toque em Ativar câmera e microfone para reconectar.",
            );
          }
        };
        track.onended = markCaptureUnavailable;
        track.onmute = () => {
          if (muteTimer) window.clearTimeout(muteTimer);
          muteTimer = window.setTimeout(markCaptureUnavailable, 2_000);
        };
        track.onunmute = () => {
          if (muteTimer) window.clearTimeout(muteTimer);
          muteTimer = null;
        };
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      const hasAudio = stream.getAudioTracks().some(
        (track) => track.readyState === "live" && track.enabled && !track.muted,
      );
      const hasVideo = stream.getVideoTracks().some(
        (track) => track.readyState === "live" && track.enabled && !track.muted,
      );
      if (!hasAudio || !hasVideo) {
        setError(
          hasAudio
            ? "Microfone ativo, mas a câmera não foi liberada. Verifique a permissão do navegador."
            : "Câmera ativa, mas o microfone não foi liberado. Verifique a permissão do navegador.",
        );
      }
      setMediaState(hasAudio && hasVideo ? "active" : "failed");
      await startPatientRtc(stream);
    } catch {
      setMediaState("failed");
      setError("Não foi possível ativar câmera e microfone neste navegador.");
    }
  };

  const statusText =
    joinState === "checking"
      ? copy.checking
      : joinState === "joined"
        ? copy.connected
        : copy.blocked;

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-4xl">
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-2xl font-bold">{copy.patientRoom}</h1>
          {uiLocale !== "pt-BR" && (
            <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-amber-300">
              {copy.pilotNotice}
            </p>
          )}
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
              muted
              className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                remoteProfessionalVideoOn ? "opacity-100" : "opacity-0"
              }`}
            />
            <audio ref={remoteAudioRef} autoPlay className="hidden" />
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
                remoteProfessionalVideoOn
                  ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                  : "inset-0 h-full w-full"
              } ${mediaState === "active" ? "opacity-100" : "opacity-0"}`}
            />
            {mediaState !== "active" && (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-slate-400">
                {copy.mediaPermission}
              </div>
            )}
            <div
              className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
                remoteProfessionalOn || remoteProfessionalVideoOn
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
                Sessão {sessionId}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                O profissional conduz a sessão pelo painel clínico FROID.
              </p>
            </div>
            <button
              type="button"
              onClick={activateMedia}
              disabled={joinState !== "joined" || mediaState === "requesting" || mediaState === "active"}
              className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mediaState === "requesting"
                ? copy.enablingMedia
                : mediaState === "active"
                  ? copy.mediaActive
                  : copy.enableMedia}
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
