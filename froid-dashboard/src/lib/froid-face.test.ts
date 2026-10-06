import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startFaceCapture } from "./froid-face";

describe("captura facial: quadros distintos e degradação visível", () => {
  let video: { readyState: number; currentTime: number; play: ReturnType<typeof vi.fn>; srcObject: unknown };
  let fetcher: ReturnType<typeof vi.fn>;
  let detect: ReturnType<typeof vi.fn>;
  let close: ReturnType<typeof vi.fn>;
  let stop: (() => void) | undefined;
  const notify = vi.fn();
  const track = { stop: vi.fn() };
  const stream = { getVideoTracks: () => [track] } as unknown as MediaStream;
  const response = () => ({ ok: true, json: async () => ({ status: "accepted",
    facial_analysis: { status: "measured" } }) });
  const vision = () => Promise.resolve({
    FilesetResolver: { forVisionTasks: async () => ({}) },
    FaceLandmarker: { createFromOptions: async () => ({ detectForVideo: detect, close }) },
  });
  const opts = () => ({ endpoint: "/facial-aus", invite: "patient-invite", onStatus: notify, loadVision: vision });
  beforeEach(() => {
    vi.useFakeTimers();
    notify.mockClear();
    track.stop.mockClear();
    video = { readyState: 2, currentTime: 1, play: vi.fn(async () => {}), srcObject: null };
    detect = vi.fn(() => ({ faceBlendshapes: [{ categories: [
      { categoryName: "mouthSmileLeft", score: 0.6 }, { categoryName: "mouthSmileRight", score: 0.6 },
    ] }] }));
    close = vi.fn();
    fetcher = vi.fn(async () => response());
    vi.stubGlobal("window", {});
    vi.stubGlobal("document", { createElement: () => video });
    vi.stubGlobal("crypto", { randomUUID: () => "distinct-stream-id" });
    vi.stubGlobal("MediaStream", class {});
    vi.stubGlobal("fetch", fetcher);
  });
  afterEach(() => {
    stop?.();
    stop = undefined;
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
  it("o mesmo tempo de vídeo não produz outro envio", async () => {
    stop = await startFaceCapture(stream, opts());
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(detect).toHaveBeenCalledTimes(1);
  });
  it("novo quadro identifica fluxo, sequência e tempo", async () => {
    stop = await startFaceCapture(stream, opts());
    await vi.advanceTimersByTimeAsync(0);
    video.currentTime = 2;
    await vi.advanceTimersByTimeAsync(333);
    expect(fetcher).toHaveBeenCalledTimes(2);
    const first = JSON.parse(fetcher.mock.calls[0][1].body);
    const second = JSON.parse(fetcher.mock.calls[1][1].body);
    expect(first.frame.stream_id).toBe("distinct-stream-id");
    expect(second.frame.sequence).toBe(first.frame.sequence + 1);
    expect(second.frame.video_time_ms).toBeGreaterThan(first.frame.video_time_ms);
    expect(first.invite).toBe("patient-invite");
    stop();
    expect(track.stop).not.toHaveBeenCalled();
    expect(close).toHaveBeenCalled();
  });
  it("não sobrepõe envios enquanto a rede está pendente", async () => {
    let release!: (value: ReturnType<typeof response>) => void;
    fetcher.mockImplementation(() => new Promise(resolve => { release = resolve; }));
    stop = await startFaceCapture(stream, opts());
    video.currentTime = 2;
    await vi.advanceTimersByTimeAsync(2000);
    expect(fetcher).toHaveBeenCalledTimes(1);
    release(response());
    await vi.advanceTimersByTimeAsync(0);
  });
  it("ausência de rosto é enviada e informada, não silêncio", async () => {
    detect.mockReturnValue({ faceBlendshapes: [] });
    fetcher.mockResolvedValue({ ok: true, json: async () => ({
      status: "accepted", facial_analysis: { status: "unavailable", reason: "Rosto ausente." },
    }) });
    stop = await startFaceCapture(stream, opts());
    await vi.advanceTimersByTimeAsync(0);
    expect(JSON.parse(fetcher.mock.calls[0][1].body).capture_status).toBe("no_face");
    expect(notify).toHaveBeenLastCalledWith("Rosto ausente.");
  });
  it("HTTP recusado fica visível", async () => {
    fetcher.mockResolvedValue({ ok: false, status: 401 });
    stop = await startFaceCapture(stream, opts());
    await vi.advanceTimersByTimeAsync(0);
    expect(notify).toHaveBeenLastCalledWith("Servidor recusou a leitura facial (HTTP 401).");
  });
  it("modelo indisponível fica visível", async () => {
    stop = await startFaceCapture(stream, { ...opts(), loadVision: async () => { throw new Error("Modelo bloqueado."); } });
    expect(notify).toHaveBeenLastCalledWith("Sem capacidade de apuração facial: Modelo bloqueado.");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("valor inválido não é substituído por zero", async () => {
    detect.mockReturnValue({ faceBlendshapes: [{ categories: [
      { categoryName: "mouthSmileLeft", score: Number.NaN },
      { categoryName: "mouthSmileRight", score: 0 },
    ] }] });
    stop = await startFaceCapture(stream, opts());
    await vi.advanceTimersByTimeAsync(0);
    const body = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(body.blendshapes).toEqual({ mouthSmileRight: 0 });
  });
});
