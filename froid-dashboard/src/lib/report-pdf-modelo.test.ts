/**
 * O gerador tem de emitir as seções dos modelos aprovados, na ordem deles.
 *
 * Este arquivo existe porque a divergência já aconteceu uma vez em silêncio: o
 * gerador foi escrito a partir de docs/modelo-relatorio-descritivo.html e
 * docs/modelo-relatorio-paciente.html, mas metade do documento do profissional
 * — síntese, leitura estatística e índices por corte — nunca chegou a ser
 * implementada, e nada acusava a falta. Um documento clínico incompleto não se
 * denuncia sozinho: ele imprime bonito e sem as seções.
 */

import { describe, expect, it } from "vitest";
import { buildReport } from "./report-pdf";
import type { SessionReportRecord } from "./session-report";

/** Seções dos modelos aprovados, na ordem em que aparecem neles. */
const SECOES_PROFISSIONAL = [
  "Síntese da sessão",
  "Leitura estatística",
  "Índices por corte",
  "Cortes semânticos",
  "Sinais observados",
  "Relatório descritivo",
];

const SECOES_PACIENTE = [
  "Como ler este documento",
  // Entrou em 04/09/2026: as duas leituras que não dependem de medir voz nem
  // rosto — onde o tempo foi, e onde o ritmo mudou. Vem antes de tudo porque é
  // o que sobra de pé quando a apuração acústica falha, e foi assim numa sessão
  // real cujo relatório saiu com vinte e uma linhas em 0,00.
  "O que mais pesou nesta conversa",
  "Percurso da sessão",
  "Sinais registrados",
  "Anotações do seu profissional",
  "O que este documento não é",
];

function titulos(html: string): string[] {
  return Array.from(html.matchAll(/<h2>([^<]+)<\/h2>/g)).map((m) => m[1].trim());
}

const SESSAO = {
  sessionId: "froid-teste",
  createdAt: "2026-08-16T14:00:00.000Z",
  durationSeconds: 2302,
  patient: { name: "Paciente de Teste" },
  professional: { name: "Profissional", email: "prof@exemplo.com" },
  baseline: { ipmAvg: 24.03, idmAvg: 0.01, dominantZone: 6, wordsPerMinute: 5 },
  sessionAverage: { ipmAvg: 24.17, idmAvg: 0.01, dominantZone: 6, emotionalTone: "neutro" },
  conversationSummaries: [
    {
      startMinute: 0, endMinute: 10, startSecond: 0, endSecond: 600,
      theme: "exploração de novas possibilidades", summary: "Trecho um.",
      ipmAvg: 24.2, idmAvg: 0.01, dominantZone: 6, emotionalTone: "neutro",
      wordsPerMinute: 11.5, dissonanceCount: 0,
    },
    {
      startMinute: 10, endMinute: 20, startSecond: 600, endSecond: 1200,
      theme: "abertura a mudanças", summary: "Trecho dois.",
      ipmAvg: 24.1, idmAvg: 0.01, dominantZone: 6, emotionalTone: "alegre",
      wordsPerMinute: 10.9, dissonanceCount: 0,
    },
  ],
  metricsAnalysis: {
    schema: "v1",
    metrics: [
      { key: "ipm", label: "IPM", unit: "", category: "indice" },
      { key: "wpm", label: "Palavras/min", unit: "", category: "fala" },
    ],
    dashboard: {
      populated_windows: 2, mean_coverage: 1, mean_confidence: 0.9,
      last_dissonance: 0, max_dissonance: 0, data_status: "ok",
      critical_alerts: 0, alerts_count: 0,
    },
    summary: {
      ipm: {
        baseline: 24.03, baseline_std: 0.1, session_mean: 24.17, last: 24.15,
        min: 24.1, max: 24.2, delta_mean: 0.005, delta_last: 0.005, z_last: 0.2, alerts: [],
      },
      wpm: {
        baseline: 5, baseline_std: 1, session_mean: 9.87, last: 7.2,
        min: 7.2, max: 11.5, delta_mean: 0.44, delta_last: 0.44, z_last: 1.1, alerts: ["desvio"],
      },
    },
    evolution: [],
    report_rendered: "",
  },
  dissonances: [],
} as unknown as SessionReportRecord;

describe("documento do profissional", () => {
  const html = buildReport("professional", SESSAO, {}, "Texto redigido pelo profissional.");

  it("emite as seis seções do modelo, na ordem", () => {
    expect(titulos(html)).toEqual(SECOES_PROFISSIONAL);
  });

  it("numera as seções de 01 a 06", () => {
    const nums = Array.from(html.matchAll(/<span class="num">(\d{2})<\/span>/g)).map((m) => m[1]);
    expect(nums).toEqual(["01", "02", "03", "04", "05", "06"]);
  });

  it("traz a nota da linha de base, que impede a leitura como valor absoluto", () => {
    expect(html).toContain("Linha de base:");
    expect(html).toContain("nunca contra média populacional");
  });

  it("monta a tabela estatística com uma linha por métrica", () => {
    expect(html).toContain("Palavras/min");
    expect(html).toContain("Baseline");
    expect(html).toContain("Último corte");
  });

  it("marca alerta quando há, e diz 'sem alerta' quando não há", () => {
    expect(html).toContain("Sem alerta");
    expect(html).toContain("desvio");
  });

  it("monta a tabela de índices com uma linha por corte", () => {
    expect(html).toContain("Pal./min");
    expect(html).toContain("00:00 – 10:00");
    expect(html).toContain("10:00 – 20:00");
  });

  it("leva o texto redigido para a seção 06", () => {
    expect(html).toContain("Texto redigido pelo profissional.");
  });
});

describe("documento do paciente", () => {
  // O modelo aprovado corresponde a UMA seleção: percurso e sinais, mais as três
  // seções que não são opcionais. O documento passou a ser dirigido pelo
  // checklist do profissional — cada item marcado acrescenta a sua seção —,
  // então reproduzir o modelo é reproduzir essa seleção, e é isso que se afirma
  // aqui. Sem amarrar a seleção, o teste diria que o documento "tem cinco
  // seções", o que deixou de ser verdade por decisão de produto e não por
  // defeito.
  // O modelo tem "Anotações do seu profissional", que passou a ser item do
  // catálogo, e "Como ler este documento", que entra porque o percurso leva
  // ritmo e tom em cada trecho.
  const SELECAO_DO_MODELO = ["conversationSummaries", "dissonances", "professionalNotes"];
  const html = buildReport(
    "patient", SESSAO, {}, "Texto redigido pelo profissional.", undefined, SELECAO_DO_MODELO,
  );

  it("com a seleção do modelo, emite as seções dele, na ordem", () => {
    expect(titulos(html)).toEqual(SECOES_PACIENTE);
  });

  it("leva a palavra do profissional ao paciente", () => {
    expect(html).toContain("Texto redigido pelo profissional.");
  });

  it("sem texto redigido, diz que não houve — não deixa a caixa vazia", () => {
    const semTexto = buildReport("patient", SESSAO, {}, "");
    expect(semTexto).toContain("não");
    expect(semTexto).toContain("registrou anotações");
  });

  it("não vaza a leitura estatística nem os índices por corte", () => {
    // Tabelas técnicas são do documento do profissional. O paciente recebe os
    // sinais descritos como medida, não a planilha.
    expect(html).not.toContain("Leitura estatística");
    expect(html).not.toContain("Índices por corte");
  });
});
