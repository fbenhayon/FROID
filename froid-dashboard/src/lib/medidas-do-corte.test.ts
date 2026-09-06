import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  menos,
  palavrasPorMinutoDoPaciente,
  transcricaoDoPaciente,
} from "./medidas-do-corte";

/**
 * O relatório dizia que nada foi medido, e publicava números.
 *
 * Sessão froid-mtpuwdafchqj, 06/09/2026, 18 minutos. O PCM do paciente nunca
 * chegou ao motor acústico — o aviso de procedência do relatório declarou
 * "nenhuma das 1077 amostras recebeu voz real do paciente" — e a face foi lida
 * em 1075 das 1077. São dois caminhos diferentes: as AUs faciais e o PCM saem
 * da página do paciente, a transcrição sai do WebRTC no navegador do
 * profissional. Um funcionou, o outro não.
 *
 * No meio desse relatório, duas classes de número que não deviam estar lá:
 *
 * 1. "Palavras/min" com 92,4; 135,7; 134,9 e 113,8. Não eram inventados: eram
 *    reais, e eram DO PROFISSIONAL. A contagem apagava os prefixos `DR. -` e
 *    `PC -` e somava as duas falas numa métrica publicada como ritmo de fala
 *    do paciente — no painel, no relatório, no PDF que ele recebe e no acervo
 *    anônimo do Data-Froid.
 *
 * 2. "IPM 0.00", "IDM 0.00", "Dissonância 0.00". O servidor declarava a
 *    ausência corretamente (`ipm_score: null`, `idm_score: null`,
 *    `perception_zones: []`); o painel a desfazia um passo antes da tela, com
 *    `rounded(...) || 0`. `0,00` é tipograficamente indistinguível de uma
 *    medida de zero, e num relatório clínico é lido como uma.
 *
 * O primeiro é um erro de atribuição; o segundo, de fabricação. Os dois
 * atravessaram 573 testes sem que nenhum caísse, porque nenhum exercitava o
 * caminho "sem apuração" — a lógica vivia dentro de um módulo React de sete
 * mil linhas que teste nenhum consegue importar.
 */

const DR = (s: number, texto: string) => ({ elapsedSeconds: s, text: `DR. - ${texto}` });
const PC = (s: number, texto: string) => ({ elapsedSeconds: s, text: `PC - ${texto}` });

describe("a transcrição do paciente exclui a fala do profissional", () => {
  it("descarta a linha do DR, em vez de tirar o prefixo dela", () => {
    const segmentos = [
      DR(1, "e como você se sentiu com isso"),
      PC(2, "eu fiquei bem"),
      DR(3, "entendo perfeitamente o que você está dizendo aqui"),
    ];
    expect(transcricaoDoPaciente(segmentos, 0, 600)).toBe("eu fiquei bem");
  });

  it("aceita o prefixo PAC das sessões antigas", () => {
    const segmentos = [{ elapsedSeconds: 1, text: "PAC - falei alguma coisa" }];
    expect(transcricaoDoPaciente(segmentos, 0, 600)).toBe("falei alguma coisa");
  });

  it("respeita a janela do corte", () => {
    const segmentos = [PC(5, "dentro"), PC(700, "fora")];
    expect(transcricaoDoPaciente(segmentos, 0, 600)).toBe("dentro");
  });
});

describe("palavras por minuto são as do paciente", () => {
  // O caso da sessão real: profissional falando, paciente sem uma linha.
  // O número saía alto e ia para o relatório como ritmo de fala DELE.
  it("é nulo quando só o profissional falou na janela", () => {
    const segmentos = [
      DR(1, "uma frase bem comprida do profissional aqui agora"),
      DR(30, "outra frase igualmente comprida do profissional agora"),
    ];
    expect(palavrasPorMinutoDoPaciente(segmentos, 0, 60)).toBeNull();
  });

  it("não soma as palavras do profissional às do paciente", () => {
    const soPaciente = [PC(1, "uma duas três quatro")];
    const comProfissional = [
      PC(1, "uma duas três quatro"),
      DR(2, "cinco seis sete oito nove dez onze doze"),
    ];
    expect(palavrasPorMinutoDoPaciente(soPaciente, 0, 60)).toBe(4);
    expect(palavrasPorMinutoDoPaciente(comProfissional, 0, 60)).toBe(4);
  });

  it("mede quando o paciente falou", () => {
    // 6 palavras em 30 s = 12 palavras/min.
    const segmentos = [PC(1, "uma duas três quatro cinco seis")];
    expect(palavrasPorMinutoDoPaciente(segmentos, 0, 30)).toBe(12);
  });

  // Zero afirmaria "o paciente falou a zero palavras por minuto", e não há
  // como distinguir paciente calado de captura que não rodou.
  it("é nulo, e não zero, quando não há transcrição nenhuma", () => {
    expect(palavrasPorMinutoDoPaciente([], 0, 600)).toBeNull();
  });
});

