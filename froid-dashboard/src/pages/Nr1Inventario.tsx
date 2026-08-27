import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { GlossarioDeSiglas, Sigla } from "../lib/siglas";

/**
 * O inventário de riscos, na tela e no papel.
 *
 * Esta é a sexta vez que este módulo produz o mesmo padrão: a rota
 * `GET .../inventory` existe desde a migration 011, o documento era gerado e
 * gravado, e nenhuma tela o lia. O cliente clicava em "Gerar inventário",
 * recebia "gerado com N linhas" — e não tinha onde ver as N linhas.
 *
 * É o documento que a fiscalização pede. Gerá-lo sem poder mostrá-lo é ter
 * metade do produto.
 *
 * Duas decisões de leitura:
 *
 * 1. **A linha declarada insuficiente aparece no MESMO documento**, e não numa
 *    seção que possa ser impressa à parte. Separá-las produziria um inventário
 *    que parece completo e uma folha que ninguém abre.
 * 2. **Quando não há nenhuma linha**, a declaração da campanha inteira ocupa o
 *    corpo do documento. Folha em branco é lida como "não há risco aqui", que é
 *    a única conclusão que a ausência de dado nunca autoriza.
 */

type LinhaInventario = {
  inventory_id: string;
  unit_id: string | null;
  unit_name: string | null;
  dimension_id: string;
  dimension_title: string;
  nr1_factor: string;
  cohort_size: number | null;
  mean_score: number | null;
  severity: number | null;
  probability: number | null;
  risk_level: string;
  rationale: string;
  generated_at: string;
  suppression_gate: string | null;
  escalation_note: string;
};

type DeclaracaoDaCampanha = {
  gate: string;
  escalation: string;
  risk_level: string;
};

type Documento = {
  campaign_id: string;
  inventory: LinhaInventario[];
  declared_campaign: DeclaracaoDaCampanha[];
  campaign: {
    status?: string;
    target_headcount?: number;
    responses?: number;
    substantive_responses?: number;
    invited?: number;
    title?: string;
    reference_period?: string;
    opens_at?: string;
    closes_at?: string;
    unit_name?: string | null;
  };
  criteria: { version?: number; source?: string; published?: boolean };
};

type Campanha = { campaign_id: string; title: string; status: string };

const NIVEL: Record<string, { rotulo: string; classe: string }> = {
  critical: { rotulo: "Crítico", classe: "border-red-800 bg-red-950/50 text-red-100" },
  high: { rotulo: "Alto", classe: "border-orange-800 bg-orange-950/40 text-orange-100" },
  moderate: { rotulo: "Moderado", classe: "border-amber-800 bg-amber-950/40 text-amber-100" },
  low: { rotulo: "Baixo", classe: "border-emerald-900 bg-emerald-950/40 text-emerald-100" },
  insuficiente: {
    rotulo: "Sem avaliação conclusiva",
    classe: "border-amber-900 bg-amber-950/30 text-amber-100",
  },
};

const FATOR: Record<string, string> = {
  work_organization: "Gestão e organização do trabalho",
  workload_demand: "Carga e demanda",
  harassment_violence: "Assédio e violência",
  environment_modality: "Ambiente e modalidade",
};

const PORTAO: Record<string, string> = {
  anonimato: "Grupo pequeno demais para publicar",
  representatividade: "Adesão insuficiente para falar pelo efetivo",
  efetivo_nao_declarado: "Efetivo não declarado",
  campanha_abaixo_do_piso: "Campanha inteira abaixo do piso",
};

/** Impressão em A4, e o que sai da folha.
 *
 *  A navegação e os botões não pertencem ao documento: quem imprime está
 *  produzindo a peça que vai para o processo, e um botão "Voltar ao painel"
 *  impresso nela denuncia que aquilo é captura de tela, não documento. */
