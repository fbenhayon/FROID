import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PAGE = readFileSync(join(__dirname, "ClinicManagement.tsx"), "utf-8");

describe("gestao da clinica: profissionais e pacientes", () => {
  it("renderiza a relacao de pacientes com profissional responsavel", () => {
    expect(PAGE).toContain("Profissionais e pacientes");
    expect(PAGE).toContain("Profissional respons");
    expect(PAGE).toContain("patient_roster");
    expect(PAGE).toContain("responsible");
  });

  it("compartilha paciente usando atribuicao read_only existente", () => {
    expect(PAGE).toContain('assignment_type: "read_only"');
    expect(PAGE).toContain("/assignments");
    expect(PAGE).toContain("Compartilhar");
  });

  it("permite remover compartilhamento sem mexer no responsavel primario", () => {
    expect(PAGE).toContain("revokePatientShare");
    expect(PAGE).toContain("shared_with.map");
    expect(PAGE).not.toContain("primary_assignment_exists");
  });
});
