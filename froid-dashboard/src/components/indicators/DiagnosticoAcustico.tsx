import React from "react";

const objeto = (valor: unknown): Record<string, unknown> =>
  valor && typeof valor === "object" ? valor as Record<string, unknown> : {};
const numero = (valor: unknown, casas: number, unidade = "") =>
  typeof valor === "number" && Number.isFinite(valor)
    ? `${valor.toFixed(casas)}${unidade}`
    : "não registrado";
const simNao = (valor: unknown) =>
  valor === true ? "sim" : valor === false ? "não" : "não registrado";

/** Diagnóstico de transporte/detecção, sem interpretar estado clínico. */
export const DiagnosticoAcustico: React.FC<{ diagnostico: unknown }> = ({ diagnostico }) => {
  const d = objeto(diagnostico);
  const captura = objeto(d.captura_cliente);
  return (
    <details className="mt-1 font-normal">
      <summary className="cursor-pointer">Diagnóstico da captura de voz</summary>
      {Object.keys(d).length === 0 ? (
        <p className="m-0">O servidor não informou o diagnóstico desta leitura.</p>
      ) : (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3">
          <dt>Estado da análise</dt><dd>{({
            medida: "voz medida", sem_audio: "sem áudio recente",
            sem_vozeamento: "áudio sem voz reconhecida para os índices",
            analisando: "janela em análise",
          } as Record<string, string>)[String(d.estado)] || "não registrado"}</dd>
          <dt>Nível recebido (RMS)</dt><dd>{numero(d.rms, 5)}</dd>
          <dt>Nível recebido (dBFS)</dt><dd>{numero(d.loudness_dbfs, 1)}</dd>
          <dt>Quadros com voz reconhecida</dt><dd>{typeof d.f0_voiced_ratio === "number"
            ? numero(d.f0_voiced_ratio * 100, 1, "%") : "não registrado"}</dd>
          <dt>Taxa do PCM recebido</dt><dd>{numero(d.sample_rate_hz, 0, " Hz")}</dd>
          <dt>Mesmo microfone da chamada</dt><dd>{simNao(captura.mesmo_dispositivo)}</dd>
          <dt>Áudio sem processamento confirmado</dt><dd>{simNao(captura.audio_bruto)}</dd>
        </dl>
      )}
    </details>
  );
};
