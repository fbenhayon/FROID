import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { defaultAuthenticatedPath, homeDoProduto } from "./product-choice";

/**
 * A empresa contratante do NR-1 entrava no painel CLINICO.
 *
 * Apurado em 27/08/2026, com a conta da TATICCA: depois de concluir o
 * cadastro, ela caía em /dashboard e via "Saldo: 5 sessões", "Meus Pacientes",
 * "Gestão da clínica" e o FROID Explica clínico.
 *
 * Além de inútil para ela, é a tela que mais contradiz o que o produto
 * promete: o empregador não tem, e não pode ter, pacientes. Numa demonstração
 * comercial é a primeira coisa que o cliente vê.
 */

const empresa = {
  access_status: { onboarding_required: false, account_type: "nr1_company" },
};
const profissional = {
  access_status: { onboarding_required: false, account_type: "individual" },
};
const clinica = {
  access_status: { onboarding_required: false, account_type: "organization" },
};

describe("cada conta vai para a casa do seu produto", () => {
  it("a empresa NR-1 vai para o painel de conformidade", () => {
    expect(homeDoProduto(empresa)).toBe("/nr1");
    expect(defaultAuthenticatedPath(empresa, null)).toBe("/nr1");
  });

  it("o profissional continua indo para o painel clínico", () => {
    expect(homeDoProduto(profissional)).toBe("/dashboard");
    expect(defaultAuthenticatedPath(profissional, null)).toBe("/dashboard");
  });

  it("a clínica continua indo para o painel clínico", () => {
    expect(homeDoProduto(clinica)).toBe("/dashboard");
  });

  it("conta sem tipo declarado não é mandada para o NR-1", () => {
    // Na dúvida, o caminho antigo: mandar um profissional para o painel de
    // conformidade o deixaria numa tela onde ele não tem permissão nenhuma.
    expect(homeDoProduto({ access_status: { onboarding_required: false } })).toBe(
      "/dashboard",
    );
    expect(homeDoProduto(null)).toBe("/dashboard");
  });
});

describe("o administrador continua tendo precedência", () => {
  it("vai para /admin mesmo com cadastro pendente", () => {
    // Ele tem onboarding_required verdadeiro para sempre, porque nunca comprou
    // plano de sessões para si mesmo.
    const admin = { access_status: { onboarding_required: true, admin: true } };
    expect(defaultAuthenticatedPath(admin, null)).toBe("/admin");
  });
});

/**
 * A mesma porta, reaberta por dentro.
 *
 * O redirecionamento de login foi corrigido acima, mas o painel NR-1 tinha um
 * botao rotulado "Dashboard" que chamava nav("/dashboard") sem condicao
 * nenhuma. Para a empresa contratante o destino e o painel CLINICO -- "Saldo
 * de sessoes", "Meus Pacientes", "Gestao da clinica" -- que e exatamente a
 * tela que `homeDoProduto` existe para nao mostrar a ela.
 *
 * A necessidade que o botao atendia era real: o painel NR-1 nao tem
 * "Administrativo", e sem porta a unica saida seria fechar o navegador. Por
 * isso a correcao nao foi remover, foi trocar o destino de quem nao tem painel
 * clinico -- sair da sessao.
 */
describe("o painel NR-1 nao oferece o painel clinico a quem nao o tem", () => {
  const PAINEL = readFileSync(
    join(__dirname, "..", "pages", "Nr1Dashboard.tsx"),
    "utf-8",
  );
  const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");

  it("so mostra 'Dashboard' quando ha organizacao clinica", () => {
    expect(PAINEL).toContain("organizacaoDoPsique ? (");
  });

  it("oferece 'Sair' no lugar, para a empresa NR-1 pura", () => {
    expect(PAINEL).toContain("onClick={onLogout}");
    expect(PAINEL).toMatch(/>\s*Sair\s*</);
  });

  // Sem esta ligacao o botao existiria e nao faria nada -- e `nav("/login")`
  // com sessao aberta e devolvido para /nr1 pelo proprio roteador, entao a
  // falha seria invisivel: um clique que parece funcionar e nao sai de lugar
  // nenhum.
  it("e o App liga a saida de verdade", () => {
    expect(APP).toContain("<Nr1Dashboard user={user} onLogout={logout} />");
  });

  // A regra, e nao a ocorrencia: o painel NR-1 nao navega para o painel
  // clinico em lugar nenhum. `irParaContexto` continua permitido porque ele
  // TROCA a organizacao ativa antes de sair -- sem isso o painel clinico abre
  // sob organizacao 'enterprise' e os pacientes somem sem explicacao.
  it("nao sobra nenhuma navegacao crua para /dashboard", () => {
    expect(PAINEL).not.toMatch(/nav\(\s*["']\/dashboard["']\s*\)/);
  });
});