describe("diferença entre medidas", () => {
  it("é nula quando qualquer um dos lados não foi apurado", () => {
    expect(menos(null, 47)).toBeNull();
    expect(menos(47, null)).toBeNull();
    expect(menos(undefined, 1)).toBeNull();
    expect(menos(Number.NaN, 1)).toBeNull();
  });

  // `null - 47` vale `-47` em JavaScript: uma queda de energia que ninguém
  // mediu, publicada como delta no relatório e no acervo.
  it("não trata ausência como zero", () => {
    expect(menos(null, 47)).not.toBe(-47);
  });

  it("subtrai quando as duas foram apuradas", () => {
    expect(menos(50.6, 50.2)).toBeCloseTo(0.4, 6);
  });
});

/**
 * A regra, e não a ocorrência: nenhum campo de medida pode voltar a fechar a
 * ausência com zero em `buildMetricSnapshot`. Varre o arquivo inteiro, para
 * que a próxima cópia caia aqui sem ninguém precisar lembrar.
 */
describe("o construtor de cortes não fabrica zero", () => {
  const FONTE = readFileSync(join(__dirname, "..", "pages", "LiveSession.tsx"), "utf-8");
  const CORTE = (() => {
    const i = FONTE.indexOf("function buildMetricSnapshot(");
    expect(i, "âncora buildMetricSnapshot ausente").toBeGreaterThan(-1);
    const f = FONTE.indexOf("\nfunction ", i + 10);
    return FONTE.slice(i, f > i ? f : undefined);
  })();

  // `[^,]*` NÃO serve aqui, e a primeira versão deste teste usava exatamente
  // isso: a vírgula de `rounded(aggregate.ipm, 2)` interrompia o casamento
  // antes do `|| 0`, então a asserção passava sobre o código defeituoso. Um
  // teste que nunca pôde falhar. Conferido contra o arquivo do commit anterior:
  // com `[\s\S]{0,160}?` os três casam lá, e nenhum casa aqui.
  const fechaComZero = (campo: string) =>
    new RegExp(`${campo}:[\\s\\S]{0,160}?\\|\\|\\s*0`);

  it("não fecha IPM nem IDM com `|| 0`", () => {
    expect(CORTE).not.toMatch(fechaComZero("ipmAvg"));
    expect(CORTE).not.toMatch(fechaComZero("idmAvg"));
  });

  it("não fecha palavras por minuto com `|| 0`", () => {
    expect(CORTE).not.toMatch(fechaComZero("wordsPerMinute"));
  });

  it("conta palavras pela função que separa o falante", () => {
    expect(CORTE).toContain("palavrasPorMinutoDoPaciente");
    // A contagem antiga apagava os dois prefixos e somava tudo.
    expect(CORTE).not.toContain("^DR\\.");
  });
});

/**
 * A leitura facial tem UMA banda: a câmera do paciente, no dispositivo dele.
 *
 * Verificado em 06/09/2026, a pedido, depois do defeito do P/MIN. Ao contrário
 * do áudio — que tem duas bandas de propósito, porque a transcrição precisa
 * dos dois falantes —, o vídeo do profissional nunca é analisado. As AUs FACS
 * saem de `startFaceCapture` na página do paciente e chegam ao painel já
 * medidas pelo servidor.
 *
 * Estas asserções travam a assimetria: se um dia o painel do profissional
 * passar a calcular ou enviar blendshape, a face dele entraria na leitura do
 * paciente sem que nada acusasse — e a interpretação das expressões passaria a
 * misturar duas pessoas.
 */
describe("a leitura facial vem só da câmera do paciente", () => {
  const raiz = join(__dirname, "..");
  // Comentários fora: a primeira versão deste bloco reprovou o código correto,
  // porque o comentário que DOCUMENTA o defeito cita os mesmos nomes que a
  // asserção proíbe. Um teste que confunde documentação com comportamento
  // acusa exatamente quem se deu ao trabalho de explicar o defeito.
  const BLOCO = new RegExp("/\\*[\\s\\S]*?\\*/", "g");
  const LINHA = new RegExp("(^|[^:])//[^\\n]*", "g");
  const semComentarios = (fonte: string) =>
    fonte.replace(BLOCO, " ").replace(LINHA, "$1 ");
  const LIVE = semComentarios(
    readFileSync(join(raiz, "pages", "LiveSession.tsx"), "utf-8"),
  );
  const PACIENTE = semComentarios(
    readFileSync(join(raiz, "pages", "PatientSessionPage.tsx"), "utf-8"),
  );

  it("a página do paciente é quem captura e envia as AUs", () => {
    expect(PACIENTE).toContain("startFaceCapture");
    expect(PACIENTE).toContain("/facial-aus");
  });

  it("o painel do profissional não captura nem envia face", () => {
    expect(LIVE).not.toContain("startFaceCapture");
    expect(LIVE).not.toContain("froid-face");
    expect(LIVE).not.toContain("/facial-aus");
  });

  it("o quadro de câmera desligada não anuncia simulação", () => {
    expect(LIVE).not.toContain("Simulação Facial Ativa");
    expect(LIVE).not.toContain("SimulatedCamera");
  });

  it("nenhum canvas do painel vira MediaStream", () => {
    expect(LIVE).not.toContain("captureStream");
  });
});
