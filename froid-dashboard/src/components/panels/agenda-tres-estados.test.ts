import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A agenda tem três motivos diferentes para não mostrar compromisso, e cada um
 * manda a pessoa para um lugar diferente:
 *
 *   - `configured: false` — o SERVIDOR não tem credencial do Google. Oferecer
 *     "conectar" aqui entrega um botão que só sabe falhar com 503, e o
 *     profissional fica tentando resolver uma coisa que não é dele.
 *   - `connected: false` — o servidor tem, e esta conta ainda não ligou. É o
 *     único caso em que o convite faz sentido.
 *   - falha de leitura — precisa aparecer. Coluna vazia por erro é
 *     indistinguível de "nenhum compromisso", que foi exatamente o padrão que
 *     custou caro no acervo de relatórios.
 */
const AGENDA = readFileSync(join(__dirname, "AgendaDoProfissional.tsx"), "utf-8");
const RESUMIDO = readFileSync(
  join(__dirname, "..", "..", "pages", "ProfessionalDashboardSummary.tsx"),
  "utf-8",
);

describe("a agenda distingue os três motivos de não ter compromisso", () => {
  it("servidor sem credencial não recebe convite para conectar", () => {
    expect(AGENDA).toContain("status.configured === false");
    const semCredencial = AGENDA.indexOf("status.configured === false");
    const convite = AGENDA.indexOf("Conectar Google Agenda");
    // A checagem do servidor vem ANTES do convite: quem cai nela nunca vê o
    // botão que não teria como funcionar.
    expect(semCredencial).toBeGreaterThan(-1);
    expect(convite).toBeGreaterThan(semCredencial);
  });

  it("conta não conectada recebe o convite e o caminho até ele", () => {
    expect(AGENDA).toContain("!status?.connected");
    expect(AGENDA).toContain('navigate("/settings")');
  });

  it("falha de leitura aparece, em vez de virar coluna vazia", () => {
    expect(AGENDA).toContain('role="alert"');
    expect(AGENDA).toContain("setErro");
    // O desligamento da carga vive num finally: a busca que falha também
    // termina, senão a coluna ficaria presa em "aguarde".
    expect(AGENDA).toContain("finally");
  });

  it("a espera não é anunciada como ausência", () => {
    expect(AGENDA).toContain("Estamos executando sua Solicitação, aguarde por favor");
    const espera = AGENDA.indexOf("Estamos executando sua Solicitação");
    const vazio = AGENDA.indexOf("Nenhum compromisso nos próximos dias");
    expect(vazio).toBeGreaterThan(espera);
  });

  it("evento de dia inteiro não é tratado como meia-noite", () => {
    expect(AGENDA).toContain("diaInteiro");
    expect(AGENDA).toContain("dia inteiro");
  });
});

describe("a coluna da agenda entra sem quebrar a tabela de pacientes", () => {
  it("é a segunda coluna da grade, e some para uma coluna só em tela estreita", () => {
    expect(RESUMIDO).toContain("lg:grid-cols-[minmax(0,1fr)_20rem]");
    expect(RESUMIDO).toContain("<AgendaDoProfissional tr={tr} />");
  });

  it("a coluna de conteúdo tem min-w-0", () => {
    // Sem isto a tabela de pacientes, que rola na horizontal, estoura a largura
    // da grade e empurra a agenda para fora da tela.
    expect(RESUMIDO).toContain('className="min-w-0 space-y-4"');
  });
});
