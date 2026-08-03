import { apiUrl } from "./api";

export const DEFAULT_RTC_CONFIG: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  bundlePolicy: "max-bundle",
  rtcpMuxPolicy: "require",
  iceCandidatePoolSize: 4,
};

type RtcConfigurationAccess = {
  sessionId: string;
  professionalToken?: string;
  inviteToken?: string;
};

type CachedRtcConfiguration = {
  expiresAt: number;
  promise: Promise<RTCConfiguration>;
};

const rtcConfigurationPromises = new Map<string, CachedRtcConfiguration>();

const TERMINAL_SIGNALING_CLOSE_CODES = new Set([1008, 4000, 4401, 4402, 4403]);
const MAX_INITIAL_SIGNALING_RECONNECTS = 8;

export function shouldReconnectRtcSignaling(
  closeCode: number,
  reconnectAttempt: number,
  connectionState: RTCPeerConnectionState,
) {
  if (TERMINAL_SIGNALING_CLOSE_CODES.has(closeCode)) return false;
  return connectionState === "connected"
    || reconnectAttempt < MAX_INITIAL_SIGNALING_RECONNECTS;
}

export function loadRtcConfiguration(
  access: RtcConfigurationAccess,
): Promise<RTCConfiguration> {
  const cacheKey = `${access.sessionId}:${access.professionalToken ? "professional" : "patient"}`;
  const now = Date.now();
  const cached = rtcConfigurationPromises.get(cacheKey);
  if (cached && cached.expiresAt > now) return cached.promise;
  if (cached) rtcConfigurationPromises.delete(cacheKey);
  const query = new URLSearchParams({ session_id: access.sessionId });
  if (access.inviteToken) query.set("invite", access.inviteToken);
  const request = fetch(apiUrl(`/api/rtc/config?${query.toString()}`), {
    cache: "no-store",
    headers: access.professionalToken
      ? { Authorization: `Bearer ${access.professionalToken}` }
      : undefined,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error("RTC configuration unavailable");
      const payload = await response.json();
      const iceServers = Array.isArray(payload?.iceServers)
        ? payload.iceServers.filter((server: RTCIceServer) => server?.urls)
        : [];
      const credentialExpiresAt = Number(payload?.credentialExpiresAt || 0) * 1000;
      const safeExpiry = credentialExpiresAt > now
        ? Math.max(now + 30_000, credentialExpiresAt - 60_000)
        : now + 5 * 60_000;
      const current = rtcConfigurationPromises.get(cacheKey);
      if (current) current.expiresAt = safeExpiry;
      return {
        iceServers: iceServers.length ? iceServers : DEFAULT_RTC_CONFIG.iceServers,
        iceTransportPolicy: payload?.iceTransportPolicy === "relay" ? "relay" : "all",
        bundlePolicy: "max-bundle",
        rtcpMuxPolicy: "require",
        iceCandidatePoolSize: 4,
      } satisfies RTCConfiguration;
    })
    .catch(() => {
      rtcConfigurationPromises.delete(cacheKey);
      return DEFAULT_RTC_CONFIG;
    });
  rtcConfigurationPromises.set(cacheKey, {
    expiresAt: now + 60_000,
    promise: request,
  });
  return request;
}

export type ScreenWakeLock = { release: () => Promise<void> };

// Numa sessão celular-para-celular (paciente e profissional usando o
// próprio telefone), o bloqueio automático de tela suspende a captura de
// câmera/microfone e trava os laços de análise em tempo real — sem aviso
// nenhum na interface. Pedimos o wake lock enquanto a mídia está ativa; a
// API o libera sozinha quando a aba perde foco, então cada chamador deve
// tentar readquirir no "visibilitychange" enquanto a sessão seguir ativa.
export async function requestScreenWakeLock(): Promise<ScreenWakeLock | null> {
  const nav = navigator as Navigator & {
    wakeLock?: { request: (type: "screen") => Promise<ScreenWakeLock> };
  };
  if (!nav.wakeLock?.request) return null;
  try {
    return await nav.wakeLock.request("screen");
  } catch {
    return null;
  }
}

