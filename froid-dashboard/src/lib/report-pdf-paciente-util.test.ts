/**
 * O documento do paciente serve para alguma coisa?
 *
 * Um relatório real de 04/09/2026 respondeu que não. Onze minutos de sessão,
 * quatro páginas, e vinte e uma linhas em `0,00` — IPM, IDM, F0, jitter,
 * shimmer, ZCR, loudness, todos os MFCC. Energia da fala `0,0` contra uma
 * referência de `0,0`. Coluna de tom vazia nas três linhas. Três seções
 * seguidas dizendo que não havia sinais, nem observações, nem anotações.
 *
 * Quem lê aquilo conclui uma de duas coisas: que ficou mudo por onze minutos,
 * ou que o aparelho não funciona. A segunda é a correta, e é a pior das duas.
 *
 * Os zeros não eram medida. `_safe_float(value, default=0.0)` no servidor
 * converte a ausência que o motor de métricas devolve com honestidade, e o PDF
 * imprimia `--` só para valor não-finito. Zero passava como número.
 *
 * E havia uma contradição achável pelo próprio paciente: a seção 03 dizia que o
 * ritmo da fala foi 161,8; a seção 08 dizia 146,17. Os dois saem dos mesmos
 * três cortes — 146,17 é a média simples de 131,1, 130,0 e 177,4, que dá ao
 * corte de DOZE SEGUNDOS o mesmo peso do corte de sete minutos e 47.
 *
 * Duas coisas, porém, tinham sido medidas de verdade naquela sessão: quanto
 * tempo cada assunto ocupou, e em que velocidade a pessoa falava dentro de cada
 * um. As duas estavam no documento — repartidas entre duas tabelas em corpo 8,
 * cercadas de zeros que as desmentiam.
 *
 * Este arquivo guarda o conserto: a ausência se declara, o que foi medido vem
 * primeiro, cada trecho termina numa pergunta, e a planilha técnica sai.
 */

import { describe, expect, it } from "vitest";
import { buildReport, teseDaSessao } from "./report-pdf";
import type { SessionReportRecord } from "./session-report";

/** Três cortes de tamanhos muito diferentes, como na sessão real. */
const CORTES = [
  {
    startMinute: 0, endMinute: 3, startSecond: 0, endSecond: 217,
    theme: "Conexão e funcionamento do FROID", summary: "Primeiro trecho.",
    wordsPerMinute: 131.1, dissonanceCount: 0,
  },
  {
    startMinute: 3, endMinute: 3, startSecond: 217, endSecond: 229,
    theme: "Continuação da sessão clínica", summary: "Doze segundos.",
    wordsPerMinute: 130.0, dissonanceCount: 0,
  },
  {
    startMinute: 3, endMinute: 11, startSecond: 229, endSecond: 696,
    theme: "Influência de crenças familiares", summary: "Terceiro trecho.",
    wordsPerMinute: 177.4, dissonanceCount: 0,
  },
];

function relatorio(procedencia?: unknown): SessionReportRecord {
  return {
    sessionId: "froid-teste",
    createdAt: "2026-09-04T13:04:00.000Z",
    durationSeconds: 699,
    patient: { name: "Fabio" },
    professional: { name: "Philippe", email: "p@b.com" },
    // Tudo em zero, como saiu do servidor quando não houve apuração acústica.
    baseline: { ipmAvg: 0, idmAvg: 0, wordsPerMinute: 134 },
    sessionAverage: { ipmAvg: 0, idmAvg: 0, wordsPerMinute: 161.8 },
    sessionSummary: {
      text:
        "A sessão percorreu 3 assuntos: A; B; C. A sequência dos cortes indica a "
        + "seguinte progressão clínica e semântica: 0-4min A: texto. Em conclusão, "
        + "este resumo deve ser lido como síntese da substância verbal.",
    },
    conversationSummaries: CORTES,
    tenMinuteCuts: [
      { label: "0-4min (manual)", ipmAvg: 0, wordsPerMinute: 131.1 },
      { label: "3-4min (manual)", ipmAvg: 0, wordsPerMinute: 130.0 },
      { label: "3-12min (final)", ipmAvg: 0, wordsPerMinute: 177.4 },
    ],
    dissonances: [],
    clinicalNotes: [],
    ...(procedencia ? { procedenciaDosDados: procedencia } : {}),
  } as unknown as SessionReportRecord;
}

const IDENT = {
  clinicName: "", professionalName: "Philippe",
  professionalRegistry: "", contactEmail: "p@b.com",
};

const SEM_VOZ = { amostras: 240, amostrasComVozReal: 0, amostrasComFaceReal: 0 };
const COM_VOZ = { amostras: 240, amostrasComVozReal: 230, amostrasComFaceReal: 200 };

