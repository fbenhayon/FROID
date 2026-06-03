import React, { useMemo } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  score: number;
  baselineScore?: number;
  isCalibrating: boolean;
  elapsedSeconds: number;
}

export const IPMGauge: React.FC<Props> = ({ score, baselineScore, isCalibrating, elapsedSeconds }) => {
  const min = 0;
  const max = 100;
  const clamped = Math.max(min, Math.min(max, score));
  const angle = -90 + (clamped / max) * 180;
  const baselineAngle = baselineScore ? -90 + (Math.max(min, Math.min(max, baselineScore)) / max) * 180 : null;

  const color = useMemo(() => {
    if (isCalibrating) return "#94a3b8";
    if (!baselineScore) return "#3b82f6";
    const diff = score - baselineScore;
    if (diff <= -10) return "#f8fafc";
    if (diff <= 5) return "#3b82f6";
    if (diff <= 15) return "#22c55e";
    if (diff <= 30) return "#eab308";
    return "#ef4444";
  }, [score, baselineScore, isCalibrating]);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 120" className="h-40 w-full">
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e2e8f0" strokeWidth={16} strokeLinecap="round" />
        {baselineAngle !== null && (
          <line x1={100 + 70 * Math.cos((baselineAngle * Math.PI) / 180)} y1={100 + 70 * Math.sin((baselineAngle * Math.PI) / 180)} x2={100 + 88 * Math.cos((baselineAngle * Math.PI) / 180)} y2={100 + 88 * Math.sin((baselineAngle * Math.PI) / 180)} stroke="#0f172a" strokeWidth={3} className="transition-all duration-700" />
        )}
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke={color} strokeWidth={16} strokeDasharray="251" strokeDashoffset={251 - (clamped / max) * 251} strokeLinecap="round" className="transition-all duration-700" />
        <circle cx={100 + 80 * Math.cos((angle * Math.PI) / 180)} cy={100 + 80 * Math.sin((angle * Math.PI) / 180)} r={6} fill="#0f172a" className="transition-all duration-300" />
      </svg>

      <div className="mt-2 text-center">
        {isCalibrating ? (
          <span className="text-sm font-bold text-slate-400">FASE DE REPOUSO: {elapsedSeconds}s / 60s</span>
        ) : (
          <>
            <FroidTooltip content={<div><p className="font-bold">Índice de Percepção Móvel (IPM)</p><p>Valor atual: {score.toFixed(1)}</p>{baselineScore && <p>Baseline (60s iniciais): {baselineScore.toFixed(1)} ({score > baselineScore ? "+" : ""}{(score - baselineScore).toFixed(1)} desvio)</p>}</div>}>
              <span className="cursor-help text-3xl font-black text-slate-800">{score.toFixed(1)}</span>
            </FroidTooltip>
            <span className="ml-1 text-xs font-bold text-slate-400">IPM</span>
            {baselineScore && (
              <div className="mt-1 text-[10px] font-medium text-slate-400">
                Marco 60s: {baselineScore.toFixed(1)} • Desvio: <span style={{ color }}>{score > baselineScore ? "+" : ""}{(score - baselineScore).toFixed(1)}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
