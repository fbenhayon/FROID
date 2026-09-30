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

  return (
    <div className="mx-auto max-w-xl p-6 text-slate-100">
      <h1 className="text-xl font-black">Confirmação da compra</h1>
      <p data-campo="situacao" className="mt-4 text-sm">
        {situacaoParaTexto(situacao)}
      </p>
      <div className="mt-6">
        <Link
          to="/settings"
          className="rounded bg-cyan-700 px-4 py-2 text-sm font-bold text-white"
        >
          Voltar às Configurações
        </Link>
      </div>
    </div>
  );
}

export function PsiqueCompraCanceladaPage() {
  return (
    <div className="mx-auto max-w-xl p-6 text-slate-100">
      <h1 className="text-xl font-black">Checkout cancelado</h1>
      <p className="mt-4 text-sm">
        Nenhum valor foi cobrado e nenhum crédito foi concedido. Quando
        quiser, recomece a compra pelas Configurações.
      </p>
      <div className="mt-6">
        <Link
          to="/settings"
          className="rounded bg-cyan-700 px-4 py-2 text-sm font-bold text-white"
        >
          Voltar às Configurações
        </Link>
      </div>
    </div>
  );
}
