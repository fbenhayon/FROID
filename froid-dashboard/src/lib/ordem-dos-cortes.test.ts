import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Os cortes aparecem na ordem em que a sessão aconteceu.
 *
 * Três listas vinham invertidas — o painel ao vivo, a lista viva do
 * LiveSession e os "Temas e Resumos por Cortes" do relatório — e a área do
 * paciente não ordenava nada, exibindo o array na ordem em que ele chegasse.
 *
 * Ler a sessão de trás para frente obriga a reconstruir a sequência de cabeça,
 * e isso acontece justamente quando o profissional está acompanhando a
 * conversa. Para o paciente é pior: ele lê o desfecho antes do começo.
 *
 * O teste varre a fonte porque a inversão é uma troca de dois caracteres —
 * `a - b` vira `b - a` — e passa despercebida em revisão.
 */

function arquivosFonte(dir: string, acc: string[] = []): string[] {
  for (const entrada of readdirSync(dir)) {
    const caminho = join(dir, entrada);
    if (statSync(caminho).isDirectory()) arquivosFonte(caminho, acc);
    else if (/\.tsx?$/.test(entrada) && !/\.test\.tsx?$/.test(entrada)) {
      acc.push(caminho);
    }
  }
  return acc;
}

const ARQUIVOS = arquivosFonte("src");

/** Comparadores descendentes sobre o início de um corte. */
const DESCENDENTE = [
  /b\.startMinute\s*-\s*a\.startMinute/,
  /b\.startSecond\s*-\s*a\.startSecond/,
  /return\s+bStart\s*-\s*aStart\s*;/,
];

describe("nenhuma lista de cortes vem invertida", () => {
  it("não existe comparador descendente por início de corte", () => {
    const achados: string[] = [];
    for (const arquivo of ARQUIVOS) {
      const conteudo = readFileSync(arquivo, "utf-8");
      // Comentário pode citar a forma antiga ao explicar a correção.
      const semComentarios = conteudo
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .replace(/^\s*\/\/.*$/gm, " ")
        .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, " ");
      for (const padrao of DESCENDENTE) {
        const m = semComentarios.match(padrao);
        if (m) achados.push(`${arquivo}: "${m[0]}"`);
      }
    }
    expect(achados).toEqual([]);
  });

  it("as quatro superfícies ordenam explicitamente", () => {
    // Sem ordenação explícita, a lista sai na ordem em que o array chegou —
    // que foi o caso da área do paciente até esta correção.
    const superficies = [
      ["components/panels/AudioTranscription.tsx", "painel ao vivo"],
      ["pages/LiveSession.tsx", "sessão em andamento"],
      ["pages/SessionReport.tsx", "relatório da consulta"],
      ["pages/PatientPortalPage.tsx", "área do paciente"],
    ];
    for (const [caminho, nome] of superficies) {
      const conteudo = readFileSync(join("src", caminho), "utf-8");
      const ordena =
        /a\.startMinute\s*-\s*b\.startMinute/.test(conteudo)
        || /aStart\s*-\s*bStart/.test(conteudo);
      expect(ordena, `${nome} (${caminho}) não ordena por início`).toBe(true);
    }
  });
});

describe("o painel ao vivo mostra régua, não transcrição", () => {
  const PAINEL = readFileSync(
    join("src", "components", "panels", "AudioTranscription.tsx"),
    "utf-8",
  );

  it("não renderiza o texto do resumo", () => {
    // Durante a sessão a transcrição competia com a escuta. O texto continua
    // inteiro no Relatório da Consulta, que é onde ele serve.
    expect(PAINEL).not.toContain("limitWords(item.summary");
  });

  it("mantém o tema do corte", () => {
    expect(PAINEL).toContain("limitWords(item.theme");
  });

  it("mantém o intervalo do corte", () => {
    expect(PAINEL).toContain("{item.startMinute}-{item.endMinute}min");
  });

  it("mantém o botão de fechar corte", () => {
    expect(PAINEL).toContain("Fechar corte");
  });

  it("desenha a régua do corte com rótulo acessível", () => {
    expect(PAINEL).toContain("spanMinutes");
    expect(PAINEL).toMatch(/aria-label=\{`Corte de \$\{item\.startMinute\}/);
  });

  it("a régua não divide por zero quando não há cortes", () => {
    // Math.max(1, ...) — sem o piso, uma sessão sem corte fechado produziria
    // largura Infinity e a barra ocuparia a tela.
    expect(PAINEL).toMatch(/Math\.max\(\s*1,\s*\.\.\.orderedSummaries/);
  });
});

describe("o Relatório da Consulta preserva o texto", () => {
  it("continua exibindo o resumo de cada corte", () => {
    // A remoção vale para os layouts da sessão, não para o relatório — é lá
    // que o profissional relê para escrever.
    const relatorio = readFileSync(join("src", "pages", "SessionReport.tsx"), "utf-8");
    expect(relatorio).toMatch(/cleanSummaryText\(|item\.summary|cut\.summary/);
  });
});
