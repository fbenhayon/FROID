import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { GlossarioDeSiglas } from "../lib/siglas";

type Campaign = {
  campaign_id: string;
  title: string;
  status: string;
  opens_at: string;
  unit_name: string | null;
};

type Review = {
  unit_id: string | null;
  dimension_id: string;
  baseline_cohort: number;
  followup_cohort: number;
  baseline_mean: number;
  followup_mean: number;
  effect_size: number;
  effect_margin: number;
  significant: boolean;
  verdict: string;
  measure_efficacy: string;
  requires_correction: boolean;
  rationale: string;
};

type Comparison = {
  comparable: boolean;
  notice: string;
  requires_correction?: number;
  reviews: Review[];
};

const VERDICT_LABEL: Record<string, string> = {
  eliminated: "Perigo eliminado",
  effective: "Medida eficaz",
  partial: "Eficácia parcial",
  no_change: "Sem mudança",
  worsened: "Piorou",
  inconclusive: "Inconclusivo",
};

const VERDICT_STYLE: Record<string, string> = {
  eliminated: "border-emerald-700 bg-emerald-950/60 text-emerald-100",
  effective: "border-emerald-800 bg-emerald-950/40 text-emerald-200",
  partial: "border-amber-800 bg-amber-950/40 text-amber-200",
  no_change: "border-orange-800 bg-orange-950/50 text-orange-200",
  worsened: "border-red-800 bg-red-950/60 text-red-200",
  inconclusive: "border-slate-700 bg-slate-900 text-slate-300",
};

/** Effect size bar, centred on zero. Left of centre is a worsening. */
const EffectBar: React.FC<{ value: number }> = ({ value }) => {
  const clamped = Math.max(-1.5, Math.min(1.5, value));
  const width = (Math.abs(clamped) / 1.5) * 50;
  const positive = clamped >= 0;
  return (
    <div className="relative mt-2 h-2 w-full rounded bg-slate-800">
      <div className="absolute left-1/2 top-0 h-2 w-px bg-slate-600" />
      <div
        className={`absolute top-0 h-2 rounded ${
          positive ? "bg-emerald-500" : "bg-red-500"
        }`}
        style={{
          width: `${width}%`,
          left: positive ? "50%" : `${50 - width}%`,
        }}
      />
    </div>
  );
};

