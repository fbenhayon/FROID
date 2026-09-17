import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * O cartão do tooltip é ESCURO, e o conteúdo tem de ser escrito para ele.
 *
 * Até 17/09/2026 o `FroidTooltip` desenhava um cartão branco num aplicativo
 * inteiramente escuro. O conteúdo, porém, já vinha sendo escrito para fundo
 * escuro: uma varredura achou 43 usos de texto claro dentro dos tooltips
 * (`text-slate-100` em 26 deles) contra 7 de texto escuro. Ou seja, a maioria
 * do texto estava quase invisível, e o cartão branco é que era a anomalia.
 *
 * Ao inverter o cartão, os 7 escuros teriam sumido — trocar uma invisibilidade
 * por outra. Este teste existe para que a próxima linha escura dentro de um
 * `content=` não entre sem ninguém ver.
 *
 * O escopo importa: a ÂNCORA (os `children`) fica sobre o painel da página,
 * que em dois lugares é branco (CommitmentPanel, CoherenceLine). Um grep
 * ingênuo reprovaria a âncora legítima; por isso a varredura abaixo casa
 * chaves para isolar exatamente a expressão passada em `content=`.
 */

const RAIZ = join(__dirname, "..", "..");
const CARTAO = readFileSync(join(__dirname, "FroidTooltip.tsx"), "utf-8");

function arquivosTsx(dir: string): string[] {
  const saida: string[] = [];
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      saida.push(...arquivosTsx(caminho));
      continue;
    }
    if (/\.tsx$/.test(nome) && !/\.test\.tsx$/.test(nome)) saida.push(caminho);
  }
  return saida;
}

/** As expressões passadas em `content=`, isoladas por casamento de chaves. */
function blocosDeConteudo(fonte: string): string[] {
  const blocos: string[] = [];
  let busca = 0;
  for (;;) {
    const marca = fonte.indexOf("content={", busca);
    if (marca === -1) break;
    let profundidade = 0;
    let i = marca + "content=".length;
    const inicio = i;
    for (; i < fonte.length; i += 1) {
      if (fonte[i] === "{") profundidade += 1;
      else if (fonte[i] === "}") {
        profundidade -= 1;
        if (profundidade === 0) break;
      }
    }
    blocos.push(fonte.slice(inicio, i + 1));
    busca = i + 1;
  }
  return blocos;
}

const COM_TOOLTIP = arquivosTsx(RAIZ)
  .map((caminho) => ({
    caminho: caminho.slice(RAIZ.length + 1).replace(/\\/g, "/"),
    fonte: readFileSync(caminho, "utf-8"),
  }))
  .filter((arquivo) => arquivo.fonte.includes("<FroidTooltip"));

describe("o cartão do tooltip segue a paleta escura da NR-1", () => {
  it("fundo escuro, borda ciano, texto claro", () => {
    expect(CARTAO).toContain("bg-slate-950");
    expect(CARTAO).toContain("border-cyan-900");
    expect(CARTAO).toContain("text-slate-200");
  });

  it("o cartão branco não volta", () => {
    const cartao = CARTAO.slice(CARTAO.indexOf('className="fixed z-[9999]'));
    expect(cartao.slice(0, 400)).not.toContain("bg-white");
  });
});

describe("nenhum conteúdo de tooltip é escrito para fundo claro", () => {
  const ESCURO = /text-(?:slate|gray|zinc)-(?:600|700|800|900)|text-black/;
  const BORDA_CLARA = /border-(?:slate|gray)-(?:100|200)/;

  it("a varredura encontra blocos (não pode passar por não achar nada)", () => {
    const total = COM_TOOLTIP.reduce(
      (soma, arquivo) => soma + blocosDeConteudo(arquivo.fonte).length,
      0,
    );
    expect(COM_TOOLTIP.length).toBeGreaterThan(5);
    expect(total).toBeGreaterThan(20);
  });

  it("nenhum texto escuro dentro de content=", () => {
    const infratores: string[] = [];
    for (const arquivo of COM_TOOLTIP) {
      for (const bloco of blocosDeConteudo(arquivo.fonte)) {
        for (const linha of bloco.split("\n")) {
          if (ESCURO.test(linha)) infratores.push(`${arquivo.caminho}: ${linha.trim()}`);
        }
      }
    }
    expect(infratores, "sumiriam no cartão escuro").toEqual([]);
  });

  it("nenhuma borda clara dentro de content=", () => {
    // Borda slate-100 sobre slate-950 vira um risco branco atravessando o
    // tooltip — o mesmo defeito, do outro lado do contraste.
    const infratores: string[] = [];
    for (const arquivo of COM_TOOLTIP) {
      for (const bloco of blocosDeConteudo(arquivo.fonte)) {
        for (const linha of bloco.split("\n")) {
          if (BORDA_CLARA.test(linha)) infratores.push(`${arquivo.caminho}: ${linha.trim()}`);
        }
      }
    }
    expect(infratores, "riscam de branco o cartão escuro").toEqual([]);
  });

  it("a âncora continua livre — ela vive no painel, não no cartão", () => {
    // CommitmentPanel tem painel BRANCO: o título no corpo do cartão e o botão
    // que abre o tooltip são legitimamente escuros, e não podem ser varridos
    // junto. Se esta linha sumir, a varredura virou grep cego.
    const painel = COM_TOOLTIP.find((a) => a.caminho.endsWith("CommitmentPanel.tsx"));
    expect(painel).toBeDefined();
    expect(painel!.fonte).toContain("text-slate-800");
  });
});
