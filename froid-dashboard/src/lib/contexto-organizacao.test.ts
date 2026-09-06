import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  nomeDaOrganizacao,
  organizacaoClinica,
  organizacoesNr1,
} from "./contexto-organizacao";

/**
 * O seletor de organização do painel clínico não abria nada, e escondia
 * pacientes.
 *
 * Apurado em 06/09/2026, na conta do administrador. O cabeçalho de /dashboard
 * tinha um seletor listando todas as organizações da conta, inclusive a
 * empresa NR-1. Escolher a empresa não levava ao painel NR-1 — /dashboard é o
 * painel clínico e continua sendo — mas trocava a organização ativa da sessão
 * para uma do tipo 'enterprise', e `effective_role_permissions` retira as
 * permissões clínicas identificadas dos papéis do lado do empregador. O único
 * efeito visível era a lista de pacientes esvaziar, sem nenhuma explicação na
 * tela, e o próprio seletor era a única forma de desfazer.
 *
 * A troca de contexto passou a viver onde ela tem destino: a lista "Clientes
 * NR-1" em /admin entra, o botão "Dashboard" do painel NR-1 volta — e as duas
 * levam a organização junto, em vez de mudar só a URL.
 */

const empresaNr1 = {
  organization_id: "org-nr1",
  organization_name: "FROID NR-1 piloto",
  organization_type: "enterprise",
  roles: ["compliance_manager"],
};
const consultorio = {
  organization_id: "org-clinica",
  organization_name: "Consultório Fábio",
  organization_type: "clinic",
  roles: ["owner"],
};
const autonomo = {
  organization_id: "org-solo",
  organization_type: "solo",
  roles: ["owner"],
};

describe("quais organizações abrem o painel NR-1", () => {
  it("só as do tipo enterprise", () => {
    const nr1 = organizacoesNr1({
      organizations: [consultorio, empresaNr1, autonomo],
    });
    expect(nr1.map((item) => item.organization_id)).toEqual(["org-nr1"]);
  });

  // `_require_enterprise_context` devolve 409 para organização que não seja
  // 'enterprise'. Listar uma clínica aqui seria oferecer uma porta que o
  // servidor recusa — rótulo que promete o que não entrega.
  it("nunca oferece uma organização clínica como porta do NR-1", () => {
    expect(organizacoesNr1({ organizations: [consultorio, autonomo] })).toEqual([]);
  });

  it("devolve lista vazia sem organizações, em vez de estourar", () => {
    expect(organizacoesNr1(null)).toEqual([]);
    expect(organizacoesNr1({})).toEqual([]);
    expect(organizacoesNr1({ organizations: "nao é lista" as never })).toEqual([]);
  });

  it("descarta entrada sem organization_id, que não daria para abrir", () => {
    expect(
      organizacoesNr1({
        organizations: [{ organization_type: "enterprise" } as never, empresaNr1],
      }),
    ).toHaveLength(1);
  });
});

describe("para onde o botão Dashboard devolve o contexto", () => {
  it("para a organização clínica, e não para a empresa", () => {
    const clinica = organizacaoClinica({
      organizations: [empresaNr1, consultorio],
    });
    expect(clinica?.organization_id).toBe("org-clinica");
  });

  it("conta autônoma também é contexto clínico", () => {
    expect(
      organizacaoClinica({ organizations: [empresaNr1, autonomo] })
        ?.organization_id,
    ).toBe("org-solo");
  });

  // A empresa NR-1 pura não tem painel clínico para restaurar. O botão
  // continua existindo para ela — o painel NR-1 não tem "Sair" nem
  // "Administrativo" — mas navega sem trocar contexto nenhum.
  it("é nulo quando a conta só tem empresa NR-1", () => {
    expect(organizacaoClinica({ organizations: [empresaNr1] })).toBeNull();
  });
});

describe("como a organização aparece na tela", () => {
  it("usa organization_name, que é o campo que o servidor devolve", () => {
    expect(nomeDaOrganizacao(empresaNr1)).toBe("FROID NR-1 piloto");
  });

  // Sem nome, o id é feio mas é verdadeiro. Inventar um rótulo genérico faria
  // duas organizações diferentes parecerem a mesma linha.
  it("cai no id quando não há nome, em vez de inventar rótulo", () => {
    expect(nomeDaOrganizacao(autonomo)).toBe("org-solo");
  });
});

/**
 * As portas precisam existir de fato na tela. Sem isto, apagar a seção
 * deixaria a conta sem nenhum caminho para o painel NR-1 e nada acusaria.
 */
describe("a porta de entrada do NR-1 vive em /admin", () => {
  const ADMIN = readFileSync(
    join(__dirname, "..", "pages", "AdminDashboard.tsx"),
    "utf-8",
  );

  it("lista os clientes NR-1", () => {
    expect(ADMIN).toContain("Clientes NR-1");
    expect(ADMIN).toContain("organizacoesNr1");
  });

  it("abre o painel levando a organização junto", () => {
    expect(ADMIN).toContain('irParaContexto(organizationId, "/nr1")');
  });

  // O laço tem dois lados. Entrar sem poder voltar deixaria a conta no painel
  // clínico com a organização do empregador ativa — pacientes invisíveis, sem
  // explicação — que é exatamente o defeito que o seletor removido causava.
  it("e devolve o contexto clínico na volta", () => {
    expect(ADMIN).toContain("organizacaoClinica");
    expect(ADMIN).toContain("irParaODashboard");
  });
});
