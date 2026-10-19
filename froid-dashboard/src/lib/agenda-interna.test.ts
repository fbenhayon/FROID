import { describe, expect, it } from "vitest";
import {
  diaIso,
  gradeDaSemana,
  horaNoFuso,
  horaParaMinutos,
  instanteDe,
  minutosParaHora,
  motivoDaAgendaIndisponivel,
  papelNaAgenda,
  semanaDe,
} from "./agenda-interna";

const caps = (rbac: number, papeis: string[]) => ({
  estado: "ok" as const,
  dados: {
    rbac_version: rbac,
    v2_roles: papeis,
    capabilities: { clinical_analysis: true, purchase_credits: false, manage_roles: false, read_audit: false, supervise: false },
  },
});

describe("semana e horas", () => {
  it("a semana comeca na segunda e tem sete dias", () => {
    const dias = semanaDe(new Date(2027, 2, 10)); // quarta, 10/03/2027
    expect(dias.map(diaIso)).toEqual([
      "2027-03-08", "2027-03-09", "2027-03-10", "2027-03-11", "2027-03-12", "2027-03-13", "2027-03-14",
    ]);
  });

  it("minutos e horas vao e voltam", () => {
    expect(minutosParaHora(8 * 60)).toBe("08:00");
    expect(horaParaMinutos("18:30")).toBe(18 * 60 + 30);
    expect(horaParaMinutos("25:00")).toBeNull();
    expect(horaParaMinutos("x")).toBeNull();
  });

  it("14h em Sao Paulo e 17h UTC, e volta como 14:00 no fuso", () => {
    const iso = instanteDe("2027-03-10", "14:00", "America/Sao_Paulo");
    expect(iso).toBe("2027-03-10T17:00:00.000Z");
    expect(horaNoFuso(iso as string, "America/Sao_Paulo")).toBe("14:00");
  });

  it("dia ou hora invalidos nao viram instante", () => {
    expect(instanteDe("2027-13-01", "14:00", "America/Sao_Paulo")).toBeNull();
    expect(instanteDe("2027-03-10", "", "America/Sao_Paulo")).toBeNull();
  });
});

describe("gradeDaSemana", () => {
  it("agrupa por clinico e por dia, em ordem de inicio, so dentro da semana", () => {
    const dias = semanaDe(new Date(2027, 2, 10));
    const item = (id: string, clinico: string, start: string) => ({
      appointment_id: id, patient_id: "p", patient_name: null, clinician_membership_id: clinico,
      start_at: start, end_at: start, timezone: "America/Sao_Paulo", appointment_status: "SCHEDULED",
      unit_id: null, version: 1,
    });
    const grade = gradeDaSemana(
      [
        item("b", "c1", "2027-03-10T19:00:00.000Z"),
        item("a", "c1", "2027-03-10T17:00:00.000Z"),
        item("fora", "c1", "2027-04-01T17:00:00.000Z"),
        item("c", "c2", "2027-03-12T12:00:00.000Z"),
      ],
      dias,
      "America/Sao_Paulo",
    );
    expect(grade.get("c1")?.get("2027-03-10")?.map((x) => x.appointment_id)).toEqual(["a", "b"]);
    expect(grade.get("c2")?.get("2027-03-12")?.map((x) => x.appointment_id)).toEqual(["c"]);
    expect([...(grade.get("c1")?.keys() || [])]).toEqual(["2027-03-10"]);
  });
});

describe("papelNaAgenda", () => {
  it("secretaria e administrador operam tudo e veem nomes", () => {
    expect(papelNaAgenda(caps(2, ["SECRETARY"]))).toEqual({ geral: true, clinico: false, veNomes: true });
    expect(papelNaAgenda(caps(2, ["ORG_ADMIN", "CLINICIAN"]))).toEqual({ geral: true, clinico: true, veNomes: true });
  });

  it("supervisor opera tudo sem nomes; clinico so a propria, com nomes", () => {
    expect(papelNaAgenda(caps(2, ["CLINICAL_SUPERVISOR"]))).toEqual({ geral: true, clinico: false, veNomes: false });
    expect(papelNaAgenda(caps(2, ["CLINICIAN"]))).toEqual({ geral: false, clinico: true, veNomes: true });
  });

  it("sem rbac v2 nao ha papel, e a frase diz quem ativa", () => {
    expect(papelNaAgenda(caps(1, ["CLINICIAN"]))).toBeNull();
    expect(motivoDaAgendaIndisponivel(caps(1, []))).toContain("Gestão da clínica");
    expect(motivoDaAgendaIndisponivel(caps(2, ["FINANCE"]))).toContain("não inclui agenda");
    expect(motivoDaAgendaIndisponivel(caps(2, ["CLINICIAN"]))).toBe("");
    expect(motivoDaAgendaIndisponivel({ estado: "indisponivel", motivo: "HTTP_404" })).toContain("não está ligada");
    expect(motivoDaAgendaIndisponivel({ estado: "negado", motivo: "x" })).toContain("Sem permissão");
  });
});
