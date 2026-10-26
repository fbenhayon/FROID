// Os cortes e a transcrição chegam ao FROID Explica em forma que cabe.
//
// 15/10/2026, sessão froid-mv85lqul447x. A página de relatório mandava os oito
// cortes inteiros (doze zonas cada) num JSON de 105 mil caracteres, e o
// servidor guardava cinco mil: os cortes nunca chegaram. A transcrição ia
// cortada aos últimos 8.000 caracteres, sem instante por linha — e o modelo
// mandava "reouvir o trecho" num produto que não grava áudio.
//
// Aqui: um corte vira uma linha nos 33 rótulos da tela; o resumo casa pelo
// corte com que mais se sobrepõe; ausência é "--" e nunca zero; e cada linha
// da transcrição ganha [mm:ss] quando o relatório registrou o instante.

import { describe, expect, it } from "vitest";
import {
  recorteFinalDaTranscricao,
  contextoDosCortes,
  corteParaOExplica,
  metricasParaOExplica,
  transcricaoParaOExplica,
} from "./painel-para-o-explica";
import type { MetricSnapshot } from "./session-report";

function snapshot(partes: Partial<MetricSnapshot>): MetricSnapshot {
  return {
    label: "0-10min (10min)",
    startSecond: 0,
    endSecond: 600,
    sampleCount: 594,
    ipmAvg: null,
    idmAvg: null,
    dominantZone: null,
    dominantTheme: "",
    coherenceStatus: "",
    emotionalTone: "",
    wordsPerMinute: null,
    theme: "",
    dissonanceCount: null,
    mfcc7: null,
    mfcc9: null,
    f0Mean: null,
    zcr: null,
    jitter: null,
    shimmer: null,
    subharmonic5_12: null,
    subharmonic12_20: null,
    zones: [],
    ...partes,
  };
}

describe("corteParaOExplica", () => {
  it("vira uma linha com os 33 rótulos da tela, ausência como -- e nunca zero", () => {
    const corte = corteParaOExplica(
      snapshot({ ipmAvg: 49.91, wordsPerMinute: 83.4, f0Mean: 96.03 }),
    );
    expect(Object.keys(corte.metricas)).toHaveLength(33);
    expect(Object.keys(corte.metricas)).toEqual(
      metricasParaOExplica(snapshot({})).map(([rotulo]) => rotulo),
    );
    expect(corte.metricas.IPM).toBe("49.9");
    expect(corte.metricas["P/MIN"]).toBe("83.4");
    expect(corte.metricas["F0 MED."]).toBe("96.03");
    expect(corte.metricas.IDM).toBe("--");
    expect(corte.corte).toBe("0-10min (10min)");
    expect(corte.duracao_s).toBe(600);
    expect(corte.amostras).toBe(594);
    expect(corte.tema).toBeNull();
    expect(corte.resumo).toBeNull();
  });

  it("um corte de quatro segundos sai com a sua duração real, não com o rótulo", () => {
    const corte = corteParaOExplica(
      snapshot({ label: "10-11min (10min)", startSecond: 600, endSecond: 604, sampleCount: 4 }),
    );
    expect(corte.duracao_s).toBe(4);
    expect(corte.amostras).toBe(4);
  });
});

