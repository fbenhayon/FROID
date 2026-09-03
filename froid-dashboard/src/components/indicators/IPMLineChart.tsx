import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

interface Props {
  data: number[];
  /** Nulo quando nao houve apuracao: o grafico nao desenha ponto atual. */
  current: number | null;
  baseline?: number;
  locale?: SessionLocale;
}

const IPM_TITLE = 'O Papel do IPM (O "Velocímetro")';

const IPM_ROLE_TEXT =
  'O Papel do IPM (O "Velocímetro"): enquanto o IDM aponta a direção do desequilíbrio, o IPM indica a intensidade ou energia global, servindo como velocímetro emocional. Ele é um índice composto atualizado a cada 1 segundo que funde magnitude acústica da voz, comportamento facial e substância semântica transcrita. Assim, o IPM mede quanto combustível emocional o paciente está empregando, independentemente de estar sendo coerente ou não.';

const clamp = (value: number, min = 0, max = 100) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

/** A janela vertical que o gráfico mostra.
 *
 *  O eixo era fixo em 0–100. Numa sessão real o IPM vive entre 50 e 54, então
 *  a linha ocupava 4% da altura e parecia reta — não dava para ler variação
 *  nenhuma, que é justamente o que o gráfico existe para mostrar.
 *
 *  Aqui a janela acompanha os dados, com três garantias:
 *
 *  - amplitude mínima (`VAO_MINIMO`), para que ruído de meio ponto não vire
 *    uma montanha e sugira instabilidade que não existe;
 *  - folga proporcional, para a linha não encostar nas bordas;
 *  - os rótulos do eixo continuam sendo o valor REAL de IPM, e a faixa visível
 *    é escrita no cabeçalho. Zoom que não se declara é gráfico que mente.
 */
const VAO_MINIMO = 10;

export function janelaVertical(values: number[]): { min: number; max: number } {
  if (!values.length) return { min: 0, max: 100 };
  const menor = Math.min(...values);
  const maior = Math.max(...values);
  const centro = (menor + maior) / 2;
  const vao = Math.max(VAO_MINIMO, (maior - menor) * 1.8);
  let min = centro - vao / 2;
  let max = centro + vao / 2;
  // Empurra para dentro de 0–100 sem encolher a janela: deslizar preserva a
  // amplitude, enquanto cortar achataria a leitura de novo.
  if (min < 0) {
    max = Math.min(100, max - min);
    min = 0;
  }
  if (max > 100) {
    min = Math.max(0, min - (max - 100));
    max = 100;
  }
  return { min, max };
}

const polarBands = [
  { from: 0, to: 25, color: "#1686c7", label: "Adaptativo" },
  { from: 25, to: 55, color: "#06a743", label: "Fluxo saudavel" },
  { from: 55, to: 75, color: "#f59e0b", label: "Atenção" },
  { from: 75, to: 100, color: "#dc2626", label: "Desadaptativo" },
];

