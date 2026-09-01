// Controle de acesso: revogar, suspender, desabilitar — e desfazer.
//
// Três alavancas separadas de propósito, porque a escolha errada causa dano
// colateral silencioso:
//
//   Vínculo      — a pessoa perde UMA organização e mantém as demais.
//                  É a alavanca de retirar acesso de teste.
//   Organização  — a empresa inteira, com todos os usuários dela.
//                  É a alavanca da inadimplência.
//   Pessoa       — perde acesso a tudo, em toda organização.
//                  É para quem saiu, ou conta comprometida.
//
// A tela obriga a consultar antes de agir. Não é cerimônia: sem ver o estado
// atual, o operador não sabe quantas organizações a pessoa tem — e escolher
// "Pessoa" quando se queria "Vínculo" derruba clientes que ninguém pretendia
// tocar, sem erro visível em lugar nenhum.

import React, { useState } from "react";

import { apiUrl } from "../../lib/api";

type Linha = {
  email: string;
  usuario_status: string;
  organization_id: string;
  organizacao: string;
  organizacao_status: string;
  vinculo_status: string;
  revogado_em: string;
};

type Resultado = {
  encontrado?: boolean;
  alvo?: string;
  nome?: string;
  anterior?: string;
  atual?: string;
  atingidos?: number;
  usuarios_afetados?: number;
};

/** Lê a resposta sem presumir JSON.
 *
 *  Um 500 do servidor devolve "Internal Server Error" em texto puro. Chamar
 *  `.json()` nele produz "Unexpected token 'I'", que esconde o erro de verdade
 *  e manda o operador caçar o problema no lugar errado. */
async function lerResposta(resposta: Response): Promise<{ ok: boolean; dados: any; motivo: string }> {
  const bruto = await resposta.text();
  let dados: any = null;
  try {
    dados = bruto ? JSON.parse(bruto) : null;
  } catch {
    dados = null;
  }
  if (resposta.ok) return { ok: true, dados, motivo: "" };
  const motivo =
    (dados && (dados.detail || dados.message)) ||
    (bruto ? bruto.slice(0, 300) : `erro ${resposta.status}`);
  return { ok: false, dados, motivo: `${resposta.status} — ${motivo}` };
}

const cabecalhos = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${window.localStorage.getItem("froid_token") || ""}`,
});

/** Verde para ativo, âmbar para o resto. O olho precisa achar o bloqueado. */
const Selo: React.FC<{ estado: string }> = ({ estado }) => {
  const ativo = estado === "active";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-black ${
        ativo
          ? "border border-emerald-700 bg-emerald-950 text-emerald-200"
          : "border border-amber-700 bg-amber-950 text-amber-200"
      }`}
    >
      {estado || "—"}
    </span>
  );
};

