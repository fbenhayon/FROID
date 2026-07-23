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
    .filter((track) => track.readyState === "live");
  const liveAudioTracks = remoteStream
    .getAudioTracks()
    .filter((track) => track.readyState === "live");

  if (videoElement) {
    videoElement.muted = true;
    attachTracks(videoElement, liveVideoTracks);
  }
  attachTracks(audioElement, liveAudioTracks);
  return {
    audio: liveAudioTracks.length > 0,
    video: liveVideoTracks.length > 0,
  };
}
