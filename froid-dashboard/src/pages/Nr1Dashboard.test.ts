import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const FONTE = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");

describe("road map do ciclo NR-1", () => {
  it("leva da estrutura à comprovação de eficácia na ordem operacional", () => {
    const passos = [
      "Estruturar",
      "Preparar a AEP",
      "Coletar",
      "Apurar",
      "Documentar",
      "Agir",
      "Reavaliar",
      "Comprovar eficácia",
      "Consolidar o dossiê",
    ];
    let anterior = -1;
    for (const passo of passos) {
      const atual = FONTE.indexOf(`titulo: "${passo}"`);
      expect(atual).toBeGreaterThan(anterior);
      anterior = atual;
    }
  });

  it("não apresenta a reavaliação como sucesso automático", () => {
    expect(FONTE).toContain("quando uma medida não demonstra eficácia");
    expect(FONTE).toContain("correção do próximo giro");
  });

  it("mantém o fluxo principal no road map e separa os recursos de apoio", () => {
    expect(FONTE).toContain('rota: "/nr1/dossie"');
    expect(FONTE).toContain("Recursos de apoio e prova");
    expect(FONTE).toContain('titulo: "Comprovante de aceite"');
    expect(FONTE).toContain('titulo: "FROID Explica NR-1"');
  });
});
