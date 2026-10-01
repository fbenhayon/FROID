/** Retorno do Checkout Stripe (Psique V2).
 *
 *  O redirect do navegador NUNCA concede crédito: quem concede é o webhook,
 *  uma única vez por compra. Esta página apenas consulta o estado da
 *  Purchase (guardado antes do redirect) até o backend confirmar APPLIED —
 *  e diz exatamente em que pé está, sem inventar sucesso.
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CHAVE_COMPRA_PENDENTE } from "../components/psique/SecaoPsiqueV2";
import { consultarCompraPsiqueV2 } from "../lib/psique-v2-api";

type Situacao =
  | { fase: "sem-registro" }
  | { fase: "consultando"; tentativas: number }
  | { fase: "aplicada"; creditos: number }
  | { fase: "pendente"; status: string }
  | { fase: "indisponivel"; motivo: string };

export function situacaoParaTexto(situacao: Situacao): string {
  switch (situacao.fase) {
    case "sem-registro":
      return "Não encontramos uma compra pendente neste navegador. Se você concluiu o pagamento, os créditos são concedidos pelo servidor de qualquer forma — confira o saldo nas Configurações (/settings).";
    case "consultando":
      return `Pagamento enviado. Aguardando a confirmação do servidor (consulta ${situacao.tentativas})… O crédito só aparece após o webhook do Stripe confirmar.`;
    case "aplicada":
      return `Compra confirmada: ${situacao.creditos} créditos adicionados ao saldo da organização.`;
    case "pendente":
      return `A compra está registrada como ${situacao.status}. Nada foi cobrado em duplicidade; você pode voltar e continuar consultando — nenhuma nova tentativa gera segunda cobrança.`;
    case "indisponivel":
      return `Não foi possível consultar agora (${situacao.motivo}). A compra não se perde: o servidor concede pelo webhook e o saldo aparece nas Configurações.`;
  }
}

/** Shell visual das páginas de retorno do checkout: o mesmo chrome escuro do
 *  app (as rotas de retorno chegam por redirect externo e não herdam layout). */
function MolduraDeRetorno({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link className="text-sm font-black tracking-[0.35em] text-cyan-700" to="/">
            FROID
          </Link>
          <Link
            to="/settings"
            className="rounded-md border border-slate-700 px-3 py-2 text-xs font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
          >
            Configurações
          </Link>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl justify-center px-5 py-16">
        <div className="w-full max-w-xl">{children}</div>
      </main>
    </div>
  );
}

export function PsiqueCompraConfirmacaoPage() {
  const [situacao, setSituacao] = useState<Situacao>({ fase: "consultando", tentativas: 0 });
  const cronometro = useRef<number | null>(null);

  useEffect(() => {
    let registro: { purchase_id: string } | null = null;
    try {
      const bruto = localStorage.getItem(CHAVE_COMPRA_PENDENTE);
      registro = bruto ? (JSON.parse(bruto) as { purchase_id: string }) : null;
    } catch {
      registro = null;
    }
    if (!registro?.purchase_id) {
      setSituacao({ fase: "sem-registro" });
      return;
    }
    const compraId = registro.purchase_id;
    let tentativas = 0;
    let ativo = true;

    async function consultar() {
      if (!ativo) return;
      tentativas += 1;
      setSituacao({ fase: "consultando", tentativas });
      const resposta = await consultarCompraPsiqueV2(compraId);
      if (!ativo) return;
      if (resposta.estado !== "ok") {
        setSituacao({ fase: "indisponivel", motivo: resposta.motivo });
      } else if (resposta.dados.status === "APPLIED") {
        setSituacao({ fase: "aplicada", creditos: resposta.dados.credits });
        try {
          localStorage.removeItem(CHAVE_COMPRA_PENDENTE);
        } catch {
          /* limpeza apenas */
        }
        return; // encerra o polling
      } else {
        setSituacao({ fase: "pendente", status: resposta.dados.status });
      }
      if (tentativas < 40) {
        cronometro.current = window.setTimeout(() => void consultar(), 3000);
      }
    }

    void consultar();
    return () => {
      ativo = false;
      if (cronometro.current !== null) window.clearTimeout(cronometro.current);
    };
  }, []);

  const aplicada = situacao.fase === "aplicada";
  return (
    <MolduraDeRetorno>
      <section className="rounded-lg border border-slate-700 bg-slate-950 p-8 text-center shadow-sm">
        {aplicada ? (
          <>
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-emerald-800/70 bg-emerald-950/30 text-2xl text-emerald-300">
              ✓
            </div>
            <p className="mt-5 text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
              FROID Psique
            </p>
            <h1 className="mt-2 text-3xl font-black">Bem-vindo! Compra confirmada</h1>
            {situacao.fase === "aplicada" && (
              <p className="mt-4 text-5xl font-black text-emerald-300">
                +{situacao.creditos}
                <span className="ml-2 align-middle text-sm font-bold text-slate-400">
                  créditos de análise
                </span>
              </p>
            )}
          </>
        ) : (
          <>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
              FROID Psique
            </p>
            <h1 className="mt-2 text-3xl font-black">Confirmação da compra</h1>
          </>
        )}
        <p data-campo="situacao" className="mt-5 text-sm leading-6 text-slate-300">
          {situacaoParaTexto(situacao)}
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            to="/settings"
            className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
          >
            {aplicada ? "Começar a usar" : "Voltar às Configurações"}
          </Link>
          {aplicada && (
            <Link
              to="/settings"
              className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
            >
              Ver saldo
            </Link>
          )}
        </div>
        {aplicada && (
          <p className="mt-6 text-[11px] leading-5 text-slate-500">
            A concessão foi feita pelo servidor após a confirmação do Stripe —
            o comprovante fica no e-mail do pagamento.
          </p>
        )}
      </section>
    </MolduraDeRetorno>
  );
}

export function PsiqueCompraCanceladaPage() {
  return (
    <MolduraDeRetorno>
      <section className="rounded-lg border border-slate-700 bg-slate-950 p-8 text-center shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
          FROID Psique
        </p>
        <h1 className="mt-2 text-3xl font-black">Checkout cancelado</h1>
        <p className="mt-5 text-sm leading-6 text-slate-300">
          Nenhum valor foi cobrado e nenhum crédito foi concedido. Quando
          quiser, recomece a compra pelas Configurações.
        </p>
        <div className="mt-8 flex justify-center">
          <Link
            to="/settings"
            className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
          >
            Voltar às Configurações
          </Link>
        </div>
      </section>
    </MolduraDeRetorno>
  );
}
