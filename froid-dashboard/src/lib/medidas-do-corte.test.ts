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

/** O fonte SEM comentários, para asserção sobre comportamento.
 *
 *  Uma versão anterior deste arquivo reprovou código correto porque o
 *  comentário que DOCUMENTA um defeito cita os mesmos nomes que a asserção
 *  proíbe. Teste que confunde documentação com comportamento acusa justamente
 *  quem se deu ao trabalho de explicar o defeito.
 *
 *  Definido uma vez: a segunda cópia foi escrita com escape quebrado e o
 *  arquivo inteiro deixou de carregar — zero testes rodando, que é pior do que
 *  um teste falhando, porque o placar não acusa.
 */
const BLOCO_DE_COMENTARIO = new RegExp("/\\*[\\s\\S]*?\\*/", "g");
const LINHA_DE_COMENTARIO = new RegExp("(^|[^:])//[^\\n]*", "g");
const semComentarios = (fonte: string) =>
  fonte.replace(BLOCO_DE_COMENTARIO, " ").replace(LINHA_DE_COMENTARIO, "$1 ");

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

/**
 * A ausência de leitura passa a se anunciar DURANTE a sessão.
 *
 * Antes, nada na tela dizia que a captura parou: a procedência da face só era
 * contabilizada ao montar o relatório, a seção "Leitura FACS/AUs" do painel só
 * aparece quando já existe leitura, e o estado da captura acústica que a
 * página do paciente envia caía apenas no log de diagnóstico do WebRTC, que
 * ninguém abre durante um atendimento.
 *
 * Numa sessão real de 18 minutos o PCM do paciente nunca chegou ao motor, o
 * profissional conduziu tudo sem saber, e a descoberta veio no relatório —
 * quando já não havia o que reprocessar. O dado viajava em `audio_meta` a cada
 * segundo e nenhuma tela o lia. É o padrão desta casa: a peça existe, está
 * correta, e nada a consome.
 */
describe("o painel avisa quando a leitura não está entrando", () => {
  const LIVE = semComentarios(
    readFileSync(join(__dirname, "..", "pages", "LiveSession.tsx"), "utf-8"),
  );

  it("lê a procedência que o motor já declarava a cada tique", () => {
    expect(LIVE).toContain('meta.facs_source === "real_facs"');
    expect(LIVE).toContain('meta.voice_features_source === "real_pcm"');
  });

  // Três layouts (detalhada, simplificada e a terceira). Um aviso que só existe
  // num deles é indistinguível de aviso nenhum para quem usa outro.
  //
  // A âncora é o quadro de câmera desligada, que marca cada caixa de vídeo: se
  // um quarto layout nascer com ele e sem o aviso, isto cai. Comparar contra o
  // literal 3 não pegaria esse caso — travaria o número, não a garantia.
  it("o aviso aparece em TODAS as telas de vídeo, e não só numa", () => {
    const avisos = LIVE.split("<AvisoDeApuracao").length - 1;
    const caixasDeVideo = LIVE.split("<CameraDesligada").length - 1;
    expect(caixasDeVideo).toBeGreaterThan(0);
    expect(avisos).toBe(caixasDeVideo);
  });

  it("não alarma antes da sessão estar de pé", () => {
    expect(LIVE).toContain('state.phase === "LIVE"');
    expect(LIVE).toContain("capturaEmCurso");
  });

  // No presencial puro não existe página do paciente, logo não existe câmera
  // dele: a ausência é estrutural do modo, não uma falha corrigível ali.
  it("no presencial puro explica o modo, em vez de alarmar", () => {
    expect(LIVE).toContain("presencialSemCamera");
    expect(LIVE).toContain("sem leitura facial");
  });

  it("tem limiar ancorado no tique de um segundo do servidor", () => {
    expect(LIVE).toContain("TIQUES_ATE_AVISAR");
    expect(LIVE).toMatch(/TIQUES_ATE_AVISAR\s*=\s*\d+/);
  });
});

/**
 * Falha de captura nao pode ser silenciosa NA TELA DE QUEM PODE RESOLVE-LA.
 *
 * Apurado ao longo de uma consulta inteira, 06/09/2026. Tres defeitos da mesma
 * familia — a mesma da CSP que desligou a analise acustica sem aviso:
 *
 *  1. `startF0Capture` reportava cada falha por `onStatus`, e o relato morria
 *     no log de diagnostico do WebRTC. O PACIENTE, unico que pode tocar a tela
 *     ou refazer a permissao, nao era informado de nada.
 *  2. `attachTracks` faz `element.play().catch(() => undefined)`. Bloqueio de
 *     reproducao automatica — que o navegador aplica a audio sem interacao, por
 *     padrao — era engolido. O profissional tem "Ouvir paciente" para esse
 *     caso; o paciente nao tinha equivalente e ficava sem ouvir sem saber por que.
 *  3. O painel do profissional sabia dizer "nao esta chegando", e nao o motivo,
 *     que o outro lado ja relatava pela sinalizacao.
 */
describe("a falha de captura chega a quem pode agir", () => {
  const raiz2 = join(__dirname, "..");
  const PAC = semComentarios(
    readFileSync(join(raiz2, "pages", "PatientSessionPage.tsx"), "utf-8"),
  );
  const PAINEL = semComentarios(
    readFileSync(join(raiz2, "pages", "LiveSession.tsx"), "utf-8"),
  );

  it("o status da captura acustica chega ao estado da tela do paciente", () => {
    expect(PAC).toContain("setStatusAcustico");
    expect(PAC).toContain("STATUS_CAPTURA_TEXTO");
  });

  it("o paciente tem como destravar o audio, e nao so o profissional", () => {
    expect(PAC).toContain("destravarAudio");
    expect(PAC).toContain("Toque para ouvir o profissional");
  });

  // `play()` rejeitado com trilha presente e bloqueio, nao ausencia de midia.
  it("o bloqueio de reproducao e detectado, e nao engolido", () => {
    expect(PAC).toContain("conferirReproducao");
    expect(PAC).toContain("audio.paused");
  });

  it("o motivo atravessa a sinalizacao ate o painel", () => {
    expect(PAC).toContain("detalhe: detalhe");
    expect(PAINEL).toContain("setCausaAcusticaNoPaciente");
    expect(PAINEL).toContain("causaNoPaciente");
  });
});
