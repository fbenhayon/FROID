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
/**
 * A pagina sem comentarios.
 *
 * Necessario para as asseroes negativas: o cabecalho da tela EXPLICA por que
 * ela nao usa /api/froid-explica/query, citando a rota pelo nome — e e assim
 * que deve continuar. Um teste que procurasse a string no texto inteiro
 * estaria proibindo a explicacao em vez da chamada.
 */
const CODIGO = PAGINA.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
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
  /**
   * A tela consulta o servidor — a pergunta aberta existe. O que ela nao pode
   * fazer e consultar o acervo CLINICO: `/api/froid-explica/query` exige
   * aprovacao profissional e injeta resumo da carteira de pacientes em
   * pergunta comparativa. A rota do NR-1 le uma collection separada.
   *
   * A trava nao e sobre haver rede. E sobre qual porta.
   */

  it("nao chama a rota do FROID Explica clinico", () => {
    expect(CODIGO).not.toContain("froid-explica/query");
    expect(CODIGO).not.toContain("/api/copilot/query");
  });

  it("chama a rota corporativa, escopada na organizacao", () => {
    expect(PAGINA).toContain("/nr1/explica");
    expect(PAGINA).toContain("X-FROID-Organization-ID");
  });

  it("nao envia contexto de sessao nem de paciente", () => {
    // O corpo da requisicao carrega uma pergunta em texto e nada mais. Nao ha
    // parametro por onde dado clinico possa chegar ao acervo corporativo.
    expect(CODIGO).toContain("JSON.stringify({ pergunta: texto })");
    expect(CODIGO).not.toContain("patient_id");
    expect(CODIGO).not.toContain("portfolio");
  });

  it("continua util quando a consulta aberta falha", () => {
    // Tela de duvida que quebra na frente do cliente e pior do que tela que
    // responde menos.
    expect(PAGINA).toContain("continuam valendo");
    expect(PAGINA).toContain("acervo_nao_indexado");
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

describe("o verbete contratual aponta, e nao reescreve", () => {
  /**
   * O contrato e os Termos sao documentos versionados, e o comprovante de
   * aceite prova QUAL texto foi aceito pelo sha256. Um verbete que reescrevesse
   * a clausula criaria uma segunda narrativa da mesma obrigacao, sem versao e
   * sem digital — e quando as duas divergissem, o cliente teria agido pela
   * parafrase enquanto o livro prova o outro texto.
   *
   * Por isso todo verbete contratual carrega destino, e o destino e o
   * documento vigente dentro do sistema.
   */

  const contratuais = VERBETES.filter((v) => v.tema === "contrato");

  it("existe um tema de contrato com verbetes", () => {
    expect(contratuais.length).toBeGreaterThanOrEqual(6);
  });

  it("todo verbete contratual leva ao documento vigente", () => {
    for (const verbete of contratuais) {
      expect(verbete.destino, `${verbete.id} sem destino`).toBeTruthy();
      expect(
        ["/contrato-nr1", "/termos-nr1", "/nr1/comprovante"],
        `${verbete.id} aponta para fora dos documentos`,
      ).toContain(verbete.destino!.para);
    }
  });

  it("os destinos existem como rota", () => {
    for (const rota of ["/contrato-nr1", "/termos-nr1", "/nr1/comprovante"]) {
      expect(APP).toContain(`path="${rota}"`);
    }
  });

  it("nao promete preco, prazo nem escopo", () => {
    // Variam por contrato e vivem na proposta comercial. Resposta estatica
    // aqui viraria promessa errada em algum contrato.
    const tudo = contratuais.flatMap((v) => v.resposta).join(" ");
    expect(tudo).not.toMatch(/R\$\s?\d/);
    expect(tudo).not.toMatch(/\b\d+\s*(dias|meses)\s*de\s*(prazo|garantia)/i);
  });

  it("diz que o texto que vale e o do documento", () => {
    const tudo = contratuais.flatMap((v) => v.resposta).join(" ").toLowerCase();
    expect(tudo).toContain("o texto que vale");
  });
});

describe("o painel manda para a resposta certa", () => {
  /**
   * O recorte declarado insuficiente diz o caminho — "avaliar pela AEP",
   * "reforcar a participacao" — e ate aqui o leitor tinha de sair do painel e
   * procurar sozinho o que aquilo significava. Quem le aquela linha ja tem a
   * pergunta formada.
   *
   * O link e POR PORTAO porque os remedios sao opostos: onde o problema e
   * tamanho de grupo, adesao nao resolve; onde e representatividade, resolve.
   * Um "saiba mais" generico mandaria metade dos leitores para o conselho
   * errado.
   */

  it("cada portao aponta para um verbete que existe", () => {
    const mapa = PAINEL.match(/const VERBETE_DO_PORTAO[^}]+}/s)?.[0] || "";
    expect(mapa).toBeTruthy();
    const ids = [...mapa.matchAll(/"([a-z-]+)",?\n/g)].map((m) => m[1]);
    expect(ids.length).toBeGreaterThanOrEqual(3);
    for (const id of ids) {
      expect(
        VERBETES.some((v) => v.id === id),
        `portao aponta para verbete inexistente: ${id}`,
      ).toBe(true);
    }
  });

  it("os quatro portoes conhecidos estao cobertos", () => {
    for (const portao of [
      "anonimato",
      "representatividade",
      "efetivo_nao_declarado",
      "campanha_abaixo_do_piso",
    ]) {
      expect(PAINEL).toContain(`${portao}:`);
    }
  });

  it("cada portao tem verbete PROPRIO, e nao uma resposta parecida", () => {
    // O primeiro mapa apontava para verbetes vizinhos — "meu setor tem 6
    // pessoas" para quem olhava um resultado suprimido. A pessoa chegava numa
    // resposta que tratava de outro momento do fluxo e concluia que a tela nao
    // sabia responder. Verbete de portao e escrito para a pergunta feita
    // OLHANDO a linha do painel.
    const mapa = PAINEL.match(/const VERBETE_DO_PORTAO[^}]+}/s)?.[0] || "";
    const ids = [...mapa.matchAll(/"(painel-[a-z-]+)"/g)].map((m) => m[1]);
    expect(ids.length).toBe(4);
    expect(new Set(ids).size).toBe(4);
    for (const id of ids) {
      const verbete = VERBETES.find((v) => v.id === id);
      expect(verbete, `verbete ${id} nao existe`).toBeTruthy();
      expect(verbete!.pergunta).toContain("O painel diz");
    }
  });

  it("so oferece a AEP onde ela e mesmo o caminho", () => {
    // Anonimato: sempre, porque tamanho de grupo nao muda com adesao.
    // Campanha inteira: so quando o porte nao sustenta coorte — oferecer AEP a
    // uma empresa de 258 pessoas que teve adesao baixa e manda-la abandonar
    // uma campanha que publicaria, e custa um ciclo inteiro.
    const inicio = PAINEL.indexOf("function ofereceAep");
    const funcao = inicio >= 0 ? PAINEL.slice(inicio, inicio + 400) : "";
    expect(funcao).toContain('portao === "anonimato"');
    expect(funcao).toContain("PISO_CAMPANHA");
    expect(funcao).not.toContain('"representatividade"');
  });

  it("a tela abre apontada quando recebe ?verbete=", () => {
    expect(PAGINA).toContain('parametros.get("verbete")');
    expect(PAGINA).toContain("verbeteAlvo ? { [verbeteAlvo]: true } : {}");
  });
});

