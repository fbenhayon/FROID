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
