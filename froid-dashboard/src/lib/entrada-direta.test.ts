import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { alvoDaEntradaDireta, ENTRADAS_DIRETAS } from "./entrada-direta";

/**
 * O convite do trabalhador chegava como tela de login.
 *
 * Apurado em 26/08/2026, no teste ponta a ponta: aberto em janela anônima,
 * `https://www.froid.com.br/avaliacao?token=…` virava
 * `https://www.froid.com.br/avaliacao?token=…#/login`. Sem erro, sem
 * mensagem — o trabalhador via um formulário de senha que não tem, e o
 * convite morria ali.
 *
 * A causa era de ORDEM, não de lógica. A reescrita rodava num `useEffect` do
 * App, e a essa altura o HashRouter já havia sido construído sem `#`, assumido
 * "/" e redirecionado para o login, escrevendo `#/login`. A primeira linha da
 * função era `if (hash) return` — guarda correta, consultada tarde demais.
 *
 * Estes testes travam as duas coisas: o que a função decide, e QUANDO ela é
 * chamada. O segundo é o que importa — a lógica sempre esteve certa.
 */

const MAIN = readFileSync(join(__dirname, "..", "main.tsx"), "utf-8");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");

describe("o token sobrevive à entrada direta", () => {
  it("leva o token do convite para dentro da rota", () => {
    expect(
      alvoDaEntradaDireta("/avaliacao", "?token=abc123", ""),
    ).toBe("/app/#/avaliacao?token=abc123");
  });

  it("preserva a query inteira, não só o primeiro parâmetro", () => {
    expect(
      alvoDaEntradaDireta("/avaliacao", "?token=abc&origem=sms", ""),
    ).toBe("/app/#/avaliacao?token=abc&origem=sms");
  });

  it("aceita o caminho com e sem o prefixo /app", () => {
    expect(alvoDaEntradaDireta("/app/avaliacao", "?token=x", "")).toBe(
      "/app/#/avaliacao?token=x",
    );
  });

  it("não diferencia maiúscula, porque o link é digitado por gente", () => {
    expect(alvoDaEntradaDireta("/Avaliacao", "?token=x", "")).toBe(
      "/app/#/avaliacao?token=x",
    );
  });

  it("não mexe em caminho que não é entrada direta", () => {
    expect(alvoDaEntradaDireta("/qualquer/outro", "?token=x", "")).toBeNull();
  });

  it("respeita o hash que já existe", () => {
    // Quem já pediu uma tela não deve ser levado para outra.
    expect(
      alvoDaEntradaDireta("/avaliacao", "?token=x", "#/paciente"),
    ).toBeNull();
  });
});

describe("a reescrita roda antes de o roteador existir", () => {
  /**
   * Este bloco é o defeito de 26/08/2026, e é o único que o impede de voltar.
   * A função pode estar perfeita: chamada depois do primeiro render, ela
   * encontra `#/login` na URL e desiste — que foi exatamente o que aconteceu.
   */

  it("main.tsx chama a normalização antes do createRoot", () => {
    const chamada = MAIN.indexOf("normalizarEntradaDireta()");
    const montagem = MAIN.indexOf("ReactDOM.createRoot");
    expect(chamada).toBeGreaterThan(-1);
    expect(montagem).toBeGreaterThan(-1);
    expect(chamada).toBeLessThan(montagem);
  });

  it("o App não normaliza mais dentro de efeito", () => {
    // Um efeito roda depois do render, e depois do render a URL já foi
    // decidida pelo roteador. Se isto reaparecer, o convite quebra de novo.
    expect(APP).not.toContain("normalizeDirectPublicPath");
    expect(APP).not.toContain("normalizarEntradaDireta");
  });

  it("a rota /avaliacao continua existindo no roteador", () => {
    // A reescrita aponta para cá. Renomear a rota sem mexer no mapa devolveria
    // o mesmo sintoma por outro caminho.
    expect(APP).toContain('path="/avaliacao"');
    expect(Object.values(ENTRADAS_DIRETAS)).toContain("/avaliacao");
  });
});
