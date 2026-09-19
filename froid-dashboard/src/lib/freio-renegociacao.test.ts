import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  limparDiagnosticoRtc,
  registrarNegociacao,
  relatorioRtc,
} from "./diagnostico-rtc";
import { criarFreioDeRenegociacao, eDesalinhamentoDeMlines } from "./webrtc";

/**
 * O defeito, vivido em 02/09/2026 numa consulta real:
 *
 * Os dois lados tratavam o erro da sinalização com
 * `.catch(() => { pedir renegociação })`. Quando a oferta falhava no paciente,
 * ele pedia renegociação; o profissional respondia com `restartIce()` e uma
 * oferta nova; essa falhava igual. O par girava na velocidade da rede — o log
 * do navegador mostrou `stable → have-local-offer → stable` duas vezes por
 * segundo, durante vinte segundos, e o ICE não chegou UMA vez a `checking`.
 *
 * Negociar leva segundos. O laço não dava milissegundos. A recuperação de erro
 * tinha virado o próprio erro.
 */
describe("o freio impede que a recuperação de erro vire o erro", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("a primeira tentativa passa — o freio não atrapalha o caso normal", () => {
    expect(criarFreioDeRenegociacao().permite()).toBe(true);
  });

  it("CEM falhas em um segundo produzem UMA renegociação, não cem", () => {
    // A regressão exata. Sem o freio, isto devolvia `true` cem vezes.
    const freio = criarFreioDeRenegociacao();
    const passaram = Array.from({ length: 100 }, () => {
      vi.advanceTimersByTime(10);
      return freio.permite();
    }).filter(Boolean).length;
    expect(passaram).toBe(1);
  });

  it("respeitado o espaçamento, as tentativas seguintes passam", () => {
    const freio = criarFreioDeRenegociacao({ intervaloMs: 2_000, maximo: 4 });
    expect(freio.permite()).toBe(true);
    vi.advanceTimersByTime(2_100);
    expect(freio.permite()).toBe(true);
  });

  it("a cota acaba, e aí o freio para de vez", () => {
    const freio = criarFreioDeRenegociacao({ intervaloMs: 1_000, maximo: 3 });
    for (let i = 0; i < 3; i += 1) {
      expect(freio.permite()).toBe(true);
      vi.advanceTimersByTime(1_100);
    }
    expect(freio.permite()).toBe(false);
    expect(freio.esgotado()).toBe(true);
  });

  it("«cedo demais» NÃO é «desisti» — só o segundo merece aviso na tela", () => {
    // Se os dois fossem iguais, o paciente veria "não foi possível conectar"
    // no primeiro milissegundo de uma chamada que ainda ia conectar.
    const freio = criarFreioDeRenegociacao({ intervaloMs: 2_000, maximo: 4 });
    expect(freio.permite()).toBe(true);
    vi.advanceTimersByTime(50);
    expect(freio.permite()).toBe(false);
    expect(freio.esgotado()).toBe(false);
  });

  it("conexão que sobe devolve a cota inteira", () => {
    const freio = criarFreioDeRenegociacao({ intervaloMs: 1_000, maximo: 2 });
    freio.permite();
    vi.advanceTimersByTime(1_100);
    freio.permite();
    expect(freio.esgotado()).toBe(true);
    freio.liberar();
    expect(freio.esgotado()).toBe(false);
    expect(freio.permite()).toBe(true);
  });

  it("depois de meio minuto quieto, a cota volta sozinha", () => {
    // Um problema novo meia hora depois não é o mesmo laço, e não deve herdar
    // a punição dele. Sem isto, uma chamada longa perderia a recuperação.
    const freio = criarFreioDeRenegociacao({ intervaloMs: 1_000, maximo: 2 });
    freio.permite();
    vi.advanceTimersByTime(1_100);
    freio.permite();
    expect(freio.permite()).toBe(false);
    vi.advanceTimersByTime(31_000);
    expect(freio.permite()).toBe(true);
  });
});

describe("o erro da sinalização não é mais descartado", () => {
  const ler = (arquivo: string) =>
    readFileSync(join(__dirname, "..", "pages", arquivo), "utf-8");

  /**
   * `.catch(() => ...)` jogava fora o objeto de erro. A investigação passou
   * por oito hipóteses sem nunca ver a mensagem do navegador que dizia o
   * motivo — porque ela era destruída a cada volta do laço.
   */
  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s registra a falha em vez de engolir",
    (arquivo) => {
      const fonte = ler(arquivo);
      expect(fonte).toContain("registrarFalha(\"tratar sinal recebido\", erro)");
      expect(fonte).not.toContain(".catch(() => {\n            setRtcStatus");
    },
  );

  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s passa a renegociação pelo freio",
    (arquivo) => {
      expect(ler(arquivo)).toContain("freioRenegociacao.permite()");
    },
  );

  it("o paciente ganhou o diagnóstico que só o profissional tinha", () => {
    expect(ler("PatientSessionPage.tsx")).toContain('observarConexao(');
  });

  it("o relatório do paciente atravessa até o painel do profissional", () => {
    // O paciente não tem console nem suporte: o que ele sabe precisa viajar.
    expect(ler("PatientSessionPage.tsx")).toContain('type: "diagnostico"');
    expect(ler("LiveSession.tsx")).toContain("incorporarRelatorioRemoto(");
  });
});

