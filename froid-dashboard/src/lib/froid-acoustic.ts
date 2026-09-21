// Captura de PCM (não comprimido) do microfone para análise acústica do
// FROID. As configurações efetivas declaram se há processamento; evita Opus e
// não depende de decodificador no servidor. Envia janelas de ~1s de PCM
// (Int16 mono, na taxa do AudioContext) ao backend, que mede a F0 real por YIN.
//
// É aditivo e tolerante a falhas: nenhum erro aqui pode derrubar a chamada.
//
// Mas "tolerante a falhas" nao pode significar "silencioso". Em 02/09/2026 uma
// sessao de 24 minutos rodou inteira com o motor em modo SIMULADO — F0 0.00,
// ZCR 0.000, derivadas zeradas — e ninguem foi avisado: o `catch` engolia a
// causa e devolvia uma funcao de parada vazia, indistinguivel de sucesso.
//
// Agora cada caminho de falha se anuncia por `onStatus`. A captura continua
// sem poder quebrar a sessao; o que ela nao pode mais e fracassar em segredo.

import type { CapturaCliente } from "./microfone-de-analise";

// O motor só considera atuais os últimos 4s de PCM. Rede pendurada não pode
// ocupar a fila indefinidamente nem reapresentar essa janela como atual.
export const PCM_VALIDITY_MS = 4_000;

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

/** O que a captura tem a dizer sobre si mesma.
 *
 *  `enviando` confirma transporte de PCM aceito pelo servidor, não vozeamento
 *  nem apuração clínica. Só o motor declara o que conseguiu medir. */
export type StatusCaptura =
  | "sem-audio"
  | "sem-suporte"
  | "aguardando-gesto"
  | "enviando"
  | "sessao-inativa"
  | "erro";

export const STATUS_CAPTURA_TEXTO: Record<StatusCaptura, string> = {
  "sem-audio": "nenhuma trilha de microfone disponivel para analise",
  "sem-suporte": "navegador sem AudioWorklet — analise acustica indisponivel",
  "aguardando-gesto":
    "o navegador suspendeu o audio ate um toque na tela; a analise comeca no primeiro clique",
  enviando: "enviando audio real para analise",
  "sessao-inativa": "o painel do profissional ainda nao abriu a analise",
  erro: "falha na captura ou no envio de audio para analise",
};

export interface F0CaptureOptions {
  endpoint: string; // URL completa do POST (apiUrl('/api/froid/<id>/acoustic-f0'))
  invite?: string;
  token?: string;
  windowSeconds?: number; // janela enviada por requisição (padrão 1.0s)
  capturaCliente?: CapturaCliente;
  /** Chamado quando muda o estado OU seu detalhe. */
  onStatus?: (status: StatusCaptura, detalhe?: string) => void;
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
  let stopped = false;
  let ultimoStatus: StatusCaptura | null = null;
  let ultimoDetalhe: string | undefined;
  const avisar = (status: StatusCaptura, detalhe?: string) => {
    if (stopped || (status === ultimoStatus && detalhe === ultimoDetalhe)) return;
    ultimoStatus = status;
    ultimoDetalhe = detalhe;
    try {
      opts.onStatus?.(status, detalhe);
    } catch {
      /* quem observa nunca pode derrubar quem e observado */
    }
  };

  const audioTracks = stream.getAudioTracks().filter((track) => track.readyState === "live");
  if (typeof window === "undefined" || !audioTracks.length) {
    avisar("sem-audio");
    return () => {};
  }
  const AudioCtx: typeof AudioContext | undefined =
    (window as any).AudioContext || (window as any).webkitAudioContext;
  if (!AudioCtx) {
    avisar("sem-suporte");
    return () => {};
  }

  const track = audioTracks[0];
  let ctx: AudioContext | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let node: AudioWorkletNode | null = null;
  let sink: GainNode | null = null;
  let buffer: number[] = [];
  let soltarGesto: (() => void) | null = null;
  let generation = 0;
  let activeRequest: AbortController | null = null;
  let sequence = 0;
  // ID efêmero de transporte, sem ligação com identidade ou conteúdo clínico.
  const streamId = crypto.randomUUID();
  const queue: Array<{ frame: Float32Array; capturedAt: number; sequence: number }> = [];
  const listeners: Array<() => void> = [];
  const interromperJanelas = () => {
    generation += 1;
    buffer = [];
    queue.length = 0;
    activeRequest?.abort();
  };

