import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * O documento que a fiscalização pede precisa ser visível.
 *
 * Sexta vez que este módulo produz o mesmo padrão: `GET .../inventory` existe
 * desde a migration 011, o documento era gerado e gravado, e nenhuma tela o
 * lia. O cliente clicava em "Gerar inventário", recebia "gerado com N linhas",
 * e não tinha onde ver as N linhas — nem onde imprimi-las.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1Inventario.tsx"), "utf-8");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAINEL = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");

describe("o inventário tem tela, e ela é alcançável", () => {
  it("a rota existe", () => {
    expect(APP).toContain('path="/nr1/inventario"');
  });

  it("o painel aponta para ela", () => {
    expect(PAINEL).toContain('nav("/nr1/inventario")');
  });

  it("lê a rota de inventário do servidor", () => {
    expect(PAGINA).toContain("/nr1/campaigns/${campaignId}/inventory");
  });
});

describe("o documento diz o que um documento de conformidade precisa dizer", () => {
  it("traz o cabeçalho que um auditor procura", () => {
    for (const campo of [
      "Período de referência",
      "Janela de coleta",
      "Efetivo do período de referência",
      "Respostas substantivas",
      "Critérios de gradação",
    ]) {
      expect(PAGINA).toContain(campo);
    }
  });

  it("declara qual régua graduou o risco", () => {
    // Inventário sem os critérios que o produziram não é explicável, e o
    // documento de critérios é o terceiro documento obrigatório do PGR.
    expect(PAGINA).toContain("criteria.published");
    expect(PAGINA).toContain("padrão FROID");
  });

  it("não transfere a responsabilidade da organização", () => {
    expect(PAGINA).toContain("permanece da organização");
  });
});

describe("a linha declarada insuficiente fica no mesmo documento", () => {
  /**
   * Separá-la produziria um inventário que parece completo e uma folha à parte
   * que ninguém abre — que é exatamente como se perde a informação de que um
   * recorte não foi avaliado.
   */

  it("as duas seções são impressas juntas", () => {
    expect(PAGINA).toContain("Riscos classificados");
    expect(PAGINA).toContain("Recortes sem avaliação conclusiva");
    // Nenhuma das duas pode ser marcada para sumir na impressão.
    const trechoDeclarado = PAGINA.slice(
      PAGINA.indexOf("Recortes sem avaliação conclusiva"),
    );
    expect(trechoDeclarado.slice(0, 600)).not.toContain("froid-nao-imprime");
  });

  it("nega a leitura de ausência de risco no próprio documento", () => {
    expect(PAGINA).toContain("não</strong> significa ausência");
    expect(PAGINA).toContain("permanece integral");
  });

  it("mostra a declaração da campanha inteira quando não há linhas", () => {
    // Ela não pode ser linha do inventário — `dimension_id` é NOT NULL e
    // insuficiência do conjunto não tem dimensão. Mas precisa chegar a quem lê,
    // senão a campanha que não fechou produz uma folha em branco.
    expect(PAGINA).toContain("declared_campaign");
    expect(PAGINA).toContain("Campanha inteira");
  });
});

describe("o que sai do papel", () => {
  it("a navegação não é impressa", () => {
    // Botão "Voltar ao painel" impresso denuncia captura de tela, não
    // documento.
    expect(PAGINA).toContain("froid-nao-imprime");
    expect(PAGINA).toContain("@media print");
    expect(PAGINA).toContain("size: A4");
  });

  it("a linha do risco não é quebrada entre páginas", () => {
    expect(PAGINA).toContain("break-inside: avoid");
  });
});
