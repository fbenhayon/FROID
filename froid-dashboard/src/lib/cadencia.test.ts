import { describe, expect, it } from "vitest";
import { CORTES_CADENCIA, RESSALVA_CADENCIA, formatarCadencia, lerCadencia } from "./cadencia";

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
