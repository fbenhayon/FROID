import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  audienciaDaConta,
  carimbo,
  cnpjFormatado,
  documentosPendentes,
  vigentesPorDocumento,
} from "./Nr1Acceptance";

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

/**
 * O reaceite, que ate 11/09/2026 nao existia para a empresa.
 *
 * A tela ja sabia dizer "o texto vigente nao e o texto aceito" — e parava ali.
 * Quando o contrato do NR-1 foi reescrito e LEGAL_DOCUMENT_VERSION subiu, o
 * aceite da contratante passou a provar um texto superado e nao havia botao
 * nenhum para aceitar o novo: o unico caminho era refazer o cadastro. Aviso
 * sem saida e pior que nenhum, porque descreve um problema que quem le nao tem
 * como resolver.
 */
function doc(chave: string, sha: string, audiencias: string[]) {
  return {
    key: chave,
    version: "2026-09-11.br-pf-v6",
    sha256: sha,
    title: `Documento ${chave}`,
    audiences: audiencias,
    sections: [],
  };
}

describe("o reaceite do texto vigente", () => {
  const vigenteA = doc("nr1_company_contract", "b".repeat(64), ["nr1_company"]);
  const vigenteB = doc("terms_nr1", "c".repeat(64), ["nr1_company"]);
  const doOutroProduto = doc("professional_contract", "d".repeat(64), ["professional"]);
  const catalogo = {
    nr1_company_contract: vigenteA,
    terms_nr1: vigenteB,
    professional_contract: doOutroProduto,
  };

  it("mapeia o tipo de conta para a audiencia do catalogo", () => {
    expect(audienciaDaConta("nr1_company")).toBe("nr1_company");
    expect(audienciaDaConta("organization")).toBe("organization");
    expect(audienciaDaConta("individual")).toBe("professional");
    expect(audienciaDaConta(undefined)).toBe("professional");
  });

  it("acusa o documento cujo texto mudou depois do aceite", () => {
    const pendentes = documentosPendentes(
      catalogo,
      [
        aceite("nr1_company_contract", "5.0", "2026-08-25T10:00:00Z", "a".repeat(64)),
        aceite("terms_nr1", "6.0", "2026-09-11T10:00:00Z", "c".repeat(64)),
      ],
      "nr1_company",
    );
    expect(pendentes.map((d) => d.key)).toEqual(["nr1_company_contract"]);
  });

  it("acusa o documento que nunca foi aceito", () => {
    const pendentes = documentosPendentes(catalogo, [], "nr1_company");
    expect(pendentes.map((d) => d.key).sort()).toEqual([
      "nr1_company_contract",
      "terms_nr1",
    ]);
  });

  it("nao pede a empresa o contrato do outro produto", () => {
    const pendentes = documentosPendentes(catalogo, [], "nr1_company");
    expect(pendentes.some((d) => d.key === "professional_contract")).toBe(false);
  });

  it("nao acusa nada quando tudo esta no texto vigente", () => {
    const pendentes = documentosPendentes(
      catalogo,
      [
        aceite("nr1_company_contract", "6.0", "2026-09-11T10:00:00Z", "b".repeat(64)),
        aceite("terms_nr1", "6.0", "2026-09-11T10:00:00Z", "c".repeat(64)),
      ],
      "nr1_company",
    );
    expect(pendentes).toEqual([]);
  });

  it("a tela envia para a rota da organizacao, e nao para a do profissional", () => {
    expect(PAGINA).toContain("/api/organizations/${organizationId}/legal-acceptances");
    expect(PAGINA).toContain('method: "POST"');
  });

  it("nenhuma caixa vem pre-marcada", () => {
    // Aceite pre-marcado descreve um ato que nao aconteceu.
    expect(PAGINA).toContain("checked={Boolean(marcados[doc.key])}");
    expect(PAGINA).toContain("useState<Record<string, boolean>>({})");
  });

  it("o botao so libera com todos os documentos marcados", () => {
    expect(PAGINA).toContain("pendentes.some((doc) => !marcados[doc.key])");
  });

  it("o bloco de reaceite fica fora da impressao", () => {
    // O comprovante em papel e documento de prova e nao carrega botao.
    const bloco = PAGINA.slice(PAGINA.indexOf("pendentes.length > 0"));
    expect(bloco.slice(0, 400)).toContain("froid-nao-imprime");
  });

  it("nao oferece aceite quando o livro nao pode ser consultado", () => {
    // Sem a chave de auditoria o servidor recusa gravar; oferecer o botao
    // produziria um erro no lugar de uma explicacao.
    expect(PAGINA).toContain("dados?.ledger_configured && pendentes.length > 0");
  });

  it("diz que o registro anterior continua valendo", () => {
    expect(PAGINA_CORRIDA).toMatch(/continua provando o que foi aceito antes/i);
  });
});

/**
 * O comprovante nao imprime chave crua, e nao cala sobre o preco.
 *
 * ACHADO DA AUDITORIA DE 11/09/2026. O aceite do valor mensal entra no livro
 * com a chave `nr1_commercial_proposal`, que NAO esta no catalogo juridico —
 * e a tela imprimia `vigente?.title || aceite.document_key`. Numa folha que e
 * documento de prova sairia a string "nr1_commercial_proposal", ao lado de
 * "Versao 1.0" e de um sha256 que e da tabela de preco e nao de um contrato.
 *
 * O segundo defeito era mais grave e mais silencioso: o valor aceito ficava
 * guardado no `commercial_snapshot` e nao chegava a lugar nenhum. O contrato
 * remete a Proposta Comercial quanto a preco, prazo e vigencia (clausulas 1.5,
 * 13.1 e 14.1) — comprovante sem o valor prova a metade que ninguem discute.
 */
describe("o comprovante fala do aceite comercial", () => {
  it("traduz a chave que nao esta no catalogo", () => {
    expect(PAGINA).toContain("TITULOS_FORA_DO_CATALOGO");
    expect(PAGINA).toContain("Proposta Comercial — valor mensal aceito");
    // A ordem importa: titulo do catalogo primeiro, mapa depois, chave crua
    // so como ultimo recurso.
    const bloco = PAGINA.slice(PAGINA.indexOf("{vigente?.title ||"));
    const catalogo = bloco.indexOf("vigente?.title");
    const mapa = bloco.indexOf("TITULOS_FORA_DO_CATALOGO[aceite.document_key]");
    const crua = bloco.indexOf("aceite.document_key}");
    expect(catalogo).toBeLessThan(mapa);
    expect(mapa).toBeLessThan(crua);
  });

  it("imprime o valor aceito quando ele existe", () => {
    expect(PAGINA).toContain("aceite.commercial_snapshot?.monthlyTotalLabel");
    expect(PAGINA_CORRIDA).toMatch(/por trabalhador\/mês/);
  });

  it("o valor vem do livro, e nao e recalculado na tela", () => {
    // Recalcular aqui produziria um numero que pode diferir do que foi aceito
    // — que e o oposto do que um comprovante existe para fazer.
    expect(PAGINA).not.toContain("monthlyTotalCents /");
    expect(PAGINA).not.toContain("baseEstablishmentCents");
  });
});