export function createConferenceStream(source: MediaStream) {
  const stream = new MediaStream();
  const audioTrack = source
    .getAudioTracks()
    .find((track) => track.readyState === "live");
  const videoTrack = source
    .getVideoTracks()
    .find((track) => track.readyState === "live");

  if (audioTrack) stream.addTrack(audioTrack);
  if (videoTrack) stream.addTrack(videoTrack);
  return stream;
}

export function activateRtcRelayFallback(peer: RTCPeerConnection) {
  const configuration = peer.getConfiguration();
  if (configuration.iceTransportPolicy === "relay") return false;
  const hasTurn = (configuration.iceServers || []).some((server) => {
    const urls = Array.isArray(server.urls) ? server.urls : [server.urls];
    return urls.some((url) => String(url || "").toLowerCase().startsWith("turn"));
  });
  if (!hasTurn) return false;
  try {
    peer.setConfiguration({
      ...configuration,
      iceTransportPolicy: "relay",
    });
    return true;
  } catch {
    return false;
  }
}

export async function configureConferenceSender(sender: RTCRtpSender) {
  const track = sender.track;
  if (!track) return;
  track.contentHint = track.kind === "audio" ? "speech" : "motion";
  const parameters = sender.getParameters();
  if (!parameters.encodings?.length) parameters.encodings = [{}];
  if (track.kind === "video") {
    parameters.degradationPreference = "maintain-framerate";
    parameters.encodings = parameters.encodings.map((encoding) => ({
      ...encoding,
      maxBitrate: 1_500_000,
      maxFramerate: 24,
    }));
  } else {
    parameters.encodings = parameters.encodings.map((encoding) => ({
      ...encoding,
      maxBitrate: 64_000,
    }));
  }
  await sender.setParameters(parameters).catch(() => undefined);
}

export function adoptRemoteTrack(
  remoteStream: MediaStream,
  track: MediaStreamTrack,
) {
  const sameKindTracks = track.kind === "audio"
    ? remoteStream.getAudioTracks()
    : remoteStream.getVideoTracks();
  let alreadyPresent = false;
  sameKindTracks.forEach((existing) => {
    if (existing.id === track.id) {
      alreadyPresent = true;
      return;
    }
    // Uma trilha nova do mesmo tipo substitui a anterior; manter as duas
    // deixa o elemento de mídia renderizando a trilha antiga/congelada.
    existing.stop();
    remoteStream.removeTrack(existing);
  });
  if (!alreadyPresent) remoteStream.addTrack(track);
  return !alreadyPresent;
}

function sameTrackSet(element: HTMLMediaElement, tracks: MediaStreamTrack[]) {
  const current = element.srcObject instanceof MediaStream
    ? element.srcObject.getTracks().map((track) => track.id).sort()
    : [];
  const next = tracks.map((track) => track.id).sort();
  return current.length === next.length
    && current.every((trackId, index) => trackId === next[index]);
}

function attachTracks(
  element: HTMLMediaElement | null,
  tracks: MediaStreamTrack[],
) {
  if (!element || sameTrackSet(element, tracks)) return;
  element.srcObject = tracks.length ? new MediaStream(tracks) : null;
  if (tracks.length) void element.play().catch(() => undefined);
}

