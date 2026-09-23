import React, { useMemo } from "react";
import { AcousticBiomarkers } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

interface Props {
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
  locale?: SessionLocale;
}

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

// AUSENCIA NAO E ZERO — e nas derivadas isso aparecia na tela.
//
// As quatro derivadas cepstrais passavam por um `read` que devolvia 0 para
// o que nao veio, e eram impressas com `.toFixed(4)`: `DMFCC7 0.0000`, com a
// mesma tipografia de uma medida real de zero. Em 22/09/2026 os quatro campos
// apareceram cravados em 0.0000 numa sessao inteira.
//
// O servidor ja declara ausencia com null nesses campos. Aqui ela passa a ser
// impressa, e nao convertida.
const lerOuAusente = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const derivada = (valor: number | null) =>
  valor === null ? "sem apuração" : valor.toFixed(4);

const percent = (value: number) => Math.round(clamp(value) * 100);

export const SpectralBandsChart: React.FC<Props> = ({ audioMeta, locale = "pt-BR" }) => {
  const metrics = useMemo(
    () => [
      {
        label: "Delta",
        band: "0.5-4 Hz",
        value: lerOuAusente(audioMeta, "spectral_delta_0_4hz"),
        color: "#7DD3FC",
        tooltip:
          "Modulações mais lentas do envelope vocal: 0,5 a 4 oscilações por segundo.",
      },
      {
        label: "Theta",
        band: "4-8 Hz",
        value: lerOuAusente(audioMeta, "spectral_theta_4_8hz"),
        color: "#A5B4FC",
        tooltip:
          "Modulações de 4 a 8 oscilações por segundo, acima da faixa Delta.",
      },
      {
        label: "Alpha",
        band: "8-12 Hz",
        value: lerOuAusente(audioMeta, "spectral_alpha_8_12hz"),
        color: "#6EE7B7",
        tooltip:
          "Modulações de 8 a 12 oscilações por segundo, entre Theta e Beta.",
      },
      {
        label: "Beta",
        band: "12-30 Hz",
        value: lerOuAusente(audioMeta, "spectral_beta_12_30hz"),
        color: "#FBBF24",
        tooltip:
          "Modulações rápidas do envelope vocal: 12 a 30 oscilações por segundo.",
      },
      {
        label: "Gama",
        band: "30-80 Hz",
        value: lerOuAusente(audioMeta, "spectral_gamma_30_80hz"),
        color: "#FB7185",
        tooltip:
          "Modulações mais rápidas entre as faixas exibidas: 30 a 80 oscilações por segundo.",
      },
    ],
    [audioMeta],
  );

  const index = lerOuAusente(audioMeta, "spectral_band_index");
  const mfcc7Delta = lerOuAusente(audioMeta, "mfcc7_delta");
  const mfcc9Delta = lerOuAusente(audioMeta, "mfcc9_delta");
  const mfcc7DeltaDelta = lerOuAusente(audioMeta, "mfcc7_delta_delta");
  const mfcc9DeltaDelta = lerOuAusente(audioMeta, "mfcc9_delta_delta");
  const hasData = metrics.some((metric) => metric.value !== null);
  const windowMs = lerOuAusente(audioMeta, "bioacoustic_window_ms");

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      <div className="mb-1.5 flex shrink-0 items-start justify-between gap-3">
        <div>
          <FroidTooltip
            width={360}
            content={
              <div>
                <p className="font-bold text-slate-100">{tooltipText(locale, "Bandas neuroacústicas")}</p>
                <p className="mt-1">
                  {tooltipText(
                    locale,
                    "Distribuição da energia de modulação do envelope vocal por faixa de frequência. O envelope acompanha as variações de amplitude da voz; Hz indica oscilações por segundo. As bandas não são uma medição de EEG.",
                  )}
                </p>
              </div>
            }
          >
            <h3 className="cursor-help text-[13px] font-black text-slate-100">
              Bandas neuroacústicas
            </h3>
          </FroidTooltip>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            Janela bioacústica: {windowMs === null ? "não informada" : `${windowMs} ms`}
          </p>
        </div>
        <FroidTooltip
          width={300}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Índice geral das bandas")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Média aritmética das cinco bandas, calculada pelo motor e apresentada em percentual. Não é a soma das bandas nem uma classificação clínica.",
                )}
              </p>
            </div>
          }
        >
          <div className="shrink-0 cursor-help rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
            <p className="text-[8px] font-black uppercase">Índice geral</p>
            <p className="font-mono text-[12px] font-black">{index === null ? "sem apuração" : `${percent(index)}%`}</p>
          </div>
        </FroidTooltip>
      </div>

      <p className="mb-2 text-[10px] leading-relaxed text-slate-300">
        Energia por faixa de modulação da voz · escala fixa de 0–100%.
        Não mede ondas cerebrais nem determina, isoladamente, um estado emocional.
      </p>
      <div className="flex shrink-0 flex-col gap-2">
        {metrics.map((metric) => (
          <FroidTooltip
            key={metric.label}
            fullWidth
            width={340}
            content={
              <div>
                <p className="font-bold text-slate-100">
                  {metric.label} | {metric.band}
                </p>
                <p className="mt-1">{tooltipText(locale, metric.tooltip)}</p>
              </div>
            }
          >
            <div className="min-w-0 rounded-md border border-slate-800 bg-slate-900/60 px-2 py-1.5">
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="font-bold" style={{ color: metric.color }}>
                  {metric.label} <span className="font-normal text-slate-400">{metric.band}</span>
                </span>
                <strong className="font-mono">
                  {metric.value === null ? "sem apuração" : `${percent(metric.value)}%`}
                </strong>
              </div>
              <div className="my-1 h-2 overflow-hidden rounded-full bg-slate-800">
                {metric.value !== null && <div
                  role="meter"
                  aria-label={`${metric.label}: energia na faixa`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent(metric.value)}
                  className="h-full rounded-full"
                  style={{ width: `${clamp(metric.value) * 100}%`, backgroundColor: metric.color }}
                />}
              </div>
              <p className="text-[10px] leading-snug text-slate-400">{metric.tooltip}</p>
            </div>
          </FroidTooltip>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-700 pt-2 font-mono text-[9px] text-slate-300">
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔMFCC7 — velocidade do MFCC7")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Primeira derivada do coeficiente cepstral MFCC7: a taxa de variacao do coeficiente ao longo do tempo. O FROID a acompanha em fala de valencia negativa. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DMFCC7 {derivada(mfcc7Delta)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔMFCC9 — velocidade do MFCC9")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Primeira derivada do coeficiente cepstral MFCC9: taxa de variacao ao longo do tempo. Quedas em discurso neutro sao descritas na literatura como correlato de tensao laringea. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DMFCC9 {derivada(mfcc9Delta)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔΔMFCC7 — aceleração do MFCC7")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Segunda derivada do MFCC7: captura mudanças bruscas na trajetória do timbre. Realça transições rápidas de estado emocional, não apenas o nível sustentado.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DDMFCC7 {derivada(mfcc7DeltaDelta)}</span>
        </FroidTooltip>
        <FroidTooltip
          width={320}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "ΔΔMFCC9 — aceleração do MFCC9")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Segunda derivada do MFCC9: a aceleracao da variacao do coeficiente ao longo da fala. Descreve dinamica do sinal, e complementa a leitura da primeira derivada. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.",
                )}
              </p>
            </div>
          }
        >
          <span className="cursor-help border-b border-dotted border-slate-600">DDMFCC9 {derivada(mfcc9DeltaDelta)}</span>
        </FroidTooltip>
      </div>
      {!hasData && (
        <p className="mt-2 text-[9px] italic text-slate-500">
          Sem Capacidade de Apuração: nenhuma banda foi recebida nesta leitura.
        </p>
      )}
    </div>
  );
};