export const Nr1Effectiveness: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId =
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [baselineId, setBaselineId] = useState("");
  const [followupId, setFollowupId] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const headers = useMemo(() => {
    const token = window.localStorage.getItem("froid_token") || "";
    return {
      Authorization: `Bearer ${token}`,
      "X-FROID-Organization-ID": organizationId,
    };
  }, [organizationId]);

  const loadCampaigns = useCallback(async () => {
    if (!organizationId) return;
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/campaigns`),
        { headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível carregar as campanhas.");
      }
      const list: Campaign[] = Array.isArray(data.campaigns) ? data.campaigns : [];
      setCampaigns(list);
      // Oldest as baseline, newest as follow-up: the usual reading direction.
      if (list.length >= 2) {
        setFollowupId((current) => current || list[0].campaign_id);
        setBaselineId((current) => current || list[list.length - 1].campaign_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar campanhas.");
    }
  }, [headers, organizationId]);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  const compare = async () => {
    if (!baselineId || !followupId || baselineId === followupId) {
      setError("Escolha duas campanhas distintas.");
      return;
    }
    setLoading(true);
    setError("");
    setComparison(null);
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/effectiveness`),
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            baseline_campaign_id: baselineId,
            followup_campaign_id: followupId,
          }),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível comparar as campanhas.");
      }
      setComparison(data as Comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao comparar campanhas.");
    } finally {
      setLoading(false);
    }
  };

  const failing = (comparison?.reviews || []).filter(
    (item) => item.requires_correction,
  );

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-6xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-1 (Norma Regulamentadora nº 1) · Subitem 1.5.4.4.5.3
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              Eficácia das medidas de prevenção
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              Cada unidade é comparada contra a própria linha de base, nunca
              contra uma média de mercado. Uma diferença menor que o ruído da
              coorte é reportada como sem mudança — não como sucesso.
            </p>
          </div>
          {/* Como o sistema prova que a medida funcionou. */}
          <div className="flex items-center border-l border-slate-800 pl-3">
            <button
              onClick={() => nav("/nr1/explica?verbete=eficacia")}
              title="Perguntas sobre a norma, sobre a metodologia e sobre como ler o resultado — com a fonte normativa."
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              FROID Explica NR-1
            </button>
          </div>
          <button
            onClick={() => nav("/nr1")}
            className="rounded border border-slate-700 px-4 py-2 text-xs font-black hover:bg-slate-900"
          >
            Voltar ao painel NR-1
          </button>
        </header>

        <section className="mt-5 rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <label className="block text-[10px] font-bold uppercase text-slate-400">
              Linha de base (antes)
              <select
                value={baselineId}
                onChange={(event) => setBaselineId(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                <option value="">Selecione</option>
                {campaigns.map((item) => (
                  <option key={item.campaign_id} value={item.campaign_id}>
                    {item.title} — {new Date(item.opens_at).toLocaleDateString("pt-BR")}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-[10px] font-bold uppercase text-slate-400">
              Reavaliação (depois)
              <select
                value={followupId}
                onChange={(event) => setFollowupId(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
              >
                <option value="">Selecione</option>
                {campaigns.map((item) => (
                  <option key={item.campaign_id} value={item.campaign_id}>
                    {item.title} — {new Date(item.opens_at).toLocaleDateString("pt-BR")}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => void compare()}
              disabled={loading}
              className="rounded bg-cyan-600 px-5 py-2 text-xs font-black text-white disabled:opacity-50"
            >
              {loading ? "Comparando..." : "Comparar"}
            </button>
          </div>
        </section>

        {error && (
          <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
            {error}
          </p>
        )}

        {comparison && !comparison.comparable && (
          <p className="mt-4 rounded border border-amber-900 bg-amber-950/50 p-3 text-xs font-bold text-amber-200">
            {comparison.notice}
          </p>
        )}

        {comparison?.comparable && (
          <>
            {failing.length > 0 && (
              <section className="mt-5 rounded-lg border border-red-900 bg-red-950/40 p-4">
                <h2 className="text-sm font-black text-red-100">
                  {failing.length} medida{failing.length > 1 ? "s" : ""} exige
                  {failing.length > 1 ? "m" : ""} correção
                </h2>
                <p className="mt-2 text-xs leading-5 text-red-100/80">
                  O acompanhamento não demonstrou eficácia. A NR-1 obriga a
                  corrigir a medida (1.5.5.3.2.1) e a rever a avaliação de riscos
                  (1.5.4.4.6 “c”). O risco correspondente não é reduzido no
                  inventário.
                </p>
              </section>
            )}

            <section className="mt-5 space-y-3">
              {comparison.reviews.map((review) => (
                <article
                  key={`${review.unit_id || "org"}-${review.dimension_id}`}
                  className={`rounded border p-4 ${
                    VERDICT_STYLE[review.verdict] || VERDICT_STYLE.inconclusive
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-black text-white">
                        {VERDICT_LABEL[review.verdict] || review.verdict}
                      </p>
                      <p className="mt-1 text-[11px] opacity-80">
                        média {review.baseline_mean.toFixed(2)} →{" "}
                        {review.followup_mean.toFixed(2)} · coortes{" "}
                        {review.baseline_cohort} e {review.followup_cohort}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-lg font-black text-white">
                        {review.effect_size > 0 ? "+" : ""}
                        {review.effect_size.toFixed(2)}
                        <span className="ml-1 text-xs font-normal opacity-70">
                          ±{review.effect_margin.toFixed(2)}
                        </span>
                      </p>
                      <p className="text-[10px] uppercase tracking-wider opacity-70">
                        diferença padronizada
                      </p>
                      <p className="mt-1 text-[10px] tracking-wider opacity-60">
                        [{(review.effect_size - review.effect_margin).toFixed(2)};{" "}
                        {(review.effect_size + review.effect_margin).toFixed(2)}]
                      </p>
                      {!review.significant && (
                        <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          intervalo alcança o zero
                        </p>
                      )}
                    </div>
                  </div>
                  <EffectBar value={review.effect_size} />
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[11px] font-bold opacity-90">
                      Memória de cálculo
                    </summary>
                    <p className="mt-2 text-[11px] leading-5 opacity-75">
                      {review.rationale}
                    </p>
                  </details>
                </article>
              ))}
              {!comparison.reviews.length && (
                <p className="rounded bg-slate-900 p-4 text-xs text-slate-400">
                  Nenhum par comparável entre as duas campanhas. Uma unidade só
                  entra aqui quando foi medida nas duas pontas.
                </p>
              )}
            </section>
          </>
        )}

        <GlossarioDeSiglas termos={["NR-1", "PGR"]} />
      </main>
    </div>
  );
};
