import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { EtapaNr1 } from "../components/nr1/EtapaNr1";
import { apiUrl } from "../lib/api";
import { printNr1Dossier, type Nr1DossierPayload as Payload } from "../lib/nr1-dossier-print";

type Version = {
  dossier_id: string;
  version: number;
  content_sha256: string;
  previous_sha256: string | null;
  sealed_at: string;
  integrity_verified?: boolean;
  integrity_scope?: string;
  created?: boolean;
  payload?: Payload;
};

type PreviewResponse = {
  preview: Payload;
  preview_sha256: string;
  preview_generated_at?: string;
  versions: Version[];
};

const COUNT_META: Record<string, { label: string; detail: string }> = {
  active_units: { label: "Unidades e grupos", detail: "Recortes organizacionais ativos que delimitam população, local e atividade avaliados." },
  published_criteria_versions: { label: "Critérios do GRO", detail: "Versões publicadas da matriz usada para severidade, probabilidade e classificação." },
  closed_campaigns: { label: "Campanhas encerradas", detail: "Coletas fechadas cuja apuração agregada já pode integrar o ciclo documental." },
  aep_documents: { label: "AEPs", detail: "Avaliações Ergonômicas Preliminares concluídas ou em curso que descrevem trabalho e método." },
  aep_evidence: { label: "Evidências da AEP", detail: "Observações, documentos e registros metodológicos vinculados à avaliação preliminar." },
  worker_participation_records: { label: "Participação", detail: "Registros de consulta e participação dos trabalhadores sem revelar respostas individuais." },
  inventory_rows: { label: "Riscos no inventário", detail: "Perigos avaliados, grupos expostos, controles existentes e classificação consolidada." },
  inventory_history_rows: { label: "Histórico preservado", detail: "Estados anteriores do inventário mantidos para reconstruir decisões e mudanças." },
  action_plan_items: { label: "Medidas de ação", detail: "Controles com responsável, prazo, acompanhamento e resultado esperado." },
  effectiveness_reviews: { label: "Revisões de eficácia", detail: "Comparações posteriores à implementação para verificar o efeito das medidas." },
  corrections_required: { label: "Correções requeridas", detail: "Medidas sem eficácia suficiente que precisam de ajuste e novo acompanhamento." },
};

const readableDate = (value?: string | null) =>
  value ? new Date(value).toLocaleString("pt-BR") : "Não registrado";

