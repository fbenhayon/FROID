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

  it("resposta vazia nao produz bloco", () => {
    expect(blocosDaResposta("")).toEqual([]);
    expect(blocosDaResposta("   \n ")).toEqual([]);
  });
});
