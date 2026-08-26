import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

/**
 * Comprovante de aceite: documento diferente do contrato.
 *
 * O contrato prova O TEXTO. O comprovante prova a CONTRATACAO daquele texto,
 * por aquela pessoa, naquela data. Sao as duas metades, e a segunda quase
 * ninguem tem: assinatura eletronica de mercado prova quem assinou, mas o
 * fornecedor tipicamente so consegue dizer "era a versao 3" sem provar qual
 * texto era a versao 3. Aqui o SHA-256 do texto viaja com o aceite.
 *
 * Duas propriedades sao o documento inteiro:
 *
 * - A INTEGRA vem junto. Comprovante que cita um documento sem reproduzi-lo
 *   obriga quem o le a ir buscar o texto em outro lugar, e no dia em que a
 *   busca importa o texto vigente ja pode ser outro.
 * - Divergencia entre o hash REGISTRADO e o hash do texto VIGENTE e dita em
 *   voz alta, e o texto vigente deixa de ser impresso como se fosse o aceito.
 *   Imprimir o texto de hoje sob a data de ontem e o defeito que anula o
 *   comprovante — e e o defeito silencioso, porque a folha sai bonita.
 */

const CSS_IMPRESSAO = `
@media print {
  @page { size: A4; margin: 18mm 16mm; }
  html, body { background: #fff !important; }
  .froid-nao-imprime { display: none !important; }
  .froid-impresso { background: #fff !important; color: #000 !important; }
  .froid-impresso * { background: transparent !important; color: #000 !important;
    border-color: #999 !important; box-shadow: none !important; }
  .froid-clausula { break-inside: avoid; page-break-inside: avoid; }
  .froid-pagina-nova { break-before: page; page-break-before: always; }
  .froid-rodape-impressao { display: block !important; }
}
.froid-rodape-impressao { display: none; }
`;

type Aceite = {
  document_key: string;
  document_version: string;
  document_sha256: string;
  acceptance_context: string;
  accepted_at: string;
  organization_id: string;
  subject_kind: string;
};

type DocumentoLegal = {
  key: string;
  version: string;
  sha256: string;
  title: string;
  sections: Array<{ heading: string; body: string }>;
};

type Resposta = {
  ledger_configured: boolean;
  acceptances: Aceite[];
  organization_id: string;
  subject_email: string;
  documents: Record<string, DocumentoLegal>;
  supplier: { name?: string; tax_id?: string; address?: string; contact_email?: string };
};

type Perfil = {
  organization_legal_name?: string;
  organization_name?: string;
  organization_document?: string;
  owner_name?: string;
  account_type?: string;
};

type Props = { user: FroidUser | null };

function token() {
  return localStorage.getItem("froid_token") || "";
}

/** Data e hora no fuso de Brasilia, com o fuso DITO.
 *
 *  "25/08/2026 21:14" sem fuso e ambiguo num documento que pode ser lido
 *  noutro pais, e a hora do aceite e exatamente o que o comprovante prova. */
