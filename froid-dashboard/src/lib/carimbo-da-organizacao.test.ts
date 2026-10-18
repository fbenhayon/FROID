// O carimbo que diz de que organizacao e cada paciente.
//
// Decisao do dono, 18/10/2026: quem atende por conta propria E por clinicas
// precisa ver, paciente a paciente, de onde cada um e. O carimbo vem do
// `organizationId` gravado no relatorio ao arquivar. Ausencia se declara;
// nunca vira "Solo".

import { describe, expect, it } from "vitest";
import {
  CARIMBO_ANTIGO,
  CARIMBO_SEM_VINCULO,
  CARIMBO_SOLO,
  carimboDaOrganizacao,
  carimbosDosRelatorios,
} from "./contexto-organizacao";

const usuario = {
  organizations: [
    { organization_id: "org-solo", organization_type: "solo", organization_name: "Dra. X" },
    { organization_id: "org-c1", organization_type: "clinic", organization_name: "Clínica Aurora" },
    { organization_id: "org-c2", organization_type: "clinic" },
    { organization_id: "org-e1", organization_type: "enterprise", organization_name: "ACME" },
  ],
};

describe("carimboDaOrganizacao", () => {
  it("solo e Solo, mesmo com nome", () => {
    expect(carimboDaOrganizacao(usuario, "org-solo")).toBe(CARIMBO_SOLO);
  });

  it("clinica com nome usa o nome; sem nome recebe numero na ordem da conta", () => {
    expect(carimboDaOrganizacao(usuario, "org-c1")).toBe("Clínica Aurora");
    expect(carimboDaOrganizacao(usuario, "org-c2")).toBe("Clínica 2");
  });

  it("empresa com nome usa o nome", () => {
    expect(carimboDaOrganizacao(usuario, "org-e1")).toBe("ACME");
  });

  it("id fora da conta e ausencia de id sao declarados, nao inferidos", () => {
    expect(carimboDaOrganizacao(usuario, "org-desconhecida")).toBe(CARIMBO_SEM_VINCULO);
    expect(carimboDaOrganizacao(usuario, "")).toBe(CARIMBO_ANTIGO);
    expect(carimboDaOrganizacao(usuario, undefined)).toBe(CARIMBO_ANTIGO);
    expect(carimboDaOrganizacao(null, "org-solo")).toBe(CARIMBO_SEM_VINCULO);
  });
});

describe("carimbosDosRelatorios", () => {
  it("um carimbo por organizacao, na ordem em que aparece, sem repetir", () => {
    const carimbos = carimbosDosRelatorios(usuario, [
      { organizationId: "org-c1" },
      { organizationId: "org-solo" },
      { organizationId: "org-c1" },
      {},
    ]);
    expect(carimbos).toEqual(["Clínica Aurora", CARIMBO_SOLO, CARIMBO_ANTIGO]);
  });
});
