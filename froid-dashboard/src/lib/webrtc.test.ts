import { afterEach, describe, expect, it, vi } from "vitest";
import {
  adoptRemoteTrack,
  attachRemoteMedia,
  evaluateInboundFlow,
  evaluateOutboundFlow,
  shouldReconnectRtcSignaling,
  type RtcMediaFlowStats,
} from "./webrtc";

let trackCounter = 0;

class FakeTrack {
  id: string;
  kind: "audio" | "video";
  readyState: "live" | "ended" = "live";
  enabled = true;
  muted = false;
  stopped = false;
  constructor(kind: "audio" | "video", overrides: Partial<FakeTrack> = {}) {
    this.id = `${kind}-${(trackCounter += 1)}`;
    this.kind = kind;
    Object.assign(this, overrides);
  }
  stop() {
    this.stopped = true;
    this.readyState = "ended";
  }
}

class FakeMediaStream {
  private tracks: FakeTrack[];
  constructor(tracks: FakeTrack[] = []) {
    this.tracks = [...tracks];
  }
  getTracks() {
    return [...this.tracks];
  }
  getAudioTracks() {
    return this.tracks.filter((track) => track.kind === "audio");
  }
  getVideoTracks() {
    return this.tracks.filter((track) => track.kind === "video");
  }
  addTrack(track: FakeTrack) {
    if (!this.tracks.some((item) => item.id === track.id)) this.tracks.push(track);
  }
  removeTrack(track: FakeTrack) {
    this.tracks = this.tracks.filter((item) => item.id !== track.id);
  }
}

class FakeMediaElement {
  srcObject: unknown = null;
  muted = false;
  play = vi.fn(() => Promise.resolve());
}

vi.stubGlobal("MediaStream", FakeMediaStream);

const asStream = (stream: FakeMediaStream) => stream as unknown as MediaStream;
const asTrack = (track: FakeTrack) => track as unknown as MediaStreamTrack;
const asVideo = (element: FakeMediaElement) => element as unknown as HTMLVideoElement;
const asAudio = (element: FakeMediaElement) => element as unknown as HTMLAudioElement;

const stats = (over: Partial<RtcMediaFlowStats> = {}): RtcMediaFlowStats => ({
  audioBytesReceived: 0,
  videoBytesReceived: 0,
  videoFramesDecoded: 0,
  audioBytesSent: 0,
  videoBytesSent: 0,
  videoFramesEncoded: 0,
  candidateType: "",
  ...over,
});

afterEach(() => {
  trackCounter = 0;
});

describe("evaluateInboundFlow", () => {
  it("retorna null sem amostra anterior (sem falso positivo no primeiro tick)", () => {
    expect(evaluateInboundFlow(null, stats({ audioBytesReceived: 100 }))).toBeNull();
  });

  it("detecta áudio e vídeo fluindo por frames decodificados", () => {
    const prev = stats({ audioBytesReceived: 100, videoFramesDecoded: 10 });
    const next = stats({ audioBytesReceived: 200, videoFramesDecoded: 12 });
    expect(evaluateInboundFlow(prev, next)).toEqual({ audioFlowing: true, videoFlowing: true });
  });

  it("reconhece vídeo por bytes quando ainda não há frames decodificados", () => {
    const prev = stats({ videoFramesDecoded: 0, videoBytesReceived: 500 });
    const next = stats({ videoFramesDecoded: 0, videoBytesReceived: 900 });
    expect(evaluateInboundFlow(prev, next)?.videoFlowing).toBe(true);
  });

  it("não considera vídeo vivo quando frames e bytes estão parados", () => {
    const prev = stats({ videoFramesDecoded: 12, videoBytesReceived: 900 });
    const next = stats({ videoFramesDecoded: 12, videoBytesReceived: 900 });
    const flow = evaluateInboundFlow(prev, next);
    expect(flow?.videoFlowing).toBe(false);
    expect(flow?.audioFlowing).toBe(false);
  });

  it("marca só áudio quando o vídeo travou (falha parcial)", () => {
    const prev = stats({ audioBytesReceived: 100, videoFramesDecoded: 5 });
    const next = stats({ audioBytesReceived: 200, videoFramesDecoded: 5 });
    expect(evaluateInboundFlow(prev, next)).toEqual({ audioFlowing: true, videoFlowing: false });
  });
});

