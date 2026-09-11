import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { clausulaTemNumeroProprio, rotuloDaClausula } from "./legal";

/**
 * O numero da clausula e dela, e nao da posicao na lista.
 *
 * Ate 11/09/2026 as duas telas que imprimem documento juridico numeravam a
 * clausula por `indice + 1`. Enquanto os titulos eram nomes descritivos isso
 * passava despercebido. Quando o contrato do NR-1 foi reescrito em 16
 * clausulas numeradas, a folha impressa passaria a dizer "8. 8. Agregacao,
 * pisos de coorte e protecao das respostas" — e o defeito so apareceria no
 * papel, ja na mao do juridico do cliente.
 *
 * O problema de fundo e maior que o numero repetido: numeracao derivada da
 * POSICAO renumera o documento inteiro, em silencio, no dia em que uma
 * clausula for retirada. Um contrato cuja clausula 8 vira 7 invalida toda
 * citacao ja feita — inclusive as do comprovante de aceite, que e documento de
 * prova, e as do acervo do FROID Explica, que cita clausula por numero.
 */

const LEGAL_PAGES = readFileSync(
  join(__dirname, "..", "pages", "LegalPages.tsx"),
  "utf-8",
);
const COMPROVANTE = readFileSync(
  join(__dirname, "..", "pages", "Nr1Acceptance.tsx"),
  "utf-8",
);
const CATALOGO = readFileSync(
  new URL("../../../froid-server/legal_documents.py", import.meta.url),
  "utf-8",
);

describe("numeracao de clausula", () => {
  it("reconhece o titulo que traz o proprio numero", () => {
    expect(clausulaTemNumeroProprio("1. Objeto e documentos integrantes")).toBe(true);
    expect(clausulaTemNumeroProprio("16. Disposições gerais")).toBe(true);
    expect(clausulaTemNumeroProprio("8.3. Vedação")).toBe(true);
  });

  it("nao confunde titulo descritivo com titulo numerado", () => {
    expect(clausulaTemNumeroProprio("Responsável pelo serviço")).toBe(false);
    expect(clausulaTemNumeroProprio("Pisos de coorte, agregação e supressão")).toBe(false);
    // Numero sem o ponto e sem o espaco nao e numeracao de clausula.
    expect(clausulaTemNumeroProprio("2026 em revisão")).toBe(false);
    expect(clausulaTemNumeroProprio("1.Objeto")).toBe(false);
  });

  it("nao duplica o numero de quem ja o tem", () => {
    expect(rotuloDaClausula("8. Agregação", 7)).toBe("8. Agregação");
    expect(rotuloDaClausula("8. Agregação", 0)).toBe("8. Agregação");
  });

  it("numera pela posicao o documento cujas secoes tem nome", () => {
    expect(rotuloDaClausula("Dados tratados", 1)).toBe("2. Dados tratados");
  });

  /** A garantia de verdade: as telas usam o helper, e nao `indice + 1` cru. */
  it("as duas telas que imprimem documento juridico usam o helper", () => {
    expect(COMPROVANTE).toContain("rotuloDaClausula(secao.heading, indice)");
    expect(LEGAL_PAGES).toContain("clausulaTemNumeroProprio(section.heading)");
  });

  /** E o contrato do NR-1 realmente se numera — senao o helper protegeria nada. */
  it("o contrato do NR-1 numera as proprias clausulas", () => {
    const bloco = CATALOGO.slice(
      CATALOGO.indexOf('DOCUMENT_TEMPLATES["nr1_company_contract"]'),
    );
    const titulos = [...bloco.matchAll(/\["(\d+\. [^"]+)",/g)].map((m) => m[1]);
    expect(titulos.length).toBe(16);
    expect(titulos[0]).toBe("1. Objeto e documentos integrantes");
    expect(titulos[15]).toBe("16. Disposições gerais");
    for (const titulo of titulos) {
      expect(clausulaTemNumeroProprio(titulo)).toBe(true);
    }
  });
});
