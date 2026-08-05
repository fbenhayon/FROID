import React, { useCallback, useEffect, useMemo, useState } from "react";
import type { FroidUser } from "../App";
import {
  INSTRUMENT,
  PILOT_PAIRS,
  TARGET_PAIRS,
  ValidationResult,
  VERDICT_LABELS,
  fetchReport,
  patternLabel,
} from "../lib/validation";

/**
 * O relatório completo do estudo: r, intervalo e veredito por hipótese.
 *
 * Fica em rota própria, e não no painel diário, porque um coeficiente
 * provisório visto todo dia deixa de ser lido com as ressalvas que o
 * acompanham. Aqui elas cabem na tela inteira.
 */
type Props = {
  user: FroidUser | null;
};

const CORES: Record<string, string> = {
  strong: "text-emerald-300",
  moderate: "text-emerald-400",
  weak: "text-amber-300",
  negligible: "text-slate-400",
  inconclusive: "text-slate-400",
  contradicted: "text-rose-300",
  insufficient_sample: "text-slate-500",
  unusable_sample: "text-slate-500",
};

export const ValidationStudy: React.FC<Props> = ({ user }) => {
  const organizationId =
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";
  const [resultados, setResultados] = useState<ValidationResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    try {
      const data = await fetchReport(organizationId);
      setResultados(data.results || []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar.");
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    load();
  }, [load]);

  const menorN = useMemo(
    () => (resultados.length ? Math.min(...resultados.map((r) => r.n)) : 0),
    [resultados],
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <header>
        <h1 className="text-lg font-black uppercase tracking-wide text-slate-100">
          Estudo de validade convergente
        </h1>
        <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-slate-400">
          Cada hipótese abaixo foi declarada — inclusive a direção esperada —
          antes de qualquer coleta. Um resultado no sentido contrário é
          evidência contra a convergência, e não um achado a reinterpretar. O
          instrumento é o {INSTRUMENT}, aplicado e interpretado pelo
          profissional.
        </p>
      </header>

      <div className="mt-4 rounded border border-slate-700 bg-slate-900/60 p-3">
        <p className="text-[11px] leading-relaxed text-slate-300">
          <strong className="text-slate-100">Dois estágios declarados.</strong>{" "}
          Piloto em {PILOT_PAIRS} pares, análise confirmatória em {TARGET_PAIRS}.
          Com uma correlação verdadeira de 0,50, o intervalo em {PILOT_PAIRS}{" "}
          pares vai de cerca de 0,17 a 0,73 — largo demais para sustentar
          afirmação. O piloto serve para decidir se vale concluir, não para
          concluir.
        </p>
      </div>

      {error && <p className="mt-3 text-[12px] text-rose-300">{error}</p>}
      {loading && <p className="mt-3 text-[12px] text-slate-400">Carregando…</p>}

      <div className="mt-5 space-y-4">
        {resultados.map((resultado) => (
          <article
            key={`${resultado.pattern_key}:${resultado.instrument}`}
            className="rounded-lg border border-slate-700 bg-slate-900/50 p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-slate-100">
                  {patternLabel(resultado.pattern_key)}
                </h2>
                <p className="text-[11px] text-slate-400">
                  contra {resultado.instrument} · direção esperada{" "}
                  {resultado.expected_direction > 0 ? "positiva" : "negativa"}
                </p>
              </div>
              <span
                className={`rounded bg-slate-950 px-2 py-1 text-[10px] font-black uppercase ${
                  CORES[resultado.verdict] || "text-slate-400"
                }`}
              >
                {VERDICT_LABELS[resultado.verdict] || resultado.verdict}
              </span>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <dt className="text-[10px] uppercase text-slate-500">Pares</dt>
                <dd className="text-sm tabular-nums text-slate-200">
                  {resultado.progress}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase text-slate-500">r</dt>
                <dd className="text-sm tabular-nums text-slate-200">
                  {resultado.r === null ? "—" : resultado.r.toFixed(2)}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-[10px] uppercase text-slate-500">IC 95%</dt>
                <dd className="text-sm tabular-nums text-slate-200">
                  {resultado.interval
                    ? `${resultado.interval[0].toFixed(2)} a ${resultado.interval[1].toFixed(2)}`
                    : "—"}
                </dd>
              </div>
            </dl>

            <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
              {resultado.detail}
            </p>

            <div className="mt-3 rounded border border-slate-800 bg-slate-950/70 p-3">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                Frase divulgável
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-200">
                {resultado.statement}
              </p>
            </div>
          </article>
        ))}
      </div>

      {!loading && !resultados.length && (
        <p className="mt-6 text-[12px] text-slate-400">
          Nenhuma hipótese avaliada ainda.
        </p>
      )}

      {menorN > 0 && menorN < TARGET_PAIRS && (
        <p className="mt-6 rounded border border-amber-900 bg-amber-950/30 p-3 text-[11px] leading-relaxed text-amber-100">
          A coleta não fechou. Nada nesta tela pode ser citado como resultado do
          estudo — nem em material comercial, nem em resposta a questionamento
          técnico. A frase que pode ser dita está no bloco de cada hipótese.
        </p>
      )}
    </div>
  );
};

export default ValidationStudy;
