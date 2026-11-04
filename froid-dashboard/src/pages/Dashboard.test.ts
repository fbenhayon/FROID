import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PAGE = readFileSync(join(__dirname, "Dashboard.tsx"), "utf-8");
const LOCALIZATION = readFileSync(
  join(__dirname, "..", "lib", "localization.ts"),
  "utf-8",
);

describe("dashboard detalhado", () => {
  it("indica o profissional responsavel no card do paciente", () => {
    expect(PAGE).toContain("professionalResponsibleFor(group.latestReport)");
    expect(PAGE).toContain("Profissional responsável");
  });

  it("usa o responsavel gravado no relatorio sem inventar nome", () => {
    expect(PAGE).toContain("report.professional?.name?.trim()");
    expect(PAGE).toContain("report.professional?.email?.trim()");
    expect(PAGE).toContain("report.professionalEmail?.trim()");
    expect(PAGE).toContain('|| tr("Não informado")');
  });

  it("mantem o rotulo traduzivel", () => {
    expect(LOCALIZATION).toContain('"Profissional responsável": "Responsible professional"');
    expect(LOCALIZATION).toContain('"Profissional responsável": "Professionnel responsable"');
    expect(LOCALIZATION).toContain('"Profissional responsável": "Profesional responsable"');
  });
});
