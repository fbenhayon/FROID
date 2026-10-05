/** Seção Psique V2 nas Configurações — sondada, nunca imposta.
 *
 *  No primeiro render ela consulta a API V2: com o flag do servidor
 *  desligado (ou sem rede), TODAS as consultas voltam "indisponivel" e a
 *  seção não renderiza NADA — a experiência V1 fica intocada, byte a byte.
 *  Quando o backend responde, aparecem saldo, trial e ofertas (números
 *  exclusivamente da API), e o botão de compra só para quem tem a
 *  capacidade — a tela apresenta, o servidor decide.
 */

import { useEffect, useState } from "react";
import {
  criarCheckoutPsiqueV2,
  menuVisivelV2,
  obterCapacidadesPsiqueV2,
  obterCarteiraPsiqueV2,
  obterPrecosPsiqueV2,
  type CapacidadesPsiqueV2,
  type CarteiraPsiqueV2,
  type EstadoV2,
  type PrecosPsiqueV2,
} from "../../lib/psique-v2-api";
import { PsiqueCreditsPanel } from "./PsiqueCreditsPanel";

export const CHAVE_COMPRA_PENDENTE = "froid_psique_v2_compra_pendente";

/** A carteira desta organização já está no V2? null = ainda consultando.
 *  O servidor recusa o checkout V2 de carteira V1 (PSIQUE_WALLET_REQUIRED),
 *  então a tela mostra uma compra só: a do sistema em que a carteira está. */
export function carteiraEmV2(carteira: EstadoV2<CarteiraPsiqueV2>): boolean | null {
  if (carteira.estado === "ok") return true;
  if (carteira.estado === "indisponivel" && carteira.motivo === "CARREGANDO") return null;
  return false;
}

export function SecaoPsiqueV2View({
  carteira,
  precos,
  capacidades,
  aoComprar,
  comprando,
  erroCompra,
}: {
  carteira: EstadoV2<CarteiraPsiqueV2>;
  precos: EstadoV2<PrecosPsiqueV2>;
  capacidades: EstadoV2<CapacidadesPsiqueV2>;
  aoComprar: (productCode: string) => void;
  comprando: string | null;
  erroCompra: string;
}) {
  // Flag desligado no servidor: nada aparece e a V1 segue dona da tela.
  if (
    capacidades.estado === "indisponivel" &&
    carteira.estado === "indisponivel" &&
    precos.estado === "indisponivel"
  ) {
    return null;
  }
  // Carteira ainda no V1: a compra V2 seria recusada pelo servidor; quem vende
  // para esta organização, até a conversão, é o bloco V1.
  if (carteira.estado === "indisponivel" && carteira.motivo === "PSIQUE_WALLET_REQUIRED") {
    return null;
  }
  const podeComprar = menuVisivelV2(capacidades, "comprar-creditos");
  return (
    <div
      data-secao="psique-v2"
      className="rounded-lg border border-cyan-800 bg-cyan-950/20 p-3"
    >
      <p className="text-sm font-semibold">Créditos e licença — Psique V2</p>
      <p className="mt-1 text-xs text-slate-400">
        Contratos separados: pacotes de créditos de análise e licença
        organizacional por profissional clínico. Valores consultados ao vivo.
      </p>
      <div className="mt-3">
        <PsiqueCreditsPanel
          carteira={carteira}
          precos={precos}
          aoComprar={podeComprar ? aoComprar : () => undefined}
        />
      </div>
      {!podeComprar && capacidades.estado === "ok" ? (
        <p data-campo="sem-capacidade-compra" className="mt-2 text-xs text-amber-300">
          Compra disponível apenas para papéis financeiro/administração da
          organização (o servidor decide; esta tela apenas apresenta).
        </p>
      ) : null}
      {comprando ? (
        <p className="mt-2 text-xs text-cyan-200">
          Abrindo o checkout seguro do Stripe para {comprando}…
        </p>
      ) : null}
      {erroCompra ? (
        <p data-campo="erro-compra" className="mt-2 text-xs text-red-300">
          A compra não foi iniciada: {erroCompra}. Nenhum valor foi cobrado.
        </p>
      ) : null}
    </div>
  );
}

export function SecaoPsiqueV2({
  aoResolverCarteira,
}: {
  aoResolverCarteira?: (emV2: boolean) => void;
} = {}) {
  const [carteira, setCarteira] = useState<EstadoV2<CarteiraPsiqueV2>>({
    estado: "indisponivel",
    motivo: "CARREGANDO",
  });
  const [precos, setPrecos] = useState<EstadoV2<PrecosPsiqueV2>>({
    estado: "indisponivel",
    motivo: "CARREGANDO",
  });
  const [capacidades, setCapacidades] = useState<EstadoV2<CapacidadesPsiqueV2>>({
    estado: "indisponivel",
    motivo: "CARREGANDO",
  });
  const [comprando, setComprando] = useState<string | null>(null);
  const [erroCompra, setErroCompra] = useState("");

  useEffect(() => {
    let ativo = true;
    void obterCarteiraPsiqueV2().then((r) => {
      if (!ativo) return;
      setCarteira(r);
      aoResolverCarteira?.(carteiraEmV2(r) === true);
    });
    void obterPrecosPsiqueV2().then((r) => ativo && setPrecos(r));
    void obterCapacidadesPsiqueV2().then((r) => ativo && setCapacidades(r));
    return () => {
      ativo = false;
    };
  }, []);

  async function comprar(productCode: string) {
    setErroCompra("");
    setComprando(productCode);
    // Uma chave por INTENÇÃO de compra: gerada aqui, guardada antes do
    // redirect, e reutilizada pela página de confirmação para consultar.
    const chave = `compra-${productCode}-${crypto.randomUUID()}`;
    const resultado = await criarCheckoutPsiqueV2(productCode, chave);
    if (resultado.estado !== "ok" || !resultado.dados.checkout_url) {
      setComprando(null);
      setErroCompra(
        resultado.estado === "ok" ? "checkout sem URL" : resultado.motivo,
      );
      return;
    }
    try {
      localStorage.setItem(
        CHAVE_COMPRA_PENDENTE,
        JSON.stringify({
          purchase_id: resultado.dados.purchase_id,
          product_code: productCode,
          chave,
        }),
      );
    } catch {
      // Sem storage a confirmação pede o retorno manual; a compra em si
      // não depende disto — o webhook concede de qualquer forma.
    }
    window.location.assign(resultado.dados.checkout_url);
  }

  return (
    <SecaoPsiqueV2View
      carteira={carteira}
      precos={precos}
      capacidades={capacidades}
      aoComprar={(codigo) => void comprar(codigo)}
      comprando={comprando}
      erroCompra={erroCompra}
    />
  );
}
