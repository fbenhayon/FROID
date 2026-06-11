import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  data: number[];
  current: number;
  baseline?: number;
}

const IPM_ROLE_TEXT =
  'O Papel do IPM (O "Velocímetro") Enquanto o IDM aponta a direção do desequilíbrio, o IPM indica a intensidade ou energia global — servindo como o velocímetro emocional. Ele é um índice composto atualizado a cada 500 milissegundos que funde a magnitude acústica da voz, o comportamento facial e a substância semântica transcrita. Assim, o IPM apenas mede "quanto combustível" o paciente está empregando, independente de estar sendo coerente ou não';

export const IPMLineChart: React.FC<Props> = ({ data, current, baseline }) => {
  const viewW = 420;
  const viewH = 220;
  const padLeft = 46;
  const padRight = 18;
  const padTop = 18;
  const padBot = 30;

  const { pathD, areaD, pts } = useMemo(() => {
    const values = Array.isArray(data)
      ? data.filter((v) => typeof v === "number" && !isNaN(v))
      : [];
    const n = values.length;
    const base = typeof baseline === "number" && !isNaN(baseline) ? baseline : 50;

    if (n === 0) return { pathD: "", areaD: "", pts: [] as number[][] };

    const w = viewW - padLeft - padRight;
    const h = viewH - padTop - padBot;
    const step = n > 1 ? w / (n - 1) : 0;
    const scaleY = h / 24;
    const points = values.map((value, index) => {
      const relative = Math.max(-12, Math.min(12, value - base));
      return [padLeft + index * step, viewH / 2 - relative * scaleY];
    });

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
  }, [data, baseline]);

  const hasBaseline = typeof baseline === "number" && !isNaN(baseline);
  const baselineLabel = hasBaseline ? baseline.toFixed(1) : "--";
  const currentRel = hasBaseline ? current - baseline : 0;
  const currentRelLabel = `${currentRel > 0 ? "+" : ""}${currentRel.toFixed(1)}`;
  const relColor =
    currentRel > 8
      ? "#dc2626"
      : currentRel > 5
        ? "#ea580c"
        : currentRel > 2
          ? "#ca8a04"
          : currentRel < -5
            ? "#2563eb"
            : "#16a34a";

  return (
    <div className="flex h-full min-h-0 w-full flex-col rounded-xl border border-slate-100 bg-white px-3 py-2 shadow-sm">
      <div className="mb-1 flex shrink-0 items-center justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="text-3xl font-black leading-none tracking-tight text-slate-800">
            {currentRelLabel}
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Δ IPM
          </span>
          <span className="truncate font-mono text-[10px] text-slate-400">
            IPM inicial 60s: {baselineLabel}
          </span>
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
          <span className="cursor-help border-b border-dashed border-slate-300 text-[10px] text-slate-400">
            ?
          </span>
        </FroidTooltip>
      </div>

      <svg viewBox={`0 0 ${viewW} ${viewH}`} className="min-h-0 flex-1">
        <defs>
          <linearGradient id="ipmRelGradCompact" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.34" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {[-10, -5, 0, 5, 10].map((tick) => {
          const relY = viewH / 2 - tick * ((viewH - padTop - padBot) / 24);
          return (
            <g key={`ipm-y-${tick}`}>
              <line
                x1={padLeft}
                y1={relY}
                x2={viewW - padRight}
                y2={relY}
                stroke={tick === 0 ? "#64748b" : "#e2e8f0"}
                strokeWidth={tick === 0 ? 1.4 : 1}
              />
              <text
                x={padLeft - 9}
                y={relY + 4}
                textAnchor="end"
                className={`font-mono text-[10px] ${
                  tick === 0 ? "fill-slate-700 font-bold" : "fill-slate-400"
                }`}
              >
                {tick > 0 ? "+" : ""}
                {tick}
              </text>
            </g>
          );
        })}

        <text
          x={10}
          y={viewH / 2}
          textAnchor="middle"
          transform={`rotate(-90, 10, ${viewH / 2})`}
          className="fill-slate-400 text-[10px] font-bold uppercase"
        >
          Δ IPM
        </text>

        {[0, 1, 2, 3].map((i) => {
          const x = padLeft + (i / 3) * (viewW - padLeft - padRight);
          return (
            <text
              key={`ipm-x-${i}`}
              x={x}
              y={viewH - 8}
              textAnchor="middle"
              className="fill-slate-400 font-mono text-[10px]"
            >
              -{Math.round((1 - i / 3) * 60)}s
            </text>
          );
        })}

        {pts.length === 0 && (
          <text
            x={viewW / 2}
            y={viewH / 2}
            textAnchor="middle"
            className="fill-slate-400 text-[11px]"
          >
            Aguardando série temporal...
          </text>
        )}

        {pts.length > 0 && (
          <>
            {areaD && <path d={areaD} fill="url(#ipmRelGradCompact)" />}
            {pathD && (
              <path
                d={pathD}
                fill="none"
                stroke={relColor}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={3.4}
              />
            )}
            {pts.map((point, index) => (
              <circle
                key={`pt-${index}`}
                cx={point[0]}
                cy={point[1]}
                r={2.7}
                fill={relColor}
                opacity={0.68}
              />
            ))}
            <circle
              cx={pts[pts.length - 1][0]}
              cy={pts[pts.length - 1][1]}
              r={5.6}
              fill={relColor}
              stroke="white"
              strokeWidth={2.8}
            />
          </>
        )}
      </svg>
    </div>
  );
};
