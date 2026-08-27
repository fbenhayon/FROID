import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { GlossarioDeSiglas, Sigla } from "../lib/siglas";

type Campaign = {
  campaign_id: string;
  title: string;
  status: string;
  opens_at: string;
  closes_at: string;
  unit_id: string | null;
  unit_name: string | null;
  target_headcount: number;
  reference_period: string;
};

type Risk = {
  dimension_id: string;
  nr1_factor: string;
  unit_id: string | null;
  cohort_size: number;
  mean_score: number;
  /** A proporção sai em faixa, e a exata não sai. Publicar o tamanho da
   *  coorte junto da proporção exata devolvia a contagem de pessoas na
   *  faixa crítica: numa coorte de 15, 0,067 é exatamente uma pessoa. */
  critical_ratio_band?: { lower: number; upper: number; label: string };
  exposure_level: number;
  severity: number;
  probability: number;
  risk_level: string;
  consequence: string;
  measure_efficacy: string;
  exposed_workers: number;
  rationale: string;
};

type Progress = {
  status: string;
  target_headcount: number;
  responses: number;
  invited: number;
  response_rate: number;
  substantive_responses?: number;
};

// Portão A. Distinto do piso de anonimato: este pergunta se a coorte fala pelo
// efetivo, aquele se ela é grande o bastante para ninguém ser reidentificado.
type Representativeness = {
  population: number;
  achieved: number;
  required: number | null;
  mode: "sample" | "census" | "undeclared";
  met: boolean;
  confidence: number;
  margin_of_error: number;
};

/**
 * Recorte que os portões reprovaram.
 *
 * Não tem coorte, média, severidade nem probabilidade — e a ausência é
 * deliberada, não um campo que faltou preencher: publicar o tamanho de um
 * recorte reprovado devolveria exatamente a coorte pequena que o piso existe
 * para proteger.
 *
 * `escalation` é o que a organização deve fazer, e muda conforme o portão: onde
 * o problema é tamanho de grupo, adesão não resolve e o caminho é a AEP; onde é
 * representatividade, subir a adesão publica o recorte.
 */
type Declared = {
  unit_id: string | null;
  dimension_id: string | null;
  nr1_factor: string | null;
  risk_level: string;
  gate: string;
  required_responses: number | null;
  declared_headcount: number | null;
  escalation: string;
};

type Panel = {
  campaign_id: string;
  reportable: boolean;
  notice: string;
  progress?: Progress;
  representativeness?: Representativeness;
  risks: Risk[];
  /** Existe nos dois casos: quando nada passou e quando parte passou. */
  declared?: Declared[];
};

const GATE_LABEL: Record<string, string> = {
  anonimato: "Grupo pequeno demais para publicar",
  representatividade: "Adesão insuficiente para falar pelo efetivo",
  efetivo_nao_declarado: "Efetivo não declarado",
  campanha_abaixo_do_piso: "Campanha inteira abaixo do piso",
};

const FACTOR_LABEL: Record<string, string> = {
  work_organization: "Gestão e organização do trabalho",
  workload_demand: "Carga e demanda",
  harassment_violence: "Assédio e violência",
  environment_modality: "Ambiente e modalidade",
};

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

const EFFICACY_LABEL: Record<string, string> = {
  none: "sem medida eficaz",
  insufficient: "medida sem eficácia demonstrada",
  partial: "eficácia parcial",
  effective: "medida eficaz",
  eliminated: "perigo eliminado",
};

/** Quanto falta para a coorte falar pelo efetivo.
 *
 * Separado da linha de convites logo acima de propósito. As duas contam
 * respostas e é fácil confundi-las, mas a de cima mede adesão de quem foi
 * convidado e esta mede representação do quadro — uma campanha pode ter 92% de
 * adesão e mesmo assim não representar nada, se só 60 de 3.000 pessoas foram
 * convidadas.
 */