export function carimbo(iso: string): string {
  if (!iso) return "";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return iso;
  const formatado = data.toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${formatado} (horário de Brasília)`;
}

export function cnpjFormatado(digitos: string): string {
  const limpo = String(digitos || "").replace(/\D/g, "");
  if (limpo.length !== 14) return digitos || "";
  return `${limpo.slice(0, 2)}.${limpo.slice(2, 5)}.${limpo.slice(5, 8)}/${limpo.slice(8, 12)}-${limpo.slice(12)}`;
}

/**
 * O aceite que vale por documento: o MAIS RECENTE.
 *
 * O ledger e append-only e acumula renovacoes. Um comprovante que listasse
 * todas as linhas mostraria o mesmo documento tres vezes com datas diferentes,
 * e quem o lesse teria de adivinhar qual esta em vigor. A ordem cronologica
 * vem do servidor (ASC), entao a ultima ocorrencia de cada chave e a vigente.
 */
export function vigentesPorDocumento(aceites: Aceite[]): Aceite[] {
  const porChave = new Map<string, Aceite>();
  for (const aceite of aceites) {
    porChave.set(aceite.document_key, aceite);
  }
  return Array.from(porChave.values());
}

export const Nr1Acceptance: React.FC<Props> = ({ user }) => {
  const organizationId = String(user?.active_organization_id || "");
  const [dados, setDados] = useState<Resposta | null>(null);
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    if (!organizationId) return;
    setErro("");
    try {
      const cabecalhos = {
        Authorization: `Bearer ${token()}`,
        "X-FROID-Organization-ID": organizationId,
      };
      const [aceites, meuPerfil] = await Promise.all([
        fetch(apiUrl(`/api/organizations/${organizationId}/legal-acceptances`), {
          headers: cabecalhos,
        }).then(async (resposta) => {
          const corpo = await resposta.json();
          if (!resposta.ok) throw new Error(corpo?.detail || "Comprovante indisponível.");
          return corpo as Resposta;
        }),
        fetch(apiUrl("/api/professional/profile"), { headers: cabecalhos })
          .then((resposta) => resposta.json())
          // Perfil e enfeite aqui: sem ele o comprovante ainda prova o aceite,
          // so fica sem a razao social no cabecalho.
          .catch(() => ({})),
      ]);
      setDados(aceites);
      setPerfil((meuPerfil?.profile as Perfil) || null);
    } catch (e) {
      setErro(String((e as Error).message));
    }
  }, [organizationId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const vigentes = useMemo(
    () => (dados ? vigentesPorDocumento(dados.acceptances) : []),
    [dados],
  );

  const emitidoEm = useMemo(() => carimbo(new Date().toISOString()), []);

  if (!organizationId) {
    return (
      <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
        <p className="text-sm">Nenhuma organização ativa nesta sessão.</p>
      </div>
    );
  }

  return (
    <div className="froid-impresso min-h-screen bg-slate-950 text-slate-100">
      <style>{CSS_IMPRESSAO}</style>

      <header className="froid-nao-imprime border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <Link
              to="/nr1"
              className="rounded border border-slate-700 px-3 py-1.5 text-xs font-black text-slate-200 hover:bg-slate-800"
            >
              ← Painel NR-1
            </Link>
            <span className="text-sm font-black uppercase tracking-[0.28em] text-cyan-300">
              FROID
            </span>
          </div>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded border border-cyan-700 bg-cyan-950 px-3 py-1.5 text-xs font-black text-cyan-200 hover:bg-cyan-900"
          >
            Imprimir / salvar em PDF
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 py-10">
        {erro && (
          <p className="froid-nao-imprime mb-6 rounded border border-red-800 bg-red-950 p-4 text-sm text-red-100">
            {erro}
          </p>
        )}

        <h1 className="text-2xl font-black text-white">
          Comprovante de aceite — FROID NR-1
        </h1>
        <p className="mt-1 text-xs text-slate-400">
          Emitido em {emitidoEm}
        </p>

        {dados && !dados.ledger_configured && (
          <p className="mt-5 rounded border border-amber-700 bg-amber-950 p-4 text-xs leading-5 text-amber-100">
            <strong>Não foi possível verificar os aceites.</strong> A chave de
            auditoria jurídica do servidor não está configurada, e sem ela não há
            como localizar os registros. Isto não significa que nada foi aceito —
            significa que este comprovante não pode afirmar nem uma coisa nem
            outra, e um documento de prova precisa dizer essa diferença em vez de
            imprimir uma lista vazia.
          </p>
        )}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900/70 p-5 froid-clausula">
          <dl className="grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                Contratante
              </dt>
              <dd className="mt-1 font-bold text-slate-100">
                {perfil?.organization_legal_name ||
                  perfil?.organization_name ||
                  "— não informado —"}
              </dd>
              {perfil?.organization_document && (
                <dd className="text-xs text-slate-400">
                  CNPJ {cnpjFormatado(perfil.organization_document)}
                </dd>
              )}
            </div>
            <div>
              <dt className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                Aceito por
              </dt>
              <dd className="mt-1 font-bold text-slate-100">
                {dados?.subject_email || user?.email || ""}
              </dd>
              {perfil?.owner_name && (
                <dd className="text-xs text-slate-400">{perfil.owner_name}</dd>
              )}
            </div>
            <div>
              <dt className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                Contratada
              </dt>
              <dd className="mt-1 text-xs text-slate-300">
                {dados?.supplier?.name || "—"}
                {dados?.supplier?.tax_id ? `, CPF/CNPJ ${dados.supplier.tax_id}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                Organização
              </dt>
              <dd className="mt-1 break-all font-mono text-[11px] text-slate-400">
                {dados?.organization_id || organizationId}
              </dd>
            </div>
          </dl>
        </section>

        <section className="mt-5">
          <h2 className="text-sm font-black text-white">
            Documentos aceitos nesta contratação
          </h2>

          {dados && dados.ledger_configured && !vigentes.length && (
            <p className="mt-3 rounded border border-amber-800 bg-amber-950/60 p-4 text-xs leading-5 text-amber-100">
              Nenhum aceite registrado para esta conta. Se o cadastro foi feito
              antes de o registro de aceites entrar em operação, o contrato
              precisa ser aceito novamente para que exista comprovante.
            </p>
          )}

          <ol className="mt-3 space-y-3">
            {vigentes.map((aceite, indice) => {
              const vigente = dados?.documents?.[aceite.document_key];
              const divergiu = Boolean(
                vigente && vigente.sha256 !== aceite.document_sha256,
              );
              return (
                <li
                  key={`${aceite.document_key}-${aceite.accepted_at}`}
                  className="froid-clausula rounded-lg border border-slate-800 bg-slate-900/70 p-4"
                >
                  <p className="text-sm font-black text-slate-100">
                    {indice + 1}. {vigente?.title || aceite.document_key}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Versão {aceite.document_version} · aceito em{" "}
                    {carimbo(aceite.accepted_at)}
                  </p>
                  <p className="mt-1 break-all font-mono text-[11px] text-slate-400">
                    SHA-256 {aceite.document_sha256}
                  </p>
                  {divergiu && (
                    <p className="mt-2 rounded border border-amber-800 bg-amber-950/60 p-2 text-[11px] leading-4 text-amber-100">
                      <strong>O texto vigente não é o texto aceito.</strong> A
                      versão publicada hoje tem impressão digital{" "}
                      <span className="break-all font-mono">{vigente?.sha256}</span>
                      . A íntegra reproduzida adiante é a do texto <em>vigente</em>,
                      e não a do que foi aceito nesta data — o FROID publica os
                      documentos por versão, e o texto aceito é o identificado
                      pelo SHA-256 acima.
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
        </section>

        {/* A integra, uma pagina nova por documento. Comprovante que cita sem
            reproduzir obriga quem le a ir buscar o texto noutro lugar — e no dia
            em que a busca importa, o vigente ja pode ser outro. */}
        {vigentes.map((aceite) => {
          const documento = dados?.documents?.[aceite.document_key];
          if (!documento) return null;
          return (
            <article
              key={`integra-${aceite.document_key}`}
              className="froid-pagina-nova mt-8 rounded-xl border border-slate-800 bg-slate-900/70 p-6"
            >
              <h2 className="text-lg font-black text-white">{documento.title}</h2>
              <p className="mt-1 text-xs text-slate-400">
                Versão {documento.version}
              </p>
              <p className="mt-1 break-all font-mono text-[11px] text-slate-400">
                SHA-256 {documento.sha256}
              </p>
              <div className="mt-4 space-y-4 text-sm leading-7 text-slate-300">
                {documento.sections.map((secao, indice) => (
                  <section key={secao.heading} className="froid-clausula">
                    <h3 className="text-sm font-black text-white">
                      {indice + 1}. {secao.heading}
                    </h3>
                    <p className="mt-1 whitespace-pre-line">{secao.body}</p>
                  </section>
                ))}
              </div>
            </article>
          );
        })}

        <section className="froid-clausula mt-8 border-t border-slate-800 pt-4 text-xs leading-5 text-slate-400">
          <p>
            Este comprovante reproduz registros de aceite mantidos em livro
            imutável: a tabela que os guarda recusa alteração e exclusão por
            gatilho de banco de dados. O FROID não armazena o endereço de e-mail
            do aceitante nesse livro — a vinculação é feita por código de
            verificação derivado com chave do servidor, o que permite conferir o
            registro sem manter o dado pessoal replicado.
          </p>
          <p className="mt-2">
            A impressão digital SHA-256 identifica o texto exato aceito. Dois
            documentos com o mesmo SHA-256 são o mesmo texto, caractere por
            caractere; qualquer alteração, ainda que de um espaço, produz uma
            impressão digital inteiramente diferente.
          </p>
          <p className="mt-2 froid-rodape-impressao hidden">
            Documento gerado em {emitidoEm}. Contato:{" "}
            {dados?.supplier?.contact_email || "froid@froid.com.br"}.
          </p>
        </section>
      </main>
    </div>
  );
};

export default Nr1Acceptance;