export const IPMLineChart: React.FC<Props> = ({ data, current, baseline, locale = "pt-BR" }) => {
  const viewW = 620;
  const viewH = 230;
  const padLeft = 0;
  const padRight = 0;
  const padTop = 10;
  const padBot = 28;
  const chartW = viewW - padLeft - padRight;
  const chartH = viewH - padTop - padBot;

  const { pathD, areaD, pts, values, janela } = useMemo(() => {
    const values = Array.isArray(data)
      ? data.filter((v) => typeof v === "number" && Number.isFinite(v))
      : [];
    const n = values.length;

    const janela = janelaVertical(values);

    if (n === 0) {
      return { pathD: "", areaD: "", pts: [] as number[][], values, janela };
    }

    const smoothed = values.map((_, index) => {
      const start = Math.max(0, index - 4);
      const end = Math.min(values.length, index + 5);
      const slice = values.slice(start, end);
      return slice.reduce((sum, value) => sum + value, 0) / slice.length;
    });

    const step = n > 1 ? chartW / (n - 1) : 0;
    const alturaNaJanela = (value: number) => {
      const amplitude = Math.max(1e-6, janela.max - janela.min);
      const proporcao = (clamp(value) - janela.min) / amplitude;
      return padTop + (1 - Math.min(1, Math.max(0, proporcao))) * chartH;
    };
    const points = smoothed.map((value, index) => [
      padLeft + index * step,
      alturaNaJanela(value),
    ]);

    let d = `M ${points[0][0]},${points[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const p0 = points[Math.max(0, i - 1)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(n - 1, i + 2)];
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
    }

    const last = points[n - 1];
    return {
      pathD: d,
      areaD: `${d} L ${last[0]},${viewH - padBot} L ${points[0][0]},${viewH - padBot} Z`,
      pts: points,
      values,
      janela,
    };
  }, [chartH, chartW, data]);

  // Mesma conversão usada fora do useMemo: faixas, marcas e baseline precisam
  // pousar na mesma régua da linha, senão o gráfico se contradiz.
  const yDoValor = (value: number) => {
    const amplitude = Math.max(1e-6, janela.max - janela.min);
    const proporcao = (value - janela.min) / amplitude;
    return padTop + (1 - Math.min(1, Math.max(0, proporcao))) * chartH;
  };
  // Cinco marcas dentro da janela, arredondadas — o eixo continua falando em
  // IPM real, não em percentual de tela.
  const marcas = Array.from({ length: 5 }, (_, i) =>
    Number((janela.min + ((janela.max - janela.min) * i) / 4).toFixed(1)),
  );

  const hasBaseline = typeof baseline === "number" && Number.isFinite(baseline);
  const baselineValue = hasBaseline ? clamp(baseline) : null;
  const baselineLabel = hasBaseline ? baseline.toFixed(1) : "--";
  const semApuracao = current === null;
  const currentValue = clamp(current ?? 0);
  // Delta contra baseline exige as duas pontas medidas.
  const currentDelta = hasBaseline && current !== null ? current - baseline : 0;
  const deltaLabel =
    semApuracao || !hasBaseline
      ? "--"
      : `${currentDelta > 0 ? "+" : ""}${currentDelta.toFixed(1)}`;
  const average =
    values.length > 0
      ? values.reduce((sum, value) => sum + value, 0) / values.length
      : currentValue;
  const peak = values.length > 0 ? Math.max(...values) : currentValue;
  const minimum = values.length > 0 ? Math.min(...values) : currentValue;
  const variability =
    values.length > 1
      ? Math.sqrt(
          values.reduce((sum, value) => sum + Math.pow(value - average, 2), 0) /
            values.length,
        )
      : 0;
  const quality =
    values.length >= 20 ? "Excelente" : values.length >= 6 ? "Boa" : "Aguardando";
  const timeline = polarBands
    .map((band) => {
      // A ultima faixa precisa incluir o proprio 100: `value < band.to` deixava
      // IPM exatamente 100 fora de TODAS as faixas, e o clamp de
      // `computeLocalIpmFromBioacoustics` produz esse valor de proposito num
      // plato de fala forte. O tempo no topo da escala simplesmente sumia da
      // contagem.
      const noTopo = band.to === 100;
      const count = values.filter(
        (value) => value >= band.from && (noTopo ? value <= band.to : value < band.to),
      ).length;
      return {
        ...band,
        count,
        pct: values.length ? Math.round((count / values.length) * 100) : 0,
      };
    })
    .filter((band) => band.pct > 0);

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 px-2 py-2 text-white shadow-sm">
      <div className="mb-1 flex shrink-0 items-center justify-between gap-3 border-b border-slate-800 pb-1">
        <div className="flex min-w-0 items-center gap-3">
          <FroidTooltip
            width={400}
            content={
              <div className="max-w-[380px]">
                <p className="font-bold">{tooltipText(locale, IPM_TITLE)}</p>
                <p className="mt-1 text-[11px] leading-relaxed">{tooltipText(locale, IPM_ROLE_TEXT)}</p>
              </div>
            }
          >
            <span className="flex cursor-help items-center gap-3">
              <span className="text-[11px] font-black uppercase tracking-widest text-slate-100">
                FROID - IPM
              </span>
              <span className="truncate text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Índice de Potência Multimodal
              </span>
            </span>
          </FroidTooltip>
          <span className="font-mono text-[18px] font-black leading-none text-emerald-400">
            {semApuracao ? "--" : currentValue.toFixed(1)}
          </span>
          <span className="font-mono text-[10px] font-black text-slate-300">
            delta {deltaLabel}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-slate-400">
            baseline {baselineLabel}
          </span>
          <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-black uppercase text-slate-950">
            ao vivo
          </span>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        <div className="relative h-full min-h-0 rounded-lg border border-slate-700 bg-slate-900 p-1.5">
          {/* Zoom que nao se declara e grafico que mente: a faixa visivel fica
              escrita, para ninguem confundir amplitude de tela com amplitude
              de IPM. */}
          <div className="absolute right-3 top-2 z-10 text-[9px] font-black uppercase text-slate-400">
            escala IPM {janela.min.toFixed(0)}–{janela.max.toFixed(0)}
          </div>
          <FroidTooltip
            content={
              <div className="max-w-[380px]">
                <p className="font-bold">{tooltipText(locale, IPM_TITLE)}</p>
                <p className="mt-1 text-[11px] leading-relaxed">
                  {tooltipText(locale, IPM_ROLE_TEXT)}
                </p>
              </div>
            }
            width={400}
          >
            <span className="absolute right-3 top-7 z-20 cursor-help border-b border-dashed border-slate-500 text-[10px] text-slate-400">
              ?
            </span>
          </FroidTooltip>

          <svg viewBox={`0 0 ${viewW} ${viewH}`} className="h-full w-full">
            <defs>
              <linearGradient id="ipmAreaCompact" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#ffffff" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {polarBands
              .filter((band) => band.to > janela.min && band.from < janela.max)
              .map((band) => {
                const yTop = yDoValor(Math.min(band.to, janela.max));
                const yBottom = yDoValor(Math.max(band.from, janela.min));
                const altura = Math.max(1, yBottom - yTop);
                return (
                  <g key={band.label}>
                    <rect
                      x={padLeft}
                      y={yTop}
                      width={chartW}
                      height={altura}
                      fill={band.color}
                      opacity={0.98}
                    />
                    {/* O rótulo só cabe se a faixa visível tiver altura para
                        ele; espremido, viraria borrão sobre a linha. */}
                    {altura > 16 && (
                      <text
                        x={padLeft + 8}
                        y={yBottom - 6}
                        className="fill-white text-[9px] font-black uppercase"
                        opacity={0.92}
                      >
                        {band.label}
                      </text>
                    )}
                  </g>
                );
              })}

            {marcas.map((tick, indice) => {
              const y = yDoValor(tick);
              return (
                <g key={`${tick}-${indice}`}>
                  <line
                    x1={padLeft}
                    x2={viewW - padRight}
                    y1={y}
                    y2={y}
                    stroke="#ffffff"
                    strokeOpacity={0.34}
                    strokeWidth={1}
                  />
                  <text
                    x={padLeft + 4}
                    y={y - 3}
                    className="fill-white font-mono text-[10px] font-bold"
                    opacity={0.85}
                  >
                    {tick.toFixed(1)}
                  </text>
                </g>
              );
            })}

            {baselineValue !== null && (
              <line
                x1={padLeft}
                x2={viewW - padRight}
                y1={yDoValor(baselineValue)}
                y2={yDoValor(baselineValue)}
                stroke="#ffffff"
                strokeDasharray="6 4"
                strokeWidth={1.6}
              />
            )}

            {[0, 1, 2, 3].map((i) => {
              const x = padLeft + (i / 3) * chartW;
              return (
                <text
                  key={i}
                  x={x}
                  y={viewH - 8}
                  textAnchor="middle"
                  className="fill-slate-300 font-mono text-[10px]"
                >
                  {i === 3 ? "agora" : `-${Math.round((1 - i / 3) * 10)}m`}
                </text>
              );
            })}

            {pts.length === 0 && (
              <text
                x={viewW / 2}
                y={viewH / 2}
                textAnchor="middle"
                className="fill-slate-300 text-[11px]"
              >
                Aguardando serie temporal...
              </text>
            )}

            {pts.length > 0 && (
              <>
                {areaD && <path d={areaD} fill="url(#ipmAreaCompact)" />}
                {pathD && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#ffffff"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    opacity={0.8}
                  />
                )}
                {pathD && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#22f58b"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3}
                  />
                )}
                <circle
                  cx={pts[pts.length - 1][0]}
                  cy={pts[pts.length - 1][1]}
                  r={5.2}
                  fill="#22f58b"
                  stroke="#ffffff"
                  strokeWidth={2.2}
                />
              </>
            )}
          </svg>
        </div>
      </div>

      <div className="mt-1 grid shrink-0 grid-cols-5 overflow-hidden rounded-md border border-slate-700 bg-slate-900 text-[9px]">
        {[
          ["Med. IPM", average.toFixed(1), "text-white"],
          ["P. Max", peak.toFixed(1), "text-orange-300"],
          ["Min", minimum.toFixed(1), "text-cyan-300"],
          ["Variabl.", variability.toFixed(1), "text-white"],
          ["Qualid.", quality, "text-emerald-300"],
        ].map(([label, value, color]) => (
          <div
            key={label}
            className="flex min-w-0 items-center justify-center gap-1 border-r border-slate-700 px-1.5 py-1 last:border-r-0"
          >
            <span className="truncate font-black uppercase text-slate-400">
              {label}:
            </span>
            <strong className={`truncate font-mono text-[11px] font-black ${color}`}>
              {value}
            </strong>
          </div>
        ))}
      </div>

      <div className="mt-1 flex shrink-0 overflow-hidden rounded-md border border-slate-700 bg-slate-900 text-[8px] font-black uppercase text-white">
        {/* Sem amostra, a barra anunciava "Fluxo saudavel — 100%" enquanto o
            grafico ao lado dizia "Aguardando serie temporal". Duas afirmacoes
            opostas na mesma tela, e a verde e a que o olho acredita. */}
        {(timeline.length
          ? timeline
          : [{ ...polarBands[1], color: "#475569", label: "Sem amostras", pct: 100, count: 0 }]
        ).map(
          (segment) => (
            <div
              key={segment.label}
              className="min-w-0 px-2 py-1"
              style={{
                width: `${Math.max(14, segment.pct)}%`,
                borderTop: `4px solid ${segment.color}`,
              }}
              title={`${segment.label}: ${segment.pct}%`}
            >
              <span className="block truncate">
                {segment.label} - {segment.pct}%
              </span>
            </div>
          ),
        )}
      </div>
    </div>
  );
};