export function attachRemoteMedia(
  remoteStream: MediaStream,
  videoElement: HTMLVideoElement | null,
  audioElement: HTMLAudioElement | null,
) {
  const liveVideoTracks = remoteStream
    .getVideoTracks()
    .filter(
      (track) =>
        track.readyState === "live"
        && track.enabled
        && !track.muted,
    );
  const liveAudioTracks = remoteStream
    .getAudioTracks()
    .filter(
      (track) =>
        track.readyState === "live"
        && track.enabled
        && !track.muted,
    );

  // Renderiza no máximo uma trilha por tipo (a mais recente): um <video> só
  // exibe uma trilha do stream, e a antiga venceria a nova se permanecesse.
  if (videoElement) {
    videoElement.muted = true;
    attachTracks(videoElement, liveVideoTracks.slice(-1));
  }
  attachTracks(audioElement, liveAudioTracks.slice(-1));
  return {
    audio: liveAudioTracks.length > 0,
    video: liveVideoTracks.length > 0,
  };
}

export type RtcMediaFlowStats = {
  audioBytesReceived: number;
  videoBytesReceived: number;
  videoFramesDecoded: number;
  audioBytesSent: number;
  videoBytesSent: number;
  videoFramesEncoded: number;
  candidateType: string;
};

export type MediaFlowDelta = {
  audioFlowing: boolean;
  videoFlowing: boolean;
};

export function evaluateInboundFlow(
  previous: RtcMediaFlowStats | null,
  current: RtcMediaFlowStats,
): MediaFlowDelta | null {
  if (!previous) return null;
  return {
    audioFlowing: current.audioBytesReceived > previous.audioBytesReceived,
    videoFlowing:
      current.videoFramesDecoded > previous.videoFramesDecoded
      || (
        current.videoFramesDecoded === 0
        && current.videoBytesReceived > previous.videoBytesReceived
      ),
  };
}

export function evaluateOutboundFlow(
  previous: RtcMediaFlowStats | null,
  current: RtcMediaFlowStats,
): MediaFlowDelta | null {
  if (!previous) return null;
  return {
    audioFlowing: current.audioBytesSent > previous.audioBytesSent,
    videoFlowing:
      current.videoFramesEncoded > previous.videoFramesEncoded
      || (
        current.videoFramesEncoded === 0
        && current.videoBytesSent > previous.videoBytesSent
      ),
  };
}

export async function readRtcMediaFlowStats(
  peer: RTCPeerConnection,
): Promise<RtcMediaFlowStats> {
  const result: RtcMediaFlowStats = {
    audioBytesReceived: 0,
    videoBytesReceived: 0,
    videoFramesDecoded: 0,
    audioBytesSent: 0,
    videoBytesSent: 0,
    videoFramesEncoded: 0,
    candidateType: "",
  };
  const reports = await peer.getStats();
  let selectedPair: any = null;
  let selectedPairId = "";
  reports.forEach((report: any) => {
    const kind = String(report.kind || report.mediaType || "");
    if (report.type === "inbound-rtp" && !report.isRemote) {
      if (kind === "audio") {
        result.audioBytesReceived += Number(report.bytesReceived || 0);
      } else if (kind === "video") {
        result.videoBytesReceived += Number(report.bytesReceived || 0);
        result.videoFramesDecoded += Number(report.framesDecoded || 0);
      }
    } else if (report.type === "outbound-rtp" && !report.isRemote) {
      if (kind === "audio") {
        result.audioBytesSent += Number(report.bytesSent || 0);
      } else if (kind === "video") {
        result.videoBytesSent += Number(report.bytesSent || 0);
        result.videoFramesEncoded += Number(report.framesEncoded || 0);
      }
    } else if (
      report.type === "candidate-pair"
      && report.state === "succeeded"
      && (report.nominated || report.selected)
    ) {
      selectedPair = report;
    } else if (report.type === "transport" && report.selectedCandidatePairId) {
      selectedPairId = String(report.selectedCandidatePairId);
    }
  });
  if (!selectedPair && selectedPairId) selectedPair = reports.get(selectedPairId);
  if (selectedPair) {
    const local = reports.get(selectedPair.localCandidateId) as any;
    const remote = reports.get(selectedPair.remoteCandidateId) as any;
    result.candidateType = [
      local?.candidateType || "",
      remote?.candidateType || "",
    ].filter(Boolean).join("/");
  }
  return result;
}
