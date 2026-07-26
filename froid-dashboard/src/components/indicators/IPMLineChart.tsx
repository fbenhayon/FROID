import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  data: number[];
  current: number;
  baseline?: number;
}

const IPM_ROLE_TEXT =
  'O Papel do IPM (O "Velocímetro"): enquanto o IDM aponta a direção do desequilíbrio, o IPM indica a intensidade ou energia global, servindo como velocímetro emocional. Ele é um índice composto atualizado a cada 1 segundo que funde magnitude acústica da voz, comportamento facial e substância semântica transcrita. Assim, o IPM mede quanto combustível emocional o paciente está empregando, independentemente de estar sendo coerente ou não.';

const clamp = (value: number, min = 0, max = 100) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const polarBands = [
  { from: 0, to: 25, color: "#1686c7", label: "Adaptativo" },
  { from: 25, to: 55, color: "#06a743", label: "Fluxo saudavel" },
  { from: 55, to: 75, color: "#f59e0b", label: "Atenção" },
  { from: 75, to: 100, color: "#dc2626", label: "Desadaptativo" },
];

export const IPMLineChart: React.FC<Props> = ({ data, current, baseline }) => {
  const viewW = 620;
  const viewH = 230;
  const padLeft = 0;
  const padRight = 0;
  const padTop = 10;
  const padBot = 28;
  const chartW = viewW - padLeft - padRight;
  const chartH = viewH - padTop - padBot;

  const { pathD, areaD, pts, values } = useMemo(() => {
    const values = Array.isArray(data)
      ? data.filter((v) => typeof v === "number" && Number.isFinite(v))
      : [];
    const n = values.length;

    if (n === 0) {
      return { pathD: "", areaD: "", pts: [] as number[][], values };
    }

    const smoothed = values.map((_, index) => {
      const start = Math.max(0, index - 4);
      const end = Math.min(values.length, index + 5);
      const slice = values.slice(start, end);
      return slice.reduce((sum, value) => sum + value, 0) / slice.length;
    });

    const step = n > 1 ? chartW / (n - 1) : 0;
    const points = smoothed.map((value, index) => [
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
      values,
    };
  }, [chartH, chartW, data]);

  const hasBaseline = typeof baseline === "number" && Number.isFinite(baseline);
  const baselineValue = hasBaseline ? clamp(baseline) : null;
  const baselineLabel = hasBaseline ? baseline.toFixed(1) : "--";
  const currentValue = clamp(current);
  const currentDelta = hasBaseline ? current - baseline : 0;
  const deltaLabel = `${currentDelta > 0 ? "+" : ""}${currentDelta.toFixed(1)}`;
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
      const count = values.filter((value) => value >= band.from && value < band.to).length;
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
                <p className="font-bold">O Papel do IPM (O "Velocímetro")</p>
                <p className="mt-1 text-[11px] leading-relaxed">{IPM_ROLE_TEXT}</p>
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
            {currentValue.toFixed(1)}
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
          <div className="absolute right-3 top-2 z-10 text-[9px] font-black uppercase text-slate-400">
            escala IPM
          </div>
          <FroidTooltip
            content={
              <div className="max-w-[380px]">
                <p className="font-bold">O Papel do IPM (O "Velocímetro")</p>
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
              <linearGradient id="ipmAreaCompact" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.22" />
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
                    opacity={0.98}
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
        {(timeline.length ? timeline : [{ ...polarBands[1], pct: 100, count: 0 }]).map(
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
