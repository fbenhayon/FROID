import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

/**
 * Plano de ação — o segundo documento obrigatório do PGR (NR-1, 1.5.7.1 "b").
 *
 * Até esta tela existir o FROID entregava um dos dois documentos mínimos: o
 * inventário era gravado e o plano voltava como rascunho no corpo da resposta
 * da API, sem nunca ser persistido. A tabela, as políticas de RLS, os grants e
 * até a permissão `nr1.action_plan.manage` existiam desde a migration 010 — o
 * desenho estava inteiro e faltava a camada que o usa.
 *
 * O que esta tela precisa fazer, e por quê:
 *
 * - **Ordenar por prioridade.** 1.5.5.2.1.1 manda que o número de trabalhadores
 *   possivelmente atingidos aumente a prioridade da ação. A ordem do documento
 *   não pode depender de quem o abre, então ela vem gravada do servidor.
 * - **Cobrar o que 1.5.5.2.2 exige**: cronograma, responsável, forma de
 *   acompanhamento e forma de aferição de resultados. O banco recusa concluir
 *   uma medida sem os quatro; a tela mostra o que falta antes de a pessoa
 *   tentar.
 * - **Registrar a implementação** (1.5.5.3.1) e, com isso, acender a
 *   reavaliação de risco residual da alínea "a" de 1.5.4.4.6 — que não tem
 *   prazo na norma porque não tem data: a obrigação nasce do evento.
 */

type PlanItem = {
  item_id: string;
  inventory_id: string;
  plan_action: string;
  measure: string;
  measure_type: string;
  responsible_membership_id: string | null;
  due_date: string | null;
  status: string;
  evidence: string;
  monitoring_method: string;
  result_measurement: string;
  implemented_at: string | null;
  effectiveness_reviewed_at: string | null;
  effectiveness: string | null;
  exposed_workers: number;
  priority_rank: number | null;
  unit_id: string | null;
  unit_name: string | null;
  dimension_id: string;
  dimension_title: string;
  nr1_factor: string;
  risk_level: string;
  severity: number;
  probability: number;
  review_due_at: string | null;
  review_trigger: string | null;
  created_at: string;
  updated_at: string;
};

type Summary = {
  total: number;
  by_status: Record<string, number>;
  overdue: number;
  awaiting_residual_review: number;
};

type Campaign = {
  campaign_id: string;
  title: string;
  status: string;
  unit_name: string | null;
  target_headcount: number;
};

type Responsible = { membership_id: string; display_name: string };

/** A hierarquia de 1.5.5.1.2, sem EPI — não existe equipamento de proteção
 *  individual contra a forma como o trabalho é organizado. A divergência está
 *  declarada no documento de critérios, onde o auditor a encontra junto da
 *  justificativa. */
const MEASURE_TYPES: Array<{ value: string; label: string; hint: string }> = [
  { value: "elimination", label: "Eliminação", hint: "evitar ou eliminar o perigo na origem" },
  { value: "substitution", label: "Substituição", hint: "substituir a condição geradora" },
  { value: "collective", label: "Coletiva", hint: "reprojeto do trabalho, proteção coletiva" },
  { value: "administrative", label: "Administrativa", hint: "organização do trabalho, procedimento" },
  { value: "monitoring", label: "Acompanhamento", hint: "monitoramento planejado do desempenho" },
];

/** Os três verbos de 1.5.5.2.1. */
const PLAN_ACTIONS: Record<string, { label: string; classe: string }> = {
  introduce: { label: "Introduzir", classe: "border-cyan-700 bg-cyan-950 text-cyan-100" },
  improve: { label: "Aprimorar", classe: "border-amber-700 bg-amber-950 text-amber-100" },
  maintain: { label: "Manter", classe: "border-emerald-800 bg-emerald-950 text-emerald-100" },
};

const STATUSES: Array<{ value: string; label: string }> = [
  { value: "planned", label: "Planejada" },
  { value: "in_progress", label: "Em andamento" },
  { value: "done", label: "Concluída" },
  { value: "cancelled", label: "Cancelada" },
];

