import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Hypothesis,
  fetchProgress,
  milestoneLabel,
  nextMilestone,
  patternLabel,
} from "../../lib/validation";

/**
 * Progresso da coleta no resumo do profissional — e nenhum coeficiente.
 *
 * A omissão é a decisão. Correlação parcial numa tela de uso diário vira
 * número que a pessoa memoriza e repete fora de contexto, e a essa altura já
 * não vem acompanhada do intervalo nem do carimbo de leitura provisória.
 * Progresso não corre esse risco: "38 de 70" não vira afirmação sobre nada.
 */
type Props = {
  organizationId: string;
};

export const ValidationProgressLine: React.FC<Props> = ({ organizationId }) => {
  const [hipoteses, setHipoteses] = useState<Hypothesis[]>([]);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      if (!organizationId) return;
      try {
        const data = await fetchProgress(organizationId);
        if (!cancelado) setHipoteses(data.hypotheses || []);
      } catch {
        // Silencioso de propósito: é uma linha informativa no resumo, e não
        // pode virar erro na tela principal do profissional.
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [organizationId]);

  if (!hipoteses.length) return null;

  const menor = Math.min(...hipoteses.map((h) => h.pairs));
  const marco = nextMilestone(menor);
  const pct = Math.min(100, Math.round((menor / marco) * 100));

  return (
    <Link
      to="/validade"
      className="block rounded border border-slate-700 bg-slate-900/60 px-3 py-2 transition hover:border-cyan-700"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-bold uppercase tracking-wide text-slate-300">
          Estudo de validade
        </span>
        <span className="text-[11px] tabular-nums text-slate-400">
          {menor}/{marco}{" "}
          <span className="text-slate-500">({milestoneLabel(menor)})</span>
        </span>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded bg-slate-800">
        <div className="h-full bg-cyan-600" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-[10px] text-slate-500">
        {hipoteses.map((h) => `${patternLabel(h.pattern_key)}: ${h.pairs}`).join(" · ")}
      </p>
    </Link>
  );
};
