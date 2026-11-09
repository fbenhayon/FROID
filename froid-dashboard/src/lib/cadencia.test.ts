import { describe, expect, it } from "vitest";
import {
  CORTES_CADENCIA,
  CORTES_LITERATURA,
  RESSALVA_CADENCIA,
  formatarCadencia,
  formatarPpmNaFala,
  lerCadencia,
  zonaDaLiteratura,
} from "./cadencia";
import { palavrasPorMinutoNaFalaDoPaciente } from "./medidas-do-corte";

describe("palavras por minuto na fala do paciente (unidade da literatura)", () => {
  const seg = (s: number, t: string) => ({ elapsedSeconds: s, text: t });

  it("divide pelo tempo dos blocos do paciente, não pela janela", () => {
    // 2 blocos do paciente (14 s) com 21 palavras = 90 PPM, mesmo numa janela
    // de 60 s em que o profissional falou o resto do tempo.
    const linhas = [
      seg(0, "DR. - " + "fala ".repeat(40)),
      seg(10, "PC - " + "um ".repeat(10)),
      seg(20, "PC - " + "dois ".repeat(11)),
    ];
    expect(palavrasPorMinutoNaFalaDoPaciente(linhas, 0, 60)).toBe(90);
  });

  it("é nula sem fala do paciente", () => {
    expect(palavrasPorMinutoNaFalaDoPaciente([seg(0, "DR. - oi tudo bem")], 0, 60)).toBeNull();
    expect(palavrasPorMinutoNaFalaDoPaciente([], 0, 60)).toBeNull();
  });
});

describe("faixas da literatura", () => {
  it("usa os cortes da tabela do dono", () => {
    expect(CORTES_LITERATURA).toEqual({ afasia: 50, lentificacao: 100, aceleracao: 190 });
    expect(zonaDaLiteratura(30)).toBe("afasia_nao_fluente");
    expect(zonaDaLiteratura(96)).toBe("lentificacao");
    expect(zonaDaLiteratura(135)).toBe("referencia");
    expect(zonaDaLiteratura(190)).toBe("aceleracao");
  });

  it("declara ausência", () => {
    expect(zonaDaLiteratura(null)).toBeNull();
    expect(formatarPpmNaFala(undefined)).toBeNull();
  });

  it("formata como referência da literatura, não como diagnóstico", () => {
    const texto = formatarPpmNaFala(92) || "";
    expect(texto).toBe("92 · < 100 · lentificação descrita em retardo psicomotor depressivo e alogia");
    expect(texto.toLowerCase()).not.toContain("diagnóstico");
  });
});

describe("cadência relativa à referência do paciente", () => {
  it("mede a variação com sinal contra a referência", () => {
    expect(lerCadencia(68, 100)?.variacao).toBeCloseTo(-0.32);
    expect(lerCadencia(120, 100)?.variacao).toBeCloseTo(0.2);
  });

  it("separa as cinco faixas pelos cortes declarados", () => {
    expect(lerCadencia(100, 100)?.faixa).toBe("na_referencia");
    expect(lerCadencia(114, 100)?.faixa).toBe("na_referencia");
    expect(lerCadencia(115, 100)?.faixa).toBe("acelerada");
    expect(lerCadencia(130, 100)?.faixa).toBe("muito_acelerada");
    expect(lerCadencia(85, 100)?.faixa).toBe("lentificada");
    expect(lerCadencia(70, 100)?.faixa).toBe("muito_lentificada");
    expect(CORTES_CADENCIA).toEqual({ moderado: 0.15, acentuado: 0.3 });
  });

  it("declara ausência em vez de inventar leitura", () => {
    expect(lerCadencia(null, 100)).toBeNull();
    expect(lerCadencia(90, null)).toBeNull();
    expect(lerCadencia(90, 0)).toBeNull();
    expect(lerCadencia("abc", 100)).toBeNull();
    expect(formatarCadencia(null)).toBeNull();
  });

  it("zero palavras é medida, não ausência", () => {
    expect(lerCadencia(0, 100)?.faixa).toBe("muito_lentificada");
  });

  it("formata para leitura", () => {
    expect(formatarCadencia(lerCadencia(68, 100))).toBe("−32% vs. referência · muito lentificada");
    expect(formatarCadencia(lerCadencia(120, 100))).toBe("+20% vs. referência · acelerada");
    expect(formatarCadencia(lerCadencia(100, 100))).toBe("0% vs. referência · na referência");
  });

  it("não classifica pânico, mania nem depressão", () => {
    const textos = [
      ...["muito_acelerada", "acelerada", "na_referencia", "lentificada", "muito_lentificada"],
      formatarCadencia(lerCadencia(200, 100)),
      formatarCadencia(lerCadencia(20, 100)),
      RESSALVA_CADENCIA,
    ].join(" ").toLowerCase();
    for (const proibido of ["pânico", "panico", "mania", "maníac", "depress", "ansiedade"]) {
      expect(textos).not.toContain(proibido);
    }
  });
});