/**
 * Os recortes que não puderam ser classificados, declarados na tela.
 *
 * Existe porque painel vazio não é neutro: quem abre e não vê nada conclui que
 * não há risco ali — e essa é exatamente a conclusão que a ausência de dado não
 * autoriza. Um painel que mostra três setores e cala sobre o quarto afirma,
 * pelo silêncio, que o quarto está bem.
 *
 * A cor é âmbar de propósito, e não vermelha nem verde: não é risco alto e não
 * é risco baixo — é ausência de avaliação, que é uma terceira coisa e precisa
 * parecer uma terceira coisa.
 */
const DeclaredFindings: React.FC<{
  achados?: Declared[];
  titulo?: string;
}> = ({ achados, titulo = "Recortes sem avaliação conclusiva" }) => {
  if (!achados || achados.length === 0) return null;
  return (
    <div className="mt-4 rounded-lg border border-amber-900 bg-amber-950/30 p-4">
      <h3 className="text-xs font-black uppercase tracking-wide text-amber-200">
        {titulo} · {achados.length}
      </h3>
      <p className="mt-1 text-[11px] leading-4 text-amber-100/70">
        Estes recortes entram no inventário como declarados insuficientes para
        classificação. Isso <strong>não</strong> significa ausência de risco: a
        obrigação de gerenciá-lo permanece integral.
      </p>
      <ul className="mt-3 space-y-3">
        {achados.map((achado, indice) => (
          <li
            key={`${achado.unit_id ?? "org"}-${achado.dimension_id ?? indice}`}
            className="rounded border border-amber-900/70 bg-amber-950/40 p-3"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-xs font-black text-amber-100">
                {achado.nr1_factor
                  ? FACTOR_LABEL[achado.nr1_factor] ?? achado.nr1_factor
                  : "Campanha inteira"}
              </span>
              <span className="text-[11px] font-bold text-amber-300">
                {GATE_LABEL[achado.gate] ?? achado.gate}
              </span>
            </div>
            {achado.required_responses !== null &&
              achado.declared_headcount !== null && (
                <p className="mt-1 text-[11px] text-amber-100/70">
                  Amostra necessária: {achado.required_responses} respostas para
                  um efetivo declarado de {achado.declared_headcount}.
                </p>
              )}
            <p className="mt-2 text-[11px] leading-5 text-amber-100/90">
              {achado.escalation}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
};

const RepresentativenessLine: React.FC<{
  verdict?: Representativeness;
}> = ({ verdict }) => {
  if (!verdict) return null;
  if (verdict.mode === "undeclared") {
    return (
      <p className="mt-1 text-xs font-bold text-amber-100/90">
        Efetivo de trabalhadores não declarado nesta campanha.
      </p>
    );
  }
  const required = verdict.required ?? 0;
  const share = required > 0 ? Math.min(1, verdict.achieved / required) : 0;
  return (
    <div className="mt-2">
      <p className="text-xs font-bold text-amber-100/90">
        {verdict.mode === "census" ? "Censo exigido" : "Amostra exigida"}:{" "}
        {verdict.achieved} de {required} respostas substantivas · efetivo{" "}
        {verdict.population}
        {verdict.mode === "sample" &&
          ` · ${Math.round(verdict.confidence * 100)}% de confiança, margem de ${Math.round(
            verdict.margin_of_error * 100,
          )} pontos`}
      </p>
      <div className="mt-1 h-1 w-full overflow-hidden rounded bg-amber-950">
        <div
          className={`h-full ${verdict.met ? "bg-emerald-500" : "bg-amber-500"}`}
          style={{ width: `${Math.round(share * 100)}%` }}
        />
      </div>
    </div>
  );
};

export const Nr1Dashboard: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId =
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [panel, setPanel] = useState<Panel | null>(null);
  const [criteriaVersion, setCriteriaVersion] = useState<number | null>(null);
  const [criteriaPublished, setCriteriaPublished] = useState(true);
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

  const loadCampaigns = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/campaigns`),
        { headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível carregar as campanhas.");
      }
      setCampaigns(Array.isArray(data.campaigns) ? data.campaigns : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar campanhas.");
    } finally {
      setLoading(false);
    }
  }, [headers, organizationId]);

  const loadCriteria = useCallback(async () => {
    if (!organizationId) return;
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/criteria`),
        { headers },
      );
      if (!response.ok) return;
      const data = await response.json();
      setCriteriaVersion(typeof data.version === "number" ? data.version : null);
      setCriteriaPublished(Boolean(data.published));
    } catch {
      // The panel still works on the default criteria; the banner covers it.
    }
  }, [headers, organizationId]);

  const loadPanel = useCallback(
    async (campaignId: string) => {
      if (!organizationId || !campaignId) return;
      setLoading(true);
      setError("");
      setPanel(null);
      try {
        const response = await fetch(
          apiUrl(
            `/api/organizations/${organizationId}/nr1/campaigns/${campaignId}/panel`,
          ),
          { headers },
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || "Não foi possível carregar o painel.");
        }
        setPanel(data as Panel);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao carregar o painel.");
      } finally {
        setLoading(false);
      }
    },
    [headers, organizationId],
  );

  useEffect(() => {
    void loadCampaigns();
    void loadCriteria();
  }, [loadCampaigns, loadCriteria]);

  const generateInventory = async () => {
    if (!selectedId) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/campaigns/${selectedId}/inventory`,
        ),
        { method: "POST", headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível gerar o inventário.");
      }
      setMessage(
        `Inventário gerado com ${data.inventory_rows} linhas. ` +
          `${(data.action_plan_seed || []).length} medidas sugeridas para o plano de ação.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar o inventário.");
    } finally {
      setLoading(false);
    }
  };

  const closeCampaign = async () => {
    if (!selectedId) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/campaigns/${selectedId}/close`,
        ),
        { method: "POST", headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível encerrar a coleta.");
      }
      setMessage("Coleta encerrada. A gradação já pode ser consultada.");
      await loadCampaigns();
      await loadPanel(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao encerrar a coleta.");
    } finally {
      setLoading(false);
    }
  };

  const selected = campaigns.find((item) => item.campaign_id === selectedId) || null;

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-1 · Riscos psicossociais
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              Painel de conformidade
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Resultados sempre agregados. Nenhum recorte abaixo do piso de coorte
              é liberado, e nenhuma resposta individual é legível por ninguém —
              nem pela empresa, nem pelo FROID.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => nav("/nr1/aep")}
              title="Avaliação Ergonômica Preliminar: o método da NR-17 pelo qual a identificação de perigos e a avaliação de riscos psicossociais efetivamente acontecem. Obrigatória para toda organização, inclusive as dispensadas do PGR."
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              AEP
            </button>
            {/* Faltava a porta de volta para a estrutura.
                /access/empresa foi feita para continuar alcancavel depois do
                cadastro — "a empresa volta aqui para acrescentar uma filial ou
                corrigir um efetivo" — e nenhuma tela apontava para ela. O
                unico link vivo estava na escolha de produto, que so aparece
                para quem AINDA NAO se cadastrou. Na pratica, quem terminava o
                cadastro nao tinha mais como cadastrar unidade nenhuma. */}
            <button
              onClick={() => nav("/access/empresa")}
              title="Estabelecimentos e setores: a estrutura sobre a qual os recortes do relatorio sao calculados."
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Estrutura da empresa
            </button>
            <button
              onClick={() => nav("/nr1/campanha")}
              title="Criar a campanha, abrir a coleta e emitir os convites de cada trabalhador."
              className="rounded border border-emerald-700 bg-emerald-950 px-4 py-2 text-xs font-black text-emerald-100 hover:bg-emerald-900"
            >
              Campanha e convites
            </button>
            {/* A duvida sobre a norma chega no meio da operacao, e nao numa
                sessao de estudo. Por isso o acesso fica aqui, ao lado dos
                botoes que a produzem, e nao num menu de ajuda. */}
            <button
              onClick={() => nav("/nr1/explica")}
              title="Perguntas sobre a norma, sobre a metodologia e sobre como ler o resultado — com a fonte normativa."
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              FROID Explica NR-1
            </button>
            <button
              onClick={() => nav("/nr1/comprovante")}
              title="Comprovante de aceite: quem contratou, quando, e a integra dos documentos com a impressao digital de cada um."
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Comprovante de aceite
            </button>
            <button
              onClick={() => nav("/nr1/plano-de-acao")}
              title="Plano de ação: o segundo documento obrigatório do Programa de Gerenciamento de Riscos (PGR), conforme NR-1, subitem 1.5.7.1 'b'."
              className="rounded border border-amber-700 bg-amber-950 px-4 py-2 text-xs font-black text-amber-100 hover:bg-amber-900"
            >
              Plano de ação
            </button>
            <button
              onClick={() => nav("/nr1/eficacia")}
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              Eficácia das medidas
            </button>
            <button
              onClick={() => nav("/dashboard")}
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black hover:bg-slate-900"
            >
              Voltar ao painel
            </button>
          </div>
        </header>

        {!criteriaPublished && (
          <p className="mt-4 rounded border border-amber-900 bg-amber-950/60 p-3 text-xs font-bold text-amber-200">
            Critérios do <Sigla nome="GRO" /> ainda não publicados. A gradação
            está usando o padrão FROID, que é válido e ancorado na{" "}
            <Sigla nome="NR-1" curta /> — alinhá-los à matriz que a sua
            organização já usa no resto do <Sigla nome="PGR" /> é opcional e
            pode ser feito depois, sem refazer avaliação nenhuma.
          </p>
        )}
        {criteriaPublished && criteriaVersion !== null && (
          <p className="mt-4 text-[11px] text-slate-500">
            Gradação pelos critérios do <Sigla nome="GRO" curta /> da
            organização, versão {criteriaVersion}.
          </p>
        )}

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

        <div className="mt-5 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-black">Campanhas</h2>
              <button
                onClick={() => void loadCampaigns()}
                className="text-xs font-bold text-cyan-300"
              >
                Atualizar
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {campaigns.map((item) => (
                <button
                  key={item.campaign_id}
                  type="button"
                  onClick={() => {
                    setSelectedId(item.campaign_id);
                    setMessage("");
                    void loadPanel(item.campaign_id);
                  }}
                  className={`w-full rounded border p-3 text-left text-xs ${
                    selectedId === item.campaign_id
                      ? "border-cyan-500 bg-cyan-950"
                      : "border-slate-700 bg-slate-950 hover:border-slate-500"
                  }`}
                >
                  <div className="flex justify-between gap-3">
                    <p className="font-black text-white">{item.title}</p>
                    <span className="uppercase text-cyan-200">{item.status}</span>
                  </div>
                  <p className="mt-2 text-slate-400">
                    {item.unit_name || "Toda a organização"} ·{" "}
                    {new Date(item.opens_at).toLocaleDateString("pt-BR")} a{" "}
                    {new Date(item.closes_at).toLocaleDateString("pt-BR")}
                  </p>
                </button>
              ))}
              {!campaigns.length && !loading && (
                <p className="rounded bg-slate-950 p-4 text-xs text-slate-400">
                  Nenhuma campanha registrada.
                </p>
              )}
              {loading && (
                <p className="text-xs font-bold text-cyan-300">Carregando...</p>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            {!selected ? (
              <p className="text-sm text-slate-400">
                Selecione uma campanha para ver a gradação de risco.
              </p>
            ) : !panel ? (
              <p className="text-sm text-slate-400">Carregando painel...</p>
            ) : !panel.reportable ? (
              <div className="rounded border border-amber-900 bg-amber-950/50 p-4">
                <h2 className="text-sm font-black text-amber-100">
                  {panel.progress?.status === "closed"
                    ? "Resultado suprimido"
                    : "Coleta em andamento"}
                </h2>
                <p className="mt-2 text-xs leading-5 text-amber-100/80">
                  {panel.notice}
                </p>
                {panel.progress && (
                  <>
                    <p className="mt-3 text-xs font-bold text-amber-100">
                      {panel.progress.responses} de {panel.progress.invited}{" "}
                      convidados responderam
                      {panel.progress.invited > 0 &&
                        ` (${Math.round(panel.progress.response_rate * 100)}%)`}
                    </p>
                    <RepresentativenessLine verdict={panel.representativeness} />
                    {panel.progress.status === "open" && (
                      <button
                        onClick={() => void closeCampaign()}
                        disabled={loading}
                        className="mt-3 rounded bg-amber-600 px-4 py-2 text-xs font-black text-white disabled:opacity-50"
                      >
                        Encerrar coleta
                      </button>
                    )}
                  </>
                )}
                <DeclaredFindings achados={panel.declared} />
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-sm font-black text-white">
                    Gradação de risco · {panel.risks.length} perigos
                  </h2>
                  <button
                    onClick={() => void generateInventory()}
                    disabled={loading}
                    className="rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white disabled:opacity-50"
                  >
                    Gerar inventário
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Ordenado por nível de risco e, em empate, pelo número de
                  trabalhadores possivelmente atingidos (NR-1 1.5.5.2.1.1).
                </p>
                {/* A base amostral fica à vista no painel liberado, e não só
                    quando ele é recusado: é ela que o auditor pergunta ao ler o
                    inventário, e é a frase que o responsável técnico repete. */}
                {panel.representativeness &&
                  panel.representativeness.mode !== "undeclared" && (
                    <p className="mt-1 text-[11px] text-slate-500">
                      Base:{" "}
                      {panel.representativeness.achieved} respostas substantivas
                      sobre um efetivo de {panel.representativeness.population}
                      {panel.representativeness.mode === "census"
                        ? " (censo)"
                        : ` (amostra mínima de ${panel.representativeness.required}, ${Math.round(
                            panel.representativeness.confidence * 100,
                          )}% de confiança, margem de ${Math.round(
                            panel.representativeness.margin_of_error * 100,
                          )} pontos)`}
                      .
                    </p>
                  )}

                <div className="mt-4 space-y-3">
                  {panel.risks.map((risk) => (
                    <article
                      key={`${risk.unit_id || "org"}-${risk.dimension_id}`}
                      className={`rounded border p-4 ${
                        RISK_STYLE[risk.risk_level] || RISK_STYLE.low
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-wider opacity-80">
                            {FACTOR_LABEL[risk.nr1_factor] || risk.nr1_factor}
                          </p>
                          <p className="mt-1 text-sm font-black text-white">
                            {RISK_LABEL[risk.risk_level] || risk.risk_level} ·
                            severidade {risk.severity} × probabilidade{" "}
                            {risk.probability}
                          </p>
                        </div>
                        <div className="text-right text-[11px] opacity-90">
                          <p>coorte n={risk.cohort_size}</p>
                          {risk.critical_ratio_band && (
                            <p title="A proporção é publicada em faixa para que o tamanho da coorte não permita recuperar quantas pessoas estão nela.">
                              faixa crítica: {risk.critical_ratio_band.label}
                            </p>
                          )}
                          <p>{risk.exposed_workers} expostos</p>
                        </div>
                      </div>
                      <p className="mt-2 text-[11px] leading-5 opacity-80">
                        Consequência de maior magnitude:{" "}
                        {risk.consequence.replace(/_/g, " ")} ·{" "}
                        {EFFICACY_LABEL[risk.measure_efficacy] ||
                          risk.measure_efficacy}
                      </p>
                      <details className="mt-2">
                        <summary className="cursor-pointer text-[11px] font-bold opacity-90">
                          Memória de cálculo
                        </summary>
                        <p className="mt-2 text-[11px] leading-5 opacity-75">
                          {risk.rationale}
                        </p>
                      </details>
                    </article>
                  ))}
                </div>
                {/* Depois dos riscos classificados, e não antes: o que foi
                    avaliado vem primeiro. Mas vem — campanha que publica parte
                    dos recortes precisa dizer o que houve com o resto. */}
                <DeclaredFindings achados={panel.declared} />
              </>
            )}
          </section>
        </div>

        <GlossarioDeSiglas termos={["NR-1", "GRO", "PGR", "AEP"]} />
      </main>
    </div>
  );
};
