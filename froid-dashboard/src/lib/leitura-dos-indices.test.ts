import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { janelaVertical } from "../components/indicators/IPMLineChart";

const ler = (...partes: string[]) =>
  readFileSync(join(__dirname, "..", ...partes), "utf-8");

const RELATORIO = ler("pages", "SessionReport.tsx");
const GRAFICO_IPM = ler("components", "indicators", "IPMLineChart.tsx");

/**
 * Item 1 do pedido de 02/09/2026: "gostaria que a abrangência das oscilações
 * ocupasse uma área maior".
 *
 * O eixo era fixo em 0–100. Numa sessão real o IPM vive entre 50 e 54 — a
 * linha ocupava 4% da altura e parecia reta. O gráfico existe para mostrar
 * variação e era exatamente a variação que ele escondia.
 */
describe("a janela do gráfico de IPM acompanha os dados", () => {
  it("uma faixa estreita vira uma janela legível", () => {
    // O caso do print: 50 a 54 num eixo de 0 a 100.
    const janela = janelaVertical([50, 52, 54, 51, 53]);
    expect(janela.max - janela.min).toBeLessThan(30);
    expect(janela.min).toBeLessThanOrEqual(50);
    expect(janela.max).toBeGreaterThanOrEqual(54);
  });

  it("a janela contém todos os pontos — nenhum fica fora da tela", () => {
    const valores = [12, 48, 33, 7, 60];
    const janela = janelaVertical(valores);
    for (const valor of valores) {
      expect(valor).toBeGreaterThanOrEqual(janela.min);
      expect(valor).toBeLessThanOrEqual(janela.max);
    }
  });

  it("ruído de meio ponto NÃO vira montanha", () => {
    // Sem amplitude mínima, uma variação clinicamente irrelevante encheria a
    // tela e sugeriria instabilidade que não existe.
    const janela = janelaVertical([50, 50.2, 50.1, 50.3]);
    expect(janela.max - janela.min).toBeGreaterThanOrEqual(10);
  });

  it("série constante não quebra a divisão", () => {
    const janela = janelaVertical([42, 42, 42]);
    expect(janela.max).toBeGreaterThan(janela.min);
  });

  it("a janela nunca sai de 0–100, e desliza em vez de encolher", () => {
    const alta = janelaVertical([98, 99, 100]);
    expect(alta.max).toBeLessThanOrEqual(100);
    expect(alta.min).toBeGreaterThanOrEqual(0);
    expect(alta.max - alta.min).toBeGreaterThanOrEqual(10);

    const baixa = janelaVertical([0, 1, 2]);
    expect(baixa.min).toBeGreaterThanOrEqual(0);
    expect(baixa.max - baixa.min).toBeGreaterThanOrEqual(10);
  });

  it("sem dados, mostra a escala inteira", () => {
    expect(janelaVertical([])).toEqual({ min: 0, max: 100 });
  });

  it("a faixa visível é declarada na tela", () => {
    // Zoom que não se declara é gráfico que mente: quem olha precisa saber que
    // está vendo um recorte, e qual.
    expect(GRAFICO_IPM).toContain("escala IPM {janela.min.toFixed(0)}");
  });
});

/**
 * Item 4: "está impossível de avaliar a escala dos índices".
 *
 * Quatro séries num eixo só, normalizadas contra o baseline. Com IDM em 0.01 e
 * dissonância em 0, uma variação irrelevante em valor absoluto virava centenas
 * de pontos percentuais; o eixo esticava para acomodá-la e IPM e palavras/min
 * viravam duas retas coladas no meio.
 */