const doc = (proc?: unknown) => buildReport("patient", relatorio(proc), IDENT, "", 0);

/** O texto como o navegador o vê.
 *
 *  Dentro de um template literal, o recuo do código é conteúdo — mas o HTML
 *  colapsa espaço em branco ao renderizar, então uma frase quebrada em duas
 *  linhas no fonte sai inteira na página. Asserção sobre o fonte cru quebraria a
 *  cada reindentação sem nada da garantia ter mudado.
 *
 *  A exceção está guardada logo abaixo: `.corrido` tem `white-space:pre-wrap`, e
 *  ali o recuo do código SAI IMPRESSO. Foi assim que "Seu / profissional não
 *  registrou" chegou à quarta página de um relatório real. */
const texto = (html: string) => html.replace(/\s+/g, " ");

describe("ausência se declara, nunca se preenche", () => {
  it("sem voz apurada, os índices dizem que não foram medidos", () => {
    const html = doc(SEM_VOZ);
    expect(html).toContain("não medido nesta sessão");
  });

  it("e explica o porquê, para não ser lido como defeito do produto", () => {
    expect(doc(SEM_VOZ)).toContain("não conseguiu");
  });

  it("o que NÃO depende da voz continua sendo publicado", () => {
    // O ritmo sai da transcrição, não do microfone. Apagá-lo junto seria trocar
    // uma mentira por um apagão.
    const html = doc(SEM_VOZ);
    expect(html).toContain("161,8");
    expect(html).toContain("134,0");
  });

  it("com voz apurada, o número aparece normalmente", () => {
    const html = doc(COM_VOZ);
    expect(html).not.toContain("não medido nesta sessão");
  });

  it("em relatório antigo, sem registro de procedência, não afirma nem nega", () => {
    // Anteriores ao registro de procedência: dizer "não medido" seria acusar uma
    // sessão que pode ter sido medida. Dizer 0,00 seria o defeito de origem.
    const html = doc(undefined);
    expect(html).toContain("0,00");
    expect(html).not.toContain("não medido nesta sessão");
  });
});

describe("o documento abre pelo que foi medido de verdade", () => {
  const html = doc(SEM_VOZ);

  it("a seção existe e vem antes das medidas de voz", () => {
    expect(html).toContain("O que mais pesou nesta conversa");
    expect(html.indexOf("O que mais pesou")).toBeLessThan(
      html.indexOf("A sua referência deste dia"),
    );
  });

  it("nomeia o assunto mais longo e a fatia que ele ocupou", () => {
    expect(html).toContain("Influência de crenças familiares");
    // 467 s de 696 s = 67%.
    expect(html).toContain("67% da conversa");
  });

  it("nomeia a virada de ritmo, com os dois números", () => {
    expect(texto(html)).toContain("de 130 para 177 palavras por minuto");
    expect(texto(html)).toContain("36% mais rápida");
  });

  it("explica o que é ritmo antes de mostrar qualquer número dele", () => {
    expect(html).toContain("Não existe ritmo certo");
  });

  it("não interpreta: devolve a leitura a quem viveu a conversa", () => {
    expect(html).toContain("só você pode dizer");
  });
});

describe("cada trecho termina numa pergunta", () => {
  const html = doc(SEM_VOZ);

  it("uma por trecho", () => {
    expect(html.split("Para pensar:").length - 1).toBe(CORTES.length);
  });

  it("a pergunta sai de um número medido, não de uma leitura do conteúdo", () => {
    expect(texto(html)).toContain("de 130 para 177 palavras por minuto");
  });

  it("sem virada de ritmo, a pergunta cai no tamanho do trecho", () => {
    // A ordem importa e é deliberada: a mudança de ritmo vem antes do tamanho
    // porque é a mais específica das duas, e a que o paciente tem menos chance
    // de ter percebido sozinho. Aqui não há mudança nenhuma, e é o tamanho que
    // sustenta a pergunta.
    const parelho = relatorio(SEM_VOZ) as unknown as Record<string, unknown>;
    parelho.conversationSummaries = CORTES.map((c) => ({ ...c, wordsPerMinute: 140 }));
    const semVirada = buildReport("patient", parelho as never, IDENT, "", 0);
    expect(texto(semVirada)).toContain("trecho mais longo");
    expect(texto(semVirada)).not.toContain("palavras por minuto. Você percebeu");
  });

  it("nenhum parágrafo de espaço preservado carrega quebra do código", () => {
    // `.corrido` imprime o recuo do fonte. Qualquer frase nova nessa classe que
    // ocupe duas linhas no código sai partida na página impressa.
    const QUEBRA = String.fromCharCode(10);
    for (const bloco of html.matchAll(/class="corrido"[^>]*>([^<]*)</g)) {
      expect(bloco[1], bloco[1].slice(0, 40)).not.toContain(QUEBRA);
    }
  });
});

