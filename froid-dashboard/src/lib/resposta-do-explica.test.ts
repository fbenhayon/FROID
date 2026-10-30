import { describe, expect, it } from "vitest";
import { blocosDaResposta } from "./resposta-do-explica";

describe("blocosDaResposta", () => {
  it("separa a tabela do texto e descarta a linha separadora", () => {
    const blocos = blocosDaResposta(
      "Abertura.\n| Corte | P/MIN | Δ |\n|---|---|---|\n| 0-10min | 83.4 | +46% |\n| 10-11min (4 s) | 30.0 | -47% |\nSintese final.",
    );
    expect(blocos).toEqual([
      { tipo: "texto", texto: "Abertura." },
      {
        tipo: "tabela",
        cabecalho: ["Corte", "P/MIN", "Δ"],
        linhas: [
          ["0-10min", "83.4", "+46%"],
          ["10-11min (4 s)", "30.0", "-47%"],
        ],
      },
      { tipo: "texto", texto: "Sintese final." },
    ]);
  });

  it("texto sem tabela sai inteiro, sem asteriscos de negrito", () => {
    expect(blocosDaResposta("A **cadencia** subiu.\n\nSegundo paragrafo.")).toEqual([
      { tipo: "texto", texto: "A cadencia subiu.\n\nSegundo paragrafo." },
    ]);
  });

  it("asteriscos de negrito dentro de celula nao quebram a tabela nem sobram", () => {
    // Revisao 20/10/2026, item 27: o contrato proibe negrito, mas o modelo
    // as vezes poe; a celula tem de sair limpa e com o mesmo numero de colunas.
    const blocos = blocosDaResposta("| corte | **IPM** | P/MIN |\n|---|---|---|\n| 0-10min | **49.9** | 83.4 |");
    expect(blocos).toHaveLength(1);
    const tabela = blocos[0];
    if (tabela.tipo !== "tabela") throw new Error("esperava tabela");
    expect(tabela.cabecalho).toEqual(["corte", "IPM", "P/MIN"]);
    expect(tabela.linhas).toEqual([["0-10min", "49.9", "83.4"]]);
  });

  it("resposta vazia nao produz bloco", () => {
    expect(blocosDaResposta("")).toEqual([]);
    expect(blocosDaResposta("   \n ")).toEqual([]);
  });
});