describe("a troca de organizacao troca de organizacao", () => {
  /**
   * Dois defeitos na mesma funcao, e os dois silenciosos: o seletor mudava na
   * tela e nada acontecia. Quem caisse numa organizacao ficava preso nela.
   *
   * 1. a guarda comparava o parametro com ele mesmo — `organizationId ===
   *    organizationId` — e era sempre verdadeira, entao a funcao retornava
   *    antes de fazer qualquer coisa;
   * 2. o corpo da requisicao enviava a organizacao ATUAL, e nao a de destino.
   *
   * O segundo teria sobrado se so o primeiro fosse corrigido.
   */

  const funcao = (() => {
    const inicio = PAINEL.indexOf("const trocarOrganizacao");
    return inicio >= 0 ? PAINEL.slice(inicio, inicio + 1400) : "";
  })();
  // Sem comentarios, para as asserçoes negativas.
  //
  // O comentario dentro da funcao explica o defeito antigo citando a
  // comparacao errada pelo nome — e e assim que ele deve continuar. Terceira
  // vez que este repositorio tropeça nisso: teste que le o texto do arquivo
  // acaba proibindo a explicacao em vez do codigo.
  const codigoDaFuncao = funcao
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

  it("o parametro nao tem o mesmo nome da organizacao ativa", () => {
    expect(codigoDaFuncao).toContain("async (destino: string)");
    expect(codigoDaFuncao).not.toContain("organizationId === organizationId");
  });

  it("envia o destino ao servidor, e nao a organizacao atual", () => {
    expect(codigoDaFuncao).toContain("organization_id: destino");
  });

  it("ainda evita recarregar quando ja se esta na organizacao escolhida", () => {
    expect(codigoDaFuncao).toContain("destino === organizationId");
  });
});