  const stop = () => {
    if (stopped) return;
    stopped = true;
    interromperJanelas();
    listeners.splice(0).forEach((remove) => remove());
    soltarGesto?.();
    soltarGesto = null;
    try {
      if (node) {
        node.port.onmessage = null;
        node.onprocessorerror = null;
      }
      node?.disconnect();
      source?.disconnect();
      sink?.disconnect();
      if (ctx && ctx.state !== "closed") void ctx.close().catch(() => undefined);
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
    // Um AudioContext suspenso nao processa NADA — o worklet nunca roda e
    // nenhum PCM sobe. Antes isso passava batido: "segue mesmo assim" seguia
    // para lugar nenhum. Os gestos são instalados ANTES de resume(): alguns
    // navegadores deixam essa Promise pendente até o próprio gesto.
    const contexto = ctx;
    const aguardarGesto = () => {
      if (soltarGesto || stopped) return;
      const retomar = () => {
        void contexto
          .resume()
          .then(() => {
            if (contexto.state === "running") soltarGesto?.();
          })
          .catch(() => avisar("aguardando-gesto", "O navegador não retomou a captura; toque novamente para tentar."));
      };
      soltarGesto = () => {
        document.removeEventListener("pointerdown", retomar);
        document.removeEventListener("keydown", retomar);
        document.removeEventListener("touchstart", retomar);
        soltarGesto = null;
      };
      document.addEventListener("pointerdown", retomar);
      document.addEventListener("keydown", retomar);
      document.addEventListener("touchstart", retomar);
    };
    const verificarContexto = () => {
      if (stopped) return;
      if (contexto.state === "running") {
        soltarGesto?.();
        return;
      }
      interromperJanelas();
      if (contexto.state === "closed") {
        avisar("erro", "O navegador encerrou o processamento de áudio. Reative a captura.");
        stop();
      } else {
        avisar("aguardando-gesto");
        aguardarGesto();
      }
    };
    contexto.addEventListener("statechange", verificarContexto);
    listeners.push(() => contexto.removeEventListener("statechange", verificarContexto));
    verificarContexto();
    if (contexto.state !== "running" && contexto.state !== "closed") {
      void contexto.resume().catch(() => {
        if (!stopped && contexto.state !== "running") verificarContexto();
      });
    }
    const verificarTrilha = () => {
      if (stopped) return;
      interromperJanelas();
      if (track.readyState === "ended") {
        avisar("sem-audio", "A trilha de análise foi encerrada. Reative a captura.");
        stop();
      } else if (track.muted || !track.enabled) {
        avisar("sem-audio", "A trilha de análise está temporariamente sem sinal no navegador.");
      }
    };
    for (const event of ["ended", "mute", "unmute"]) {
      track.addEventListener(event, verificarTrilha);
      listeners.push(() => track.removeEventListener(event, verificarTrilha));
    }
    verificarTrilha();
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
    // Downmix padrão Web Audio: estéreo -> mono (L + R) / 2. Ler só o canal
    // esquerdo descartava integralmente uma voz presente apenas à direita.
    node = new AudioWorkletNode(ctx, "froid-pcm-tap", {
      channelCount: 1,
      channelCountMode: "explicit",
      channelInterpretation: "speakers",
      outputChannelCount: [1],
    });
    node.onprocessorerror = () => {
      avisar("erro", "O processamento do áudio parou no navegador. Reative a captura.");
      stop();
    };

    const windowSamples = Math.max(
      1,
      Math.round(sampleRate * (opts.windowSeconds ?? 1.0)),
    );

    // Envio SERIALIZADO: o servidor concatena cada janela num buffer rolante,
    // então a ordem importa. Sem esta fila, uma oscilação de rede poderia
    // fazer janelas chegarem fora de ordem e corromper a análise temporal
    // (F0/MFCC/envelope calculados sobre um sinal remontado errado).
    let sending = false;
    const enviarFila = async () => {
      if (sending) return;
      sending = true;
      try {
        while (!stopped && queue.length) {
          const janela = queue.shift()!;
          const remaining = PCM_VALIDITY_MS - (performance.now() - janela.capturedAt);
          if (remaining <= 0) {
            avisar("erro", "Áudio não enviado a tempo: janela descartada para não analisar sinal antigo.");
            continue;
          }
          const currentGeneration = generation;
          const controller = new AbortController();
          activeRequest = controller;
          let timedOut = false;
          const timeout = window.setTimeout(() => {
            timedOut = true;
            controller.abort();
          }, remaining);
          let removeAbort = () => {};
          const aborted = new Promise<never>((_resolve, reject) => {
            const cancel = () => reject(new Error("capture-request-aborted"));
            controller.signal.addEventListener("abort", cancel, { once: true });
            removeAbort = () => controller.signal.removeEventListener("abort", cancel);
          });
          try {
            const enviar = async () => {
              const resposta = await fetch(opts.endpoint, {
                method: "POST",
                signal: controller.signal,
                headers: {
                  "Content-Type": "application/json",
                  ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
                },
                body: JSON.stringify({
                  pcm_base64: floatToBase64Int16(janela.frame),
                  sample_rate: sampleRate,
                  invite: opts.invite || "",
                  capture_stream_id: streamId,
                  capture_sequence: janela.sequence,
                  ...(opts.capturaCliente ? { captura_cliente: opts.capturaCliente } : {}),
                }),
              });
              if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
              const corpo = await resposta.json().catch(() => {
                throw new Error("Resposta inválida do servidor: JSON não legível.");
              });
              if (!corpo || typeof corpo !== "object" || typeof corpo.status !== "string") {
                throw new Error("Resposta inválida do servidor: estado da captura ausente.");
              }
              return corpo;
            };
            const corpo = await Promise.race([enviar(), aborted]);
            if (stopped || generation !== currentGeneration) continue;
            // O servidor responde 200 com `session_inactive` quando o painel do
            // profissional ainda nao abriu a analise. Era um sucesso aparente
            // que nao produzia medida nenhuma.
            if (corpo.status === "session_inactive") avisar("sessao-inativa");
            else if (corpo.status !== "ok") avisar("erro", "O servidor não confirmou o recebimento desta janela de áudio.");
            else avisar("enviando");
          } catch (erro) {
            if (!stopped && generation === currentGeneration) {
              avisar("erro", timedOut
                ? "O envio do áudio excedeu 4 segundos; a próxima janela será tentada."
                : erro instanceof Error && (erro.message.startsWith("HTTP ") || erro.message.startsWith("Resposta inválida"))
                  ? erro.message : "Falha de rede ao enviar áudio para análise; a próxima janela será tentada.");
            }
          } finally {
            window.clearTimeout(timeout);
            removeAbort();
            if (activeRequest === controller) activeRequest = null;
          }
        }
      } finally {
        sending = false;
      }
    };
    const flush = () => {
      const frame = Float32Array.from(buffer.splice(0, windowSamples));
      sequence += 1;
      if (queue.length + (sending ? 1 : 0) >= 3) {
        avisar("erro", "Rede atrasada: uma janela de áudio foi descartada, sem interromper a chamada.");
        return;
      }
      queue.push({ frame, sequence, capturedAt: performance.now() });
      void enviarFila();
    };

    node.port.onmessage = (event: MessageEvent) => {
      if (stopped || contexto.state !== "running" || track.readyState !== "live" || track.muted || !track.enabled) return;
      const chunk = event.data as Float32Array;
      for (let i = 0; i < chunk.length; i += 1) buffer.push(chunk[i]);
      while (buffer.length >= windowSamples) flush();
    };

    // Um AudioWorkletNode só processa quando alcança o destino do grafo.
    // Ligamos a um ganho zero -> destino para rodar sem produzir eco audível.
    sink = ctx.createGain();
    sink.gain.value = 0;
    source.connect(node);
    node.connect(sink);
    sink.connect(ctx.destination);
  } catch (erro) {
    avisar("erro", erro instanceof Error ? erro.message : undefined);
    stop();
    return () => {};
  }

  return stop;
}
