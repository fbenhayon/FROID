import { describe, expect, it } from "vitest";
import type { SessionReportRecord } from "./session-report";
import {
  FALLBACK_SUMMARY,
  buildPatientReport,
  buildProfessionalReport,
  escapeHtml,
  formatClock,
  formatDurationLong,
  summaryOrFallback,
} from "./report-pdf";

/**
 * O gerador dos dois documentos.
 *
 * A trava central: o documento do PACIENTE não pode carregar rótulo nem
 * conduta. Os testes de fronteira já cobrem o modelo em docs/ e os módulos de
 * texto; aqui a verificação é sobre o HTML EFETIVAMENTE GERADO, que é o que sai
 * impresso e assinado.
 */

const RELATORIO: SessionReportRecord = {
  id: "rel-1",
  sessionId: "froid-teste",
  patientName: "Maria <script>alert(1)</script>",
  createdAt: "2026-08-08T22:04:23.000Z",
  durationSeconds: 2302,
  baseline: {} as never,
  sessionAverage: { ipmAvg: 24.3, idmAvg: 0.01 } as never,
  tenMinuteCuts: [],
  clinicalNotes: [],
  conversationSummaries: [
    { id: "c3", startSecond: 1200, endSecond: 1800, startMinute: 20, endMinute: 30,
      theme: "Terceiro", summary: "Resumo indisponível" },
    { id: "c1", startSecond: 0, endSecond: 600, startMinute: 0, endMinute: 10,
      theme: "Primeiro", summary: "Conversa sobre abertura." },
    { id: "c2", startSecond: 600, endSecond: 1200, startMinute: 10, endMinute: 20,
      theme: "Segundo", summary: "Exploração de possibilidades." },
  ],
  dissonances: [
    { id: "d1", timestamp: "", elapsedSeconds: 1016, zone: 7,
      report: "Sorriso falso / falsa calma. Mitigar validando a fala." },
  ],
} as never;

const IDENTIDADE = {
  clinicName: "Clínica Exemplo",
  professionalName: "Dra. Ana",
  professionalRegistry: "CRP 00/00000",
  contactEmail: "contato@exemplo.com",
};

describe("utilitários", () => {
  it("escapa marcação vinda de campo livre", () => {
    // Nome de paciente e texto redigido entram no documento; sem escapar, um
    // trecho colado de outro sistema traria marcação junto.
    expect(escapeHtml("<b>x</b>")).toBe("&lt;b&gt;x&lt;/b&gt;");
  });

  it("formata tempo e duração", () => {
    expect(formatClock(1016)).toBe("16:56");
    expect(formatClock(-5)).toBe("00:00");
    expect(formatDurationLong(2302)).toBe("38 min 22 s");
  });

  it("substitui resumo ausente por texto digno", () => {
    // "Resumo indisponível" impresso e assinado lê como falha do produto — e
    // para o paciente, como se aquele pedaço da sessão não tivesse valido nada.
    expect(summaryOrFallback("Resumo indisponível")).toBe(FALLBACK_SUMMARY);
    expect(summaryOrFallback("  ")).toBe(FALLBACK_SUMMARY);
    expect(summaryOrFallback("Sem fala transcrita neste intervalo")).toBe(FALLBACK_SUMMARY);
    expect(summaryOrFallback("Texto real")).toBe("Texto real");
  });
});

describe("documento do paciente", () => {
  const html = buildPatientReport(RELATORIO, IDENTIDADE, 2);

  it("não carrega rótulo que nomeia a pessoa", () => {
    for (const rotulo of ["sorriso falso", "falsa calma", "shutdown", "tristeza mascarada"]) {
      expect(html.toLowerCase().includes(rotulo), rotulo).toBe(false);
    }
  });

  it("não prescreve conduta", () => {
    expect(/\b(mitigar|facilitar|estimular|acolher)\s/i.test(html)).toBe(false);
  });

  it("omite sinal sem tradução escrita, em vez de cair no texto técnico", () => {
    // A dissonância do fixture não tem `title` correspondente no catálogo de
    // tradução. Some do documento — e leva o texto técnico junto.
    expect(html).toContain("Nenhum sinal registrado");
  });

  it("declara o que não é", () => {
    expect(html).toContain("Não é um diagnóstico");
    expect(html).toContain("Não substitui o seu profissional");
  });

  it("traz a abertura sorteada, com a salvaguarda", () => {
    expect(/profissional/i.test(html)).toBe(true);
    expect(/reconhecimento pessoal/i.test(html)).toBe(true);
  });

  it("NÃO identifica o paciente pelo nome", () => {
    // O documento é entregue ao próprio paciente; repetir o nome dele não
    // acrescenta nada e cria mais uma cópia de dado pessoal circulando.
    expect(html).not.toContain("Maria");
  });

  it("usa o nome da clínica como título", () => {
    expect(html).toContain("Clínica Exemplo");
  });
});

