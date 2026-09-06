import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * A REGRA, e não a ocorrência.
 *
 * Em 06/09/2026 corrigi a contagem de palavras num lugar e declarei resolvido.
 * Havia outro: `buildMetricSnapshot` produz os cortes e o relatório, mas o
 * P/MIN exibido AO VIVO vinha de um segundo contador, dentro de
 * `appendTranscriptText`, que somava a fala do profissional à do paciente. O
 * dono testou, o erro continuou, e ele estava certo em cobrar.
 *
 * É o defeito que o guia desta casa já cataloga: "corrigi o lugar, não a
 * regra". Este arquivo existe para que a próxima cópia caia aqui sem ninguém
 * precisar lembrar — varre o diretório inteiro, e não os arquivos que eu me
 * lembrei de olhar.
 *
 * Duas regras, com a mesma raiz: um número que ninguém mediu não pode chegar à
 * tela parecendo medida.
 */

const RAIZ = join(__dirname, "..");

function arquivosDeFonte(dir: string): string[] {
  const saida: string[] = [];
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      saida.push(...arquivosDeFonte(caminho));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(nome)) continue;
    if (/\.test\.(ts|tsx)$/.test(nome)) continue;
    saida.push(caminho);
  }
  return saida;
}

const BLOCO = new RegExp("/\\*[\\s\\S]*?\\*/", "g");
const LINHA = new RegExp("(^|[^:])//[^\\n]*", "g");
/** Sem comentários: o texto que EXPLICA um defeito cita os mesmos nomes que a
 *  asserção proíbe, e reprovaria quem se deu ao trabalho de documentá-lo. */
const semComentarios = (fonte: string) =>
  fonte.replace(BLOCO, " ").replace(LINHA, "$1 ");

const FONTES = arquivosDeFonte(RAIZ).map((caminho) => ({
  caminho: caminho.slice(RAIZ.length + 1).replace(/\\/g, "/"),
  codigo: semComentarios(readFileSync(caminho, "utf-8")),
}));

describe("nenhum índice clínico fecha a ausência com um número", () => {
  it("há fontes para varrer (a varredura não pode passar por estar vazia)", () => {
    expect(FONTES.length).toBeGreaterThan(30);
  });

  // Os campos que descrevem o paciente. Um zero aqui não é "quase nada": é
  // uma afirmação clínica — energia zero, nenhuma dissonância, silêncio.
  const CAMPOS = [
    "ipmAvg",
    "idmAvg",
    "wordsPerMinute",
    "dissonanceCount",
  ];

  for (const campo of CAMPOS) {
    it(`${campo} não é fechado com \`|| 0\` nem \`?? 0\``, () => {
      const padrao = new RegExp(`${campo}\\s*(\\|\\||\\?\\?)\\s*\\d`);
      const infratores = FONTES.filter((f) => padrao.test(f.codigo)).map(
        (f) => f.caminho,
      );
      expect(infratores, `fecham ${campo} com número`).toEqual([]);
    });
  }

  // `String(x || 0)` era como o "0" chegava à faixa de índices e às tabelas:
  // não é formatação, é fabricação, e escapa da varredura acima porque o
  // número fica dentro da chamada.
  it("nenhum índice é impresso via String(... || 0)", () => {
    const padrao = new RegExp(
      `String\\(\\s*[A-Za-z_.?\\[\\]']*(?:${CAMPOS.join("|")})[^)]*\\|\\|\\s*\\d`,
    );
    const infratores = FONTES.filter((f) => padrao.test(f.codigo)).map(
      (f) => f.caminho,
    );
    expect(infratores).toEqual([]);
  });
});

describe("as palavras contadas são as do paciente, em todo lugar", () => {
  // `countSpokenUnits` é a única função que conta palavras faladas. Onde ela
  // for chamada, o falante tem de ter sido perguntado — foi a chamada sem essa
  // pergunta que somou a fala do profissional ao ritmo do paciente.
  const chamadores = FONTES.filter((f) => f.codigo.includes("countSpokenUnits("));

  it("existe pelo menos um chamador (senão a regra não protege nada)", () => {
    // A definição vive em localization.ts; os chamadores são o que interessa.
    const fora = chamadores.filter((f) => f.caminho !== "lib/localization.ts");
    expect(fora.length).toBeGreaterThan(0);
  });

  it("toda contagem ao vivo pergunta quem falou", () => {
    const semFiltro = chamadores
      .filter((f) => f.caminho !== "lib/localization.ts")
      .filter((f) => {
        const i = f.codigo.indexOf("countSpokenUnits(");
        const janela = f.codigo.slice(Math.max(0, i - 400), i + 200);
        return !/speaker|falante|"DR"|'DR'|PC/.test(janela);
      })
      .map((f) => f.caminho);
    expect(semFiltro, "contam palavras sem separar o falante").toEqual([]);
  });

  // O outro contador, o dos cortes: tem de passar pela função que descarta a
  // linha do profissional, e não por um regex que só apaga os prefixos.
  it("o construtor de cortes usa a contagem que separa o falante", () => {
    const live = FONTES.find((f) => f.caminho === "pages/LiveSession.tsx");
    expect(live).toBeDefined();
    expect(live!.codigo).toContain("palavrasPorMinutoDoPaciente");
  });
});
