import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { PILOT_PAIRS, TARGET_PAIRS, nextMilestone, milestoneLabel } from "./validation";

describe("marcos do estudo", () => {
  it("mostra o piloto ate ele fechar, depois o confirmatorio", () => {
    expect(nextMilestone(0)).toBe(PILOT_PAIRS);
    expect(nextMilestone(PILOT_PAIRS - 1)).toBe(PILOT_PAIRS);
    expect(nextMilestone(PILOT_PAIRS)).toBe(TARGET_PAIRS);
    expect(milestoneLabel(PILOT_PAIRS - 1)).toBe("piloto");
    expect(milestoneLabel(PILOT_PAIRS)).toBe("confirmatório");
  });

  it("os marcos batem com os do backend", () => {
    const py = readFileSync(
      new URL("../../../froid-server/froid_validation.py", import.meta.url),
      "utf-8",
    );
    expect(py).toContain(`PILOT_PAIRS = ${PILOT_PAIRS}`);
    expect(py).toContain(`TARGET_PAIRS = ${TARGET_PAIRS}`);
  });
});

/**
 * O prompt de fim de sessao nao pode aplicar nem pontuar o instrumento, e nao
 * pode travar o encerramento. Se travasse, o profissional aprenderia a digitar
 * qualquer coisa para sair — e amostra suja e pior que amostra pequena.
 */
describe("prompt de fim de sessao", () => {
  const fonte = readFileSync(
    new URL("../components/validation/InstrumentScorePrompt.tsx", import.meta.url),
    "utf-8",
  );

  it("oferece pular", () => {
    expect(fonte).toContain("Pular");
  });

  it("nao renderiza item de questionario", () => {
    // Um sistema que apresenta e pontua o instrumento passa a ser um.
    for (const sinal of ["Pouco interesse", "Sentir-se para baixo", "item_", "questions"]) {
      expect(fonte).not.toContain(sinal);
    }
  });

  it("so aparece com consentimento concedido", () => {
    expect(fonte).toContain('consent.state === "granted"');
    // Falha ao consultar consentimento nao pode exibir o prompt.
    expect(fonte).toContain("setVisivel(false)");
  });
});

describe("linha do painel diario", () => {
  // So o codigo: o comentario explica por que o coeficiente nao esta ali, e
  // "intervalo" em portugues contem "interval".
  const codigo = readFileSync(
    new URL("../components/validation/ValidationProgressLine.tsx", import.meta.url),
    "utf-8",
  )
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((linha) => !linha.trim().startsWith("//"))
    .join("\n");

  it("nao busca nem exibe coeficiente", () => {
    // Correlacao parcial numa tela de uso diario vira numero que a pessoa
    // memoriza e repete sem o intervalo que a acompanha.
    for (const proibido of ["fetchReport", "verdict", "statement", "ValidationResult"]) {
      expect(codigo, proibido).not.toContain(proibido);
    }
  });

  it("busca apenas o progresso", () => {
    expect(codigo).toContain("fetchProgress");
  });
});
