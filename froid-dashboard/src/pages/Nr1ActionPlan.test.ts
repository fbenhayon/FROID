import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * A tela do plano de ação — o segundo documento obrigatório do PGR.
 *
 * O FROID entregava um dos dois: o inventário era gravado e o plano voltava
 * como rascunho no corpo da resposta da API, sem nunca ser persistido. Estes
 * testes travam o que a tela não pode perder de vista, porque cada item é uma
 * exigência da norma e não uma preferência de interface.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1ActionPlan.tsx"), "utf-8");
const CORRIDA = PAGINA.replace(/\s+/g, " ");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAINEL = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");

describe("a tela cobre os quatro campos que 1.5.5.2.2 exige", () => {
  it("pede cronograma, responsável, acompanhamento e aferição", () => {
    for (const campo of [
      "due_date",
      "responsible_membership_id",
      "monitoring_method",
      "result_measurement",
    ]) {
      expect(PAGINA).toContain(campo);
    }
  });

  it("separa acompanhamento de aferição, que são coisas diferentes", () => {
    // Como se verifica que a medida continua de pé, e como se mede se ela
    // produziu efeito. Sem a segunda não há o que comparar no ciclo seguinte e
    // a prova de eficácia deixa de existir.
    expect(CORRIDA).toMatch(/Forma de acompanhamento/);
    expect(CORRIDA).toMatch(/Forma de aferição do resultado/);
  });

  it("mostra o que falta antes de a pessoa tentar concluir", () => {
    // O banco recusa a conclusão por CHECK. Deixar a pessoa descobrir isso por
    // erro de constraint seria ensinar nada.
    expect(PAGINA).toContain("pendenciasPara");
    expect(CORRIDA).toMatch(/ainda falta/);
  });
});

describe("os três verbos de 1.5.5.2.1 aparecem", () => {
  it("introduzir, aprimorar e manter", () => {
    expect(PAGINA).toContain("introduce");
    expect(PAGINA).toContain("improve");
    expect(PAGINA).toContain("maintain");
    expect(CORRIDA).toMatch(/Introduzir/);
    expect(CORRIDA).toMatch(/Aprimorar/);
    expect(CORRIDA).toMatch(/Manter/);
  });
});

describe("a hierarquia de medidas segue a decisão declarada", () => {
  it("não oferece EPI", () => {
    // Não existe equipamento de proteção individual contra a forma como o
    // trabalho é organizado. A divergência de 1.5.5.1.2 está declarada no
    // documento de critérios, junto da justificativa.
    expect(PAGINA).not.toMatch(/"epi"/i);
    expect(PAGINA).toContain("elimination");
    expect(PAGINA).toContain("collective");
  });

  it("nomeia a eliminação como primeiro degrau", () => {
    const inicio = PAGINA.indexOf("const MEASURE_TYPES");
    const trecho = PAGINA.slice(inicio, PAGINA.indexOf("];", inicio));
    expect(trecho.indexOf("elimination")).toBeLessThan(trecho.indexOf("administrative"));
  });
});

describe("o gatilho da alínea a de 1.5.4.4.6 é visível", () => {
  it("avisa que a reavaliação de risco residual está devida", () => {
    expect(CORRIDA).toMatch(/risco residual/);
    expect(CORRIDA).toMatch(/1\.5\.4\.4\.6/);
  });

  it("explica que a obrigação nasce do evento, e não de uma data", () => {
    // É a resposta à pergunta que sempre volta: "qual é o prazo da segunda
    // avaliação?". Não há prazo porque não há data — implementou, deve
    // reavaliar.
    expect(CORRIDA).toMatch(/nasceu do evento|nasce do evento/);
  });

  it("conta as medidas implementadas sem reavaliação no resumo", () => {
    expect(PAGINA).toContain("awaiting_residual_review");
  });
});

describe("prioridade e ordem", () => {
  it("mostra o rank gravado, e não uma ordem calculada na tela", () => {
    // 1.5.5.2.1.1: o número de trabalhadores possivelmente atingidos aumenta a
    // prioridade. A ordem do documento não pode depender de quem o abre.
    expect(PAGINA).toContain("priority_rank");
    expect(CORRIDA).toMatch(/trabalhador\(es\) possivelmente atingido/);
  });
});

describe("a rota existe e é alcançável", () => {
  it("está registrada no App", () => {
    expect(APP).toContain('path="/nr1/plano-de-acao"');
    expect(APP).toContain("Nr1ActionPlan");
  });

  it("o painel NR-1 aponta para ela", () => {
    // A rota /nr1 existiu por meses sem nenhuma tela apontando para ela. Não
    // repetir.
    expect(PAINEL).toContain('nav("/nr1/plano-de-acao")');
  });
});
