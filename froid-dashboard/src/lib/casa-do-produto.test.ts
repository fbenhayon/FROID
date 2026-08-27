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
