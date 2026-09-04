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

  it("dá o título ao paciente, e não ao profissional", () => {
    // Decisão revista. A capa trazia a clínica, e o bloco de identificação logo
    // abaixo já nomeia "Profissional" e "Registro": o destaque da folha ficava
    // com quem não é o destinatário do documento. Este documento também é
    // gerado pelo profissional para entregar em mãos, e duas cópias impressas
    // sem nome são indistinguíveis uma da outra.
    expect(html).toContain("<h1>Maria");
    // O nome entra pelo mesmo escape de todo campo livre: o do fixture carrega
    // marcação de propósito.
    expect(html).not.toContain("<script>alert(1)</script>");
  });

  it("mantém a clínica identificando a origem no rodapé", () => {
    expect(html).toContain("Clínica Exemplo · Documento pessoal e confidencial");
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
      expect(html).toContain('class=\\"prof\\"');
      // A faixa NÃO é mais <img> dentro do molde: seria uma cópia por folha.
      expect(html).not.toContain("<img");
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

  it("imprimem quando a paginação termina, e não num temporizador", () => {
    // Foi assim que o sistema travou: openPrintable chamava print() em 350 ms,
    // e a paginação — que espera a imagem e remonta o documento — ainda estava
    // em curso. Imprimir com o DOM mudando sob o motor de layout wedgeia a aba.
    for (const html of [paciente, profissional]) {
      expect(html).toContain("__froidPaginado");
      expect(html).toContain("window.print()");
    }
  });

  it("carregam UMA referência à faixa, não uma por folha", () => {
    // Como <img> por folha, um documento de 34 folhas levava 34 cópias do mesmo
    // data URI de 92 KB, que a impressão rasteriza uma por uma. Agora a imagem
    // aparece uma vez, na configuração, e o paginador a instala como fundo numa
    // regra única.
    //
    // O teste conta REFERÊNCIAS e não data URIs: na build o import vira base64,
    // mas na suíte o Vite entrega um caminho. O que importa — uma só — vale nos
    // dois casos.
    for (const html of [paciente, profissional]) {
      expect((html.match(/relatorio-logo/g) || []).length).toBe(1);
      expect(html).toContain("instalarFaixa");
      expect(html).toContain("background-image:url(");
    }
  });

  it("tem teto de folhas, para defeito não travar a maquina de quem atende", () => {
    for (const html of [paciente, profissional]) {
      expect(html).toContain("folhas.length >= 300");
    }
  });

  it("partem tabela em vez de saltar a folha inteira", () => {
    // Tabela indivisível deixava até um terço de página em branco antes dela.
    // A continuação herda o thead e a largura medida das colunas — sem isso a
    // segunda parte é uma parede de números com as colunas fora de registro.
    for (const html of [paciente, profissional]) {
      expect(html).toContain("function partirTabela");
      expect(html).toContain("tabCont.style.tableLayout");
      expect(html).toContain("continuação da tabela anterior");
      // A continuação começa em folha nova: devolvê-la à folha cheia fazia a
      // tabela partir de novo, até sair uma linha por tabelinha.
      expect(html).toContain("corpo = novaFolha();");
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