describe("a evolução deixou de espremer grandezas incomparáveis num eixo só", () => {
  it("cada índice ganhou o próprio painel", () => {
    expect(RELATORIO).toContain("const PainelEvolucao");
    expect(RELATORIO).toContain("<PainelEvolucao");
  });

  it("o eixo compartilhado saiu junto com a normalização que o alimentava", () => {
    // `norm` existia só para forçar quatro grandezas na mesma régua.
    expect(RELATORIO).not.toContain("function norm(");
  });

  it("cada painel calcula a própria faixa", () => {
    expect(RELATORIO).toContain("const menor = Math.min(...validos)");
    expect(RELATORIO).toContain("const maior = Math.max(...validos)");
  });

  it("série sem leitura DIZ isso, em vez de desenhar zero", () => {
    // Uma linha reta no zero parece medida. Uma medida ausente que parece
    // medida é pior do que um espaço vazio — foi o que fez a dissonância
    // parecer inútil quando na verdade estava vazia.
    expect(RELATORIO).toContain("sem leitura");
    expect(RELATORIO).toContain("Nenhum corte deste período produziu valor");
  });

  it("os valores reais aparecem escritos, não só desenhados", () => {
    expect(RELATORIO).toContain("atual.toFixed(serie.casas)");
    expect(RELATORIO).toContain("baseline");
  });
});

/**
 * Item 3: "os tooltips não estão informando a descrição representativa".
 *
 * A busca era casamento exato por rótulo. A tabela do motor estatístico passa
 * o rótulo do SERVIDOR ("Elevação multimodal (IPM)"), que nunca esteve no
 * dicionário — então todas as suas linhas mostravam "Métrica FROID.".
 */
describe("todo campo do relatório tem descrição de verdade", () => {
  const dicionario = (() => {
    const inicio = RELATORIO.indexOf("const METRIC_TOOLTIPS");
    const fim = RELATORIO.indexOf("};", inicio);
    const bloco = RELATORIO.slice(inicio, fim);
    const chaves = new Set<string>();
    for (const m of bloco.matchAll(/^\s*(?:"([^"]+)"|([A-Za-zÀ-ÿ_][A-Za-z0-9À-ÿ_]*)):/gm)) {
      chaves.add(m[1] || m[2]);
    }
    return chaves;
  })();

  const normalizar = (t: string) =>
    t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const normalizadas = new Set([...dicionario].map(normalizar));

  it("as chaves do motor estatístico estão todas cobertas", () => {
    // Estas nomeiam as linhas da tabela de evolução — as que mostravam o texto
    // genérico para o Fábio.
    const inicio = RELATORIO.indexOf("const METRIC_SUMMARY_KEYS");
    const fim = RELATORIO.indexOf("];", inicio);
    const chaves = [...RELATORIO.slice(inicio, fim).matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]);
    expect(chaves.length).toBeGreaterThan(5);
    const semDescricao = chaves.filter((c) => !normalizadas.has(normalizar(c)));
    expect(semDescricao).toEqual([]);
  });

  it("os rótulos da tabela de métricas estão todos cobertos", () => {
    const inicio = RELATORIO.indexOf("function metricRows(");
    const fim = RELATORIO.indexOf("];", inicio);
    const rotulos = [...RELATORIO.slice(inicio, fim).matchAll(/\["([^"]+)",/g)].map((m) => m[1]);
    expect(rotulos.length).toBeGreaterThan(15);
    const semDescricao = rotulos.filter((r) => !normalizadas.has(normalizar(r)));
    expect(semDescricao).toEqual([]);
  });

  it("a busca aceita a chave, e não só o rótulo", () => {
    // É o que conserta a tabela do motor: o rótulo vem do servidor, a chave é
    // nossa.
    expect(RELATORIO).toContain("export function descricaoDaMetrica(rotulo: string, chave?: string)");
    expect(RELATORIO).toContain("chave={key}");
  });

  it("a busca ignora acento e pontuação", () => {
    // "Dissonância" contra "Dissonancia": um acento separava a métrica da sua
    // descrição.
    expect(RELATORIO).toContain("INDICE_NORMALIZADO");
  });

  it("sem descrição, o texto ADMITE isso", () => {
    // "Métrica FROID." ocupava o lugar da explicação e fazia parecer que a
    // explicação era aquela.
    expect(RELATORIO).not.toContain('|| "Métrica FROID."');
    expect(RELATORIO).toContain("ainda não tem descrição cadastrada");
  });
});