describe("contextoDosCortes", () => {
  const base = snapshot({ label: "Linha de base", startSecond: 0, endSecond: 60, sampleCount: 60, ipmAvg: 50 });
  const cortes = [
    snapshot({ label: "0-10min", startSecond: 0, endSecond: 600 }),
    snapshot({ label: "10-20min", startSecond: 600, endSecond: 1200 }),
  ];
  const resumos = [
    {
      id: "r1",
      startSecond: 650,
      endSecond: 1100,
      startMinute: 10,
      endMinute: 18,
      theme: "medo de dirigir",
      summary: "O paciente descreve o medo na estrada.",
    },
  ];

  it("casa cada resumo com o corte de maior sobreposição e deixa os outros sem tema", () => {
    const contexto = contextoDosCortes(base, cortes, resumos, "cortes desta sessao");
    const lista = contexto.panel_cuts as Array<{ tema: string | null; resumo: string | null }>;
    expect(lista).toHaveLength(2);
    expect(lista[0].tema).toBeNull();
    expect(lista[1].tema).toBe("medo de dirigir");
    expect(lista[1].resumo).toBe("O paciente descreve o medo na estrada.");
    expect(contexto.panel_cuts_window).toBe("cortes desta sessao");
  });

  it("manda a linha de base nos mesmos rótulos", () => {
    const contexto = contextoDosCortes(base, cortes, resumos, "cortes desta sessao");
    const linhaDeBase = contexto.panel_baseline as { janela: string; amostras: number; metricas: Record<string, string> };
    expect(linhaDeBase.janela).toBe("0-60 s");
    expect(linhaDeBase.amostras).toBe(60);
    expect(linhaDeBase.metricas.IPM).toBe("50.0");
  });

  it("sem cortes não cria chave nenhuma: ausência não vira lista vazia", () => {
    expect(contextoDosCortes(null, [], [], "x")).toEqual({});
    expect(contextoDosCortes(undefined, null, null, "x")).toEqual({});
  });
});

describe("recorteFinalDaTranscricao", () => {
  it("corta em linhas inteiras e diz quantas ficaram de fora", () => {
    const linhas = ["[00:01] DR: um", "[00:05] PC: dois dois", "[00:09] DR: tres", "[00:12] PC: quatro"];
    const texto = linhas.join("\n");
    const r = recorteFinalDaTranscricao(texto, 36); // 16 + 1 + 18 = 35 cabe; a linha anterior nao
    expect(r.texto).toBe("[00:09] DR: tres\n[00:12] PC: quatro");
    expect(r.linhasOmitidas).toBe(2);
    // Toda linha mantida conserva o carimbo: nenhuma começa no meio.
    for (const linha of r.texto.split("\n")) expect(linha).toMatch(/^\[\d\d:\d\d\] /);
  });

  it("dentro do limite nada muda; uma linha maior que o limite fica inteira", () => {
    expect(recorteFinalDaTranscricao("[00:01] DR: um", 100)).toEqual({ texto: "[00:01] DR: um", linhasOmitidas: 0 });
    const r = recorteFinalDaTranscricao("[00:01] DR: curta\n[00:02] PC: " + "x".repeat(50), 20);
    expect(r.texto).toBe("[00:02] PC: " + "x".repeat(50));
    expect(r.linhasOmitidas).toBe(1);
  });
});

describe("transcricaoParaOExplica", () => {
  it("abre cada linha com [mm:ss] quando há um instante por linha", () => {
    const saida = transcricaoParaOExplica("PC - oi\nDR - olá", [5, 65]);
    expect(saida.session_transcript).toBe("[00:05] PC - oi\n[01:05] DR - olá");
    expect(saida.transcript_timestamps).toContain("[mm:ss]");
  });

  it("tolera só a quebra de linha final", () => {
    const saida = transcricaoParaOExplica("PC - oi\nDR - olá\n", [5, 65]);
    expect(saida.session_transcript).toBe("[00:05] PC - oi\n[01:05] DR - olá");
  });

  it("sem instantes, ou com contagem diferente, não inventa nada e declara", () => {
    const semLista = transcricaoParaOExplica("PC - oi\nDR - olá", undefined);
    expect(semLista.session_transcript).toBe("PC - oi\nDR - olá");
    expect(semLista.transcript_timestamps).toContain("nao registrados");

    const desalinhado = transcricaoParaOExplica("PC - oi\nDR - olá", [5]);
    expect(desalinhado.session_transcript).toBe("PC - oi\nDR - olá");
    expect(desalinhado.transcript_timestamps).toContain("nao registrados");
  });
});
