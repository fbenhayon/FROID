/** Cliente do Psique V2 — preços, carteira, capacidades e compra.
 *
 * Regra da casa (incidente dos zeros de 03/09/2026): falha da API NUNCA vira
 * saldo 0 nem preço antigo. Toda resposta destas funções é um estado
 * discriminado — quem consome só tem acesso aos números quando o estado é
 * "ok"; nos demais, o que existe é o motivo, para a tela declarar.
 */

import { apiUrl } from "./api";

export type EstadoV2<T> =
  | { estado: "ok"; dados: T }
  | { estado: "indisponivel"; motivo: string }
  | { estado: "negado"; motivo: string };

export interface OfertaPsiqueV2 {
  product_code: string;
  name: string;
  credits: number;
  total_cents: number;
  unit_price_display: string;
}

export interface PrecosPsiqueV2 {
  pricing_version: string;
  currency: string;
  trial: { credits: number; days: number };
  offers: OfertaPsiqueV2[];
  organization_license: { self_service_max: number };
}

export interface CarteiraPsiqueV2 {
  balance: number;
  reserved_balance: number;
  available_balance: number;
  trial_status: string;
  trial_free_remaining: number;
  trial_expires_at: string | null;
}

export interface CapacidadesPsiqueV2 {
  rbac_version: number;
  v2_roles: string[];
  capabilities: {
    clinical_analysis: boolean;
    purchase_credits: boolean;
    manage_roles: boolean;
    read_audit: boolean;
    supervise: boolean;
  };
}

function cabecalhos(): Record<string, string> {
  const token =
    typeof localStorage !== "undefined"
      ? localStorage.getItem("froid_token") || ""
      : "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function chamar<T>(
  caminho: string,
  init?: RequestInit,
): Promise<EstadoV2<T>> {
  let resposta: Response;
  try {
    resposta = await fetch(apiUrl(caminho), init);
  } catch {
    return { estado: "indisponivel", motivo: "SEM_CONEXAO" };
  }
  if (resposta.ok) {
    try {
      return { estado: "ok", dados: (await resposta.json()) as T };
    } catch {
      return { estado: "indisponivel", motivo: "RESPOSTA_ILEGIVEL" };
    }
  }
  const corpo = await resposta.json().catch(() => null);
  const motivo = String(
    (corpo && (corpo.detail || corpo.code)) || `HTTP_${resposta.status}`,
  );
  if (resposta.status === 401 || resposta.status === 403) {
    return { estado: "negado", motivo };
  }
  return { estado: "indisponivel", motivo };
}

export function obterPrecosPsiqueV2(): Promise<EstadoV2<PrecosPsiqueV2>> {
  return chamar<PrecosPsiqueV2>("/api/psique/v2/pricing");
}

export function obterCarteiraPsiqueV2(): Promise<EstadoV2<CarteiraPsiqueV2>> {
  return chamar<CarteiraPsiqueV2>("/api/psique/v2/wallet", { headers: cabecalhos() });
}

export function obterCapacidadesPsiqueV2(): Promise<EstadoV2<CapacidadesPsiqueV2>> {
  return chamar<CapacidadesPsiqueV2>("/api/psique/v2/capabilities", {
    headers: cabecalhos(),
  });
}

/** O corpo leva SOMENTE o código do produto; preço, créditos e moeda são do
 *  servidor. A chave de idempotência é da intenção do usuário: gere uma por
 *  clique de compra e reutilize a mesma em retentativas dessa intenção. */
export function criarCheckoutPsiqueV2(
  productCode: string,
  chaveIdempotencia: string,
): Promise<EstadoV2<{ purchase_id: string; status: string; checkout_url: string | null }>> {
  return chamar("/api/psique/v2/checkout", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Idempotency-Key": chaveIdempotencia,
      ...cabecalhos(),
    },
    body: JSON.stringify({ product_code: productCode }),
  });
}

export function consultarCompraPsiqueV2(
  purchaseId: string,
): Promise<EstadoV2<{ status: string; credits: number; applied_at: string | null }>> {
  return chamar(`/api/psique/v2/purchases/${purchaseId}`, { headers: cabecalhos() });
}

/** Paywall V2: sem saldo, SOMENTE a análise nova fecha. Login, histórico e
 *  relatórios já entregues nunca dependem de crédito — isto é contrato, não
 *  preferência de tela, e o teste trava os quatro campos. */
export function portaoDeAcessoV2(carteira: EstadoV2<CarteiraPsiqueV2>): {
  novaAnalise: boolean;
  motivoNovaAnalise: string;
  login: true;
  historico: true;
  relatoriosEntregues: true;
} {
  if (carteira.estado !== "ok") {
    return {
      novaAnalise: false,
      motivoNovaAnalise: carteira.motivo,
      login: true,
      historico: true,
      relatoriosEntregues: true,
    };
  }
  const disponivel = carteira.dados.available_balance;
  return {
    novaAnalise: disponivel > 0,
    motivoNovaAnalise: disponivel > 0 ? "" : "INSUFFICIENT_CREDITS",
    login: true,
    historico: true,
    relatoriosEntregues: true,
  };
}

/** Menus por capacidade: a tela apresenta, o servidor decide. */
export const MENUS_POR_CAPACIDADE: Record<string, keyof CapacidadesPsiqueV2["capabilities"]> = {
  "nova-analise": "clinical_analysis",
  "comprar-creditos": "purchase_credits",
  "licenca-organizacional": "purchase_credits",
  "gestao-de-papeis": "manage_roles",
  auditoria: "read_audit",
  supervisao: "supervise",
};

export function menuVisivelV2(
  capacidades: EstadoV2<CapacidadesPsiqueV2>,
  menu: keyof typeof MENUS_POR_CAPACIDADE,
): boolean {
  if (capacidades.estado !== "ok") return false;
  return capacidades.dados.capabilities[MENUS_POR_CAPACIDADE[menu]] === true;
}
