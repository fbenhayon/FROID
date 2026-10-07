/**
 * Um 401 de login, uma frase — e ela tem dono.
 *
 * O caso, 06/10/2026. Com a sessão de trabalho vencida, o painel já dizia "Sua
 * sessao expirou" no acervo de relatórios, e o botão "Presencial" recusava a
 * abertura com uma frase completa: expirou, entre de novo NESTA MESMA conta. O
 * caminho do convite remoto, ao lado, levava o profissional ao formulário de
 * início, ele preenchia tudo, e só então recebia o detalhe cru do servidor —
 * "não autenticado". A mesma recusa, duas frases de qualidade diferente, e a
 * pior delas no caminho mais usado.
 *
 * O que este arquivo guarda:
 *
 *  - a frase tem UMA fonte (seção 2.7 aplicada a texto: duas cópias divergem em
 *    silêncio, e quem corrige uma não sabe da outra);
 *  - ela diz que a conta é a mesma, porque "entre de novo" sem isso já mandou
 *    profissional procurar outro login (padrão 2.11);
 *  - os caminhos que recusam por 401 a usam, enumerados um a um — presença no
 *    repositório é mecanismo, a garantia é cada ponto se declarando (seção 3).
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { SESSAO_DE_TRABALHO_EXPIRADA } from "./sessao-de-trabalho";

const FONTE = (...caminho: string[]) =>
  readFileSync(join(__dirname, "..", ...caminho), "utf-8");

/** Os caminhos que recusam por 401 de login e têm de nomear a causa. */
const CAMINHOS = [
  ["lib", "sessao-presencial.ts"],
  ["pages", "NewPatient.tsx"],
];

describe("a frase da sessão de trabalho vencida", () => {
  it("diz o que venceu, o que fazer e que a conta é a mesma", () => {
    expect(SESSAO_DE_TRABALHO_EXPIRADA).toContain("expirou");
    expect(SESSAO_DE_TRABALHO_EXPIRADA).toContain("Entre de novo");
    expect(SESSAO_DE_TRABALHO_EXPIRADA).toContain("nesta mesma conta");
  });

  it("cada caminho que recusa por 401 a importa, em vez de reescrevê-la", () => {
    for (const caminho of CAMINHOS) {
      const fonte = FONTE(...caminho);
      expect(
        fonte,
        `${caminho.join("/")} não importa a frase da fonte única`,
      ).toContain("SESSAO_DE_TRABALHO_EXPIRADA");
      expect(
        fonte,
        `${caminho.join("/")} tem uma cópia literal da frase`,
      ).not.toContain(SESSAO_DE_TRABALHO_EXPIRADA);
    }
  });

  it("o convite separa o 401 do resto das recusas", () => {
    // Sem este recorte o 401 voltaria a sair como "não autenticado", que é o
    // detalhe do servidor e não uma instrução a quem está atendendo. As outras
    // recusas desta rota têm código próprio — 402 de crédito, 403 de acesso — e
    // continuam mostrando o detalhe delas.
    const novoPaciente = FONTE("pages", "NewPatient.tsx");
    expect(novoPaciente).toContain("response.status === 401");
    expect(novoPaciente).toContain('data?.detail || "Não foi possível criar o convite."');
  });
});
