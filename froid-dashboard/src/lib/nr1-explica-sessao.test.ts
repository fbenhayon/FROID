import { describe, expect, it } from "vitest";

import {
  LIMITE_HISTORICO,
  LIMITE_PROMPTS,
  acrescentaAoHistorico,
  chaveHistorico,
  chavePrompts,
  grava,
  jaSalvo,
  ler,
  removePrompt,
  salvaPrompt,
  tituloDoPrompt,
  type ItemHistorico,
  type PromptSalvo,
} from "./nr1-explica-sessao";

const item = (id: string, pergunta = "p"): ItemHistorico => ({
  id,
  pergunta,
  quando: "2026-08-29T10:00:00.000Z",
  resposta: null,
});

const prompt = (id: string, texto: string): PromptSalvo => ({
  id,
  titulo: tituloDoPrompt(texto),
  texto,
});

describe("o historico nao se perde", () => {
  /**
   * O defeito que este modulo corrige: a tela fazia `setAberta(null)` a cada
   * pergunta, e a resposta anterior sumia. Quem comparava duas, ou ia copiar a
   * que acabara de receber, perdia o trabalho.
   */
  it("acrescenta em vez de substituir", () => {
    const um = acrescentaAoHistorico([], item("a"));
    const dois = acrescentaAoHistorico(um, item("b"));
    expect(dois.map((i) => i.id)).toEqual(["b", "a"]);
  });

  it("mais recente primeiro", () => {
    const lista = acrescentaAoHistorico(
      acrescentaAoHistorico([], item("velho")),
      item("novo"),
    );
    expect(lista[0].id).toBe("novo");
  });

  it("respeita o teto sem perder os recentes", () => {
    let lista: ItemHistorico[] = [];
    for (let i = 0; i < LIMITE_HISTORICO + 12; i += 1) {
      lista = acrescentaAoHistorico(lista, item(`i${i}`));
    }
    expect(lista).toHaveLength(LIMITE_HISTORICO);
    expect(lista[0].id).toBe(`i${LIMITE_HISTORICO + 11}`);
  });

  it("a pergunta que falhou tambem entra", () => {
    const comErro: ItemHistorico = { ...item("x"), erro: "rede caiu" };
    expect(acrescentaAoHistorico([], comErro)[0].erro).toBe("rede caiu");
  });
});

describe("meus prompts", () => {
  it("salvar duas vezes a mesma pergunta nao duplica", () => {
    const um = salvaPrompt([], prompt("a", "quantas respostas preciso?"));
    const dois = salvaPrompt(um, prompt("b", "quantas respostas preciso?"));
    expect(dois).toHaveLength(1);
  });

  it("ignora diferenca de espaco em branco ao comparar", () => {
    const um = salvaPrompt([], prompt("a", "quantas   respostas\npreciso?"));
    expect(jaSalvo(um, " quantas respostas preciso? ")).toBe(true);
  });

  it("promove o repetido ao topo", () => {
    let lista = salvaPrompt([], prompt("a", "primeira"));
    lista = salvaPrompt(lista, prompt("b", "segunda"));
    lista = salvaPrompt(lista, prompt("c", "primeira"));
    expect(lista.map((p) => p.texto)).toEqual(["primeira", "segunda"]);
  });

  it("remove pelo identificador", () => {
    const lista = salvaPrompt(salvaPrompt([], prompt("a", "x")), prompt("b", "y"));
    expect(removePrompt(lista, "a").map((p) => p.id)).toEqual(["b"]);
  });

  it("respeita o teto", () => {
    let lista: PromptSalvo[] = [];
    for (let i = 0; i < LIMITE_PROMPTS + 5; i += 1) {
      lista = salvaPrompt(lista, prompt(`p${i}`, `pergunta ${i}`));
    }
    expect(lista).toHaveLength(LIMITE_PROMPTS);
  });

  it("o titulo cabe num chip e preserva perguntas curtas", () => {
    expect(tituloDoPrompt("  curta  ")).toBe("curta");
    const longa = "a".repeat(200);
    expect(tituloDoPrompt(longa).length).toBeLessThanOrEqual(64);
    expect(tituloDoPrompt(longa).endsWith("…")).toBe(true);
  });

  it("o titulo usa so a primeira linha", () => {
    expect(tituloDoPrompt("pergunta\ndetalhe irrelevante")).toBe("pergunta");
  });
});

describe("as chaves separam organizacoes", () => {
  /** Quem opera uma carteira alterna entre organizacoes. Misturar o rastro de
   *  uma no painel de outra confunde na melhor das hipoteses. */
  it("historico e prompts nao colidem entre si nem entre organizacoes", () => {
    expect(chaveHistorico("org-a")).not.toBe(chaveHistorico("org-b"));
    expect(chavePrompts("org-a")).not.toBe(chavePrompts("org-b"));
    expect(chaveHistorico("org-a")).not.toBe(chavePrompts("org-a"));
  });
});

describe("o armazenamento falha sem derrubar a tela", () => {
  /** Janela anonima que bloqueia, cota estourada, conteudo de uma versao
   *  anterior. O Explica precisa abrir mesmo sem memoria nenhuma. */
  const deposito = (comportamento: Partial<Storage>): Storage =>
    ({ getItem: () => null, setItem: () => undefined, ...comportamento }) as Storage;

  it("deposito ausente devolve o padrao", () => {
    expect(ler(undefined, "k", ["padrao"])).toEqual(["padrao"]);
  });

  it("json corrompido devolve o padrao", () => {
    expect(ler(deposito({ getItem: () => "{isto nao e json" }), "k", [])).toEqual([]);
  });

  it("tipo divergente do padrao devolve o padrao", () => {
    // Uma versao anterior podia ter gravado um objeto onde hoje se espera lista.
    expect(ler(deposito({ getItem: () => '{"a":1}' }), "k", [])).toEqual([]);
  });

  it("gravar com cota cheia nao lanca", () => {
    const cheio = deposito({
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });
    expect(() => grava(cheio, "k", { a: 1 })).not.toThrow();
  });

  it("ler de deposito que lanca nao derruba", () => {
    const quebrado = deposito({
      getItem: () => {
        throw new Error("acesso negado");
      },
    });
    expect(ler(quebrado, "k", ["padrao"])).toEqual(["padrao"]);
  });
});
