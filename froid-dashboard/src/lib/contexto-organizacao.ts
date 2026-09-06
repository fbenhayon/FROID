// A organização ativa é UMA por sessão, e atravessa os dois produtos.
//
// `active_organization_id` vive na sessão do servidor (SESSION_USERS) e é o
// que todas as telas — clínicas e NR-1 — usam para saber de quem é o dado.
// Trocar para a empresa NR-1 no painel clínico não abria nada do NR-1: só
// estreitava as permissões (organization_type 'enterprise' retira as
// permissões clínicas identificadas) e os pacientes sumiam da tela. O seletor
// que fazia isso foi retirado do painel clínico por esse motivo.
//
// Quem entra num contexto precisa poder sair dele. Estas funções existem para
// que toda porta entre os dois produtos leve a organização junto, em vez de
// mudar só a URL e deixar a sessão apontando para o lugar errado.

import { apiUrl } from "./api";

export type OrganizacaoDoUsuario = {
  organization_id: string;
  organization_name?: string;
  organization_type?: string;
  roles?: string[];
};

type ComOrganizacoes = {
  organizations?: Array<OrganizacaoDoUsuario | Record<string, unknown>>;
} | null | undefined;

function lista(user: ComOrganizacoes): OrganizacaoDoUsuario[] {
  const bruto = user?.organizations;
  if (!Array.isArray(bruto)) return [];
  return bruto
    .filter((item): item is OrganizacaoDoUsuario =>
      Boolean(item && typeof item === "object" && (item as any).organization_id),
    )
    .map((item) => ({
      organization_id: String(item.organization_id),
      organization_name: item.organization_name
        ? String(item.organization_name)
        : undefined,
      organization_type: String(item.organization_type || "clinic"),
      roles: Array.isArray(item.roles) ? item.roles.map(String) : undefined,
    }));
}

/** As empresas contratantes do NR-1 desta conta.
 *
 *  'enterprise' é o único organization_type que o módulo NR-1 aceita —
 *  `_require_enterprise_context` devolve 409 para qualquer outro. Filtrar aqui
 *  é o que impede a lista de oferecer uma porta que o servidor recusa.
 *
 *  São as organizações de que a conta é MEMBRO, e não todas as empresas da
 *  plataforma: `POST /api/auth/active-organization` responde 403 para
 *  organização sem vínculo, então uma lista mais larga renderizaria links
 *  mortos. Para entrar numa empresa nova, o caminho é conceder o vínculo.
 */
export function organizacoesNr1(user: ComOrganizacoes): OrganizacaoDoUsuario[] {
  return lista(user).filter((item) => item.organization_type === "enterprise");
}

/** A organização clínica desta conta — para onde o painel do Psique olha.
 *
 *  Null quando a conta só tem empresa NR-1: aí não há painel clínico para
 *  restaurar, e a volta é a navegação simples de sempre.
 */
export function organizacaoClinica(
  user: ComOrganizacoes,
): OrganizacaoDoUsuario | null {
  return lista(user).find((item) => item.organization_type !== "enterprise") || null;
}

export function nomeDaOrganizacao(organizacao: OrganizacaoDoUsuario): string {
  return organizacao.organization_name || organizacao.organization_id;
}

/** Troca a organização ativa da sessão. Devolve o motivo quando não troca.
 *
 *  Não engole a falha: navegar assim mesmo levaria a pessoa a um painel vazio
 *  — que é indistinguível de "esta empresa não tem nada" — sem nada na tela
 *  dizendo que a troca não aconteceu.
 */
export async function trocarOrganizacaoAtiva(
  organizationId: string,
): Promise<{ ok: boolean; erro: string }> {
  const alvo = String(organizationId || "").trim();
  if (!alvo) return { ok: false, erro: "Organização não informada." };
  const token = localStorage.getItem("froid_token") || "";
  try {
    const resposta = await fetch(apiUrl("/api/auth/active-organization"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ organization_id: alvo }),
    });
    if (resposta.ok) return { ok: true, erro: "" };
    const corpo = await resposta.json().catch(() => null);
    return {
      ok: false,
      erro: String(corpo?.detail || `Falha ao trocar de organização (${resposta.status}).`),
    };
  } catch {
    return { ok: false, erro: "Sem conexão com o servidor FROID." };
  }
}

/** Entra no contexto de uma organização e abre a rota dela.
 *
 *  Recarrega de propósito: a organização ativa é lida uma vez, no /api/auth/me
 *  do carregamento, e atravessa todas as telas. Meia troca — rota nova,
 *  contexto velho — é o defeito que esta função existe para evitar.
 */
export async function irParaContexto(
  organizationId: string,
  rota: string,
): Promise<string> {
  const resultado = await trocarOrganizacaoAtiva(organizationId);
  if (!resultado.ok) return resultado.erro;
  window.location.hash = `#${rota}`;
  window.location.reload();
  return "";
}
