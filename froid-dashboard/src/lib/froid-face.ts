// Captura do vídeo do paciente. Interpretação exclusivamente no backend.
// 3 Hz preserva a cadência existente; não certifica captura de microexpressões.
const DEFAULT_VISION_MODULE =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";
const DEFAULT_WASM_BASE =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const DEFAULT_MODEL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export interface FaceCaptureOptions {
  endpoint: string;
  invite?: string;
  token?: string;
  fps?: number;
  visionModuleUrl?: string;
  wasmBaseUrl?: string;
  modelUrl?: string;
  onStatus?: (message: string) => void;
  /** Injeção para testar captura sem rede/modelo externo. */
  loadVision?: () => Promise<any>;
}

export async function startFaceCapture(
  stream: MediaStream,
  opts: FaceCaptureOptions,
): Promise<() => void> {
  const tracks = stream.getVideoTracks();
  if (typeof window === "undefined" || !tracks.length) {
    opts.onStatus?.("Sem capacidade de apuração facial: vídeo indisponível.");
    return () => {};
  }
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let landmarker: any = null;
  let video: HTMLVideoElement | null = null;
  const abort = new AbortController();
  const streamId = crypto.randomUUID();
  const streamStartedAt = Date.now();
  let sequence = 0;
  let lastVideoTime = -1;
  const notify = (message: string) => { if (!stopped) opts.onStatus?.(message); };
  const stop = () => {
    stopped = true;
    abort.abort();
    if (timer) clearTimeout(timer);
    try { landmarker?.close(); } catch { /* captura já foi encerrada */ }
    if (video) video.srcObject = null;
  };

  try {
    notify("Preparando a leitura facial.");
    const vision = opts.loadVision
      ? await opts.loadVision()
      : await import(/* @vite-ignore */ opts.visionModuleUrl || DEFAULT_VISION_MODULE);
    const fileset = await vision.FilesetResolver.forVisionTasks(opts.wasmBaseUrl || DEFAULT_WASM_BASE);
    if (stopped) return stop;
    landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: opts.modelUrl || DEFAULT_MODEL },
      runningMode: "VIDEO",
      numFaces: 1,
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: false,
    });
    if (stopped) { stop(); return stop; }
    video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = new MediaStream([tracks[0]]);
    await video.play();
    const intervalMs = Math.max(150, Math.round(1000 / (opts.fps ?? 3)));

    const tick = async () => {
      if (stopped || !video || !landmarker) return;
      try {
        if (video.readyState >= 2 && video.currentTime > lastVideoTime) {
          lastVideoTime = video.currentTime;
          const capturedAt = performance.now();
          const frame = {
            stream_id: streamId, sequence: ++sequence,
            stream_started_at_ms: streamStartedAt,
            captured_at_ms: capturedAt, video_time_ms: video.currentTime * 1000,
          };
          let blendshapes: Record<string, number> = {};
          let captureStatus = "measured";
          try {
            const categories = landmarker.detectForVideo(video, capturedAt)?.faceBlendshapes?.[0]?.categories;
            if (Array.isArray(categories)) {
              for (const category of categories) {
                if (typeof category?.categoryName === "string" &&
                    typeof category.score === "number" &&
                    Number.isFinite(category.score) && category.score >= 0 && category.score <= 1) {
                  blendshapes[category.categoryName] = category.score;
                }
              }
            }
            if (!Object.keys(blendshapes).length) captureStatus = "no_face";
          } catch {
            captureStatus = "capture_error";
            blendshapes = {};
          }
          if (captureStatus !== "measured") {
            notify("Sem capacidade de apuração facial: rosto ausente ou quadro inválido.");
          }
          // Aguarda o envio: não acumula requisições nem inverte quadros.
          const response = await fetch(opts.endpoint, {
            method: "POST", signal: abort.signal,
            headers: { "Content-Type": "application/json",
              ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}) },
            body: JSON.stringify({ blendshapes, frame, capture_status: captureStatus, invite: opts.invite || "" }),
          });
          if (!response.ok) throw new Error(`Servidor recusou a leitura facial (HTTP ${response.status}).`);
          const body = await response.json();
          if (body.status === "session_inactive") throw new Error("Canal de análise facial inativo.");
          if (body.status === "ignored_frame") throw new Error("Quadro facial repetido ou fora de ordem.");
          notify(body.facial_analysis?.status === "measured" ? ""
            : body.facial_analysis?.reason || "Sem capacidade de apuração facial.");
        }
      } catch (error) {
        notify(error instanceof Error ? error.message : "Falha no envio da leitura facial.");
      } finally {
        if (!stopped) timer = setTimeout(tick, intervalMs);
      }
    };
    void tick();
  } catch (error) {
    notify(error instanceof Error ? `Sem capacidade de apuração facial: ${error.message}`
      : "Sem capacidade de apuração facial: modelo indisponível.");
    stop();
  }
  return stop;
}
