// Captura FACIAL real do FROID: computa, no navegador, os coeficientes de
// blendshape faciais (MediaPipe FaceLandmarker / ARKit, 52 formas) a partir do
// vídeo do paciente e os envia ao backend, que os converte em Unidades de Ação
// (FACS) reais e em dissonâncias faciais.
//
// É TOLERANTE A FALHAS, mas não silencioso: se o modelo não carregar (rede/CSP),
// se não houver vídeo, ou se o navegador não suportar, a captura não inicia e o
// servidor declara `facs_source = "sem_apuracao"` — os campos faciais ficam
// nulos, e a tela e o relatório dizem que não houve apuração. NÃO existe mais
// modo simulado: o gerador foi removido em 03/09/2026, e a ausência de medida
// nunca vira número. O modelo é carregado por import dinâmico de URL (externo
// ao bundle), evitando nova dependência de build.

// Versão fixada do MediaPipe Tasks Vision (pode ser sobrescrita via opções).
const DEFAULT_VISION_MODULE =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";
const DEFAULT_WASM_BASE =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const DEFAULT_MODEL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export interface FaceCaptureOptions {
  endpoint: string; // apiUrl('/api/froid/<id>/facial-aus')
  invite?: string;
  token?: string;
  fps?: number; // taxa de envio (padrão 3 Hz — suficiente e leve)
  visionModuleUrl?: string;
  wasmBaseUrl?: string;
  modelUrl?: string;
}

type Blendshapes = Record<string, number>;

/**
 * Inicia a captura facial a partir de um MediaStream com trilha de vídeo.
 * Retorna uma função de parada (sempre segura de chamar).
 */
export async function startFaceCapture(
  stream: MediaStream,
  opts: FaceCaptureOptions,
): Promise<() => void> {
  const videoTracks = stream.getVideoTracks();
  if (typeof window === "undefined" || !videoTracks.length) return () => {};

  let stopped = false;
  let raf = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let landmarker: any = null;
  let video: HTMLVideoElement | null = null;

  const stop = () => {
    stopped = true;
    if (raf) cancelAnimationFrame(raf);
    if (timer) clearTimeout(timer);
    try {
      landmarker?.close?.();
    } catch {
      /* noop */
    }
    if (video) {
      try {
        video.srcObject = null;
      } catch {
        /* noop */
      }
      video = null;
    }
  };

  try {
    const moduleUrl = opts.visionModuleUrl || DEFAULT_VISION_MODULE;
    // Import dinâmico por variável -> o bundler o trata como externo (não tenta
    // resolvê-lo em build) e o navegador o busca em runtime.
    const vision: any = await import(/* @vite-ignore */ moduleUrl);
    if (stopped) return stop;
    const { FilesetResolver, FaceLandmarker } = vision;
    const fileset = await FilesetResolver.forVisionTasks(
      opts.wasmBaseUrl || DEFAULT_WASM_BASE,
    );
    if (stopped) return stop;
    landmarker = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: opts.modelUrl || DEFAULT_MODEL },
      runningMode: "VIDEO",
      numFaces: 1,
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: false,
    });
    if (stopped) return stop;

    // Elemento de vídeo oculto que serve os quadros ao detector.
    video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = new MediaStream([videoTracks[0]]);
    await video.play().catch(() => undefined);

    const intervalMs = Math.max(150, Math.round(1000 / (opts.fps ?? 3)));

    const send = async (blendshapes: Blendshapes) => {
      try {
        await fetch(opts.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
          },
          body: JSON.stringify({
            blendshapes,
            invite: opts.invite || "",
          }),
        });
      } catch {
        /* falha transitória de rede é ignorada */
      }
    };

    const tick = () => {
      if (stopped || !video || !landmarker) return;
      try {
        if (video.readyState >= 2) {
          const result = landmarker.detectForVideo(video, performance.now());
          const categories = result?.faceBlendshapes?.[0]?.categories;
          if (Array.isArray(categories) && categories.length) {
            const blendshapes: Blendshapes = {};
            for (const c of categories) {
              if (c && typeof c.categoryName === "string") {
                blendshapes[c.categoryName] = Number(c.score) || 0;
              }
            }
            if (Object.keys(blendshapes).length) void send(blendshapes);
          }
        }
      } catch {
        /* um quadro problemático não interrompe a captura */
      }
      if (!stopped) timer = setTimeout(tick, intervalMs);
    };

    tick();
  } catch {
    stop();
    return () => {};
  }

  return stop;
}
