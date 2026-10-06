import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { FacialAnalysisPanel } from "../components/FacialAnalysisPanel";
import { RiskChart } from "../components/indicators/RiskChart";
import { currentFacialAnalysis, mergeFacialEvents, type FacialAnalysis, type FacialEvent } from "./facial-analysis";
import { buildPatientReport, buildProfessionalReport } from "./report-pdf";
import type { SessionReportRecord } from "./session-report";

const event = {
  id: "frame:event", schema_version: "facial_families_v1", family: "sorriso",
  title: "Título canônico", report: "TEXTO EXCLUSIVO PROFISSIONAL",
  patient_title: "Movimento facial observado", patient_description: "TEXTO CANÔNICO PARA PACIENTE",
  confirmed: true, source: "real_facs", variant: "sorriso_com_AU6",
  active_aus: ["AU12", "AU6"], side: "bilateral",
  started_at_ms: 100, last_observed_at_ms: 200, ended_at_ms: null,
  observations: 2, ambiguous: false, strength: 0.6, peak_strength: 0.6,
  action_units: { AU12: 0.6, AU6: 0.6, AU23: null }, lateral: {}, clinical_confidence: null,
} as FacialEvent;

describe("acervo facial canônico", () => {
  it("atualiza por ID, não duplica, conserva o início e a recepção", () => {
    const first = mergeFacialEvents([], [{ ...event, recorded_elapsed_seconds: 10 }]);
    const updated = mergeFacialEvents(first, [{ ...event, last_observed_at_ms: 300, ended_at_ms: 300,
      observations: 3, recorded_elapsed_seconds: 20 }]);
    expect(updated).toHaveLength(1);
    expect(updated[0].started_at_ms).toBe(100);
    expect(updated[0].ended_at_ms).toBe(300);
    expect(updated[0].recorded_elapsed_seconds).toBe(10);
  });
  it("não grava candidato ou origem não medida", () => {
    expect(mergeFacialEvents([], [{ ...event, confirmed: false }])).toEqual([]);
    expect(mergeFacialEvents([], [{ ...event, source: "mock" } as unknown as FacialEvent])).toEqual([]);
  });
  it("não corta o acervo nas últimas 18 ocorrências", () => {
    const events = Array.from({ length: 30 }, (_, i) => ({ ...event, id: String(i) }));
    expect(mergeFacialEvents([], events)).toHaveLength(30);
  });
  it("não regride um evento ao receber versão anterior", () => {
    const newer = { ...event, last_observed_at_ms: 300, observations: 3 };
    expect(mergeFacialEvents([newer], [event])[0]).toEqual(newer);
  });
});

const analysis = {
  schema_version: "facial_families_v1", status: "measured", reason: null,
  families: [{ id: "sorriso", title: "Sorriso", description: "Descrição do servidor",
    status: "observed", confirmed: true, variants: [{ id: "sorriso_com_AU6", aus: ["AU12", "AU6"], side: "bilateral" }] }],
  action_units: { AU12: 0, AU23: null }, lateral: {}, raw_blendshapes: {}, legacy_estimates: {},
  ambiguous: true, limitations: ["Limite canônico"], dissonance: { status: "unavailable", reason: "Dissonância não apurada." },
} as FacialAnalysis;

