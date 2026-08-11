import { describe, expect, it } from "vitest";
import type { EvidentMarker } from "./froid-engine";
import {
  countOutOfBounds,
  normalizeKey,
  statusLabel,
  STATUS_CLASSES,
  withBounds,
} from "./metric-bounds";

/**
 * A junção entre a lista completa de métricas e os limites do servidor.
 *
 * O layout Simplificado mostrava TODAS as métricas sem cor nenhuma; o Índices
 * mostrava só as que tinham métrica base, essas coloridas. Quem quisesse o
 * conjunto inteiro com indicação de ruptura alternava entre os dois e comparava
 * de cabeça.
 */

function marker(over: Partial<EvidentMarker>): EvidentMarker {
  return {
    key: "mfcc7",
    label: "MFCC7",
    category: "acustico",
    value: 6.71,
    band: [0.2, 1.5],
    direction: "acima",
    severity: 2,
    unit: "",
    interpretation: "Acima da faixa de referência.",
    ...over,
  };
}

describe("correlação de rótulos", () => {
  it("ignora acento, caixa e separador", () => {
    // O que a normalizacao resolve: rotulo e chave que so diferem em formato.
    expect(normalizeKey("JITTER")).toBe(normalizeKey("jitter"));
    expect(normalizeKey("IND. ESPECTRAL")).toBe(normalizeKey("Ind Espectral"));
    expect(normalizeKey("Dissonância")).toBe(normalizeKey("dissonancia"));
  });

  it("o que a normalização NÃO resolve depende do de-para", () => {
    // Abreviacao nao vira palavra inteira, e o servidor nomeia por FENOMENO
    // enquanto a tabela nomeia por GRANDEZA. Eu supus o contrario e este teste
    // e o que mostrou.
    expect(normalizeKey("IPM")).not.toBe(normalizeKey("ipm_hyper"));
    expect(normalizeKey("ZCR")).not.toBe(normalizeKey("zcr_dev"));

    const [ipm] = withBounds(
      [["IPM", "24,3"]],
      [marker({ key: "ipm_hyper", label: "Elevação multimodal (IPM)", direction: "acima" })],
    );
    expect(ipm.status).toBe("acima");
  });

  it("casa pela chave ou pelo rótulo do marcador", () => {
    const porChave = withBounds([["mfcc7", "6,710"]], [marker({ label: "Outro" })]);
    expect(porChave[0].status).toBe("acima");

    const porRotulo = withBounds([["MFCC7", "6,710"]], [marker({ key: "outra_coisa" })]);
    expect(porRotulo[0].status).toBe("acima");
  });
});

describe("situação de cada métrica", () => {
  it("distingue acima de abaixo", () => {
    const [acima] = withBounds([["MFCC7", "6,710"]], [marker({ direction: "acima" })]);
    const [abaixo] = withBounds([["MFCC7", "0,010"]], [marker({ direction: "abaixo" })]);
    expect(acima.status).toBe("acima");
    expect(abaixo.status).toBe("abaixo");
    // As duas pedem leituras opostas — nao podem compartilhar a cor.
    expect(STATUS_CLASSES.acima.box).not.toBe(STATUS_CLASSES.abaixo.box);
  });

  it("dentro da faixa não é marcado", () => {
    const [dentro] = withBounds([["MFCC7", "0,800"]], [marker({ direction: "dentro" })]);
    expect(dentro.status).toBe("dentro");
  });

  it("ruptura sem direção declarada ainda sinaliza", () => {
    // Melhor sinalizar sem dizer o lado do que engolir a informacao.
    const [m] = withBounds(
      [["MFCC7", "9,000"]],
      [marker({ direction: "", breached: true })],
    );
    expect(m.status).not.toBe("dentro");
  });

  it("métrica sem marcador sai como sem-limite, e não como dentro", () => {
    // Fingir que esta normal quando ninguem a avaliou e pior do que dizer que
    // nao ha regua para ela.
    const [m] = withBounds([["ZCR", "0,180"]], []);
    expect(m.status).toBe("sem-limite");
    expect(m.band).toBeUndefined();
  });

  it("preserva a faixa e a leitura do servidor", () => {
    const [m] = withBounds([["MFCC7", "6,710"]], [marker({})]);
    expect(m.band).toEqual([0.2, 1.5]);
    expect(m.interpretation).toContain("faixa de referência");
  });
});

describe("robustez", () => {
  it("lista vazia não quebra", () => {
    expect(withBounds([], [])).toEqual([]);
  });

  it("marcadores ausentes não quebram", () => {
    expect(withBounds([["IPM", "24,3"]], undefined as never)[0].status).toBe("sem-limite");
  });

  it("preserva a ordem original das métricas", () => {
    // A ordem da tabela e deliberada; reordenar por severidade faria a mesma
    // metrica trocar de lugar a cada tique.
    const entradas: Array<[string, string]> = [
      ["IPM", "24,3"], ["IDM", "0,01"], ["MFCC7", "6,7"],
    ];
    const saida = withBounds(entradas, [marker({})]);
    expect(saida.map((m) => m.label)).toEqual(["IPM", "IDM", "MFCC7"]);
  });
});

describe("contador e rótulos", () => {
  it("conta apenas as que saíram da faixa", () => {
    const metricas = withBounds(
      [["MFCC7", "6,7"], ["MFCC9", "0,01"], ["IPM", "24,3"], ["ZCR", "0,18"]],
      [
        marker({ key: "mfcc7", direction: "acima" }),
        marker({ key: "mfcc9", label: "MFCC9", direction: "abaixo" }),
        marker({ key: "ipm", label: "IPM", direction: "dentro" }),
      ],
    );
    expect(countOutOfBounds(metricas)).toBe(2);
  });

  it("todo status tem rótulo e classe", () => {
    for (const status of ["acima", "abaixo", "dentro", "sem-limite"] as const) {
      expect(statusLabel(status).length).toBeGreaterThan(10);
      expect(STATUS_CLASSES[status].box.length).toBeGreaterThan(5);
    }
  });

  it("o rótulo de ruptura diz o que fazer", () => {
    expect(statusLabel("acima")).toContain("reavaliar");
    expect(statusLabel("abaixo")).toContain("reavaliar");
  });
});
