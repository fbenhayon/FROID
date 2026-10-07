/**
 * O PDF profissional sai na hora — e diz de quem é o texto que ele leva.
 *
 * Até 06/10/2026 o botão "PDF profissional" ficava travado enquanto o campo
 * descritivo fosse idêntico ao texto que o sistema compôs. A trava existia por
 * um motivo que continua valendo: documento assinado com texto de máquina é
 * pior do que documento nenhum, porque quem assina responde pelo que está
 * escrito. O dono abriu o acesso imediato ao PDF naquele dia.
 *
 * O que este arquivo guarda é que apenas a TRAVA saiu, e não a garantia. A
 * distinção entre o que o profissional redigiu e o que a máquina compôs passou
 * a ser DECLARADA dentro do documento, acima da assinatura — regra 1.2: onde a
 * afirmação registrada existe, ela é que decide; onde ela falta, declare-se a
 * ausência, nunca se preencha por conveniência.
 *
 * O teste afirma a garantia nos dois lados: no gerador, que imprime a
 * declaração, e na tela, que precisa dizer ao gerador qual é a origem — sem
 * esse argumento o documento sairia sempre afirmando autoria do profissional,
 * que é exatamente o defeito que a trava evitava.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { buildReport } from "./report-pdf";
import type { SessionReportRecord } from "./session-report";

const DECLARACAO = "Procedência deste texto.";

const SESSAO = {
  sessionId: "froid-teste-procedencia",
  createdAt: "2026-10-06T14:00:00.000Z",
  durationSeconds: 1800,
  patient: { name: "Paciente de Teste" },
  professional: { name: "Profissional", email: "prof@exemplo.com" },
  baseline: { ipmAvg: 24.03, idmAvg: 0.01, dominantZone: 6, wordsPerMinute: 5 },
  sessionAverage: {
    ipmAvg: 24.17, idmAvg: 0.01, dominantZone: 6, emotionalTone: "neutro",
  },
  conversationSummaries: [
    {
      startMinute: 0, endMinute: 10, startSecond: 0, endSecond: 600,
      theme: "tema do corte", summary: "Trecho um.",
      ipmAvg: 24.2, idmAvg: 0.01, dominantZone: 6, emotionalTone: "neutro",
      wordsPerMinute: 11.5, dissonanceCount: 0,
    },
  ],
  dissonances: [],
} as unknown as SessionReportRecord;

const TEXTO = "Paciente relatou melhora do sono desde a última sessão.";

describe("documento do profissional: origem do texto descritivo", () => {
  it("texto reescrito pelo profissional sai sem declaração nenhuma", () => {
    const html = buildReport("professional", SESSAO, {}, TEXTO, undefined, undefined, true);
    expect(html).toContain(TEXTO);
    expect(html).not.toContain(DECLARACAO);
  });

  it("o padrão é atribuir ao profissional — chamador antigo não acusa a máquina", () => {
    // Nenhum chamador que não conhece o argumento pode fazer o documento dizer
    // que o texto é de máquina: a acusação é tão grave quanto a omissão.
    const html = buildReport("professional", SESSAO, {}, TEXTO);
    expect(html).not.toContain(DECLARACAO);
  });

  it("texto ainda composto pelo sistema sai declarado, e o documento sai", () => {
    const html = buildReport("professional", SESSAO, {}, TEXTO, undefined, undefined, false);
    expect(html).toContain(DECLARACAO);
    expect(html).toContain("ainda n");
    // O documento continua completo, com o texto e a assinatura: o acesso é
    // imediato, e a declaração é o que o acompanha.
    expect(html).toContain(TEXTO);
    expect(html).toContain("Assinatura do profissional respons");
  });

  it("campo vazio não vira acusação: a seção diz que não foi redigido", () => {
    const html = buildReport("professional", SESSAO, {}, "", undefined, undefined, false);
    expect(html).toContain("Não redigido.");
    expect(html).not.toContain(DECLARACAO);
  });

  it("o documento do paciente não declara procedência: não é ele que se assina", () => {
    const html = buildReport("patient", SESSAO, {}, TEXTO, undefined, undefined, false);
    expect(html).not.toContain(DECLARACAO);
  });
});

describe("tela do relatório da sessão", () => {
  const FONTE = readFileSync(
    join(__dirname, "..", "pages", "SessionReport.tsx"),
    "utf-8",
  );

  it("o botão do PDF profissional não é mais travado pelo campo descritivo", () => {
    expect(FONTE).not.toContain("disabled={!descriptiveEdited}");
  });

  it("a tela informa ao gerador qual é a origem do texto", () => {
    // Sem esta linha o acesso imediato viraria documento silencioso: sairia
    // afirmando autoria do profissional sobre texto que ele não escreveu.
    expect(FONTE).toContain("descriptiveEdited,");
  });

  it("o aviso na tela não promete mais que reescrever libera o documento", () => {
    // Padrão 2.4: rótulo que descreve outra coisa é pior que rótulo nenhum,
    // porque quem lê confia nele.
    expect(FONTE).not.toContain("para liberar o documento do profissional");
    expect(FONTE).toContain("quem assina responde pelo que está escrito");
  });
});