describe("o relatório diz se as DUAS trilhas subiram, nos DOIS sentidos", () => {
  /**
   * A pergunta do Fábio em 02/09/2026: "isso engloba as duas trilhas, uma do
   * paciente e outra do profissional?". O desenho engloba — mas o diagnóstico
   * não sabia dizer. Ele registrava o que CHEGAVA (`ontrack`), e o que chega
   * é justamente o que falta quando a chamada falha.
   *
   * A resposta vive nos transceptores, e só fica definitiva depois que a
   * resposta SDP é aplicada: antes disso `currentDirection` é nulo.
   */
  const transceptor = (
    kind: string,
    currentDirection: string | null,
    { envia = true, recebe = true, mudo = false } = {},
  ) =>
    ({
      currentDirection,
      sender: { track: envia ? { kind } : null },
      receiver: { track: recebe ? { kind, muted: mudo } : null },
    }) as never;

  const peerFalso = (transceptores: unknown[]) =>
    ({ getTransceivers: () => transceptores }) as never;

  beforeEach(() => limparDiagnosticoRtc());

  it("uma chamada saudável mostra áudio E vídeo em sendrecv", () => {
    registrarNegociacao(
      peerFalso([
        transceptor("audio", "sendrecv"),
        transceptor("video", "sendrecv"),
      ]),
    );
    const relatorio = relatorioRtc();
    expect(relatorio).toContain("audio sendrecv");
    expect(relatorio).toContain("video sendrecv");
    expect(relatorio).not.toContain("NAO envia");
    expect(relatorio).not.toContain("NAO recebe");
  });

  it("vídeo que ficou só de recepção aparece como tal", () => {
    // O caso que era invisível: negociar `recvonly` por engano de um lado
    // produz exatamente o sintoma de rede — sem nunca ser rede.
    registrarNegociacao(
      peerFalso([transceptor("video", "recvonly", { envia: false })]),
    );
    expect(relatorioRtc()).toContain("video recvonly — NAO envia");
  });

  it("trilha ainda muda é distinguida de trilha ausente", () => {
    // Uma trilha remota nasce muda e só desmuta quando o primeiro pacote
    // chega. Confundir as duas leva a investigar permissão de câmera quando o
    // problema é transporte.
    registrarNegociacao(peerFalso([transceptor("audio", "sendrecv", { mudo: true })]));
    expect(relatorioRtc()).toContain("recebe (ainda mudo)");
  });

  it("negociação vazia é dita com todas as letras", () => {
    registrarNegociacao(peerFalso([]));
    expect(relatorioRtc()).toContain("nenhum transceptor");
  });

  // A asserção era `.toBe(2)`, e travava a CONTAGEM em vez da garantia. Em
  // 19/09/2026 nasceu um terceiro ponto de desistência legítimo — o vigia da
  // oferta, que agora reenvia com teto e, ao atingi-lo, para e avisa. Tirar o
  // retrato ali é exatamente o que a regra pede, e o teste reprovou por isso.
  //
  // O que importa é que TODO caminho de desistência e a subida da conexão
  // deixem o retrato da negociação registrado: sem ele, "não conectou" é
  // indistinguível de "conectou sem trilha nenhuma". O número de caminhos é
  // detalhe, e travá-lo reprova a próxima correção em vez do próximo defeito.
  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s tira o retrato quando a conexão sobe e em toda desistência",
    (arquivo) => {
      const fonte = readFileSync(join(__dirname, "..", "pages", arquivo), "utf-8");
      const retratos = fonte.match(/registrarNegociacao\(peer\)/g)?.length ?? 0;
      // A subida da conexão e, no mínimo, a desistência do freio.
      expect(retratos).toBeGreaterThanOrEqual(2);
      // Âncora no ramo que trata a conexão subindo, e não em qualquer
      // `=== "connected"`: os dois arquivos têm outro, no monitor de fluxo, e
      // era nele que a primeira versão desta asserção caía.
      expect(fonte).toMatch(
        /connectionState === "connected"\)\s*\{\s*freioRenegociacao\.liberar\(\)[\s\S]{0,200}registrarNegociacao\(peer\)/,
      );
      // E o freio esgotado, que é a desistência mais antiga. O CANAL do
      // diagnóstico difere entre os dois lados de propósito — o profissional
      // pede o relatório do outro (`pedir-diagnostico`), o paciente envia o
      // seu (`enviarDiagnostico`) —, então o que se exige aqui é o retrato, que
      // é a garantia comum aos dois.
      const esgotou = fonte.indexOf("freioRenegociacao.esgotado()");
      expect(esgotou).toBeGreaterThan(-1);
      expect(fonte.slice(esgotou, esgotou + 600)).toContain("registrarNegociacao(peer)");
    },
  );

  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s registra o que ESTE lado está enviando",
    (arquivo) => {
      const fonte = readFileSync(join(__dirname, "..", "pages", arquivo), "utf-8");
      expect(fonte).toContain("registrarEnvio(peer)");
    },
  );
});

