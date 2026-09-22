import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startF0Capture, PCM_VALIDITY_MS } from "./froid-acoustic";
import { selecionarMicrofoneDeAnalise, configuracaoDaCaptura } from "./microfone-de-analise";

class Track extends EventTarget {
  readyState = "live";
  enabled = true;
  muted = false;
  stop = vi.fn(() => { this.readyState = "ended"; });
  constructor(public settings: MediaTrackSettings = {}) { super(); }
  getSettings() { return this.settings; }
}
class Stream {
  constructor(public tracks: Track[]) {}
  getAudioTracks() { return this.tracks; }
  getTracks() { return this.tracks; }
}
const asStream = (s: Stream) => s as unknown as MediaStream;
const rawSettings = { deviceId: "microfone-da-chamada", echoCancellation: false,
  noiseSuppression: false, autoGainControl: false, sampleRate: 48000, channelCount: 2 };
const request = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };

describe("a análise usa o mesmo dispositivo efetivo da chamada", () => {
  it("fixa deviceId e informa as configurações observadas sem expor identificadores", async () => {
    const call = new Stream([new Track(rawSettings)]);
    const candidate = new Stream([new Track(rawSettings)]);
    const get = vi.fn(async () => asStream(candidate));
    const result = await selecionarMicrofoneDeAnalise(asStream(call), request, get);
    expect(get).toHaveBeenCalledWith({ video: false, audio: { ...request, deviceId: { exact: rawSettings.deviceId } } });
    expect(result.stream).toBe(candidate);
    expect(configuracaoDaCaptura(rawSettings, result.mesmoDispositivo)).toEqual({
      mesmo_dispositivo: true, audio_bruto: true, canais: 2, taxa_amostragem: 48000,
      echo_cancellation: false, noise_suppression: false, auto_gain_control: false,
    });
    expect(call.tracks[0].stop).not.toHaveBeenCalled();
  });
  it.each([
    { ...rawSettings, deviceId: "outro-microfone" },
    { ...rawSettings, autoGainControl: true },
    { deviceId: rawSettings.deviceId },
  ])("recusa fonte/configuração não confirmada e fecha apenas a captura candidata", async (settings) => {
    const call = new Stream([new Track(rawSettings)]);
    const candidate = new Stream([new Track(settings)]);
    const result = await selecionarMicrofoneDeAnalise(asStream(call), request, async () => asStream(candidate));
    expect(result.stream).toBeNull();
    expect(result.motivo).not.toBe("");
    expect(candidate.tracks[0].stop).toHaveBeenCalledOnce();
    expect(call.tracks[0].stop).not.toHaveBeenCalled();
  });
  it("sem identificação não abre outro microfone por padrão", async () => {
    const get = vi.fn();
    const result = await selecionarMicrofoneDeAnalise(asStream(new Stream([new Track()])), request, get);
    expect(result.stream).toBeNull();
    expect(get).not.toHaveBeenCalled();
    expect(configuracaoDaCaptura({}, true).echo_cancellation).toBeNull();
  });
  it("permissão recusada mantém o áudio existente", async () => {
    const track = new Track(rawSettings);
    const result = await selecionarMicrofoneDeAnalise(asStream(new Stream([track])), request,
      async () => { throw new Error("NotAllowedError"); });
    expect(result.stream).toBeNull();
    expect(track.stop).not.toHaveBeenCalled();
  });
});

let initialState = "running";
let workletSupported = true;
const contexts: Context[] = [];
const nodes: Worklet[] = [];
class Context extends EventTarget {
  state = initialState;
  sampleRate = 48000;
  destination = {};
  audioWorklet = workletSupported ? { addModule: vi.fn(async () => {}) } : undefined;
  close = vi.fn(async () => { this.state = "closed"; });
  resume = vi.fn(() => this.state === "running" ? Promise.resolve() : new Promise<void>(() => {}));
  constructor() { super(); contexts.push(this); }
  createMediaStreamSource() { return { connect: vi.fn(), disconnect: vi.fn() }; }
  createGain() { return { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() }; }
}
class Worklet {
  port = { onmessage: null as null | ((event: { data: Float32Array }) => void) };
  onprocessorerror: null | (() => void) = null;
  connect = vi.fn();
  disconnect = vi.fn();
  constructor(_ctx: Context, _name: string, public options: AudioWorkletNodeOptions) { nodes.push(this); }
}
const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
const emit = () => nodes[0].port.onmessage?.({ data: new Float32Array(480).fill(0.25) });
let stop: (() => void) | undefined;
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  initialState = "running"; workletSupported = true; contexts.length = 0; nodes.length = 0;
  vi.stubGlobal("window", { AudioContext: Context, setTimeout, clearTimeout });
  vi.stubGlobal("document", new EventTarget());
  vi.stubGlobal("MediaStream", Stream);
  vi.stubGlobal("AudioWorkletNode", Worklet);
  vi.stubGlobal("crypto", { randomUUID: () => "stream-test" });
  vi.stubGlobal("fetch", vi.fn(async () => response({ status: "processed" })));
});
afterEach(() => { stop?.(); stop = undefined; vi.unstubAllGlobals(); vi.useRealTimers(); });
async function start(track = new Track()) {
  const onStatus = vi.fn();
  stop = await startF0Capture(asStream(new Stream([track])), {
    endpoint: "/acoustic-f0", windowSeconds: 0.01, onStatus,
    capturaCliente: configuracaoDaCaptura(rawSettings, true),
  });
  return { onStatus, track, ctx: contexts[0] };
}

