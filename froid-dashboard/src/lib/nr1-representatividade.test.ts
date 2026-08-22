import { describe, expect, it } from "vitest";
import {
  amostraNecessaria,
  caminhoDoPorte,
  exigeCenso,
  exigidoNaCampanha,
  exigidoNoRecorte,
  PISO_CAMPANHA,
  PISO_RECORTE,
} from "./nr1-representatividade";

/**
 * Este arquivo é um ESPELHO, e espelho que diverge é pior que espelho ausente.
 *
 * A autoridade é froid_nr1_required_sample (migrations/025) e o mesmo cálculo
 * em nr1_compliance.required_sample. Os números fixados abaixo são exatamente
 * os que tests/test_nr1_representatividade.py fixa do lado do servidor: se um
 * dos dois lados mudar sozinho, o cadastro passa a prometer resultado que o
 * banco vai suprimir — que foi o defeito que motivou este arquivo existir.
 */

const PRIMEIRA_AMOSTRA = 98;

describe("amostra exigida", () => {
  // A mesma tabela de tests/test_nr1_representatividade.py::PUBLICADA.
  const PUBLICADA: Record<number, number> = {
    3000: 341,
    1000: 278,
    500: 218,
    300: 169,
    200: 132,
    150: 109,
    100: 80,
  };

  it("reproduz a tabela publicada do servidor", () => {
    for (const [populacao, esperado] of Object.entries(PUBLICADA)) {
      expect(amostraNecessaria(Number(populacao))).toBe(esperado);
    }
  });

  it("nunca pede mais do que existe", () => {
    for (let n = 1; n < 400; n++) {
      expect(amostraNecessaria(n)!).toBeLessThanOrEqual(n);
    }
  });

  it("cresce com a população dentro do regime de amostra", () => {
    let anterior = 0;
    for (let n = PRIMEIRA_AMOSTRA; n < 4000; n++) {
      const atual = amostraNecessaria(n)!;
      expect(atual).toBeGreaterThanOrEqual(anterior);
      anterior = atual;
    }
  });

  it("sem efetivo declarado não há amostra", () => {
    expect(amostraNecessaria(0)).toBeNull();
    expect(amostraNecessaria(-3)).toBeNull();
    expect(amostraNecessaria(Number.NaN)).toBeNull();
    expect(exigidoNoRecorte(0)).toBeNull();
    expect(exigidoNaCampanha(0)).toBeNull();
  });
});

describe("transição para censo", () => {
  it("grupo pequeno vira censo", () => {
    for (const n of [1, 5, 20, 50, 80, 90, PRIMEIRA_AMOSTRA - 1]) {
      expect(amostraNecessaria(n)).toBe(n);
      expect(exigeCenso(n)).toBe(true);
    }
  });

  it("cem pessoas ainda é amostra", () => {
    expect(amostraNecessaria(100)).toBe(80);
    expect(exigeCenso(100)).toBe(false);
  });

  it("a transição acontece uma única vez", () => {
    // Regressão do defeito encontrado no servidor: comparar contra a fração de
    // corte o inteiro já arredondado fazia a exigência oscilar — 100 pedia
    // amostra, 101 pedia censo, 102 voltava a pedir amostra.
    const modos = Array.from({ length: 4999 }, (_, i) =>
      amostraNecessaria(i + 1) === i + 1 ? "censo" : "amostra",
    );
    const trocas = modos
      .map((modo, i) => (i > 0 && modo !== modos[i - 1] ? i : -1))
      .filter((i) => i >= 0);
    expect(trocas).toHaveLength(1);
    expect(trocas[0] + 1).toBe(PRIMEIRA_AMOSTRA);
  });
});

describe("os dois portões compostos", () => {
  it("o piso de anonimato domina onde a amostra é menor que ele", () => {
    // 98 pessoas exigem amostra de 79, mas a campanha nunca abre com menos de
    // 50 — e um recorte nunca com menos de 10.
    expect(exigidoNaCampanha(60)).toBe(60);
    expect(exigidoNoRecorte(12)).toBe(12);
    expect(exigidoNoRecorte(10)).toBe(PISO_RECORTE);
  });

  it("a representatividade domina onde ela é maior", () => {
    expect(exigidoNaCampanha(3000)).toBe(341);
    expect(exigidoNaCampanha(3000)).toBeGreaterThan(PISO_CAMPANHA);
    expect(exigidoNoRecorte(300)).toBe(169);
  });
});

describe("caminho de conformidade por porte", () => {
  it("abaixo do piso absoluto nenhuma campanha publica, por mais adesão que haja", () => {
    // 49 pessoas respondendo TODAS dão 49 respostas, e o piso de anonimato pede
    // 50. Não é questão de adesão: é aritmética, e por isso o caminho é outro.
    for (const n of [1, 10, 30, 49]) {
      expect(caminhoDoPorte(n)).toBe("aep");
    }
    expect(caminhoDoPorte(0)).toBe("aep");
  });

  it("entre o piso absoluto e a fronteira da amostra, exige censo", () => {
    for (const n of [50, 60, 80, 97]) {
      expect(caminhoDoPorte(n)).toBe("censo");
      expect(exigidoNaCampanha(n)).toBe(n);
    }
  });

  it("de 98 em diante a amostra economiza respostas", () => {
    expect(caminhoDoPorte(98)).toBe("campanha");
    expect(exigidoNaCampanha(98)).toBeLessThan(98);
    expect(caminhoDoPorte(3000)).toBe("campanha");
  });

  it("as três faixas cobrem tudo e não se sobrepõem", () => {
    const vistos = new Set<string>();
    let anterior = caminhoDoPorte(1);
    vistos.add(anterior);
    for (let n = 2; n <= 4000; n++) {
      const atual = caminhoDoPorte(n);
      if (atual !== anterior) {
        // Cada faixa aparece uma vez só: a sequência é aep → censo → campanha,
        // sem voltar. Oscilar aqui significaria empresa vizinha em caminho
        // diferente por uma pessoa a mais no quadro.
        expect(vistos.has(atual)).toBe(false);
        vistos.add(atual);
        anterior = atual;
      }
    }
    expect([...vistos]).toEqual(["aep", "censo", "campanha"]);
  });
});