describe("apresentação sem reclassificação", () => {
  it("mostra zero medido, ausência, ambiguidade e origem canônica", () => {
    const html = renderToStaticMarkup(<FacialAnalysisPanel analysis={analysis} events={[event]} />);
    expect(html).toContain("AU12: 0.0000");
    expect(html).toContain("AU23: não apurada");
    expect(html).toContain("interpretação ambígua");
    expect(html).toContain("Título canônico");
    expect(html).toContain("TEXTO EXCLUSIVO PROFISSIONAL");
  });
  it("não mostra medida vencida como atual", () => {
    const html = renderToStaticMarkup(<FacialAnalysisPanel analysis={{ ...analysis, expires_at_ms: 1 }} events={[]} />);
    expect(html).toContain("Leitura facial vencida");
    expect(html).not.toContain("AU12: 0.0000");
    expect(html).not.toContain("Padrão repetido em quadros distintos");
  });
  it("declara ausência sem servidor", () => {
    expect(renderToStaticMarkup(<FacialAnalysisPanel events={[]} />)).toContain("Sem capacidade de apuração");
  });
  it("contexto atual remove medidas vencidas sem apagar o arquivo original", () => {
    const archived = { ...analysis, expires_at_ms: 10 };
    expect(currentFacialAnalysis(archived, 5)).toBe(archived);
    const current = currentFacialAnalysis(archived, 11)!;
    expect(current.status).toBe("unavailable");
    expect(current.action_units).toBeNull();
    expect(current.families[0].variants).toEqual([]);
    expect(current.families[0].confirmed).toBe(false);
    expect(archived.action_units!.AU12).toBe(0);
  });
  it("relatório identifica leitura histórica sem exigir quadro novo", () => {
    const html = renderToStaticMarkup(<FacialAnalysisPanel historical analysis={{ ...analysis, expires_at_ms: 1 }} events={[]} />);
    expect(html).toContain("Leitura arquivada");
    expect(html).toContain("não representa uma medida atual");
    expect(html).toContain("AU12: 0.0000");
    expect(html).not.toContain("aguardando um quadro novo");
  });
  it("o adaptador legado só transporta título, não decide por AUs", () => {
    const source = readFileSync(new URL("../pages/LiveSession.tsx", import.meta.url), "utf8");
    const adapter = source.slice(source.indexOf("function classifyDissonance("), source.indexOf("function reducer("));
    expect(adapter).toContain("return { title: event.title }");
    expect(adapter).not.toMatch(/hasAu|AU6|AU12|Sorriso falso/);
    expect(source).not.toContain("function dissonanceTechnicalFactors(");
    expect(source).toContain("facialEvents: facialEventLog");
    expect(source).toContain("FacialAnalysisPanel");
  });
  it("face atravessa sem áudio, sem retirar a guarda da trilha vocal", () => {
    const source = readFileSync(new URL("../pages/LiveSession.tsx", import.meta.url), "utf8");
    const start = source.indexOf("const data: FroidPayload = JSON.parse(event.data)");
    const end = source.indexOf("dispatch({ type: \"PAYLOAD\", data })", start);
    const handler = source.slice(start, end);
    expect(handler.indexOf("setFacialPacket(")).toBeLessThan(handler.indexOf("if (!shouldUseForMetrics)"));
    expect(handler).toContain("if (data.facial_only) return");
    expect(handler).toContain("patientTrackUsable()");
    expect(source.match(/<FacialAnalysisPanel/g)).toHaveLength(2);
  });
  it("relatório não converte dissonância não apurada em ausência de conflito", () => {
    const source = readFileSync(new URL("../pages/SessionReport.tsx", import.meta.url), "utf8");
    const summary = source.slice(source.indexOf("function derivedSessionSummary("), source.indexOf("function metricRows("));
    expect(summary).toContain('typeof report.sessionAverage.dissonanceCount !== "number"');
    expect(summary).toContain("dissonância facial-vocal: sem capacidade de apuração");
    expect(source).toContain("Isso não comprova ausência de emoção ou de dissonância");
  });
  it("estado descritivo de energia reduzida não fabrica alerta de conflito", () => {
    const render = (status: string) => renderToStaticMarkup(<RiskChart zones={[]} ipmScore={50} coherenceStatus={status} />);
    const reduced = render("ENERGIA_VOCAL_REDUZIDA");
    expect(reduced).toBe(render("COERENTE"));
    expect(reduced).not.toContain("contenção facial");
    expect(reduced).not.toContain("AU15/AU20");
  });
});

const report = {
  sessionId: "facial-test", createdAt: "2026-10-06T12:00:00Z", durationSeconds: 60,
  patient: { name: "Teste" }, professional: { name: "Profissional" },
  baseline: {}, sessionAverage: {}, tenMinuteCuts: [], conversationSummaries: [],
  clinicalNotes: [], dissonances: [], facialEvents: [event], transcript: "",
} as unknown as SessionReportRecord;

describe("relatórios usam o mesmo evento sem vazar texto profissional", () => {
  it("profissional recebe título e relatório canônicos", () => {
    const html = buildProfessionalReport(report);
    expect(html).toContain("Título canônico");
    expect(html).toContain("TEXTO EXCLUSIVO PROFISSIONAL");
    expect(html).toContain("sorriso_com_AU6");
  });
  it("paciente recebe só a tradução explícita", () => {
    const html = buildPatientReport(report, undefined, 0, "", ["dissonances"]);
    expect(html).toContain("TEXTO CANÔNICO PARA PACIENTE");
    expect(html).not.toContain("TEXTO EXCLUSIVO PROFISSIONAL");
    expect(html).not.toContain("sorriso_com_AU6");
    expect(html).not.toContain("Título canônico");
  });
  it("desmarcar sinais não entrega eventos faciais", () => {
    expect(buildPatientReport(report, undefined, 0, "", [])).not.toContain("TEXTO CANÔNICO PARA PACIENTE");
  });
  it("ausência de tradução nunca usa o relatório técnico", () => {
    const noTranslation = { ...report, facialEvents: [{ ...event, patient_description: "" }] };
    const html = buildPatientReport(noTranslation, undefined, 0, "", ["dissonances"]);
    expect(html).not.toContain("TEXTO EXCLUSIVO PROFISSIONAL");
    expect(html).not.toContain("Movimento facial observado");
  });
});