describe("o que saiu do documento do paciente", () => {
  const html = doc(SEM_VOZ);

  it("a planilha técnica não vai mais junto", () => {
    expect(html).not.toContain("Medidas detalhadas");
    expect(html).not.toContain("MFCC");
    expect(html).not.toContain("DDMFCC9");
  });

  it("o título não promete dez minutos sobre cortes manuais", () => {
    expect(html).not.toContain("Medidas a cada dez minutos");
    expect(html).toContain("Medidas trecho a trecho");
  });

  it("coluna sem apuração não vira coluna vazia", () => {
    expect(html).not.toContain("<th>Tom</th>");
  });

  it("registro profissional em branco não imprime traço", () => {
    expect(html).not.toContain("<dt>Registro</dt>");
  });

  it("a frase quebrada no meio parou de sair quebrada", () => {
    expect(html).toContain("Seu profissional não registrou anotações");
  });
});

describe("o resumo não repete o percurso inteiro", () => {
  it("corta na marca do nosso próprio gabarito", () => {
    expect(teseDaSessao("A sessão percorreu 2 assuntos: A; B. A sequência dos cortes indica x."))
      .toBe("A sessão percorreu 2 assuntos: A; B.");
  });

  it("sem a marca, devolve o texto inteiro — degrada para o comportamento de hoje", () => {
    expect(teseDaSessao("Texto livre do profissional.")).toBe("Texto livre do profissional.");
  });

  it("nunca devolve vazio quando havia texto", () => {
    expect(teseDaSessao("A sequência dos cortes indica x.")).toBe("A sequência dos cortes indica x.");
  });

  it("no documento, a recomposição dos cortes não aparece duas vezes", () => {
    const html = doc(SEM_VOZ);
    expect(html).not.toContain("Em conclusão, este resumo deve ser lido");
  });
});

/**
 * `Number(null)` vale ZERO, e zero é finito.
 *
 * Enquanto `ipmAvg`, `idmAvg`, `wordsPerMinute` e `dissonanceCount` chegavam
 * sempre como número — a origem em `buildMetricSnapshot` fechava a ausência com
 * `|| 0` —, esta armadilha ficava dormente neste arquivo: o zero vinha de lá,
 * não daqui. Em 06/09/2026 esses campos passaram a `number | null`, que é o que
 * o servidor já grava (`_medida` devolve `None`), e a armadilha acordaria de
 * uma vez: `num()` e `medida()` chamavam `Number(value)` sem perguntar se havia
 * valor, então `null` voltaria a imprimir "0,0" — o mesmo `0,00` que este
 * arquivo inteiro existe para não repetir, entrando pela porta ao lado.
 *
 * Um relatório com o campo NULO tem de sair igual ao que declara ausência. Se
 * um dia sair "0,0", este teste cai.
 */
describe("campo nulo não vira zero no documento do paciente", () => {
  const nulo = () => {
    const base = relatorio(SEM_VOZ) as unknown as Record<string, any>;
    // Como o construtor de cortes passa a entregar quando não houve apuração.
    base.baseline = { ipmAvg: null, idmAvg: null, wordsPerMinute: null, dissonanceCount: null };
    base.sessionAverage = { ipmAvg: null, idmAvg: null, wordsPerMinute: null, dissonanceCount: null };
    base.tenMinuteCuts = [
      { label: "0-10min", ipmAvg: null, idmAvg: null, wordsPerMinute: null, dissonanceCount: null },
    ];
    return base as unknown as SessionReportRecord;
  };

  const html = () => buildReport("patient", nulo(), IDENT, "", 0);

  it("não imprime 0,0 nem 0,00 para campo ausente", () => {
    const corpo = texto(html());
    expect(corpo).not.toMatch(/>\s*0,0+\s*</);
  });

  it("diz que não foi medido", () => {
    expect(html()).toContain("não medido nesta sessão");
  });

  // O "Ritmo da fala" é o caso decisivo: a chamada passa `apurado: true` fixo
  // — a transcrição não depende da procedência do PCM —, então a única defesa
  // contra o nulo está dentro de `medida`. Com o `Number(null)` antigo esta
  // célula saía `<td class="n">0,0</td>`.
  //
  // A primeira versão desta asserção procurava a substring "0,0 palavras/min",
  // e caiu sobre "130,0 palavras/min" — uma medida REAL do fixture. Substring
  // sem fronteira é o defeito que esta casa já catalogou; aqui ele reprovou a
  // correção certa. A asserção agora é sobre a célula, não sobre um pedaço de
  // número solto.
  it("a célula do ritmo diz não medido, em vez de 0,0", () => {
    expect(texto(html())).toMatch(
      /Ritmo da fala<\/td>\s*<td class="n"><span class="ausente">/,
    );
  });
});
