import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { combina, normalizar } from "./Nr1Explica";
import { TEMAS, VERBETES } from "../lib/nr1-explica-conteudo";
import {
  amostraNecessaria,
  PISO_CAMPANHA,
  PISO_RECORTE,
} from "../lib/nr1-representatividade";

/**
 * Travas do FROID Explica NR-1.
 *
 * O conteudo desta tela e lido na frente do cliente e, as vezes, na frente de
 * um auditor. Duas coisas precisam ser verdade sempre:
 *
 * 1. os numeros que ele afirma sao os que o sistema aplica — este arquivo e o
 *    sexto ponto de espelho dos pisos, e o unico que fala diretamente ao
 *    comprador;
 * 2. ele nao se apresenta como parecer juridico.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1Explica.tsx"), "utf-8");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAINEL = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");

const texto = (id: string) => {
  const verbete = VERBETES.find((item) => item.id === id);
  if (!verbete) throw new Error(`verbete ${id} sumiu`);
  return verbete.resposta.join(" ");
};

describe("o conteudo esta integro", () => {
  it("tem verbetes suficientes para responder uma reunião", () => {
    expect(VERBETES.length).toBeGreaterThanOrEqual(30);
  });

  it("nenhum id repetido", () => {
    const ids = VERBETES.map((verbete) => verbete.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("todo verbete pertence a um tema declarado", () => {
    const temas = new Set(TEMAS.map((tema) => tema.id));
    for (const verbete of VERBETES) {
      expect(temas.has(verbete.tema), `${verbete.id} tem tema órfão`).toBe(true);
    }
  });

  it("todo tema tem ao menos um verbete", () => {
    // Tema vazio vira uma aba que não abre nada — o usuário conclui que a tela
    // está quebrada, e não que aquele assunto não foi coberto.
    for (const tema of TEMAS) {
      const quantos = VERBETES.filter((v) => v.tema === tema.id).length;
      expect(quantos, `tema ${tema.id} está vazio`).toBeGreaterThan(0);
    }
  });

  it("nenhuma resposta vazia", () => {
    for (const verbete of VERBETES) {
      expect(verbete.resposta.length, `${verbete.id} sem resposta`).toBeGreaterThan(0);
      for (const paragrafo of verbete.resposta) {
        expect(paragrafo.trim().length).toBeGreaterThan(20);
      }
    }
  });
});

describe("os numeros afirmados sao os que o sistema aplica", () => {
  /**
   * O piso da campanha ja foi 50 e virou 15 na migration 027. O corpus do
   * FROID Explica no servidor continuou dizendo 50 por tres dias, respondendo
   * ao cliente com um numero que o banco havia abandonado. Esta tela nao pode
   * repetir isso.
   */

  it("o piso de anonimato citado e o vigente", () => {
    const resposta = texto("dois-portoes");
    expect(resposta).toContain(`${PISO_CAMPANHA} respostas substantivas`);
    expect(resposta).toContain(`${PISO_RECORTE} por recorte`);
  });

  it("nenhum verbete ressuscita o piso de 50", () => {
    for (const verbete of VERBETES) {
      expect(
        /\b50 respostas\b/i.test(verbete.resposta.join(" ")),
        `${verbete.id} cita 50 respostas como piso`,
      ).toBe(false);
    }
  });

  it("a tabela de porte confere com a funcao de amostra", () => {
    const resposta = texto("quantas-respostas");
    // "28 pessoas exigem 28", "250 exigem 152", e assim por diante.
    const pares = [...resposta.matchAll(/(\d[\d.]*) (?:pessoas )?exigem (\d+)/g)];
    expect(pares.length).toBeGreaterThanOrEqual(5);
    for (const par of pares) {
      const efetivo = Number(par[1].replace(".", ""));
      const afirmado = Number(par[2]);
      expect(afirmado, `porte ${efetivo} está errado na tela`).toBe(
        amostraNecessaria(efetivo),
      );
    }
  });

  it("a fronteira do censo citada e a real", () => {
    const ultimoCenso = (() => {
      for (let n = 400; n >= PISO_CAMPANHA; n -= 1) {
        if (amostraNecessaria(n) === n) return n;
      }
      throw new Error("fronteira do censo não encontrada");
    })();
    const resposta = texto("quantas-respostas");
    expect(resposta).toContain(String(ultimoCenso + 1));
  });
});

describe("a tela nao se apresenta como parecer", () => {
  it("declara o limite na propria pagina", () => {
    expect(PAGINA).toContain("Não constitui parecer jurídico");
    expect(PAGINA).toContain("Diário Oficial da União");
  });

  it("nao promete conformidade automatica", () => {
    const tudo = VERBETES.flatMap((v) => v.resposta).join(" ").toLowerCase();
    for (const promessa of [
      "garante conformidade",
      "elimina o risco de multa",
      "isenta a empresa",
    ]) {
      expect(tudo).not.toContain(promessa);
    }
  });
});

describe("a fronteira clinica continua de pe nesta tela", () => {
  it("nao consulta o acervo do FROID Explica clinico", () => {
    // Uma tela do lado do empregador que chamasse /api/froid-explica/query
    // atravessaria a separacao que o produto existe para sustentar — aquele
    // endpoint injeta resumo da carteira de pacientes em pergunta comparativa.
    expect(PAGINA).not.toContain("froid-explica/query");
    expect(PAGINA).not.toContain("apiUrl");
    expect(PAGINA).not.toContain("fetch(");
  });
});

describe("a busca acha o que a pessoa digita", () => {
  it("ignora acento e maiuscula", () => {
    expect(normalizar("Inventário")).toBe("inventario");
  });

  it("acha por palavra que nao esta na pergunta", () => {
    const filial = VERBETES.find((v) => v.id === "filial-nao-publica")!;
    expect(combina(filial, "endereço")).toBe(true);
    expect(combina(filial, "ENDERECO")).toBe(true);
  });

  it("exige todas as palavras, em qualquer ordem", () => {
    const multa = VERBETES.find((v) => v.id === "multas")!;
    expect(combina(multa, "multa fiscalizacao")).toBe(true);
    expect(combina(multa, "multa unicornio")).toBe(false);
  });

  it("termo vazio devolve tudo", () => {
    expect(VERBETES.every((v) => combina(v, ""))).toBe(true);
  });
});

describe("a tela e alcancavel", () => {
  it("a rota existe", () => {
    expect(APP).toContain('path="/nr1/explica"');
  });

  it("o painel aponta para ela", () => {
    // Rota sem tela que aponte para ela e o padrao que este modulo ja repetiu
    // quatro vezes.
    expect(PAINEL).toContain('nav("/nr1/explica")');
  });
});