describe("evaluateOutboundFlow", () => {
  it("detecta envio por frames codificados", () => {
    const prev = stats({ audioBytesSent: 100, videoFramesEncoded: 4 });
    const next = stats({ audioBytesSent: 180, videoFramesEncoded: 7 });
    expect(evaluateOutboundFlow(prev, next)).toEqual({ audioFlowing: true, videoFlowing: true });
  });

  it("marca só vídeo quando o áudio parou de sair", () => {
    const prev = stats({ audioBytesSent: 100, videoFramesEncoded: 4 });
    const next = stats({ audioBytesSent: 100, videoFramesEncoded: 9 });
    expect(evaluateOutboundFlow(prev, next)).toEqual({ audioFlowing: false, videoFlowing: true });
  });
});

describe("adoptRemoteTrack", () => {
  it("substitui a trilha antiga do mesmo tipo, parando-a (impede mistura)", () => {
    const oldVideo = new FakeTrack("video");
    const stream = new FakeMediaStream([oldVideo]);
    const newVideo = new FakeTrack("video");

    const added = adoptRemoteTrack(asStream(stream), asTrack(newVideo));

    expect(added).toBe(true);
    expect(stream.getVideoTracks()).toHaveLength(1);
    expect(stream.getVideoTracks()[0].id).toBe(newVideo.id);
    expect(oldVideo.stopped).toBe(true);
  });

  it("não mexe em trilhas de outro tipo ao adotar vídeo", () => {
    const audio = new FakeTrack("audio");
    const oldVideo = new FakeTrack("video");
    const stream = new FakeMediaStream([audio, oldVideo]);
    const newVideo = new FakeTrack("video");

    adoptRemoteTrack(asStream(stream), asTrack(newVideo));

    expect(stream.getAudioTracks()).toHaveLength(1);
    expect(audio.stopped).toBe(false);
    expect(stream.getVideoTracks()).toHaveLength(1);
  });

  it("é idempotente quando a mesma trilha reentra", () => {
    const video = new FakeTrack("video");
    const stream = new FakeMediaStream([video]);

    const added = adoptRemoteTrack(asStream(stream), asTrack(video));

    expect(added).toBe(false);
    expect(stream.getVideoTracks()).toHaveLength(1);
    expect(video.stopped).toBe(false);
  });
});

describe("attachRemoteMedia", () => {
  it("anexa no máximo uma trilha de vídeo viva mesmo com duas presentes", () => {
    const staleVideo = new FakeTrack("video");
    const freshVideo = new FakeTrack("video");
    const stream = new FakeMediaStream([staleVideo, freshVideo]);
    const videoEl = new FakeMediaElement();

    const result = attachRemoteMedia(asStream(stream), asVideo(videoEl), null);

    expect(result.video).toBe(true);
    const attached = videoEl.srcObject as unknown as FakeMediaStream;
    expect(attached.getVideoTracks()).toHaveLength(1);
    expect(attached.getVideoTracks()[0].id).toBe(freshVideo.id);
  });

  it("ignora trilhas não vivas, desabilitadas ou mudas", () => {
    const dead = new FakeTrack("video", { readyState: "ended" });
    const muted = new FakeTrack("audio", { muted: true });
    const stream = new FakeMediaStream([dead, muted]);
    const videoEl = new FakeMediaElement();
    const audioEl = new FakeMediaElement();

    const result = attachRemoteMedia(asStream(stream), asVideo(videoEl), asAudio(audioEl));

    expect(result).toEqual({ audio: false, video: false });
    expect(videoEl.srcObject).toBeNull();
    expect(audioEl.srcObject).toBeNull();
  });
});

describe("shouldReconnectRtcSignaling", () => {
  it("nunca reconecta em códigos terminais de autorização", () => {
    for (const code of [1008, 4000, 4401, 4402, 4403]) {
      expect(shouldReconnectRtcSignaling(code, 0, "connected")).toBe(false);
    }
  });

  it("reconecta sempre que a conexão de mídia já está estabelecida", () => {
    expect(shouldReconnectRtcSignaling(1006, 99, "connected")).toBe(true);
  });

  it("reconecta nas tentativas iniciais e desiste após o teto", () => {
    expect(shouldReconnectRtcSignaling(1006, 7, "connecting")).toBe(true);
    expect(shouldReconnectRtcSignaling(1006, 8, "connecting")).toBe(false);
  });
});
