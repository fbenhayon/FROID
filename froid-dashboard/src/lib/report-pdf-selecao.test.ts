/**
 * A seleção do profissional tem de MUDAR o documento do paciente.
 *
 * Este arquivo existe porque não mudava. O filtro vivia só no servidor, para o
 * que a área do paciente recebe; o botão "PDF paciente" na tela do profissional
 * montava do registro completo. E, pior, seis dos oito itens do catálogo não
 * tinham seção nenhuma no documento — marcar ou desmarcar não podia produzir
 * efeito, porque não havia o que produzir.
 *
 * O que se afirma aqui: cada item liga uma seção, desligá-lo tira a seção, e o
 * que não está no catálogo permanece em qualquer combinação.
 */

import { describe, expect, it } from "vitest";
import { PATIENT_ITEM_KEYS, buildReport } from "./report-pdf";
import type { SessionReportRecord } from "./session-report";

/** Título de cada seção que um item liga. */
const SECAO_DE: Record<string, string> = {
  baseline: "A sua referência deste dia",
  sessionAverage: "A sessão no conjunto",
  sessionSummary: "Resumo da sessão",
  conversationSummaries: "Percurso da sessão",
  tenMinuteCuts: "Medidas trecho a trecho",
  dissonances: "Sinais registrados",
  clinicalNotes: "Observações registradas durante a sessão",
  professionalNotes: "Anotações do seu profissional",
};

/** A ÚNICA seção travada. O produto se define por esta fronteira, e o risco que
 *  ela cobre não é o profissional decidir retirá-la — é retirá-la por descuido. */
const SEMPRE = ["O que este documento não é"];

/** Itens que levam medida. "Como ler este documento" só entra com algum deles:
 *  num documento só de texto ela explicaria números que não estão lá. */
// "metricsAnalysis" saiu do catálogo do paciente em 04/09/2026 — a tabela de
// MFCC e ZCR continua só no documento do profissional.
const COM_MEDIDA = ["baseline", "sessionAverage", "conversationSummaries", "tenMinuteCuts"];

const RELATORIO = {
  sessionId: "sel",
  createdAt: "2026-08-17T14:00:00.000Z",
  durationSeconds: 1800,
  patient: { name: "Maria" },
  professional: { name: "Dra. Ana", email: "a@b.com" },
  baseline: { ipmAvg: 24.03, idmAvg: 0.01, dominantZone: 6, wordsPerMinute: 5 },
  sessionAverage: {
    ipmAvg: 24.17, idmAvg: 0.01, dominantZone: 6,
    emotionalTone: "neutro", wordsPerMinute: 9.4,
  },
  sessionSummary: { text: "Conversa centrada em abertura a mudanças." },
  conversationSummaries: [
    {
      startMinute: 0, endMinute: 10, startSecond: 0, endSecond: 600,
      theme: "abertura", summary: "Primeiro trecho.",
      ipmAvg: 24.2, idmAvg: 0.01, dominantZone: 6,
      emotionalTone: "neutro", wordsPerMinute: 11.5, dissonanceCount: 0,
    },
  ],
  tenMinuteCuts: [
    { label: "00–10 min", ipmAvg: 24.2, wordsPerMinute: 11.5, emotionalTone: "neutro" },
  ],
  dissonances: [
    { elapsedSeconds: 600, zone: 7, title: "AU12 sem AU6", report: "Sorriso social." },
  ],
  metricsAnalysis: {
    schema: "v1",
    metrics: [{ key: "ipm", label: "Energia da fala", unit: "", category: "x" }],
    dashboard: {
      populated_windows: 1, mean_coverage: 1, mean_confidence: 0.9,
      last_dissonance: 0, max_dissonance: 0, data_status: "ok",
      critical_alerts: 0, alerts_count: 0,
    },
    summary: {
      ipm: {
        baseline: 24.03, baseline_std: 0.1, session_mean: 24.17, last: 24.15,
        min: 24.1, max: 24.2, delta_mean: 0, delta_last: 0, z_last: 0, alerts: [],
      },
    },
    evolution: [],
    report_rendered: "",
  },
  clinicalNotes: [{ id: "n1", text: "Observação registrada na sessão.", timestamp: 1 }],
} as unknown as SessionReportRecord;

const IDENT = { clinicName: "Clínica", professionalName: "Dra. Ana", professionalRegistry: "CRP 1", contactEmail: "a@b.com" };

const doc = (itens?: string[]) =>
  buildReport("patient", RELATORIO, IDENT, "Mensagem do profissional.", 0, itens);

function titulos(html: string): string[] {
  return Array.from(html.matchAll(/<h2>([^<]+)<\/h2>/g)).map((m) => m[1].trim());
}