const CSS_IMPRESSAO = `
@media print {
  @page { size: A4; margin: 16mm 14mm; }
  html, body { background: #fff !important; }
  /* Tudo, e nao so o documento.
     A primeira versao limpava .froid-doc e seus filhos — mas o fundo escuro
     mora no <div> que ENVOLVE a pagina inteira, fora do documento. Com o
     navegador configurado para imprimir cor de fundo, a folha saia um borrao
     preto com texto quase invisivel. Zerar a partir de body alcanca o
     invólucro, os cartoes de risco e as tarjas de nivel, que tambem tem fundo
     proprio. */
  body * {
    background: transparent !important;
    background-image: none !important;
    color: #000 !important;
    border-color: #999 !important;
    box-shadow: none !important;
  }
  .froid-nao-imprime { display: none !important; }
  /* O documento perde a moldura de tela: na folha ele JA e a folha. */
  .froid-doc { border: none !important; padding: 0 !important; }
  .froid-linha { break-inside: avoid; page-break-inside: avoid; }
  .froid-so-impresso { display: block !important; }
}
.froid-so-impresso { display: none; }
`;

function dataCurta(valor?: string | null): string {
  if (!valor) return "—";
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? "—" : data.toLocaleDateString("pt-BR");
}

type Props = { user: FroidUser | null };

