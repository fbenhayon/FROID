/** Painel de créditos e licença do Psique V2 — apresentacional e à prova de
 *  suposição: só imprime número quando o estado é "ok"; indisponibilidade e
 *  negação aparecem declaradas com o motivo, nunca como saldo 0 ou preço
 *  antigo. Créditos e licença são contratos separados e blocos separados.
 *  A fiação nas rotas do app acontece na virada, junto com a ativação.
 */

import type {
  CarteiraPsiqueV2,
  EstadoV2,
  PrecosPsiqueV2,
} from "../../lib/psique-v2-api";

function formatarBRL(cents: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    cents / 100,
  );
}

function Indisponivel({ contexto, motivo }: { contexto: string; motivo: string }) {
  return (
    <div
      data-estado="indisponivel"
      style={{
        border: "1px dashed #f59e0b",
        borderRadius: 10,
        padding: "12px 14px",
        color: "#b45309",
        fontSize: "0.92rem",
      }}
    >
      {contexto} temporariamente indisponível ({motivo}). Nenhum valor é exibido no
      lugar — tente novamente em instantes.
    </div>
  );
}

export function PsiqueCreditsPanel({
  carteira,
  precos,
  aoComprar,
  compraDesativada = false,
}: {
  carteira: EstadoV2<CarteiraPsiqueV2>;
  precos: EstadoV2<PrecosPsiqueV2>;
  aoComprar: (productCode: string) => void;
  /** Sem permissao de compra, ou um checkout ja abrindo (evita dois por clique duplo). */
  compraDesativada?: boolean;
}) {
  return (
    <section data-painel="psique-v2-creditos">
      <h2 style={{ marginBottom: 8 }}>Créditos de análise</h2>
      {carteira.estado !== "ok" ? (
        <Indisponivel contexto="Saldo" motivo={carteira.motivo} />
      ) : (
        <div data-estado="ok">
          <p data-campo="saldo-disponivel" style={{ fontSize: "1.4rem", fontWeight: 800 }}>
            {carteira.dados.available_balance} créditos disponíveis
          </p>
          <p data-campo="reservado" style={{ fontSize: "0.9rem" }}>
            {carteira.dados.reserved_balance} em análises em andamento
          </p>
          {carteira.dados.trial_status === "ACTIVE" ? (
            <p data-campo="trial" style={{ fontSize: "0.9rem", color: "#2563eb" }}>
              Teste gratuito ativo: {carteira.dados.trial_free_remaining} análises restantes
              {carteira.dados.trial_expires_at
                ? ` (até ${new Date(carteira.dados.trial_expires_at).toLocaleDateString("pt-BR")})`
                : ""}
            </p>
          ) : null}
        </div>
      )}

      <h3 style={{ marginTop: 20 }}>Comprar créditos</h3>
      {precos.estado !== "ok" ? (
        <Indisponivel contexto="Preços" motivo={precos.motivo} />
      ) : (
        <ul data-lista="ofertas" style={{ listStyle: "none", padding: 0 }}>
          {precos.dados.offers.map((oferta) => (
            <li
              key={oferta.product_code}
              data-produto={oferta.product_code}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                padding: "10px 12px",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                marginBottom: 8,
              }}
            >
              <span>
                <strong>{oferta.credits}</strong> créditos — {oferta.name}
              </span>
              <span style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <span data-campo="preco">{formatarBRL(oferta.total_cents)}</span>
                <button
                  type="button"
                  disabled={compraDesativada}
                  aria-disabled={compraDesativada}
                  onClick={() => aoComprar(oferta.product_code)}
                >
                  Comprar
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: 12 }}>
        A licença organizacional é um contrato separado e não concede créditos; sem
        saldo, apenas a análise nova fica bloqueada — histórico e relatórios já
        entregues permanecem acessíveis.
      </p>
    </section>
  );
}
