import { describe, expect, it } from "vitest";
import { REPORT_EPIGRAPHS, pickEpigraph } from "./report-epigraph";

/**
 * A trava aqui é de ATRIBUIÇÃO, não de estilo.
 *
 * Einstein e Gandhi são os autores mais mal citados da história. "Seja a
 * mudança que você quer ver no mundo" e "a mente que se abre a uma nova ideia
 * jamais volta ao tamanho original" circulam como deles e não são. Num
 * documento assinado que vai para prontuário, uma frase apócrifa contamina a
 * credibilidade de tudo o mais que está no papel.
 */

const APOCRIFAS = [
  "seja a mudança",
  "jamais volta",
  "jamais voltará",
  "tamanho original",
  "insanidade é fazer",
  "todos são gênios",
  "olho por olho",
];

describe("cada citação tem procedência", () => {
  it("são cinco", () => {
    expect(REPORT_EPIGRAPHS.length).toBe(5);
  });

  it("nenhuma fonte está vazia", () => {
    // O campo existe para ser conferível. Vazio, ele vira decoração e a
    // próxima citação entra sem procedência.
    for (const e of REPORT_EPIGRAPHS) {
      expect(e.fonte.trim().length, `${e.autor}: fonte vazia`).toBeGreaterThan(8);
    }
  });

  it("toda fonte declara obra e ano, ou obra e localização", () => {
    for (const e of REPORT_EPIGRAPHS) {
      const temAno = /\b(1[5-9]\d{2}|20\d{2})\b/.test(e.fonte);
      const temLocalizacao = /ato\s+[IVX]+|cena|cap[íi]tulo|p\.\s*\d+/i.test(e.fonte);
      expect(temAno || temLocalizacao, `${e.autor}: "${e.fonte}"`).toBe(true);
    }
  });

  it("nenhuma é das apócrifas conhecidas", () => {
    for (const e of REPORT_EPIGRAPHS) {
      const baixo = e.texto.toLowerCase();
      for (const falsa of APOCRIFAS) {
        expect(baixo.includes(falsa), `${e.autor}: "${falsa}"`).toBe(false);
      }
    }
  });

  it("autor e texto preenchidos", () => {
    for (const e of REPORT_EPIGRAPHS) {
      expect(e.autor.trim().length).toBeGreaterThan(3);
      expect(e.texto.trim().length).toBeGreaterThan(20);
    }
  });

  it("nenhuma passa de 40 palavras", () => {
    // Epígrafe longa deixa de ser epígrafe.
    for (const e of REPORT_EPIGRAPHS) {
      expect(e.texto.trim().split(/\s+/).length, e.autor).toBeLessThanOrEqual(40);
    }
  });
});

describe("o sorteio", () => {
  it("com semente, é determinístico", () => {
    expect(pickEpigraph(0).autor).toBe(REPORT_EPIGRAPHS[0].autor);
    expect(pickEpigraph(6).autor).toBe(REPORT_EPIGRAPHS[1].autor);
  });

  it("alcança todas as cinco", () => {
    const vistas = new Set(
      Array.from({ length: 40 }, (_, i) => pickEpigraph(i).autor),
    );
    expect(vistas.size).toBe(REPORT_EPIGRAPHS.length);
  });

  it("sem semente, devolve sempre uma citação válida", () => {
    for (let i = 0; i < 50; i += 1) {
      expect(REPORT_EPIGRAPHS.map((e) => e.autor)).toContain(pickEpigraph().autor);
    }
  });
});
