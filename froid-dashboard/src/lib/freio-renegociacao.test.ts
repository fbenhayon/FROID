import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { criarFreioDeRenegociacao } from "./webrtc";

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
