import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ondeDaLinha, SEM_ESTABELECIMENTO } from "./nr1-onde";

const loja = (n: number) => ({ id: `l${n}`, name: `Loja ${n}`, headcount: 1 });

describe("onde vale a linha do inventário", () => {
  it("setor continua como estabelecimento / setor", () => {
    expect(
      ondeDaLinha({ unit_name: "Caixa", site_name: "Loja 17", unit_type: "sector" }),
    ).toBe("Loja 17 / Caixa");
  });

  it("grupo por função em vários endereços é contado, não listado", () => {
    const linha = {
      unit_name: "Gerentes de loja",
      site_name: null,
      unit_type: "exposure_group",
      establishments: Array.from({ length: 40 }, (_, i) => loja(i + 1)),
    };
    expect(ondeDaLinha(linha)).toBe(
      "Gerentes de loja · lançado em 40 estabelecimentos",
    );
  });

  it("grupo por função em um só endereço nomeia o endereço", () => {
    expect(
      ondeDaLinha({
        unit_name: "Comércio digital",
        unit_type: "exposure_group",
        establishments: [loja(1)],
      }),
    ).toBe("Loja 1 / Comércio digital");
  });

  it("grupo por função sem cobertura denuncia a pendência", () => {
    expect(
      ondeDaLinha({ unit_name: "Gerentes de loja", unit_type: "exposure_group", establishments: [] }),
    ).toContain(SEM_ESTABELECIMENTO);
  });

  it("a linha da projeção num estabelecimento usa o endereço projetado", () => {
    expect(
      ondeDaLinha({
        unit_name: "Gerentes de loja",
        site_name: "Loja 17",
        unit_type: "exposure_group",
        establishments: Array.from({ length: 40 }, (_, i) => loja(i + 1)),
      }),
    ).toBe("Loja 17 / Gerentes de loja");
  });

  it("o inventário de um estabelecimento é alcançável pela tela", () => {
    // O parâmetro do servidor sem quem o chame seria a peça que nada consome.
    const fonte = readFileSync(join(__dirname, "..", "pages", "Nr1Inventario.tsx"), "utf-8");
    expect(fonte).toContain("?establishment_id=${encodeURIComponent(estabelecimentoId)}");
    expect(fonte).toContain("Todos os estabelecimentos");
    expect(fonte).toContain("exposto(s) neste estabelecimento");
    // Trocar de campanha zera o filtro: os endereços de uma não valem na outra.
    expect(fonte).toContain('setEstabelecimento("");');
  });

  it("a prévia dos convites nomeia também o grupo por função", () => {
    // "matrícula;Gerentes de loja" casa com qualquer unidade; a prévia que
    // conta pessoas por grupo precisa mostrar o nome, não o identificador.
    const fonte = readFileSync(join(__dirname, "..", "pages", "Nr1Campaign.tsx"), "utf-8");
    expect(fonte).toContain("nome: unidades.find((u) => u.unit_id === unitId)?.name || unitId");
  });

  it("as duas telas usam a mesma regra", () => {
    for (const pagina of ["Nr1Inventario.tsx", "Nr1ActionPlan.tsx"]) {
      const fonte = readFileSync(join(__dirname, "..", "pages", pagina), "utf-8");
      expect(fonte).toContain("ondeDaLinha(");
    }
  });
});
