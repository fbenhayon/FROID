import { describe, expect, it } from "vitest";
import {
  RESSALVA_HISTORICO,
  falaDaSessao,
  formatarHistorico,
  referenciaDoHistorico,
} from "./cadencia-historico";
import type { SessionReportRecord } from "./session-report";

/** Sessão com N blocos do paciente de `palavras` palavras cada (7 s por bloco). */
function sessao(
  id: string,
  quando: string,
  paciente: { id?: string; name?: string },
  blocos: number,
  palavras: number,
  comInstantes = true,
): SessionReportRecord {
  const linhas = Array.from({ length: blocos }, (_, i) => `PC - ${"a ".repeat(palavras).trim()}`);
  linhas.push("DR. - " + "x ".repeat(80).trim());
  return {
    sessionId: id,
    createdAt: quando,
    patient: paciente,
    transcript: linhas.join("\n"),
    transcriptLineSeconds: comInstantes ? linhas.map((_, i) => i * 10) : undefined,
  } as unknown as SessionReportRecord;
}

const ANA = { id: "p-ana", name: "Ana" };

describe("palavras por minuto na fala do paciente, por sessão", () => {
  it("conta só a fala do paciente, pelo tempo dos blocos dele", () => {
    // 2 blocos de 7 s com 14 palavras cada = 28 palavras em 14 s = 120/min.
    expect(falaDaSessao(sessao("s1", "2026-11-01T10:00:00Z", ANA, 2, 14))).toBe(120);
  });

  it("sem o instante de cada linha, declara ausência", () => {
    expect(falaDaSessao(sessao("s1", "2026-11-01T10:00:00Z", ANA, 2, 14, false))).toBeNull();
  });
});

describe("referência pelo histórico do paciente", () => {
  const relatorios = [
    sessao("s1", "2026-09-01T10:00:00Z", ANA, 2, 14), // 120
    sessao("s2", "2026-10-01T10:00:00Z", ANA, 2, 7), // 60
    sessao("s3", "2026-10-15T10:00:00Z", ANA, 2, 21), // 180
    sessao("outro", "2026-10-02T10:00:00Z", { id: "p-beto", name: "Beto" }, 2, 35),
    sessao("s4", "2026-11-10T10:00:00Z", ANA, 2, 14, false), // sem instantes: não entra
  ];

  it("é a mediana das sessões anteriores do MESMO paciente, com o n e o período", () => {
    const h = referenciaDoHistorico(relatorios, ANA, { antesDe: "2026-11-11T10:00:00Z" });
    expect(h).toEqual({
      mediana: 120,
      sessoes: 3,
      desde: "2026-09-01T10:00:00Z",
      ate: "2026-10-15T10:00:00Z",
    });
  });

  it("se refina a cada sessão: só entram as anteriores à data pedida", () => {
    expect(referenciaDoHistorico(relatorios, ANA, { antesDe: "2026-10-10T00:00:00Z" }).sessoes).toBe(2);
    expect(referenciaDoHistorico(relatorios, ANA, { antesDe: "2026-09-02T00:00:00Z" }).mediana).toBe(120);
  });

  it("tira a sessão em curso e não mistura outro paciente", () => {
    const h = referenciaDoHistorico(relatorios, ANA, { excluirSessao: "s3" });
    expect(h.sessoes).toBe(2);
    expect(h.mediana).toBe(90);
  });

  it("sem paciente ou sem sessões, declara que ainda não há histórico", () => {
    const vazio = referenciaDoHistorico(relatorios, null);
    expect(vazio).toEqual({ mediana: null, sessoes: 0, desde: null, ate: null });
    expect(formatarHistorico(100, vazio)).toContain("Sem histórico ainda");
  });

  it("formata com variação, faixa, n de sessões e período", () => {
    const h = referenciaDoHistorico(relatorios, ANA, { antesDe: "2026-11-11T10:00:00Z" });
    const texto = formatarHistorico(96, h);
    expect(texto).toMatch(/^−20% vs\. histórico · lentificada \(referência: 120 p\/min, mediana de 3 sessões anteriores \(/);
  });

  it("com uma sessão só, diz que é uma sessão", () => {
    const h = referenciaDoHistorico([relatorios[0]], ANA);
    expect(formatarHistorico(120, h)).toContain("mediana de 1 sessão anterior");
  });

  it("a ressalva diz que a indicação se refina a cada sessão", () => {
    expect(RESSALVA_HISTORICO).toContain("se refina a cada sessão realizada");
    expect(RESSALVA_HISTORICO).toContain("escolha do produto");
  });
});
