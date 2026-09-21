/** Configuração observada no navegador; nunca contém nome ou ID do microfone. */
export interface CapturaCliente {
  mesmo_dispositivo: boolean | null;
  audio_bruto: boolean;
  canais: number | null;
  taxa_amostragem: number | null;
  echo_cancellation: boolean | null;
  noise_suppression: boolean | null;
  auto_gain_control: boolean | null;
}

const booleano = (value: unknown): boolean | null =>
  typeof value === "boolean" ? value : null;
const numero = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;

export function configuracaoDaCaptura(
  ajustes: MediaTrackSettings,
  mesmoDispositivo: boolean | null,
): CapturaCliente {
  return {
    mesmo_dispositivo: mesmoDispositivo,
    audio_bruto: ajustes.echoCancellation === false
      && ajustes.noiseSuppression === false && ajustes.autoGainControl === false,
    canais: numero(ajustes.channelCount),
    taxa_amostragem: numero(ajustes.sampleRate),
    echo_cancellation: booleano(ajustes.echoCancellation),
    noise_suppression: booleano(ajustes.noiseSuppression),
    auto_gain_control: booleano(ajustes.autoGainControl),
  };
}

export function ajustesDoMicrofone(track?: MediaStreamTrack): MediaTrackSettings {
  try { return track?.getSettings?.() || {}; } catch { return {}; }
}

/** null significa usar a própria trilha da chamada, sem transferir sua posse. */
export async function selecionarMicrofoneDeAnalise(
  chamada: MediaStream,
  constraints: MediaTrackConstraints,
  obterMedia: (constraints: MediaStreamConstraints) => Promise<MediaStream> =
    (pedido) => navigator.mediaDevices.getUserMedia(pedido),
): Promise<{ stream: MediaStream | null; motivo: string; mesmoDispositivo: boolean | null }> {
  const original = chamada.getAudioTracks().find((track) => track.readyState === "live");
  const fallback = (motivo: string) => ({
    stream: null, motivo, mesmoDispositivo: original ? true : null,
  });
  const deviceId = ajustesDoMicrofone(original).deviceId;
  if (!original || !deviceId) {
    return fallback("Análise usando a trilha da chamada: o navegador não identificou o microfone para uma captura separada.");
  }
  let candidato: MediaStream | null = null;
  try {
    candidato = await obterMedia({
      video: false,
      audio: { ...constraints, deviceId: { exact: deviceId } },
    });
    const track = candidato.getAudioTracks()[0];
    const ajustes = ajustesDoMicrofone(track);
    if (!track || track.readyState !== "live" || !track.enabled
      || ajustes.deviceId !== deviceId || !configuracaoDaCaptura(ajustes, true).audio_bruto
      || candidato.getTracks().some((item) => chamada.getTracks().includes(item))) {
      // Só fechamos trilhas que abrimos; nunca o microfone ou a câmera da chamada.
      candidato.getTracks().forEach((item) => {
        if (!chamada.getTracks().includes(item)) item.stop();
      });
      return fallback("Análise usando a trilha da chamada: não foi possível confirmar captura sem processamento no mesmo microfone.");
    }
    return { stream: candidato, motivo: "", mesmoDispositivo: true };
  } catch {
    candidato?.getTracks().forEach((item) => {
      if (!chamada.getTracks().includes(item)) item.stop();
    });
    return fallback("Análise usando a trilha da chamada: a captura separada do mesmo microfone não pôde ser aberta.");
  }
}