const EFFICACY: Array<{ value: string; label: string }> = [
  { value: "none", label: "Sem efeito medido" },
  { value: "insufficient", label: "Insuficiente" },
  { value: "partial", label: "Parcial" },
  { value: "effective", label: "Eficaz" },
  { value: "eliminated", label: "Perigo eliminado" },
];

const RISK_STYLE: Record<string, string> = {
  critical: "border-red-800 bg-red-950/60 text-red-200",
  high: "border-orange-800 bg-orange-950/50 text-orange-200",
  moderate: "border-amber-800 bg-amber-950/40 text-amber-200",
  low: "border-emerald-900 bg-emerald-950/40 text-emerald-200",
};

const RISK_LABEL: Record<string, string> = {
  critical: "Crítico",
  high: "Alto",
  moderate: "Moderado",
  low: "Baixo",
};

const FACTOR_LABEL: Record<string, string> = {
  work_organization: "Gestão e organização do trabalho",
  workload_demand: "Carga e demanda",
  harassment_violence: "Assédio e violência",
  environment_modality: "Ambiente e modalidade",
};

function diaLegivel(valor: string | null): string {
  if (!valor) return "—";
  return String(valor).slice(0, 10).split("-").reverse().join("/");
}

/** O que ainda falta para esta medida poder ser concluída.
 *
 *  As mesmas quatro condições que o banco exige em CHECK (migration 026).
 *  Mostrar antes evita que a pessoa preencha tudo, clique em concluir e receba
 *  um erro de constraint que não ensina nada. */
function pendenciasPara(item: PlanItem): string[] {
  const faltando: string[] = [];
  if (!item.measure.trim()) faltando.push("descrição da medida");
  if (!item.responsible_membership_id) faltando.push("responsável");
  if (!item.due_date) faltando.push("prazo");
  if (!item.monitoring_method.trim()) faltando.push("forma de acompanhamento");
  if (!item.result_measurement.trim()) faltando.push("forma de aferição do resultado");
  if (!item.implemented_at) faltando.push("data de implementação");
  return faltando;
}

