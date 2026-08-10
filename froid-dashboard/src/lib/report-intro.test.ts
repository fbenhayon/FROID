import { describe, expect, it } from "vitest";
import { REPORT_INTROS, pickIntro } from "./report-intro";

/**
 * O rodízio das cinco aberturas.
 *
 * Como o paciente recebe UMA, cada variante precisa carregar sozinha as duas
 * salvaguardas. Não existe "a versão mais protegida": a que saiu é a única que
 * aquela pessoa vai ler. É por isso que estes testes varrem TODAS, e não uma
 * amostra.
 */

describe("cada abertura protege sozinha", () => {
  it("são cinco", () => {
    expect(REPORT_INTROS.length).toBe(5);
  });

  it("todas apontam para o profissional", () => {
    for (const frase of REPORT_INTROS) {
      expect(/profissional/i.test(frase), frase.slice(0, 45)).toBe(true);
    }
  });

  it("todas negam ser conclusão sobre a pessoa", () => {
    // Uma alternância só, e legível: cada padrão corresponde a uma das cinco
    // formas de dizer a mesma coisa sem repetir a frase da variante C.
    const NEGA_CONCLUSAO =
      /nunca conclus[ãa]o|n[ãa]o fecha conclus[ãa]o|nada aqui conclui|n[ãa]o um retrato|n[ãa]o afirma[çc][õo]es sobre quem/i;
    for (const frase of REPORT_INTROS) {
      expect(NEGA_CONCLUSAO.test(frase), frase.slice(0, 45)).toBe(true);
    }
  });

  it("todas declaram o objetivo de reconhecimento pessoal", () => {
    for (const frase of REPORT_INTROS) {
      expect(/reconhecimento pessoal/i.test(frase), frase.slice(0, 45)).toBe(true);
    }
  });

  it("nenhuma prescreve conduta", () => {
    const conduta = /\b(mitigar|facilitar|estimular|acolher|conter|reduzir|diminuir)\s/i;
    for (const frase of REPORT_INTROS) {
      expect(conduta.test(frase), frase.slice(0, 45)).toBe(false);
    }
  });

  it("nenhuma promete diagnóstico nem avaliação", () => {
    for (const frase of REPORT_INTROS) {
      expect(/diagn[óo]stico|avalia[çc][ãa]o cl[íi]nica|laudo/i.test(frase),
        frase.slice(0, 45)).toBe(false);
    }
  });

  it("nenhuma passa de 70 palavras", () => {
    // Abertura longa não é lida. A salvaguarda precisa caber no que a pessoa
    // realmente lê antes de pular para os números.
    for (const frase of REPORT_INTROS) {
      const palavras = frase.trim().split(/\s+/).length;
      expect(palavras, `${palavras} palavras: ${frase.slice(0, 45)}`)
        .toBeLessThanOrEqual(70);
    }
  });
});

describe("o sorteio", () => {
  it("com semente, é determinístico", () => {
    // Sorteio verdadeiro em teste produz reprovação intermitente, que ensina a
    // ignorar falha — pior do que teste nenhum.
    expect(pickIntro(0)).toBe(REPORT_INTROS[0]);
    expect(pickIntro(7)).toBe(REPORT_INTROS[2]);
    expect(pickIntro(-3)).toBe(REPORT_INTROS[3]);
  });

  it("alcança todas as cinco", () => {
    const vistas = new Set(
      Array.from({ length: 40 }, (_, i) => pickIntro(i)),
    );
    expect(vistas.size).toBe(REPORT_INTROS.length);
  });

  it("sem semente, devolve sempre uma frase válida", () => {
    for (let i = 0; i < 60; i += 1) {
      expect(REPORT_INTROS).toContain(pickIntro());
    }
  });
});
