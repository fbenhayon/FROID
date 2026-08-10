import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * A trava de toda a superficie visivel do produto.
 *
 * Os testes anteriores cobriam os arquivos que eu havia corrigido. Este varre
 * o frontend inteiro, porque o proximo lapso vai ser num arquivo que ninguem
 * esta olhando — foi assim que "Diretriz Clinica: estimular a transicao para a
 * autovalidacao" viveu doze vezes nas descricoes de zona, e que o grafico
 * exibiu percentuais de "Depressao" crachados com PHQ-9.
 *
 * Sao dois grupos, ambos sem uso legitimo em texto de produto:
 *   - prescricao de conduta clinica ao profissional;
 *   - nome de instrumento psicometrico que o FROID nao aplica.
 */
function arquivosFonte(dir: string, acc: string[] = []): string[] {
  for (const entrada of readdirSync(dir)) {
    const caminho = join(dir, entrada);
    if (statSync(caminho).isDirectory()) arquivosFonte(caminho, acc);
    else if (/\.(ts|tsx|html)$/.test(entrada) && !/\.test\.tsx?$/.test(entrada)) {
      acc.push(caminho);
    }
  }
  return acc;
}

const PRESCRICAO = [
  "diretriz clínica", "diretriz clinica",
  "considere regular", "acolha a emoção", "contenha a",
  "investigar resistências", "estimule suavemente", "não force o",
];

// Instrumentos validados que o FROID nao administra. Citar como referencia
// bibliografica e legitimo; usar como rotulo de saida ou alegar calibracao
// contra eles nao e.
const CALIBRACAO_FALSA = [
  "predição matemática da escala",
  "matriz psicométrica para calibração",
  "correlacionável a escalas validadas",
  "espelha subescalas",
  "baseada em preditores vocais da",
];

describe("fronteira clinica em todo o frontend", () => {
  const arquivos = arquivosFonte("src");

  it("nao prescreve conduta clinica em nenhum arquivo de produto", () => {
    const achados: string[] = [];
    for (const arquivo of arquivos) {
      const baixo = readFileSync(arquivo, "utf-8").toLowerCase();
      for (const termo of PRESCRICAO) {
        if (baixo.includes(termo)) achados.push(`${arquivo}: "${termo}"`);
      }
    }
    expect(achados).toEqual([]);
  });

  it("nao alega calibracao contra instrumento que nao aplica", () => {
    const achados: string[] = [];
    for (const arquivo of arquivos) {
      const baixo = readFileSync(arquivo, "utf-8").toLowerCase();
      for (const termo of CALIBRACAO_FALSA) {
        if (baixo.includes(termo)) achados.push(`${arquivo}: "${termo}"`);
      }
    }
    expect(achados).toEqual([]);
  });
});

/**
 * A trava acima procura FRASES. Isso não bastou.
 *
 * Um relatório de produção trouxe, no texto que o profissional lê, "Mitigar
 * validando a fala sem confrontar bruscamente" e "Mitigar pausando confronto
 * direto". É prescrição de conduta, da mesma família de "acolha a emoção" — e
 * passou porque usa outras palavras. Sete blocos assim conviviam com um teste
 * escrito para impedi-los.
 *
 * Procurar frase pega o que já aconteceu. Procurar PADRÃO pega a próxima
 * redação. É a diferença entre uma trava e um histórico.
 */

/** Verbo de conduta dirigido a quem conduz a sessão, seguido de gerúndio ou
 *  infinitivo — "Mitigar validando", "Facilitar aceitação", "Reduzir demanda". */
const CONDUTA = new RegExp(
  "\\b(mitigar|facilitar|estimular|acolher|conter|desacelerar|pausar|reduzir|"
  + "diminuir|restaurar|confrontar|investigar|validar|orientar)\\s+"
  + "(?:a |o |as |os )?[a-zà-ú]+(?:ndo|ção|cao|ao|encia|ência)\\b",
  "i",
);

/** Rótulos que nomeiam a PESSOA, e não o sinal medido. */
const ROTULO_DE_PESSOA = [
  "sorriso falso", "falsa calma", "tristeza mascarada", "raiva contida",
  "desprezo unilateral", "shutdown psíquico", "shutdown psiquico",
  "retraumatizacao", "retraumatização",
];

/** Onde a regra vale sem exceção: o que chega ao paciente. */
const SUPERFICIE_DO_PACIENTE = [
  "dissonance-patient-view.ts",
  "PatientPortalPage.tsx",
  "PatientSessionPage.tsx",
];

describe("o que chega ao paciente nao prescreve nem rotula", () => {
  const arquivos = arquivosFonte("src").filter((caminho) =>
    SUPERFICIE_DO_PACIENTE.some((nome) => caminho.endsWith(nome)),
  );

  it("as superficies do paciente existem", () => {
    // Se um arquivo for renomeado e sair da lista, o teste passaria vazio e
    // ninguem notaria a cobertura evaporando.
    expect(arquivos.length).toBeGreaterThanOrEqual(SUPERFICIE_DO_PACIENTE.length);
  });

  it("nao prescreve conduta", () => {
    const achados: string[] = [];
    for (const arquivo of arquivos) {
      const conteudo = readFileSync(arquivo, "utf-8");
      // Comentario explicando a regra pode citar o padrao; texto de produto nao.
      const semComentarios = conteudo
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .replace(/^\s*\/\/.*$/gm, " ");
      const m = semComentarios.match(CONDUTA);
      if (m) achados.push(`${arquivo}: "${m[0]}"`);
    }
    expect(achados).toEqual([]);
  });

  it("nao rotula a pessoa", () => {
    const achados: string[] = [];
    for (const arquivo of arquivos) {
      const linhas = readFileSync(arquivo, "utf-8")
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .split(/\r?\n/);
      linhas.forEach((linha, indice) => {
        const baixo = linha.toLowerCase();
        if (baixo.trim().startsWith("//")) return;
        // O módulo de tradução PRECISA citar o título técnico como chave de
        // correspondência. A linha da chave é isenta; qualquer outra, não —
        // e é essa distinção, e não a frase inteira, que separa "traduzir de"
        // de "dizer ao paciente".
        if (baixo.trim().startsWith("professionaltitle:")) return;
        for (const termo of ROTULO_DE_PESSOA) {
          if (baixo.includes(termo)) {
            achados.push(`${arquivo}:${indice + 1}: "${termo}"`);
          }
        }
      });
    }
    expect(achados).toEqual([]);
  });
});
