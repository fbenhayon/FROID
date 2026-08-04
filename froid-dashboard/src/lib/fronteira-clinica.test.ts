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
