import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { carimbo, cnpjFormatado, vigentesPorDocumento } from "./Nr1Acceptance";

/**
 * Travas do comprovante de aceite.
 *
 * O comprovante e um documento de PROVA, e a diferenca entre um bom e um
 * inutil esta em tres detalhes que sao faceis de errar sem que a folha fique
 * feia: o hash inteiro, a integra junto, e a divergencia dita em voz alta
 * quando o texto vigente nao e o texto aceito.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1Acceptance.tsx"), "utf-8");
const PAGINA_CORRIDA = PAGINA.replace(/\s+/g, " ");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAINEL = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");

function aceite(chave: string, versao: string, quando: string, sha = "a".repeat(64)) {
  return {
    document_key: chave,
    document_version: versao,
    document_sha256: sha,
    acceptance_context: "professional_onboarding",
    accepted_at: quando,
    organization_id: "org-1",
    subject_kind: "professional",
  };
}

describe("qual aceite vale", () => {
  it("mantém o mais recente de cada documento", () => {
    // O ledger é append-only e acumula renovações. Listar todas as linhas
    // mostraria o mesmo contrato três vezes com datas diferentes, e quem
    // lesse teria de adivinhar qual está em vigor.
    const vigentes = vigentesPorDocumento([
      aceite("nr1_company_contract", "1.0", "2026-01-01T10:00:00Z"),
      aceite("nr1_company_contract", "2.0", "2026-08-25T10:00:00Z"),
      aceite("privacy", "1.0", "2026-01-01T10:00:00Z"),
    ]);
    expect(vigentes).toHaveLength(2);
    const contrato = vigentes.find((v) => v.document_key === "nr1_company_contract");
    expect(contrato?.document_version).toBe("2.0");
  });

  it("não perde documento nenhum", () => {
    const vigentes = vigentesPorDocumento([
      aceite("terms_nr1", "1.0", "2026-08-25T10:00:00Z"),
      aceite("privacy", "1.0", "2026-08-25T10:00:00Z"),
      aceite("nr1_company_contract", "1.0", "2026-08-25T10:00:00Z"),
    ]);
    expect(vigentes.map((v) => v.document_key).sort()).toEqual([
      "nr1_company_contract",
      "privacy",
      "terms_nr1",
    ]);
  });

  it("devolve vazio sem aceite nenhum", () => {
    expect(vigentesPorDocumento([])).toEqual([]);
  });
});

describe("a hora do aceite", () => {
  it("sai no fuso de Brasília, com o fuso dito", () => {
    // Data sem fuso é ambígua num documento que pode ser lido noutro país, e a
    // hora do aceite é exatamente o que este documento prova.
    const texto = carimbo("2026-08-26T00:14:00Z");
    expect(texto).toContain("25/08/2026");
    expect(texto).toContain("21:14");
    expect(texto).toMatch(/Bras[ií]lia/);
  });

  it("não inventa data para valor inválido", () => {
    expect(carimbo("")).toBe("");
    expect(carimbo("nada disso")).toBe("nada disso");
  });
});

describe("o CNPJ no cabeçalho", () => {
  it("formata os 14 dígitos", () => {
    expect(cnpjFormatado("12345678000199")).toBe("12.345.678/0001-99");
  });

  it("devolve o original quando não são 14 dígitos", () => {
    // Melhor mostrar o que foi cadastrado do que mascarar em formato errado:
    // num documento de prova, o número exibido precisa ser o número gravado.
    expect(cnpjFormatado("123")).toBe("123");
  });
});

describe("o que a folha impressa precisa ter", () => {
  it("imprime o SHA-256 inteiro, nunca abreviado", () => {
    // Meia impressão digital não confere nada. Na tela ela é referência
    // visual; no papel levado ao jurídico do cliente ela é a prova.
    expect(PAGINA).toContain("{aceite.document_sha256}");
    expect(PAGINA).not.toContain("document_sha256.slice");
  });

  it("traz a íntegra dos documentos, e não só a referência", () => {
    expect(PAGINA).toContain("documento.sections.map");
    expect(PAGINA).toContain("froid-pagina-nova");
  });

  it("sai em A4 branco, sem menu", () => {
    expect(PAGINA).toContain("size: A4");
    expect(PAGINA).toContain("froid-nao-imprime");
    expect(PAGINA).toContain("froid-clausula");
  });

  it("avisa quando o texto vigente não é o texto aceito", () => {
    // Imprimir o texto de hoje sob a data de ontem é o defeito que anula o
    // comprovante — e é silencioso, porque a folha sai bonita.
    expect(PAGINA).toContain("vigente.sha256 !== aceite.document_sha256");
    expect(PAGINA_CORRIDA).toMatch(/texto vigente n[aã]o [eé] o texto aceito/i);
  });

  it("distingue 'nada foi aceito' de 'não consigo verificar'", () => {
    // A diferença entre as duas é a diferença inteira num documento de prova.
    expect(PAGINA).toContain("ledger_configured");
    expect(PAGINA_CORRIDA).toMatch(/N[aã]o foi poss[ií]vel verificar os aceites/i);
  });
});

describe("o caminho até o comprovante", () => {
  it("a rota existe", () => {
    expect(APP).toContain('path="/nr1/comprovante"');
    expect(APP).toContain("<Nr1Acceptance user={user} />");
  });

  it("o painel NR-1 aponta para ele", () => {
    expect(PAINEL).toContain('nav("/nr1/comprovante")');
  });
});