describe("o PCM enviado e a resposta usam o contrato real do servidor", () => {
  it("processed confirma envio, usa a taxa efetiva e entrega captura_cliente", async () => {
    const c = await start();
    emit(); await settle();
    expect(c.onStatus).toHaveBeenLastCalledWith("enviando", undefined);
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string);
    expect(body.sample_rate).toBe(48000);
    expect(body.capture_sequence).toBeGreaterThan(0);
    expect(body.capture_stream_id).toBe("stream-test");
    expect(body.captura_cliente.mesmo_dispositivo).toBe(true);
    expect(body.captura_cliente).not.toHaveProperty("deviceId");
    expect(atob(body.pcm_base64).length).toBe(960);
    expect(nodes[0].options).toMatchObject({ channelCount: 1, channelCountMode: "explicit", channelInterpretation: "speakers" });
  });
  it.each([null, {}, { status: "superseded" }])("200 com corpo %j não confirma envio", async (body) => {
    vi.mocked(fetch).mockResolvedValue(response(body) as Response);
    const c = await start(); emit(); await settle();
    expect(c.onStatus.mock.calls.at(-1)?.[0]).toBe("erro");
  });
  it("sessão inativa permanece distinta de falha de rede", async () => {
    vi.mocked(fetch).mockResolvedValue(response({ status: "session_inactive" }) as Response);
    const c = await start(); emit(); await settle();
    expect(c.onStatus).toHaveBeenLastCalledWith("sessao-inativa", undefined);
  });
  it("erro de rede após sucesso aparece e a próxima janela recupera", async () => {
    const c = await start(); emit(); await settle();
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network"));
    emit(); await settle();
    expect(c.onStatus.mock.calls.at(-1)?.[0]).toBe("erro");
    emit(); await settle();
    expect(c.onStatus).toHaveBeenLastCalledWith("enviando", undefined);
  });
  it("requisição pendurada expira e libera a fila", async () => {
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => {}));
    const c = await start(); emit(); await settle();
    const signal = vi.mocked(fetch).mock.calls[0][1]!.signal!;
    await vi.advanceTimersByTimeAsync(PCM_VALIDITY_MS);
    expect(signal.aborted).toBe(true);
    expect(c.onStatus.mock.calls.at(-1)?.[0]).toBe("erro");
    emit(); await settle();
    expect(c.onStatus).toHaveBeenLastCalledWith("enviando", undefined);
  });
  it("encerrar aborta envio e não aceita sucesso tardio nem para a chamada", async () => {
    let resolve!: (value: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
    const c = await start(); emit(); await settle();
    const signal = vi.mocked(fetch).mock.calls[0][1]!.signal!;
    stop!(); resolve(response({ status: "processed" }) as Response); await settle();
    expect(signal.aborted).toBe(true);
    expect(c.onStatus).not.toHaveBeenCalledWith("enviando", undefined);
    expect(c.track.stop).not.toHaveBeenCalled();
    expect(c.ctx.close).toHaveBeenCalledOnce();
  });
  it("suspensão inicial não trava inicialização nem impede gesto de retomada", async () => {
    initialState = "suspended";
    const c = await start();
    expect(c.onStatus).toHaveBeenCalledWith("aguardando-gesto", undefined);
    c.ctx.resume.mockImplementation(async () => { c.ctx.state = "running"; c.ctx.dispatchEvent(new Event("statechange")); });
    document.dispatchEvent(new Event("pointerdown")); await settle();
    emit(); await settle();
    expect(c.onStatus).toHaveBeenLastCalledWith("enviando", undefined);
  });
  it("mute cria lacuna de sequência mesmo se durar menos que quatro segundos", async () => {
    const c = await start(); emit(); await settle();
    const before = JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string).capture_sequence;
    c.track.muted = true; c.track.dispatchEvent(new Event("mute"));
    expect(c.onStatus.mock.calls.at(-1)?.[0]).toBe("sem-audio");
    c.track.muted = false; c.track.dispatchEvent(new Event("unmute")); emit(); await settle();
    const after = JSON.parse(vi.mocked(fetch).mock.calls[1][1]!.body as string).capture_sequence;
    expect(after).toBeGreaterThan(before + 1);
    expect(c.track.stop).not.toHaveBeenCalled();
  });
  it("trilha desabilitada informa ausência durante processamento", async () => {
    const c = await start(); emit(); await settle();
    c.track.enabled = false; emit(); await settle();
    expect(c.onStatus.mock.calls.at(-1)?.[0]).toBe("sem-audio");
  });
  it("navegador sem worklet declara falta de suporte", async () => {
    workletSupported = false;
    const c = await start();
    expect(c.onStatus).toHaveBeenLastCalledWith("sem-suporte", undefined);
    expect(fetch).not.toHaveBeenCalled();
  });
});