describe("o rollback saiu — era ele que embaralhava as m-lines", () => {
  /**
   * A causa raiz, lida no log de uma sessão real em 02/09/2026:
   *
   *   11:54:54  have-local-offer        ← oferta A
   *   11:54:54  stable                  ← ROLLBACK
   *   11:54:54  have-local-offer        ← oferta B
   *   11:54:55  FALHOU ... the order of m-lines in answer doesn't match
   *
   * A resposta do paciente era da oferta A e chegou na oferta B. O navegador
   * recusou. Pior: o peer do paciente já havia negociado com a ordem antiga, e
   * passou a recusar TODA oferta seguinte — seis recusas idênticas até
   * `failed`, cada uma respondida com um pedido de renegociação que só podia
   * falhar do mesmo jeito.
   */
  const fonte = (arquivo: string) =>
    readFileSync(join(__dirname, "..", "pages", arquivo), "utf-8");

  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s não faz rollback em lugar nenhum",
    (arquivo) => {
      expect(fonte(arquivo)).not.toContain('type: "rollback"');
    },
  );

  it("a oferta forçada REENVIA a pendente em vez de refazer", () => {
    // O impasse original — uma oferta entregue à sala vazia — se resolve sem
    // rollback: a sala agora tem alguém, então a mesma oferta serve.
    expect(fonte("LiveSession.tsx")).toContain("reenviarOfertaPendente()");
  });

  // O recorte era `i + 400` a partir do `setTimeout`, e quebrou pelo motivo que
  // esta casa já catalogou duas vezes: janela de caracteres não sobrevive ao
  // crescimento do bloco. Em 19/09/2026 o vigia ganhou teto e aviso de
  // desistência, o reenvio passou dos 400 caracteres, e o teste reprovou uma
  // correção. Agora o recorte é o corpo da função, pelo delimitador dela.
  it("o cão de guarda também reenvia, em vez de refazer", () => {
    const texto = fonte("LiveSession.tsx");
    const i = texto.indexOf("const armOfferWatchdog");
    expect(i).toBeGreaterThan(-1);
    // Até o fecho do próprio setTimeout: `makeOffer` vem logo abaixo e ele SIM
    // chama createOffer, legitimamente.
    const fim = texto.indexOf("}, 8_000);", i);
    expect(fim).toBeGreaterThan(i);
    const corpo = texto.slice(i, fim);
    expect(corpo).toContain("reenviarOfertaPendente()");
    expect(corpo).not.toContain("createOffer()");
  });

  it("cada oferta leva número, e a resposta o devolve", () => {
    expect(fonte("LiveSession.tsx")).toContain("seq: ofertaSeq");
    expect(fonte("PatientSessionPage.tsx")).toContain("seq: data.seq");
  });

  it("resposta de oferta superada é descartada, não aplicada", () => {
    // Aplicá-la era exatamente o que produzia o desalinhamento.
    expect(fonte("LiveSession.tsx")).toContain("data.seq !== ofertaSeq");
  });
});

describe("o desalinhamento de m-lines é reconhecido pelo nome", () => {
  it("reconhece as duas mensagens reais do incidente", () => {
    // Copiadas literalmente do log de 02/09/2026, uma de cada lado.
    const doProfissional = new Error(
      "Failed to execute 'setRemoteDescription' on 'RTCPeerConnection': "
      + "Failed to set remote answer sdp: The order of m-lines in answer "
      + "doesn't match order in offer. Rejecting answer.",
    );
    const doPaciente = new Error(
      "Failed to execute 'setRemoteDescription' on 'RTCPeerConnection': "
      + "Failed to set remote offer sdp: The order of m-lines in subsequent "
      + "offer doesn't match order from previous offer/answer.",
    );
    expect(eDesalinhamentoDeMlines(doProfissional)).toBe(true);
    expect(eDesalinhamentoDeMlines(doPaciente)).toBe(true);
  });

  it("não confunde com outros erros — reconstruir sem motivo derruba a chamada", () => {
    expect(eDesalinhamentoDeMlines(new Error("Failed to set remote answer sdp: Called in wrong state"))).toBe(false);
    expect(eDesalinhamentoDeMlines(new Error("ICE failed"))).toBe(false);
    expect(eDesalinhamentoDeMlines("m-lines")).toBe(false);
    expect(eDesalinhamentoDeMlines(null)).toBe(false);
  });

  it.each(["LiveSession.tsx", "PatientSessionPage.tsx"])(
    "%s reconstrói o peer em vez de renegociar, e com teto",
    (arquivo) => {
      const texto = readFileSync(join(__dirname, "..", "pages", arquivo), "utf-8");
      expect(texto).toContain("eDesalinhamentoDeMlines(erro)");
      // Sem teto, a reconstrução vira o laço que ela veio resolver.
      expect(texto).toContain("reconstrucoesRtcRef.current >= 2");
      expect(texto).toContain("reconstrucoesRtcRef.current = 0");
    },
  );
});
