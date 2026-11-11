import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import * as cadencia from "./cadencia";
import {
  CORTES_CADENCIA,
  RESSALVA_CADENCIA,
  cadenciaNaFalaDoPaciente,
  formatarCadencia,
  formatarFalaDoPaciente,
  lerCadencia,
  segmentosDoRelatorio,
} from "./cadencia";
import { palavrasPorMinutoNaFalaDoPaciente } from "./medidas-do-corte";

const seg = (s: number, t: string) => ({ elapsedSeconds: s, text: t });

describe("palavras por minuto na fala do paciente (unidade da literatura)", () => {
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

describe("sem faixas absolutas da literatura (decisão do dono, 11/11/2026)", () => {
  it("o módulo não exporta mais régua absoluta de palavras por minuto", () => {
    // A verificação das fontes mostrou: o 190 não tem fonte, o 100 é média de
    // grupo tratada como corte, o 50 é citação de segunda mão — e os números
    // dos estudos não são comparáveis aos do FROID.
    for (const nome of ["zonaDaLiteratura", "CORTES_LITERATURA", "ROTULO_ZONA_LITERATURA", "formatarPpmNaFala"]) {
      expect(nome in cadencia).toBe(false);
    }
  });

  it("nenhuma tela nem o PDF voltam a mostrar a faixa absoluta", () => {
    for (const arquivo of ["../pages/LiveSession.tsx", "../pages/SessionReport.tsx", "./report-pdf.ts"]) {
      const fonte = readFileSync(resolve(__dirname, arquivo), "utf8");
      expect(fonte).not.toMatch(/zonaDaLiteratura|formatarPpmNaFala|faixa descrita na afasia|pressão de fala e mania/);
    }
  });
});

describe("cadência só na fala do paciente", () => {
  it("a fala do profissional não mexe na cadência", () => {
    const base = [seg(5, "PC - " + "a ".repeat(14)), seg(70, "PC - " + "b ".repeat(14))];
    const comProfissional = [
      ...base,
      seg(12, "DR. - " + "x ".repeat(60)),
      seg(80, "DR. - " + "y ".repeat(5)),
    ];
    const sem = cadenciaNaFalaDoPaciente(base, 60, 120);
    const com = cadenciaNaFalaDoPaciente(comProfissional, 60, 120);
    expect(com.atual).toBe(sem.atual);
    expect(com.referencia).toBe(sem.referencia);
    expect(com.leitura?.variacao).toBeCloseTo(0);
  });

  it("a referência é dos 60 s iniciais e mostra de quantas palavras saiu", () => {
    const linhas = [seg(5, "PC - " + "a ".repeat(14)), seg(70, "PC - " + "b ".repeat(7))];
    const c = cadenciaNaFalaDoPaciente(linhas, 60, 120);
    expect(c.referencia).toBe(120);
    expect(c.palavrasNaReferencia).toBe(14);
    expect(c.atual).toBe(60);
    expect(formatarCadencia(c.leitura)).toBe("−50% vs. 60 s iniciais desta sessão · muito lentificada");
    expect(formatarFalaDoPaciente(c)).toBe("60 p/min (referência: 120 p/min em 14 palavras)");
  });

  it("sem fala do paciente nos 60 s iniciais, declara a falta de referência", () => {
    const c = cadenciaNaFalaDoPaciente([seg(70, "PC - " + "b ".repeat(7))], 60, 120);
    expect(c.referencia).toBeNull();
    expect(c.leitura).toBeNull();
    expect(formatarFalaDoPaciente(c)).toContain("sem referência");
  });

  it("o relatório só monta segmentos com o instante de cada linha", () => {
    expect(segmentosDoRelatorio("PC - oi\nDR. - ola", [3, 9])).toEqual([seg(3, "PC - oi"), seg(9, "DR. - ola")]);
    expect(segmentosDoRelatorio("PC - oi\nDR. - ola", [3])).toBeNull();
    expect(segmentosDoRelatorio("PC - oi", undefined)).toBeNull();
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

  it("formata para leitura, dizendo de que referência se trata", () => {
    expect(formatarCadencia(lerCadencia(68, 100))).toBe("−32% vs. 60 s iniciais desta sessão · muito lentificada");
    expect(formatarCadencia(lerCadencia(120, 100))).toBe("+20% vs. 60 s iniciais desta sessão · acelerada");
    expect(formatarCadencia(lerCadencia(100, 100))).toBe("0% vs. 60 s iniciais desta sessão · na referência");
  });

  it("a ressalva diz o que a medida mostra e o que não mostra", () => {
    expect(RESSALVA_CADENCIA).toContain("só a fala dele");
    expect(RESSALVA_CADENCIA).toContain("não o estado em que o paciente chegou");
    expect(RESSALVA_CADENCIA).toContain("escolha do produto");
    expect(RESSALVA_CADENCIA).toContain("não cortes para um indivíduo");
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
