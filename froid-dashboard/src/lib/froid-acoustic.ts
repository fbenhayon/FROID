// Captura de PCM cru (não comprimido) do microfone para análise acústica do
// FROID — a rota mais correta cientificamente: evita a perda do Opus/WebRTC e
// não depende de decodificador no servidor. Envia janelas de ~1s de PCM
// (Int16 mono, na taxa do AudioContext) ao backend, que mede a F0 real por YIN.
//
// É aditivo e tolerante a falhas: qualquer erro (permissão, CSP de worklet,
// rede) apenas interrompe silenciosamente a captura sem afetar a sessão.

const WORKLET_CODE = `
class FroidPcmTap extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      // Copia o canal mono do bloco atual (128 amostras) para a thread principal.
      this.port.postMessage(input[0].slice(0));
    }
    return true;
  }
}
registerProcessor('froid-pcm-tap', FroidPcmTap);
`;

export interface F0CaptureOptions {
  endpoint: string; // URL completa do POST (apiUrl('/api/froid/<id>/acoustic-f0'))
  invite?: string;
  token?: string;
  windowSeconds?: number; // janela enviada por requisição (padrão 1.0s)
}

function floatToBase64Int16(frame: Float32Array): string {
  const int16 = new Int16Array(frame.length);
  for (let i = 0; i < frame.length; i += 1) {
    const s = Math.max(-1, Math.min(1, frame[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(bytes.subarray(i, i + chunk)) as unknown as number[],
    );
  }
  return btoa(binary);
}

/**
 * Inicia a captura de PCM do stream e o envio periódico ao backend.
 * Retorna uma função de parada (sempre segura de chamar).
 */
export async function startF0Capture(
  stream: MediaStream,
  opts: F0CaptureOptions,
): Promise<() => void> {
  const audioTracks = stream.getAudioTracks();
  if (typeof window === "undefined" || !audioTracks.length) return () => {};
  const AudioCtx: typeof AudioContext | undefined =
    (window as any).AudioContext || (window as any).webkitAudioContext;
  if (!AudioCtx) return () => {};

  let stopped = false;
  let ctx: AudioContext | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let node: AudioWorkletNode | null = null;
  let sink: GainNode | null = null;
  let buffer: number[] = [];

  const stop = () => {
    stopped = true;
    try {
      if (node) node.port.onmessage = null;
      node?.disconnect();
      source?.disconnect();
      sink?.disconnect();
      if (ctx && ctx.state !== "closed") void ctx.close();
    } catch {
      /* noop */
    }
  };

  try {
    // Solicita 16 kHz (Nyquist 8 kHz cobre a F0 até 400 Hz com folga). Se o
    // navegador não honrar, usamos ctx.sampleRate real — o backend recebe a
    // taxa efetiva e o cálculo permanece correto.
    ctx = new AudioCtx({ sampleRate: 16000 });
    const sampleRate = ctx.sampleRate;
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {
        /* alguns navegadores exigem gesto do usuário; segue mesmo assim */
      }
    }
    source = ctx.createMediaStreamSource(new MediaStream([audioTracks[0]]));

    const blob = new Blob([WORKLET_CODE], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    try {
      await ctx.audioWorklet.addModule(url);
    } finally {
      URL.revokeObjectURL(url);
    }
    if (stopped) {
      stop();
      return stop;
    }
    node = new AudioWorkletNode(ctx, "froid-pcm-tap");

    const windowSamples = Math.max(
      1,
      Math.round(sampleRate * (opts.windowSeconds ?? 1.0)),
    );

    // Envio SERIALIZADO: o servidor concatena cada janela num buffer rolante,
    // então a ordem importa. Sem esta fila, uma oscilação de rede poderia
    // fazer janelas chegarem fora de ordem e corromper a análise temporal
    // (F0/MFCC/envelope calculados sobre um sinal remontado errado).
    let sendChain: Promise<void> = Promise.resolve();
    let pendingSends = 0;

    const flush = () => {
      if (!buffer.length) return;
      const frame = Float32Array.from(buffer);
      buffer = [];
      // Descarta a janela se houver acúmulo (rede muito lenta): manter o
      // tempo real é preferível a processar áudio obsoleto em atraso crescente.
      if (pendingSends >= 3) return;
      pendingSends += 1;
      const pcmBase64 = floatToBase64Int16(frame);
      sendChain = sendChain
        .then(async () => {
          if (stopped) return;
          try {
            await fetch(opts.endpoint, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
              },
              body: JSON.stringify({
                pcm_base64: pcmBase64,
                sample_rate: sampleRate,
                invite: opts.invite || "",
              }),
            });
          } catch {
            /* falha transitória de rede é ignorada */
          }
        })
        .finally(() => {
          pendingSends -= 1;
        });
    };

    node.port.onmessage = (event: MessageEvent) => {
      if (stopped) return;
      const chunk = event.data as Float32Array;
      for (let i = 0; i < chunk.length; i += 1) buffer.push(chunk[i]);
      if (buffer.length >= windowSamples) flush();
    };

    // Um AudioWorkletNode só processa quando alcança o destino do grafo.
    // Ligamos a um ganho zero -> destino para rodar sem produzir eco audível.
    sink = ctx.createGain();
    sink.gain.value = 0;
    source.connect(node);
    node.connect(sink);
    sink.connect(ctx.destination);
  } catch {
    stop();
    return () => {};
  }

  return stop;
}
