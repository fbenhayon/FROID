/** Fase 5 — garantias do cliente e do painel Psique V2.
 *
 * O que se afirma: falha da API vira estado declarado (nunca saldo 0 nem
 * preço), o checkout envia somente product_code com a chave de idempotência
 * do cliente, o paywall fecha só a análise nova, e os menus seguem as
 * capacidades do servidor.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";

import {
  criarCheckoutPsiqueV2,
  menuVisivelV2,
  obterCarteiraPsiqueV2,
  obterPrecosPsiqueV2,
  portaoDeAcessoV2,
  type CapacidadesPsiqueV2,
  type CarteiraPsiqueV2,
  type EstadoV2,
  type PrecosPsiqueV2,
} from "./psique-v2-api";
import { PsiqueCreditsPanel } from "../components/psique/PsiqueCreditsPanel";

const memoria = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (chave: string) => memoria.get(chave) ?? null,
  setItem: (chave: string, valor: string) => void memoria.set(chave, valor),
  removeItem: (chave: string) => void memoria.delete(chave),
  clear: () => memoria.clear(),
});

afterEach(() => {
  memoria.clear();
});

function respostaJson(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const PRECOS: PrecosPsiqueV2 = {
  pricing_version: "2.1",
  currency: "brl",
  trial: { credits: 10, days: 14 },
  offers: [
    {
      product_code: "FROID_PRO_10",
      name: "FROID PRO 10",
      credits: 10,
      total_cents: 19900,
      unit_price_display: "19.90",
    },
  ],
  organization_license: { self_service_max: 200 },
};

it("falha de rede vira estado indisponível, sem nenhum número no lugar", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  // fetch continua estubado por teste; localStorage e o shim acima.
  const carteira = await obterCarteiraPsiqueV2();
  expect(carteira.estado).toBe("indisponivel");
  expect("dados" in carteira).toBe(false); // não existe saldo para exibir
  const precos = await obterPrecosPsiqueV2();
  expect(precos.estado).toBe("indisponivel");
});

it("flag desligada (404) e catálogo fora do ar (503) declaram o motivo", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respostaJson(404, { detail: "Not Found" })));
  expect((await obterPrecosPsiqueV2()).estado).toBe("indisponivel");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(respostaJson(503, { code: "PRICING_UNAVAILABLE" })),
  );
  const fora = await obterPrecosPsiqueV2();
  expect(fora.estado === "indisponivel" && fora.motivo).toBe("PRICING_UNAVAILABLE");
});

it("o checkout envia somente product_code, com a chave de idempotência do cliente", async () => {
  const chamadas: Array<{ url: string; init: RequestInit }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      chamadas.push({ url, init });
      return respostaJson(200, { purchase_id: "SYNTHETIC", status: "CHECKOUT_CREATED", checkout_url: "https://x" });
    }),
  );
  localStorage.setItem("froid_token", "SYNTHETIC-token");
  const resultado = await criarCheckoutPsiqueV2("FROID_PRO_10", "intencao-1");
  expect(resultado.estado).toBe("ok");
  expect(chamadas).toHaveLength(1);
  expect(JSON.parse(String(chamadas[0].init.body))).toEqual({ product_code: "FROID_PRO_10" });
  const headers = chamadas[0].init.headers as Record<string, string>;
  expect(headers["X-Idempotency-Key"]).toBe("intencao-1");
  expect(headers.Authorization).toBe("Bearer SYNTHETIC-token");
});

it("paywall: sem saldo fecha SÓ a análise nova; login, histórico e relatórios ficam", () => {
  const zerada: EstadoV2<CarteiraPsiqueV2> = {
    estado: "ok",
    dados: {
      balance: 0,
      reserved_balance: 0,
      available_balance: 0,
      trial_status: "EXPIRED",
      trial_free_remaining: 0,
      trial_expires_at: null,
    },
  };
  const portao = portaoDeAcessoV2(zerada);
  expect(portao.novaAnalise).toBe(false);
  expect(portao.motivoNovaAnalise).toBe("INSUFFICIENT_CREDITS");
  expect(portao.login).toBe(true);
  expect(portao.historico).toBe(true);
  expect(portao.relatoriosEntregues).toBe(true);
  // Carteira indisponível também não fecha o acervo — só a análise nova.
  const indisponivel = portaoDeAcessoV2({ estado: "indisponivel", motivo: "SEM_CONEXAO" });
  expect(indisponivel.novaAnalise).toBe(false);
  expect(indisponivel.historico).toBe(true);
});

it("menus seguem as capacidades do servidor; sem capacidades, nada aparece", () => {
  const capacidades: EstadoV2<CapacidadesPsiqueV2> = {
    estado: "ok",
    dados: {
      rbac_version: 2,
      v2_roles: ["FINANCE"],
      capabilities: {
        clinical_analysis: false,
        purchase_credits: true,
        manage_roles: false,
        read_audit: false,
        supervise: false,
      },
    },
  };
  expect(menuVisivelV2(capacidades, "comprar-creditos")).toBe(true);
  expect(menuVisivelV2(capacidades, "nova-analise")).toBe(false);
  expect(menuVisivelV2(capacidades, "gestao-de-papeis")).toBe(false);
  expect(menuVisivelV2({ estado: "indisponivel", motivo: "x" }, "comprar-creditos")).toBe(false);
});

it("o painel declara indisponibilidade e nunca imprime 0 no lugar do saldo", () => {
  const html = renderToStaticMarkup(
    <PsiqueCreditsPanel
      carteira={{ estado: "indisponivel", motivo: "SEM_CONEXAO" }}
      precos={{ estado: "indisponivel", motivo: "PRICING_UNAVAILABLE" }}
      aoComprar={() => undefined}
    />,
  );
  expect(html).toContain("indisponivel");
  expect(html).toContain("SEM_CONEXAO");
  expect(html).not.toContain("0 créditos");
  expect(html).not.toContain("R$");
});

it("com dados, o painel separa saldo, trial e ofertas com preço do backend", () => {
  const html = renderToStaticMarkup(
    <PsiqueCreditsPanel
      carteira={{
        estado: "ok",
        dados: {
          balance: 12,
          reserved_balance: 2,
          available_balance: 10,
          trial_status: "ACTIVE",
          trial_free_remaining: 3,
          trial_expires_at: "2027-01-10T12:00:00Z",
        },
      }}
      precos={{ estado: "ok", dados: PRECOS }}
      aoComprar={() => undefined}
    />,
  );
  expect(html).toContain("10 créditos disponíveis");
  expect(html).toContain("2 em análises em andamento");
  expect(html).toContain("3 análises restantes");
  expect(html).toContain("FROID_PRO_10");
  expect(html).toContain("199,00");
});