describe("documento do profissional", () => {
  const html = buildProfessionalReport(RELATORIO, IDENTIDADE, "Texto redigido pela profissional.", 0);

  it("mantém o texto técnico integral", () => {
    expect(html.toLowerCase()).toContain("sorriso falso");
  });

  it("traz a epígrafe com autor e fonte", () => {
    expect(html).toContain("Shakespeare");
    expect(html).toContain("Hamlet");
  });

  it("inclui o texto redigido e a linha de assinatura", () => {
    expect(html).toContain("Texto redigido pela profissional.");
    expect(html).toContain("Assinatura do profissional responsável");
  });

  it("identifica o paciente, porque é documento de prontuário", () => {
    expect(html).toContain("Maria");
  });

  it("escapa a marcação do nome", () => {
    // O documento passou a carregar um <script> legítimo — o paginador —, então
    // "não existe <script> no HTML" deixou de servir como prova. O que se
    // afirma agora é o que de fato importa: o nome injetado aparece escapado, e
    // não aparece cru em lugar nenhum, nem no corpo nem na configuração que vai
    // serializada para dentro do script.
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>alert");
    expect(html).not.toContain("<script>Dra");
  });

  it("avisa quando o relatório não foi redigido", () => {
    const semTexto = buildProfessionalReport(RELATORIO, IDENTIDADE, "", 0);
    expect(semTexto).toContain("Não redigido");
  });
});

describe("os dois documentos", () => {
  const paciente = buildPatientReport(RELATORIO, IDENTIDADE, 0);
  const profissional = buildProfessionalReport(RELATORIO, IDENTIDADE, "x", 0);

  it("ordenam os cortes do primeiro para o último", () => {
    for (const html of [paciente, profissional]) {
      const ordem = ["Primeiro", "Segundo", "Terceiro"].map((t) => html.indexOf(t));
      expect(ordem[0]).toBeGreaterThan(-1);
      expect(ordem[0]).toBeLessThan(ordem[1]);
      expect(ordem[1]).toBeLessThan(ordem[2]);
    }
  });

  it("trocam o resumo ausente pelo texto de contingência", () => {
    for (const html of [paciente, profissional]) {
      expect(html).not.toContain("Resumo indisponível");
      expect(html).toContain("Não houve fala suficiente");
    }
  });

  it("são HTML completo e paginado em A4", () => {
    for (const html of [paciente, profissional]) {
      expect(html.startsWith("<!doctype html>")).toBe(true);
      expect(html.trimEnd().endsWith("</html>")).toBe(true);
      expect(html).toContain("size:A4");
      // As folhas deixaram de existir no HTML estático: elas são criadas no
      // navegador, pelo paginador, que mede a altura real de cada bloco antes
      // de decidir onde a página acaba. Contar blocos nunca funcionaria, porque
      // a altura de um bloco depende do texto da sessão — e foi assim que
      // apareceram as meias páginas em branco.
      //
      // O que este teste pode afirmar sobre o HTML estático é que o material da
      // paginação está todo lá. Que as folhas cabem em A4, que nenhuma corta
      // conteúdo e que a numeração fecha só se verifica com layout de verdade,
      // e isso é medido no Chromium, fora da suíte.
      expect(html).toContain('id="fluxo"');
      expect((html.match(/class="bloco"/g) || []).length).toBeGreaterThanOrEqual(4);
      expect(html).toContain("function paginador");
    }
  });

  it("levam a faixa e o nome do profissional para toda folha", () => {
    // O cabeçalho é um molde: o paginador o repete em cada folha que cria.
    // Folha que se separou da pilha precisa dizer de quem é.
    for (const html of [paciente, profissional]) {
      expect(html).toContain('class=\\"cabecalho\\"');
      expect(html).toContain('class=\\"faixa\\"');
      expect(html).toContain('class=\\"prof\\"');
    }
  });

  it("esperam a faixa carregar antes de medir", () => {
    // Medir com a imagem ainda sem decodificar fazia sobrar espaço aparente, e
    // o excesso era cortado quando ela aparecia.
    for (const html of [paciente, profissional]) {
      expect(html).toContain("pre.onload = paginar");
      expect(html).toContain("pre.onerror = paginar");
    }
  });

  it("conferem de novo depois de montar, e empurram o que sobrou", () => {
    for (const html of [paciente, profissional]) {
      expect(html).toContain("guarda++ < 100");
    }
  });

  it("mandam imprimir com as cores", () => {
    // Sem print-color-adjust o navegador descarta fundo ao imprimir, e a cor
    // aqui carrega significado: verde, âmbar e vermelho por métrica.
    for (const html of [paciente, profissional]) {
      expect(html).toContain("print-color-adjust:exact");
      expect(html).toContain("-webkit-print-color-adjust:exact");
    }
  });

  it("sobrevivem a uma sessão sem cortes e sem dissonâncias", () => {
    const vazio = { ...RELATORIO, conversationSummaries: [], dissonances: [] } as never;
    expect(buildPatientReport(vazio)).toContain("Nenhum trecho registrado");
    expect(buildProfessionalReport(vazio)).toContain("Nenhum corte registrado");
  });

  it("sobrevivem à identidade ausente", () => {
    // Clínica sem nome cadastrado nao pode produzir documento quebrado.
    expect(buildPatientReport(RELATORIO)).toContain("Relatório da sessão");
    expect(buildProfessionalReport(RELATORIO)).toContain("Relatório da sessão");
  });
});