export const Nr1Inventario: React.FC<Props> = ({ user }) => {
  const organizationId = String(user?.active_organization_id || "");
  const [parametros, setParametros] = useSearchParams();
  const campanhaUrl = parametros.get("campanha") || "";

  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [selecionada, setSelecionada] = useState(campanhaUrl);
  const [documento, setDocumento] = useState<Documento | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const cabecalhos = useMemo(
    () => ({
      "Content-Type": "application/json",
      Authorization: `Bearer ${window.localStorage.getItem("froid_token") || ""}`,
      "X-FROID-Organization-ID": organizationId,
    }),
    [organizationId],
  );

  const carregarCampanhas = useCallback(async () => {
    if (!organizationId) return;
    try {
      const resposta = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/campaigns`),
        { headers: cabecalhos },
      );
      const corpo = await resposta.json();
      if (!resposta.ok) throw new Error(corpo?.detail || "falha ao listar campanhas");
      const lista: Campanha[] = corpo.campaigns || [];
      setCampanhas(lista);
      // Encerrada mais recente por padrão: é a única que produz documento, e
      // fazer o operador escolher numa lista onde só uma opção funciona é
      // transferir a ele um trabalho que a tela sabe fazer.
      if (!selecionada) {
        const encerrada = lista.find((c) => c.status === "closed");
        if (encerrada) setSelecionada(encerrada.campaign_id);
      }
    } catch (e) {
      setErro(String((e as Error).message));
    }
  }, [cabecalhos, organizationId, selecionada]);

  const carregarDocumento = useCallback(
    async (campaignId: string) => {
      if (!organizationId || !campaignId) return;
      setCarregando(true);
      setErro("");
      try {
        const resposta = await fetch(
          apiUrl(
            `/api/organizations/${organizationId}/nr1/campaigns/${campaignId}/inventory`,
          ),
          { headers: cabecalhos },
        );
        const corpo = await resposta.json();
        if (!resposta.ok) throw new Error(corpo?.detail || "falha ao ler o inventário");
        setDocumento(corpo as Documento);
      } catch (e) {
        setErro(String((e as Error).message));
        setDocumento(null);
      } finally {
        setCarregando(false);
      }
    },
    [cabecalhos, organizationId],
  );

  useEffect(() => {
    void carregarCampanhas();
  }, [carregarCampanhas]);

  useEffect(() => {
    if (selecionada) {
      setParametros({ campanha: selecionada }, { replace: true });
      void carregarDocumento(selecionada);
    }
    // setParametros muda a cada render e não pode entrar aqui.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selecionada, carregarDocumento]);

  const linhas = documento?.inventory || [];
  const classificadas = linhas.filter((linha) => !linha.suppression_gate);
  const declaradas = linhas.filter((linha) => linha.suppression_gate);
  const declaracaoGeral = documento?.declared_campaign || [];

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <style>{CSS_IMPRESSAO}</style>
      <main className="mx-auto max-w-5xl">
        <div className="froid-nao-imprime flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-1 · 1.5.7.3.2
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              Inventário de riscos psicossociais
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => window.print()}
              className="rounded bg-cyan-500 px-4 py-2 text-xs font-black text-cyan-950 hover:bg-cyan-400"
            >
              Imprimir / salvar em PDF
            </button>
            <Link
              to="/nr1"
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Voltar ao painel
            </Link>
          </div>
        </div>

        <div className="froid-nao-imprime mt-4">
          <label className="block">
            <span className="text-xs font-black text-slate-300">Campanha</span>
            <select
              value={selecionada}
              onChange={(e) => setSelecionada(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">Selecione</option>
              {campanhas.map((campanha) => (
                <option key={campanha.campaign_id} value={campanha.campaign_id}>
                  {campanha.title}
                  {campanha.status !== "closed" ? " — ainda em coleta" : ""}
                </option>
              ))}
            </select>
          </label>
          {erro && (
            <p className="mt-3 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
              {erro}
            </p>
          )}
          {carregando && (
            <p className="mt-3 text-xs text-slate-400">Carregando documento...</p>
          )}
        </div>

        {documento && (
          <article className="froid-doc mt-6 rounded-lg border border-slate-800 bg-slate-900 p-6">
            <header className="border-b border-slate-800 pb-4">
              <h2 className="text-lg font-black text-white">
                Inventário de riscos psicossociais relacionados ao trabalho
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                {documento.campaign.title || "Campanha"} ·{" "}
                {documento.campaign.unit_name || "Organização inteira"}
              </p>
              <dl className="mt-3 grid gap-x-6 gap-y-1 text-[11px] leading-5 text-slate-300 sm:grid-cols-2">
                <div>
                  <dt className="inline font-black">Período de referência: </dt>
                  <dd className="inline">
                    {documento.campaign.reference_period || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="inline font-black">Janela de coleta: </dt>
                  <dd className="inline">
                    {dataCurta(documento.campaign.opens_at)} a{" "}
                    {dataCurta(documento.campaign.closes_at)}
                  </dd>
                </div>
                <div>
                  <dt className="inline font-black">
                    Efetivo do período de referência:{" "}
                  </dt>
                  <dd className="inline">
                    {documento.campaign.target_headcount ?? "—"} trabalhadores
                  </dd>
                </div>
                <div>
                  <dt className="inline font-black">Respostas substantivas: </dt>
                  <dd className="inline">
                    {documento.campaign.substantive_responses ??
                      documento.campaign.responses ??
                      0}{" "}
                    de {documento.campaign.invited ?? 0} convidados
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="inline font-black">Critérios de gradação: </dt>
                  <dd className="inline">
                    {documento.criteria.published
                      ? `critérios do GRO da organização, versão ${documento.criteria.version}`
                      : "padrão FROID, ancorado na NR-1 e no Guia do MTE"}
                  </dd>
                </div>
              </dl>
            </header>

            {classificadas.length > 0 && (
              <section className="mt-5">
                <h3 className="text-xs font-black uppercase tracking-wide text-slate-300">
                  Riscos classificados · {classificadas.length}
                </h3>
                <div className="mt-3 space-y-3">
                  {classificadas.map((linha) => (
                    <div
                      key={linha.inventory_id}
                      className={`froid-linha rounded border p-3 ${
                        NIVEL[linha.risk_level]?.classe ||
                        "border-slate-700 bg-slate-950"
                      }`}
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-sm font-black">
                          {linha.dimension_title}
                        </span>
                        <span className="text-[11px] font-black uppercase">
                          {NIVEL[linha.risk_level]?.rotulo || linha.risk_level}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] opacity-80">
                        {FATOR[linha.nr1_factor] || linha.nr1_factor}
                        {linha.unit_name ? ` · ${linha.unit_name}` : ""}
                        {linha.severity && linha.probability
                          ? ` · severidade ${linha.severity} × probabilidade ${linha.probability}`
                          : ""}
                        {linha.cohort_size ? ` · coorte de ${linha.cohort_size}` : ""}
                      </p>
                      {linha.rationale && (
                        <p className="mt-2 text-[11px] leading-5 opacity-90">
                          {linha.rationale}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {(declaradas.length > 0 || declaracaoGeral.length > 0) && (
              <section className="mt-6">
                <h3 className="text-xs font-black uppercase tracking-wide text-amber-200">
                  Recortes sem avaliação conclusiva ·{" "}
                  {declaradas.length + declaracaoGeral.length}
                </h3>
                <p className="mt-1 text-[11px] leading-5 text-amber-100/80">
                  Declarados insuficientes para classificação, nos termos do
                  subitem 1.5.7.3.1. Isso <strong>não</strong> significa ausência
                  de risco: a obrigação de gerenciá-lo permanece integral.
                </p>
                <div className="mt-3 space-y-3">
                  {declaradas.map((linha) => (
                    <div
                      key={linha.inventory_id}
                      className="froid-linha rounded border border-amber-900 bg-amber-950/30 p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-sm font-black text-amber-100">
                          {linha.dimension_title}
                          {linha.unit_name ? ` · ${linha.unit_name}` : ""}
                        </span>
                        <span className="text-[11px] font-bold text-amber-300">
                          {PORTAO[linha.suppression_gate || ""] ||
                            linha.suppression_gate}
                        </span>
                      </div>
                      <p className="mt-2 text-[11px] leading-5 text-amber-100/90">
                        {linha.escalation_note || linha.rationale}
                      </p>
                    </div>
                  ))}
                  {declaracaoGeral.map((declaracao, indice) => (
                    <div
                      key={`geral-${indice}`}
                      className="froid-linha rounded border border-amber-900 bg-amber-950/30 p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-sm font-black text-amber-100">
                          Campanha inteira
                        </span>
                        <span className="text-[11px] font-bold text-amber-300">
                          {PORTAO[declaracao.gate] || declaracao.gate}
                        </span>
                      </div>
                      <p className="mt-2 text-[11px] leading-5 text-amber-100/90">
                        {declaracao.escalation}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {!classificadas.length &&
              !declaradas.length &&
              !declaracaoGeral.length && (
                <p className="mt-6 rounded border border-slate-700 bg-slate-950 p-4 text-xs leading-5 text-slate-300">
                  Nenhuma linha para esta campanha. Se a coleta ainda está aberta,
                  o inventário só é gerado depois do encerramento — durante a
                  coleta o resultado ainda não existe. Se já foi encerrada, gere
                  o inventário no painel de conformidade.
                </p>
              )}

            <footer className="mt-6 border-t border-slate-800 pt-3 text-[11px] leading-5 text-slate-400">
              <p>
                Documento gerado pelo FROID a partir da campanha acima. A
                responsabilidade pelo <Sigla nome="GRO" curta /> e pelo{" "}
                <Sigla nome="PGR" curta /> permanece da organização, que deve
                analisar os resultados, deliberar sobre as medidas e assinar os
                documentos sob sua responsabilidade.
              </p>
              <p className="froid-so-impresso mt-2">
                Emitido em {new Date().toLocaleString("pt-BR")}.
              </p>
            </footer>
          </article>
        )}

        <div className="froid-nao-imprime">
          <GlossarioDeSiglas termos={["NR-1", "PGR", "GRO", "AEP", "MTE"]} />
        </div>
      </main>
    </div>
  );
};

export default Nr1Inventario;
