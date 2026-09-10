import { describe, expect, it } from "vitest";
import { buildNr1DossierPrintable, type Nr1DossierPayload } from "./nr1-dossier-print";

const PAYLOAD: Nr1DossierPayload = {
  document: { title: "Dossiê NR-1", scope: "Resultados organizacionais agregados.", schema_version: "1.1" },
  organization: { organization_name: "Organização Teste" },
  normative_basis: [{ reference: "NR-1", purpose: "GRO/PGR", url: "https://example.test/nr1" }],
  response_protocol: ["Registrar a solicitação.", "Apresentar o inventário."],
  privacy: { individual_answers: "Não incluídas." },
  completeness: {
    status: "complete",
    gaps: [],
    counts: { active_units: 3, closed_campaigns: 2 },
  },
  records: {
    campaigns: [{ id: "c1", title: "Linha de base", status: "closed", substantive_responses: 120, target_headcount: 150 }],
    inventory: [],
    action_plan: [],
    effectiveness: [],
  },
};

describe("PDF institucional do dossiê NR-1", () => {
  const hash = "a".repeat(64);
  const html = buildNr1DossierPrintable(PAYLOAD, {
    version: 2,
    content_sha256: hash,
    previous_sha256: "b".repeat(64),
    sealed_at: "2026-09-10T12:00:00Z",
    integrity_verified: true,
  });

  it("usa o mesmo papel timbrado, paginação e rodapé do relatório da sessão", () => {
    expect(html).toContain(".cabecalho{");
    expect(html).toContain("relatorio-logo.jpeg");
    expect(html).toContain("Página 00 de 00");
    expect(html).toContain("FROID NR-1 / ISO 45003");
  });

  it("leva a identificação e a cadeia criptográfica para o documento", () => {
    expect(html).toContain("Organização Teste");
    expect(html).toContain(hash);
    expect(html).toContain("Encadeado ao SHA-256 anterior");
    expect(html).toContain("append-only");
  });

  it("apresenta o conteúdo em seções legíveis além da exportação JSON", () => {
    expect(html).toContain("Mapa das evidências consolidadas");
    expect(html).toContain("Campanhas e representatividade");
    expect(html).toContain("Roteiro de apresentação à fiscalização");
  });
});