describe("a seleção governa o documento do paciente", () => {
  it("cada item do catálogo tem uma seção — nenhum é decorativo", () => {
    // Era esta a falha de fundo: seis dos oito itens não ligavam nada.
    for (const chave of PATIENT_ITEM_KEYS) {
      expect(SECAO_DE[chave], `item sem seção: ${chave}`).toBeTruthy();
    }
    expect(Object.keys(SECAO_DE).length).toBe(PATIENT_ITEM_KEYS.length);
  });

  it("com todos marcados, todas as seções aparecem", () => {
    const html = doc(PATIENT_ITEM_KEYS.slice());
    for (const chave of PATIENT_ITEM_KEYS) {
      expect(titulos(html).join(" | "), chave).toContain(SECAO_DE[chave]);
    }
  });

  it("desmarcar um item remove a seção dele, e só a dela", () => {
    for (const alvo of PATIENT_ITEM_KEYS) {
      const restantes = PATIENT_ITEM_KEYS.filter((k) => k !== alvo);
      const html = doc(restantes.slice());
      const lista = titulos(html).join(" | ");
      expect(lista, `${alvo} deveria ter saído`).not.toContain(SECAO_DE[alvo]);
      for (const outro of restantes) {
        expect(lista, `${outro} não deveria ter saído junto com ${alvo}`).toContain(SECAO_DE[outro]);
      }
    }
  });

  it("com um único item, o documento tem esse e mais nada do catálogo", () => {
    const lista = titulos(doc(["dissonances"])).join(" | ");
    expect(lista).toContain("Sinais registrados");
    expect(lista).not.toContain("A sessão no conjunto");
    expect(lista).not.toContain("Medidas detalhadas");
    expect(lista).not.toContain("Percurso da sessão");
    // Só texto: nem a chave de leitura dos números entra.
    expect(lista).not.toContain("Como ler este documento");
    // Duas seções: o sinal e a advertência.
    expect(titulos(doc(["dissonances"])).length).toBe(2);
  });

  it("a advertência entra em QUALQUER combinação, inclusive nenhuma", () => {
    for (const itens of [[], ["baseline"], ["professionalNotes"], PATIENT_ITEM_KEYS.slice()]) {
      const lista = titulos(doc(itens as string[])).join(" | ");
      for (const fixa of SEMPRE) expect(lista, `${fixa} com [${itens}]`).toContain(fixa);
    }
  });

  it("\"Como ler\" entra com medida e sai sem ela", () => {
    for (const chave of COM_MEDIDA) {
      expect(titulos(doc([chave])).join(" | "), chave).toContain("Como ler este documento");
    }
    for (const chave of PATIENT_ITEM_KEYS.filter((k) => COM_MEDIDA.indexOf(k) < 0)) {
      expect(titulos(doc([chave])).join(" | "), chave).not.toContain("Como ler este documento");
    }
    expect(titulos(doc([])).join(" | ")).not.toContain("Como ler este documento");
  });

  it("texto livre sai em um bloco por parágrafo, para poder fluir", () => {
    // Como bloco único, a anotação não descia para preencher o espaço livre da
    // folha anterior E era cortada quando passava de uma folha: medido em 154%
    // de ocupação, mais da metade do texto perdida em silêncio.
    const html = buildReport(
      "patient", RELATORIO, IDENT, "Primeiro parágrafo.\n\nSegundo.\n\nTerceiro.", 0,
      ["professionalNotes"],
    );
    expect((html.match(/class="corrido"/g) || []).length).toBe(3);
    // E não sobrou a caixa de altura fixa, que era o que empurrava a seção
    // inteira para a folha seguinte.
    expect(html).not.toContain("min-height:130px");
  });

  it("o paginador não parte por palavra um elemento com estrutura dentro", () => {
    // Escrever textContent num elemento estruturado apaga a marcação: a caixa
    // da advertência saiu como texto corrido, sem título e truncada no meio de
    // uma frase, porque a partição por palavra a tratou como parágrafo.
    const html = doc(PATIENT_ITEM_KEYS.slice());
    expect(html).toContain("if (alvoP.children.length > 0) return null;");
  });

  it("a palavra do profissional virou item, e desmarcá-la tira a seção", () => {
    // Sem texto redigido a seção imprimia uma caixa dizendo que não havia nada,
    // o que é pior do que não imprimir. Mandar só as medidas é decisão clínica.
    expect(titulos(doc(["professionalNotes"])).join(" | ")).toContain("Anotações do seu profissional");
    expect(titulos(doc(["dissonances"])).join(" | ")).not.toContain("Anotações do seu profissional");
  });

  it("numera corridamente, sem buracos, com qualquer seleção", () => {
    // Numeração fixa produziria "01, 03, 05" ao desmarcar, que lê como se
    // faltassem páginas no documento impresso.
    for (const itens of [[], ["dissonances"], ["baseline", "sessionAverage"], PATIENT_ITEM_KEYS.slice()]) {
      const html = doc(itens as string[]);
      const nums = Array.from(html.matchAll(/<span class="num">(\d{2})<\/span>/g)).map((m) => Number(m[1]));
      expect(nums).toEqual(nums.map((_, i) => i + 1));
    }
  });

  it("sem seleção informada, respeita o que o servidor gravou na liberação", () => {
    const comMarca = {
      ...RELATORIO,
      patientReportItems: ["dissonances"],
    } as unknown as SessionReportRecord;
    const lista = titulos(buildReport("patient", comMarca, IDENT, "x", 0)).join(" | ");
    expect(lista).toContain("Sinais registrados");
    expect(lista).not.toContain("Medidas detalhadas");
  });

  it("sem seleção e sem marca no registro, entra tudo", () => {
    // Documento aberto fora do contexto de liberação não deve esconder o que
    // ninguém pediu para esconder.
    const lista = titulos(doc(undefined)).join(" | ");
    for (const chave of PATIENT_ITEM_KEYS) expect(lista, chave).toContain(SECAO_DE[chave]);
  });

  it("o documento do profissional não é afetado pela seleção", () => {
    // Ele sai sempre completo: a seleção descreve o que o PACIENTE recebe.
    const a = buildReport("professional", RELATORIO, IDENT, "texto", 0, ["dissonances"]);
    const b = buildReport("professional", RELATORIO, IDENT, "texto", 0, PATIENT_ITEM_KEYS.slice());
    expect(titulos(a)).toEqual(titulos(b));
  });
});
