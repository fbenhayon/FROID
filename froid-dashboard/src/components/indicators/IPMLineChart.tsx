import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  data: number[];
  current: number;
  baseline?: number;
}

const IPM_ROLE_TEXT =
  'O Papel do IPM (O "Velocimetro"): enquanto o IDM aponta a direcao do desequilibrio, o IPM indica a intensidade ou energia global, servindo como velocimetro emocional. Ele e um indice composto atualizado a cada 500 milissegundos que funde magnitude acustica da voz, comportamento facial e substancia semantica transcrita. Assim, o IPM mede quanto combustivel emocional o paciente esta empregando, independente de estar sendo coerente ou nao.';

const clamp = (value: number, min = 0, max = 100) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const polarBands = [
  { from: 0, to: 25, color: "#1686c7", label: "Adaptativo" },
  { from: 25, to: 55, color: "#06a743", label: "Fluxo saudavel" },
  { from: 55, to: 75, color: "#f59e0b", label: "Atencao" },
  { from: 75, to: 100, color: "#dc2626", label: "Desadaptativo" },
];

export const IPMLineChart: React.FC<Props> = ({ data, current, baseline }) => {
  const viewW = 620;
  const viewH = 260;
  const padLeft = 44;
  const padRight = 28;
  const padTop = 22;
  const padBot = 34;
  const chartW = viewW - padLeft - padRight;
  const chartH = viewH - padTop - padBot;

  const { pathD, areaD, pts } = useMemo(() => {
    const values = Array.isArray(data)
      ? data.filter((v) => typeof v === "number" && Number.isFinite(v))
      : [];
    const n = values.length;

    if (n === 0) return { pathD: "", areaD: "", pts: [] as number[][] };

    const step = n > 1 ? chartW / (n - 1) : 0;
    const points = values.map((value, index) => [
      padLeft + index * step,
      padTop + (1 - clamp(value) / 100) * chartH,
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
    };
  }, [chartH, chartW, data]);

  const hasBaseline = typeof baseline === "number" && Number.isFinite(baseline);
  const baselineValue = hasBaseline ? clamp(baseline) : null;
  const baselineLabel = hasBaseline ? baseline.toFixed(1) : "--";
  const currentValue = clamp(current);
  const currentDelta = hasBaseline ? current - baseline : 0;
  const deltaLabel = `${currentDelta > 0 ? "+" : ""}${currentDelta.toFixed(1)}`;

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-white shadow-sm">
      <div className="mb-2 flex shrink-0 items-center justify-between gap-3 border-b border-slate-800 pb-2">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-[11px] font-black uppercase tracking-widest text-slate-100">
            FROID - IPM
          </span>
          <span className="truncate text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Indice de potencia motivacional
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

      <div className="grid min-h-0 flex-1 grid-cols-[90px_minmax(0,1fr)] gap-3">
        <div className="flex flex-col justify-between rounded-lg border border-slate-700 bg-slate-900 p-2">
          <div>
            <p className="text-[10px] font-black uppercase text-slate-400">
              IPM atual
            </p>
            <p className="mt-1 text-3xl font-black leading-none text-emerald-400">
              {currentValue.toFixed(1)}
            </p>
          </div>
          <div className="space-y-1 text-[10px] font-bold text-slate-300">
            <p>Delta {deltaLabel}</p>
            <p className="text-slate-500">vs 60s iniciais</p>
          </div>
          <div>
            <p className="mb-1 text-[9px] font-black uppercase text-slate-500">
              Sinal
            </p>
            <div className="h-2 overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-emerald-400"
                style={{ width: `${Math.max(6, currentValue)}%` }}
              />
            </div>
          </div>
        </div>

        <div className="relative min-h-0 rounded-lg border border-slate-700 bg-slate-900 p-2">
          <div className="absolute right-3 top-2 z-10 text-[9px] font-black uppercase text-slate-400">
            escala IPM
          </div>
          <FroidTooltip
            content={
              <div className="max-w-[380px]">
                <p className="font-bold">O Papel do IPM (O "Velocimetro")</p>
                <p className="mt-1 text-[11px] leading-relaxed">
                  {IPM_ROLE_TEXT}
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
              <linearGradient id="ipmAreaV4" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.26" />
                <stop offset="100%" stopColor="#ffffff" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {polarBands.map((band) => {
              const yTop = padTop + (1 - band.to / 100) * chartH;
              const yBottom = padTop + (1 - band.from / 100) * chartH;
              return (
                <g key={band.label}>
                  <rect
                    x={padLeft}
                    y={yTop}
                    width={chartW}
                    height={Math.max(1, yBottom - yTop)}
                    fill={band.color}
                    opacity={0.9}
                  />
                  <text
                    x={padLeft + 8}
                    y={yBottom - 8}
                    className="fill-white text-[9px] font-black uppercase"
                    opacity={0.92}
                  >
                    {band.label}
                  </text>
                </g>
              );
            })}

            {[0, 25, 50, 75, 100].map((tick) => {
              const y = padTop + (1 - tick / 100) * chartH;
              return (
                <g key={tick}>
                  <line
                    x1={padLeft}
                    x2={viewW - padRight}
                    y1={y}
                    y2={y}
                    stroke="#ffffff"
                    strokeDasharray={tick === 50 ? "5 4" : "0"}
                    strokeOpacity={tick === 50 ? 0.72 : 0.34}
                    strokeWidth={tick === 50 ? 1.4 : 1}
                  />
                  <text
                    x={padLeft - 8}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-slate-300 font-mono text-[10px] font-bold"
                  >
                    {tick}
                  </text>
                </g>
              );
            })}

            {baselineValue !== null && (
              <line
                x1={padLeft}
                x2={viewW - padRight}
                y1={padTop + (1 - baselineValue / 100) * chartH}
                y2={padTop + (1 - baselineValue / 100) * chartH}
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
                {areaD && <path d={areaD} fill="url(#ipmAreaV4)" />}
                {pathD && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#ffffff"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    opacity={0.85}
                  />
                )}
                {pathD && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#22f58b"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3.2}
                  />
                )}
                <circle
                  cx={pts[pts.length - 1][0]}
                  cy={pts[pts.length - 1][1]}
                  r={5.4}
                  fill="#22f58b"
                  stroke="#ffffff"
                  strokeWidth={2.4}
                />
              </>
            )}
          </svg>
        </div>
      </div>
    </div>
  );
};