export const Nr1Dossier: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId = String(
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "",
  );
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [selected, setSelected] = useState<Version | null>(null);
  const [loading, setLoading] = useState(true);
  const [sealing, setSealing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const headers = useMemo(() => ({
    Authorization: `Bearer ${window.localStorage.getItem("froid_token") || ""}`,
    "X-FROID-Organization-ID": organizationId,
  }), [organizationId]);

  const load = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/dossiers`),
        { headers },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "Não foi possível preparar o dossiê.");
      setData(body as PreviewResponse);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao preparar o dossiê.");
    } finally {
      setLoading(false);
    }
  }, [headers, organizationId]);

  useEffect(() => { void load(); }, [load]);

  const seal = async () => {
    setSealing(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/dossiers`),
        { method: "POST", headers },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "Não foi possível registrar a versão.");
      setSelected(body as Version);
      setMessage(body.created
        ? `Nova versão ${body.version} registrada. O conteúdo foi conferido e encadeado à versão anterior.`
        : `Nenhuma alteração documental foi encontrada. A versão ${body.version} permanece atual e sua integridade foi reconferida.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao registrar a versão.");
    } finally {
      setSealing(false);
    }
  };

  const openVersion = async (version: Version) => {
    setError("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/dossiers/${version.dossier_id}`),
        { headers },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "Não foi possível abrir a versão.");
      setSelected(body as Version);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao abrir a versão.");
    }
  };

  const downloadJson = () => {
    const payload = selected || (data ? {
      status: "preview",
      preview_sha256: data.preview_sha256,
      payload: data.preview,
    } : null);
    if (!payload) return;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = selected ? `froid-nr1-dossie-v${selected.version}.json` : "froid-nr1-dossie-previa.json";
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const printDocument = () => {
    if (!payload) return;
    const opened = printNr1Dossier(payload, {
      version: selected?.version,
      content_sha256: selected?.content_sha256 || data?.preview_sha256 || "",
      previous_sha256: selected?.previous_sha256,
      sealed_at: selected?.sealed_at || data?.preview_generated_at,
      integrity_verified: selected?.integrity_verified,
    });
    if (!opened) setError("O navegador bloqueou a janela de impressão. Autorize pop-ups para o FROID e tente novamente.");
  };

  const payload = selected?.payload || data?.preview;
  const counts = payload?.completeness.counts || {};
  const campaigns = payload?.records.campaigns || [];
  const inventory = payload?.records.inventory || [];
  const actions = payload?.records.action_plan || [];
  const effectiveness = payload?.records.effectiveness || [];
  const riskCounts = inventory.reduce<Record<string, number>>((result, item) => {
    const key = String(item.risk_level || "não classificado");
    result[key] = (result[key] || 0) + 1;
    return result;
  }, {});
  const actionCounts = actions.reduce<Record<string, number>>((result, item) => {
    const key = String(item.status || "não registrado");
    result[key] = (result[key] || 0) + 1;
    return result;
  }, {});

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 print:bg-white print:text-slate-950">
      <main className="mx-auto w-full max-w-[96rem]">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <EtapaNr1 user={user} etapa="NR-1 · Dossiê de evidências" />
            <h1 className="mt-2 text-2xl font-black">Dossiê do processo de avaliação psicossocial</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400 print:text-slate-700">
              Consolida escopo, método, participação, apuração agregada, inventário, medidas e eficácia em uma cadeia verificável. Nenhuma resposta individual integra este documento.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 print:hidden">
            <button onClick={() => nav("/nr1")} className="rounded border border-slate-700 px-4 py-2 text-xs font-black">Voltar ao road map</button>
            <button onClick={downloadJson} disabled={!payload} className="rounded border border-cyan-700 px-4 py-2 text-xs font-black text-cyan-100 disabled:opacity-50">Baixar JSON</button>
            <button onClick={printDocument} disabled={!payload} className="rounded border border-cyan-700 px-4 py-2 text-xs font-black text-cyan-100 disabled:opacity-50">Gerar PDF institucional</button>
            <button onClick={() => void seal()} disabled={!payload || sealing} className="rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white disabled:opacity-50">{sealing ? "Registrando..." : "Registrar nova versão"}</button>
          </div>
        </header>

        {loading && <p className="mt-5 text-sm text-slate-400">Preparando a cadeia documental...</p>}
        {error && <p className="mt-5 rounded border border-red-900 bg-red-950/50 p-3 text-xs font-bold text-red-200">{error}</p>}
        {message && <p className="mt-5 rounded border border-emerald-800 bg-emerald-950/50 p-3 text-xs font-bold text-emerald-200">{message}</p>}

        {payload && <>
          <section className="mt-5 grid gap-4 lg:grid-cols-[1fr_1.2fr]">
            <div className={`rounded-xl border p-5 ${payload.completeness.status === "complete" ? "border-emerald-800 bg-emerald-950/30" : "border-amber-800 bg-amber-950/30"}`}>
              <p className="text-[10px] font-black uppercase tracking-[.18em] text-slate-400">Prontidão documental</p>
              <h2 className="mt-2 text-lg font-black">{payload.completeness.status === "complete" ? "Cadeia documental completa" : "Pontos que exigem atenção"}</h2>
              {payload.completeness.gaps.length === 0 ? <p className="mt-2 text-xs leading-5 text-emerald-100">As etapas previstas no dossiê possuem registros vinculados. A organização ainda deve conferir o conteúdo, as competências profissionais e a assinatura aplicável antes de apresentá-lo.</p> : <ul className="mt-3 space-y-2 text-xs text-amber-100">{payload.completeness.gaps.map((gap) => <li key={gap}>• {gap}</li>)}</ul>}
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white">
              <p className="text-[10px] font-black uppercase tracking-[.18em] text-cyan-300">Identificação da versão</p>
              <p className="mt-2 text-sm font-black">{payload.organization.organization_name || payload.organization.legal_name}</p>
              <p className="mt-1 text-xs text-slate-400">{selected ? "Registro" : "Prévia preparada"}: {readableDate(selected?.sealed_at || data?.preview_generated_at || payload.document.generated_at)}</p>
              <p className="mt-3 break-all font-mono text-[10px] text-cyan-200 print:text-slate-800">SHA-256: {selected?.content_sha256 || data?.preview_sha256}</p>
              {selected ? <p className="mt-2 text-xs text-slate-400">Versão {selected.version} · registrada em {readableDate(selected.sealed_at)} · integridade {selected.integrity_verified ? "conferida" : "não conferida"}</p> : <p className="mt-2 text-xs text-amber-300">Prévia ainda não registrada. Alterações posteriores mudarão o hash.</p>}
              <div className="mt-3 space-y-1 text-[11px] leading-5 text-slate-400">
                <p><strong className="text-slate-300">Integridade:</strong> o FROID recalcula o SHA-256 do conteúdo canônico; a igualdade confirma que os dados lidos são exatamente os registrados.</p>
                <p><strong className="text-slate-300">Imutabilidade verificável:</strong> cada versão é append-only, sem alteração ou exclusão pelo papel operacional, e guarda o hash da versão anterior. Uma divergência evidencia adulteração ou quebra da cadeia.</p>
                <p><strong className="text-slate-300">Limite:</strong> o hash não identifica o signatário. O PDF institucional pode receber a assinatura eletrônica adotada pela organização.</p>
              </div>
            </div>
          </section>

          <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-4 print:bg-white">
            <h2 className="text-sm font-black">Mapa das evidências consolidadas</h2>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">{Object.entries(counts).map(([key, value]) => {
              const meta = COUNT_META[key] || { label: key, detail: "Quantidade de registros consolidados neste componente." };
              // UM tooltip por card, e e o escuro.
              //
              // Os dois carregavam o MESMO texto (`meta.detail`): o `title`
              // nativo do navegador, em caixa de fundo branco junto ao cursor,
              // e o painel estilizado ancorado ao card. O nativo saiu em
              // 11/09/2026, pelo mesmo motivo que saiu do road map em 90bdf5b7
              // — abria fora da largura do card e sobrepunha o vizinho.
              //
              // O `aria-label` abaixo ja leva valor, rotulo e detalhe, entao o
              // leitor de tela nao perde nada com a remocao.
              return <div key={key} tabIndex={0} aria-label={`${value} — ${meta.label}. ${meta.detail}`} className="group relative flex min-h-10 items-center gap-2 rounded-md border border-slate-800 bg-slate-950 px-2 py-1.5 print:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                <strong className="text-base leading-none text-cyan-300 print:text-slate-950">{value}</strong>
                <span className="text-[9px] leading-3 text-slate-400">{meta.label}</span>
                <span role="tooltip" className="pointer-events-none absolute left-1/2 top-full z-30 mt-1 hidden w-60 -translate-x-1/2 rounded-md border border-cyan-900 bg-slate-950 p-2 text-[10px] leading-4 text-slate-200 shadow-xl group-hover:block group-focus:block">{meta.detail}</span>
              </div>;
            })}</div>
          </section>

          <section className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white"><h2 className="text-sm font-black">Campanhas e recortes</h2><div className="mt-3 space-y-3">{campaigns.map((item) => <div key={String(item.id)} className="border-l-2 border-cyan-700 pl-3 text-xs"><strong>{String(item.title)}</strong><p className="mt-1 text-slate-400">{String(item.status)} · {String(item.substantive_responses)} respostas substantivas de {String(item.target_headcount)}</p></div>)}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white"><h2 className="text-sm font-black">Inventário por nível</h2><div className="mt-3 space-y-2">{Object.entries(riskCounts).map(([key, value]) => <p key={key} className="flex justify-between text-xs"><span>{key}</span><strong>{value}</strong></p>)}</div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white"><h2 className="text-sm font-black">Plano por situação</h2><div className="mt-3 space-y-2">{Object.entries(actionCounts).map(([key, value]) => <p key={key} className="flex justify-between text-xs"><span>{key}</span><strong>{value}</strong></p>)}</div><p className="mt-4 text-[11px] text-slate-400">{effectiveness.length} verificações de eficácia vinculadas.</p></div>
          </section>

          <section className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white"><h2 className="text-base font-black">Roteiro para fiscalização</h2><ol className="mt-4 space-y-3">{payload.response_protocol.map((step, index) => <li key={step} className="flex gap-3 text-xs leading-5"><strong className="text-cyan-300">{String(index + 1).padStart(2, "0")}</strong><span>{step}</span></li>)}</ol></div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 print:bg-white"><h2 className="text-base font-black">Base e limites da prova</h2><div className="mt-4 space-y-4">{payload.normative_basis.map((item) => <div key={item.reference}><a href={item.url} target="_blank" rel="noreferrer" className="text-xs font-black text-cyan-300 underline">{item.reference}</a><p className="mt-1 text-[11px] leading-5 text-slate-400">{item.purpose}</p></div>)}</div><div className="mt-5 border-t border-slate-800 pt-4 text-[11px] leading-5 text-slate-400">{Object.values(payload.privacy).map((item) => <p key={item}>• {item}</p>)}</div></div>
          </section>

          {data && data.versions.length > 0 && <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-5 print:hidden"><h2 className="text-base font-black">Histórico imutável e encadeado</h2><p className="mt-1 text-[11px] leading-5 text-slate-400">Abra uma versão para recomputar seu hash e conferir a integridade do conteúdo preservado. Cada registro aponta para o SHA-256 anterior, formando a trilha cronológica.</p><div className="mt-3 grid gap-2 md:grid-cols-2">{data.versions.map((version) => <button key={version.dossier_id} onClick={() => void openVersion(version)} className="rounded-lg border border-slate-700 p-3 text-left hover:border-cyan-600"><strong className="text-xs">Versão {version.version}</strong><span className="ml-2 text-[10px] text-slate-500">{readableDate(version.sealed_at)}</span><span className="mt-2 block truncate font-mono text-[10px] text-cyan-300">{version.content_sha256}</span>{version.previous_sha256 && <span className="mt-1 block truncate font-mono text-[9px] text-slate-600">anterior: {version.previous_sha256}</span>}</button>)}</div></section>}
        </>}
      </main>
    </div>
  );
};
