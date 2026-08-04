import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  matchesPatientSearch,
  normalizeSearchText,
  type PatientDashboardGroup,
} from "./patient-dashboard";

function fakeGroup(patient: PatientDashboardGroup["patient"]): PatientDashboardGroup {
  return { patient } as PatientDashboardGroup;
}

describe("normalizeSearchText", () => {
  it("folds accents and case so accented and plain queries match", () => {
    expect(normalizeSearchText("José da Conceição")).toBe("jose da conceicao");
    expect(normalizeSearchText("  MARIA  ")).toBe("maria");
    expect(normalizeSearchText("jose")).toBe(normalizeSearchText("josé"));
  });

  it("returns an empty string for an empty query", () => {
    expect(normalizeSearchText("")).toBe("");
    expect(normalizeSearchText("   ")).toBe("");
  });
});

describe("matchesPatientSearch", () => {
  const group = fakeGroup({
    name: "Ana Cecília Souza",
    email: "ana.souza@example.com",
    phone: "11988887777",
    document: "123.456.789-00",
  });

  it("matches with an empty query (no filter applied)", () => {
    expect(matchesPatientSearch(group, "")).toBe(true);
    expect(matchesPatientSearch(group, "   ")).toBe(true);
  });

  it("matches the patient name regardless of accents or case", () => {
    expect(matchesPatientSearch(group, "cecilia")).toBe(true);
    expect(matchesPatientSearch(group, "CECÍLIA")).toBe(true);
  });

  it("matches every typed word even when they are not contiguous in the name", () => {
    // "Ana Souza" digitado por quem não lembra o nome do meio ainda precisa
    // encontrar "Ana Cecília Souza".
    expect(matchesPatientSearch(group, "ana souza")).toBe(true);
    expect(matchesPatientSearch(group, "souza ana")).toBe(true);
    expect(matchesPatientSearch(group, "ana roberto")).toBe(false);
  });

  it("matches email, phone, and document as fallback fields", () => {
    expect(matchesPatientSearch(group, "ana.souza@example.com")).toBe(true);
    expect(matchesPatientSearch(group, "988887777")).toBe(true);
    expect(matchesPatientSearch(group, "123.456.789-00")).toBe(true);
  });

  it("does not match an unrelated query", () => {
    expect(matchesPatientSearch(group, "Roberto")).toBe(false);
  });

  it("does not crash on a patient with missing fields", () => {
    const bare = fakeGroup({});
    expect(matchesPatientSearch(bare, "anything")).toBe(false);
    expect(matchesPatientSearch(bare, "")).toBe(true);
  });
});

/**
 * A fronteira entre medir e interpretar, travada no codigo.
 *
 * O painel escrevia, ao lado do nome do paciente, "risco clinico alto" — e
 * classificava a pessoa em Alto/Moderado/Baixo a partir de um escore 0-100
 * rotulado "Triagem". Inferir estado e classificar pessoa e ato privativo de
 * profissional habilitado, e contradizia os limites clinicos que o proprio
 * contrato do FROID ja declarava.
 *
 * Este teste falha se o vocabulario voltar. Ele varre o modulo inteiro, e nao
 * so as funcoes que eu troquei, porque o proximo lapso vai ser em outro lugar.
 */
describe("fronteira entre medida e interpretacao", () => {
  const fonte = readFileSync(new URL("./patient-dashboard.ts", import.meta.url), "utf-8");
  // So o codigo: os comentarios explicam a remocao e citam os termos de
  // proposito.
  const codigo = fonte
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((linha) => !linha.trim().startsWith("//"))
    .join("\n");

  const PROIBIDOS = [
    "risco clínico",
    "risco clinico",
    "sofrimento ativo",
    "embotamento",
    "fluxo saudavel",
    "fluxo saudável",
    "dissocia",
    "somatiza",
    "depressao / mania",
    "adaptativo",
  ];

  it("nao nomeia construto clinico em nenhuma string do modulo", () => {
    const encontrados = PROIBIDOS.filter((termo) =>
      codigo.toLowerCase().includes(termo),
    );
    expect(encontrados).toEqual([]);
  });

  it("nao classifica o paciente em faixa de risco", () => {
    expect(codigo).not.toMatch(/riskLabel|clinicalRisk|riskTypes/);
    // "Alto"/"Moderado"/"Baixo" como rotulo de risco atribuido a pessoa.
    expect(codigo).not.toMatch(/return\s+"(Alto|Moderado|Baixo)"/);
  });

  it("descreve o estado pelo sinal medido, nao por conclusao clinica", () => {
    // As seis categorias continuam existindo — a particao de IPM x IDM nao
    // mudou. O que mudou e que elas dizem o que o sinal fez.
    expect(codigo).toContain("ENERGIA ALTA + DESVIO NEGATIVO");
    expect(codigo).toContain("ENERGIA BAIXA + DESVIO NEUTRO");
  });
});