export const Nr1ActionPlan: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId =
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [items, setItems] = useState<PlanItem[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [responsibles, setResponsibles] = useState<Responsible[]>([]);
  const [rascunhos, setRascunhos] = useState<Record<string, Partial<PlanItem>>>({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const headers = useMemo(() => {
    const token = window.localStorage.getItem("froid_token") || "";
    return {
      Authorization: `Bearer ${token}`,
      "X-FROID-Organization-ID": organizationId,
    };
  }, [organizationId]);

  const jsonHeaders = useMemo(
    () => ({ ...headers, "Content-Type": "application/json" }),
    [headers],
  );

  const loadCampaigns = useCallback(async () => {
    if (!organizationId) return;
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/campaigns`),
        { headers },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Falha ao carregar campanhas.");
      const lista: Campaign[] = Array.isArray(data.campaigns) ? data.campaigns : [];
      setCampaigns(lista);
      // O plano só existe depois do inventário, e o inventário só depois de a
      // campanha encerrar (migration 014): abrir já na encerrada mais recente
      // poupa um clique que não tem alternativa.
      const encerrada = lista.find((item) => item.status === "closed");
      if (encerrada && !campaignId) setCampaignId(encerrada.campaign_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar campanhas.");
    }
  }, [headers, organizationId, campaignId]);

  const loadResponsibles = useCallback(async () => {
    if (!organizationId) return;
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/responsibles`),
        { headers },
      );
      const data = await response.json();
      if (response.ok && Array.isArray(data.responsibles)) {
        setResponsibles(data.responsibles);
      }
    } catch {
      /* Nomear responsável fica manual; não é motivo para derrubar a tela. */
    }
  }, [headers, organizationId]);

  const loadPlan = useCallback(async () => {
    if (!organizationId || !campaignId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/campaigns/${campaignId}/action-plan`,
        ),
        { headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível carregar o plano de ação.");
      }
      setItems(Array.isArray(data.action_plan) ? data.action_plan : []);
      setSummary(data.summary || null);
      setRascunhos({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar o plano.");
    } finally {
      setLoading(false);
    }
  }, [headers, organizationId, campaignId]);

  useEffect(() => {
    void loadCampaigns();
    void loadResponsibles();
  }, [loadCampaigns, loadResponsibles]);

  useEffect(() => {
    void loadPlan();
  }, [loadPlan]);

  const gerar = async () => {
    if (!campaignId) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/campaigns/${campaignId}/action-plan`,
        ),
        { method: "POST", headers: jsonHeaders },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível gerar o plano.");
      setMessage(
        data.created > 0
          ? `${data.created} medida(s) abertas a partir do inventário.`
          : "Todos os riscos do inventário já têm medida no plano.",
      );
      await loadPlan();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar o plano.");
    } finally {
      setLoading(false);
    }
  };

  const salvar = async (item: PlanItem, campos: Partial<PlanItem>) => {
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/action-plan/items/${item.item_id}`,
        ),
        { method: "PATCH", headers: jsonHeaders, body: JSON.stringify(campos) },
      );
      const data = await response.json();
      if (!response.ok) {
        // As mensagens vêm do servidor já traduzidas para a exigência da norma
        // que foi tocada; repassar a do banco não ensinaria a preencher.
        throw new Error(data?.detail || "Não foi possível salvar a medida.");
      }
      await loadPlan();
      setMessage("Medida atualizada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar.");
    }
  };

  const rascunhoDe = (item: PlanItem): PlanItem =>
    ({ ...item, ...(rascunhos[item.item_id] || {}) }) as PlanItem;

  const editar = (item: PlanItem, campo: keyof PlanItem, valor: unknown) =>
    setRascunhos((atual) => ({
      ...atual,
      [item.item_id]: { ...(atual[item.item_id] || {}), [campo]: valor },
    }));

  const campanhaSelecionada = campaigns.find((c) => c.campaign_id === campaignId);

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-1 · 1.5.7.1 "b"
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">Plano de ação</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              O segundo dos dois documentos obrigatórios do PGR. Indica as
              medidas a serem <strong>introduzidas, aprimoradas ou mantidas</strong>,
              cada uma com cronograma, responsável, forma de acompanhamento e
              forma de aferição de resultados — os quatro que 1.5.5.2.2 exige e
              sem os quais o sistema não deixa concluir.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => nav("/nr1")}
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black hover:bg-slate-900"
            >
              Painel NR-1
            </button>
            <button
              onClick={() => nav("/nr1/aep")}
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              AEP
            </button>
          </div>
        </header>

        {error && (
          <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
            {error}
          </p>
        )}
        {message && (
          <p className="mt-4 rounded border border-emerald-900 bg-emerald-950 p-3 text-xs font-bold text-emerald-200">
            {message}
          </p>
        )}

        <section className="mt-5 rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block">
              <span className="text-xs font-black text-slate-300">Campanha</span>
              <select
                value={campaignId}
                onChange={(e) => setCampaignId(e.target.value)}
                className="mt-1 w-80 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              >
                <option value="">Selecione</option>
                {campaigns.map((campanha) => (
                  <option key={campanha.campaign_id} value={campanha.campaign_id}>
                    {campanha.title}
                    {campanha.unit_name ? ` · ${campanha.unit_name}` : ""}
                    {campanha.status !== "closed" ? " (não encerrada)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void gerar()}
              disabled={!campaignId || loading}
              className="h-10 rounded-lg bg-amber-500 px-4 text-sm font-black text-amber-950 hover:bg-amber-400 disabled:opacity-50"
            >
              Abrir medidas que faltam
            </button>
            <button
              type="button"
              onClick={() => void loadPlan()}
              disabled={!campaignId}
              className="h-10 rounded-lg border border-slate-700 px-4 text-sm font-black text-slate-200"
            >
              Atualizar
            </button>
          </div>
          {campanhaSelecionada && campanhaSelecionada.status !== "closed" && (
            <p className="mt-3 text-xs leading-5 text-amber-200">
              Esta campanha ainda não foi encerrada. Nenhum resultado é liberado
              enquanto a coorte cresce, então não há inventário — e sem
              inventário não há plano.
            </p>
          )}
        </section>

        {summary && summary.total > 0 && (
          <section className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-2xl font-black text-white">{summary.total}</p>
              <p className="mt-1 text-xs text-slate-400">medidas no documento</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <p className="text-2xl font-black text-white">
                {summary.by_status.done || 0}
              </p>
              <p className="mt-1 text-xs text-slate-400">concluídas</p>
            </div>
            <div
              className={`rounded-lg border p-4 ${
                summary.overdue > 0
                  ? "border-red-800 bg-red-950/50"
                  : "border-slate-800 bg-slate-900"
              }`}
            >
              <p className="text-2xl font-black text-white">{summary.overdue}</p>
              <p className="mt-1 text-xs leading-5 text-slate-300">
                com prazo vencido. O prazo foi a própria organização que escreveu
                (1.5.5.2.2) — é contra ele que a fiscalização compara.
              </p>
            </div>
            <div
              className={`rounded-lg border p-4 ${
                summary.awaiting_residual_review > 0
                  ? "border-amber-800 bg-amber-950/50"
                  : "border-slate-800 bg-slate-900"
              }`}
            >
              <p className="text-2xl font-black text-white">
                {summary.awaiting_residual_review}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-300">
                implementadas aguardando reavaliação de risco residual. A
                obrigação nasceu no dia da implementação (1.5.4.4.6 "a").
              </p>
            </div>
          </section>
        )}

        {!loading && campaignId && items.length === 0 && (
          <section className="mt-5 rounded-lg border border-slate-800 bg-slate-900 p-5">
            <p className="text-sm font-black text-slate-200">
              Nenhuma medida registrada para esta campanha.
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              O plano nasce do inventário. Gere o inventário no painel NR-1 e
              volte aqui, ou use "abrir medidas que faltam" se o inventário já
              existir.
            </p>
          </section>
        )}

        <section className="mt-5 space-y-4">
          {items.map((original) => {
            const item = rascunhoDe(original);
            const sujo = Boolean(rascunhos[original.item_id]);
            const faltando = pendenciasPara(item);
            const verbo = PLAN_ACTIONS[item.plan_action] || PLAN_ACTIONS.introduce;
            return (
              <article
                key={item.item_id}
                className="rounded-lg border border-slate-800 bg-slate-900 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  {item.priority_rank !== null && (
                    <span className="rounded bg-slate-800 px-2 py-1 text-[11px] font-black text-slate-300">
                      #{item.priority_rank}
                    </span>
                  )}
                  <span
                    className={`rounded border px-2 py-1 text-[11px] font-black ${
                      RISK_STYLE[item.risk_level] || RISK_STYLE.low
                    }`}
                  >
                    {RISK_LABEL[item.risk_level] || item.risk_level} ·{" "}
                    {item.severity}×{item.probability}
                  </span>
                  <span className={`rounded border px-2 py-1 text-[11px] font-black ${verbo.classe}`}>
                    {verbo.label}
                  </span>
                  <span className="text-sm font-black text-white">
                    {item.dimension_title}
                  </span>
                  <span className="text-xs text-slate-400">
                    {FACTOR_LABEL[item.nr1_factor] || item.nr1_factor}
                    {item.unit_name ? ` · ${item.unit_name}` : " · organização"}
                    {` · ${item.exposed_workers} trabalhador(es) possivelmente atingido(s)`}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  <label className="block lg:col-span-2">
                    <span className="text-xs font-black text-slate-300">
                      Medida
                    </span>
                    <textarea
                      rows={2}
                      value={item.measure}
                      onChange={(e) => editar(original, "measure", e.target.value)}
                      placeholder="O que será feito, concretamente, nas condições de trabalho"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">
                      Tipo, na hierarquia de 1.5.5.1.2
                    </span>
                    <select
                      value={item.measure_type}
                      onChange={(e) => editar(original, "measure_type", e.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    >
                      {MEASURE_TYPES.map((tipo) => (
                        <option key={tipo.value} value={tipo.value}>
                          {tipo.label} — {tipo.hint}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">Responsável</span>
                    <select
                      value={item.responsible_membership_id || ""}
                      onChange={(e) =>
                        editar(original, "responsible_membership_id", e.target.value || null)
                      }
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    >
                      <option value="">Sem responsável</option>
                      {responsibles.map((pessoa) => (
                        <option key={pessoa.membership_id} value={pessoa.membership_id}>
                          {pessoa.display_name || pessoa.membership_id}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">Prazo</span>
                    <input
                      type="date"
                      value={(item.due_date || "").slice(0, 10)}
                      onChange={(e) => editar(original, "due_date", e.target.value || null)}
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">Situação</span>
                    <select
                      value={item.status}
                      onChange={(e) => editar(original, "status", e.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    >
                      {STATUSES.map((situacao) => (
                        <option key={situacao.value} value={situacao.value}>
                          {situacao.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">
                      Forma de acompanhamento
                    </span>
                    <input
                      value={item.monitoring_method}
                      onChange={(e) => editar(original, "monitoring_method", e.target.value)}
                      placeholder="Como se verifica que a medida continua de pé"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">
                      Forma de aferição do resultado
                    </span>
                    <input
                      value={item.result_measurement}
                      onChange={(e) => editar(original, "result_measurement", e.target.value)}
                      placeholder="Como se mede se ela produziu efeito"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-black text-slate-300">
                      Data de implementação
                    </span>
                    <input
                      type="date"
                      value={(item.implemented_at || "").slice(0, 10)}
                      onChange={(e) => editar(original, "implemented_at", e.target.value || null)}
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="block lg:col-span-2">
                    <span className="text-xs font-black text-slate-300">
                      Evidência
                      {item.status === "cancelled" && (
                        <span className="ml-1 text-red-300">
                          · obrigatória para cancelar
                        </span>
                      )}
                    </span>
                    <input
                      value={item.evidence}
                      onChange={(e) => editar(original, "evidence", e.target.value)}
                      placeholder="Ata, registro, comunicado — o que comprova"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                    />
                  </label>

                  {item.implemented_at && (
                    <label className="block">
                      <span className="text-xs font-black text-slate-300">
                        Eficácia apurada
                      </span>
                      <select
                        value={item.effectiveness || ""}
                        onChange={(e) =>
                          editar(original, "effectiveness", e.target.value || null)
                        }
                        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                      >
                        <option value="">Ainda não apurada</option>
                        {EFFICACY.map((eficacia) => (
                          <option key={eficacia.value} value={eficacia.value}>
                            {eficacia.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>

                {faltando.length > 0 && (
                  <p className="mt-3 text-xs leading-5 text-amber-200">
                    Para concluir esta medida ainda falta: {faltando.join(", ")}.
                    São as exigências de 1.5.5.2.2 e 1.5.5.3.1, e o banco recusa
                    a conclusão sem elas.
                  </p>
                )}

                {item.implemented_at && !item.effectiveness && (
                  <p className="mt-2 text-xs leading-5 text-amber-200">
                    Medida implementada em {diaLegivel(item.implemented_at)}:
                    a reavaliação de risco residual está devida desde então
                    (1.5.4.4.6 "a"). Ela não tem prazo na norma porque não tem
                    data — a obrigação nasceu do evento.
                  </p>
                )}

                {original.review_trigger === "residual_risk" && (
                  <p className="mt-2 text-xs leading-5 text-cyan-200">
                    Este risco está marcado para reavaliação por risco residual
                    desde {diaLegivel(original.review_due_at)}.
                  </p>
                )}

                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!sujo}
                    onClick={() =>
                      void salvar(original, {
                        measure: item.measure,
                        measure_type: item.measure_type,
                        responsible_membership_id: item.responsible_membership_id,
                        due_date: item.due_date,
                        status: item.status,
                        evidence: item.evidence,
                        monitoring_method: item.monitoring_method,
                        result_measurement: item.result_measurement,
                        implemented_at: item.implemented_at,
                        effectiveness: item.effectiveness,
                      })
                    }
                    className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-black text-white hover:bg-cyan-500 disabled:opacity-40"
                  >
                    Salvar
                  </button>
                  {sujo && (
                    <button
                      type="button"
                      onClick={() =>
                        setRascunhos((atual) => {
                          const copia = { ...atual };
                          delete copia[original.item_id];
                          return copia;
                        })
                      }
                      className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-black text-slate-300"
                    >
                      Descartar alterações
                    </button>
                  )}
                  <span className="self-center text-[11px] text-slate-500">
                    Criada em {diaLegivel(original.created_at)}
                  </span>
                </div>
              </article>
            );
          })}
        </section>
      </main>
    </div>
  );
};

export default Nr1ActionPlan;