export const ControleDeAcesso: React.FC = () => {
  const [busca, setBusca] = useState("");
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");

  const consultar = async () => {
    const alvo = busca.trim();
    if (!alvo) return;
    setCarregando(true);
    setErro("");
    setAviso("");
    try {
      const parametro = alvo.includes("@")
        ? `email=${encodeURIComponent(alvo)}`
        : `organization_id=${encodeURIComponent(alvo)}`;
      const resposta = await fetch(apiUrl(`/api/admin/access?${parametro}`), {
        headers: cabecalhos(),
      });
      const { ok, dados, motivo } = await lerResposta(resposta);
      if (!ok) throw new Error(motivo);
      setLinhas(dados?.linhas || []);
      if (!(dados?.linhas || []).length) setAviso("Nada encontrado para este alvo.");
    } catch (e) {
      setErro(String((e as Error).message));
      setLinhas(null);
    } finally {
      setCarregando(false);
    }
  };

  const agir = async (
    rota: "user" | "organization" | "membership",
    corpo: Record<string, string>,
    confirmacao: string,
  ) => {
    if (!window.confirm(confirmacao)) return;
    setCarregando(true);
    setErro("");
    setAviso("");
    try {
      const resposta = await fetch(apiUrl(`/api/admin/access/${rota}`), {
        method: "POST",
        headers: cabecalhos(),
        body: JSON.stringify(corpo),
      });
      const { ok, dados: retorno, motivo } = await lerResposta(resposta);
      if (!ok) throw new Error(motivo);
      const dados: Resultado = retorno || {};
      const alvos = dados.atingidos ?? 0;
      setAviso(
        `Feito: ${dados.anterior} → ${dados.atual}. ` +
          `${alvos} registro alterado` +
          (dados.usuarios_afetados
            ? `, ${dados.usuarios_afetados} usuário(s) da organização afetado(s).`
            : ".") +
          " A sessão do alvo foi encerrada.",
      );
      await consultar();
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setCarregando(false);
    }
  };

  return (
    <section className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h2 className="text-sm font-black text-white">Controle de acesso</h2>
      <p className="mt-1 text-[11px] leading-4 text-slate-400">
        Bloqueia e restaura acesso sem apagar nada. Todo estado é reversível, e o
        comprovante de aceite, as campanhas e o inventário permanecem intactos.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void consultar()}
          placeholder="E-mail da pessoa, ou identificador da organização"
          className="min-w-[22rem] flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500"
        />
        <button
          type="button"
          onClick={() => void consultar()}
          disabled={carregando || !busca.trim()}
          className="rounded-lg bg-cyan-500 px-4 py-2 text-xs font-black text-cyan-950 hover:bg-cyan-400 disabled:opacity-50"
        >
          {carregando ? "Consultando…" : "Consultar"}
        </button>
      </div>

      {erro && (
        <p className="mt-3 rounded border border-red-900 bg-red-950/60 p-3 text-[11px] leading-4 text-red-100">
          {erro}
        </p>
      )}
      {aviso && (
        <p className="mt-3 rounded border border-emerald-800 bg-emerald-950/50 p-3 text-[11px] leading-4 text-emerald-100">
          {aviso}
        </p>
      )}

      {linhas && linhas.length > 0 && (
        <div className="mt-4 space-y-3">
          {linhas.map((linha, indice) => (
            <article
              key={`${linha.email}-${linha.organization_id}-${indice}`}
              className="rounded-lg border border-slate-800 bg-slate-950 p-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs font-black text-slate-100">{linha.email}</p>
                <span className="text-[10px] text-slate-500">
                  conta <Selo estado={linha.usuario_status} />
                </span>
              </div>

              {linha.organization_id ? (
                <>
                  <p className="mt-2 text-[11px] text-slate-300">
                    {linha.organizacao}{" "}
                    <span className="text-slate-600">· {linha.organization_id}</span>
                  </p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                    organização <Selo estado={linha.organizacao_status} />
                    vínculo <Selo estado={linha.vinculo_status} />
                    {linha.revogado_em && <span>revogado em {linha.revogado_em.slice(0, 10)}</span>}
                  </p>

                  {/* A alavanca cirúrgica primeiro: é a que menos machuca. */}
                  <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-800 pt-3">
                    {linha.vinculo_status === "active" ? (
                      <button
                        type="button"
                        onClick={() =>
                          void agir(
                            "membership",
                            {
                              email: linha.email,
                              organization_id: linha.organization_id,
                              status: "revoked",
                            },
                            `Revogar o acesso de ${linha.email} a "${linha.organizacao}"?\n\n` +
                              `As demais organizações desta pessoa NÃO são afetadas. Nada é apagado, e dá para restaurar depois.`,
                          )
                        }
                        className="rounded border border-amber-700 bg-amber-950 px-3 py-1.5 text-[11px] font-black text-amber-100 hover:bg-amber-900"
                       title="Estado atual do vínculo: ativo"
                      >
                        Ativo · revogar este vínculo
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() =>
                          void agir(
                            "membership",
                            {
                              email: linha.email,
                              organization_id: linha.organization_id,
                              status: "active",
                            },
                            `Restaurar o acesso de ${linha.email} a "${linha.organizacao}"?`,
                          )
                        }
                        className="rounded border border-emerald-700 bg-emerald-950 px-3 py-1.5 text-[11px] font-black text-emerald-100 hover:bg-emerald-900"
                       title="Estado atual do vínculo: sem acesso"
                      >
                        {linha.vinculo_status === "revoked" ? "Revogado" : linha.vinculo_status} · restaurar
                      </button>
                    )}

                    {linha.organizacao_status === "active" ? (
                      <button
                        type="button"
                        onClick={() =>
                          void agir(
                            "organization",
                            { organization_id: linha.organization_id, status: "suspended" },
                            `SUSPENDER a organização "${linha.organizacao}" inteira?\n\n` +
                              `TODOS os usuários dela perdem acesso — não apenas ${linha.email}.\n\n` +
                              `Use isto para inadimplência. Para retirar o acesso de uma pessoa só, use "Revogar este vínculo".`,
                          )
                        }
                        className="rounded border border-slate-700 px-3 py-1.5 text-[11px] font-black text-slate-300 hover:bg-slate-800"
                       title="Estado atual da organização: ativa"
                      >
                        Ativa · suspender a organização
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() =>
                          void agir(
                            "organization",
                            { organization_id: linha.organization_id, status: "active" },
                            `Reativar a organização "${linha.organizacao}"?`,
                          )
                        }
                        className="rounded border border-emerald-700 bg-emerald-950 px-3 py-1.5 text-[11px] font-black text-emerald-100 hover:bg-emerald-900"
                       title="Estado atual da organização: sem acesso"
                      >
                        {linha.organizacao_status === "suspended" ? "Suspensa" : linha.organizacao_status} · reativar
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <p className="mt-2 text-[11px] text-slate-500">
                  Sem vínculo com organização — provavelmente profissional autônomo.
                </p>
              )}
            </article>
          ))}

          {/* A alavanca mais ampla fica separada e por último, de propósito. */}
          <div className="rounded-lg border border-red-900 bg-red-950/30 p-4">
            <p className="text-[11px] font-black text-red-200">
              Desabilitar a pessoa inteira
            </p>
            <p className="mt-1 text-[11px] leading-4 text-red-100/80">
              Retira o acesso de <strong>{linhas[0].email}</strong> a{" "}
              <strong>todas</strong> as organizações, de uma vez. Se a intenção é
              apenas tirar o acesso a um cliente, use “Revogar este vínculo” acima
              — a diferença não aparece em lugar nenhum depois de feita.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {linhas[0].usuario_status === "active" ? (
                <button
                  type="button"
                  onClick={() =>
                    void agir(
                      "user",
                      { email: linhas[0].email, status: "disabled" },
                      `DESABILITAR a conta de ${linhas[0].email}?\n\n` +
                        `Ela perde acesso a TODAS as organizações. Nada é apagado e dá para reabilitar.`,
                    )
                  }
                  className="rounded border border-red-800 bg-red-950 px-3 py-1.5 text-[11px] font-black text-red-100 hover:bg-red-900"
                 title="Estado atual da conta: ativa"
                >
                  Ativa · desabilitar a conta
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    void agir(
                      "user",
                      { email: linhas[0].email, status: "active" },
                      `Reabilitar a conta de ${linhas[0].email}?`,
                    )
                  }
                  className="rounded border border-emerald-700 bg-emerald-950 px-3 py-1.5 text-[11px] font-black text-emerald-100 hover:bg-emerald-900"
                 title="Estado atual da conta: desabilitada"
                >
                  Desabilitada · reabilitar
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <p className="mt-4 border-t border-slate-800 pt-3 text-[10px] leading-4 text-slate-600">
        Quem for bloqueado recebe, ao tentar entrar: “Acesso restrito, entre em
        contato com froid@froid.com.br para maiores detalhes”. Toda operação
        encerra a sessão aberta do alvo e fica registrada na trilha de auditoria,
        com quem fez e o estado anterior.
      </p>
    </section>
  );
};
