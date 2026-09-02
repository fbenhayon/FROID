import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { bloqueadoPorSaldo } from "../lib/product-choice";

const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const AVISO = readFileSync(join(__dirname, "AvisoSemSaldo.tsx"), "utf-8");

const usuario = (acesso: Record<string, unknown>) => ({ access_status: acesso } as never);

describe("quem ficou sem saldo vê a causa, e não uma tela sem relação", () => {
  /**
   * O defeito, vivido em 02/09/2026: `onboarding_required` fica verdadeiro
   * quando o saldo zera. O roteador mandava a pessoa para onde ela resolveria
   * isso — e para conta administradora, para /admin, por uma correção anterior
   * que evitava outro círculo. Só que /admin não vende sessão.
   *
   * O Fábio caiu numa tela sem relação com o problema, sem uma linha
   * explicando, e toda tentativa de ir ao painel era devolvida para lá. Ele
   * descobriu a causa lendo o código-fonte; um cliente não teria como.
   */

  it("saldo zerado com perfil existente é bloqueio de saldo", () => {
    expect(
      bloqueadoPorSaldo(
        usuario({ onboarding_required: true, has_profile: true, remaining_sessions: 0 }),
      ),
    ).toBe(true);
  });

  it("cobrança pendente também bloqueia, mesmo com saldo", () => {
    expect(
      bloqueadoPorSaldo(
        usuario({
          onboarding_required: true,
          has_profile: true,
          remaining_sessions: 10,
          pending_settlement_count: 3,
        }),
      ),
    ).toBe(true);
  });

  it("avaliação esgotada bloqueia", () => {
    expect(
      bloqueadoPorSaldo(
        usuario({ onboarding_required: true, has_profile: true, trial_exhausted: true }),
      ),
    ).toBe(true);
  });

  it("QUEM NUNCA SE CADASTROU não é bloqueio de saldo", () => {
    // A distinção que importa: sem perfil não há saldo que possa ter acabado,
    // e o caminho certo continua sendo o formulário. Confundir os dois mandaria
    // todo cadastro novo para uma tela de "suas sessões acabaram".
    expect(
      bloqueadoPorSaldo(
        usuario({ onboarding_required: true, has_profile: false, remaining_sessions: 0 }),
      ),
    ).toBe(false);
  });

  it("quem tem saldo e está em dia não vê nada disso", () => {
    expect(
      bloqueadoPorSaldo(
        usuario({ onboarding_required: false, has_profile: true, remaining_sessions: 5 }),
      ),
    ).toBe(false);
  });

  it("usuário ausente não quebra a checagem", () => {
    expect(bloqueadoPorSaldo(null)).toBe(false);
    expect(bloqueadoPorSaldo(undefined)).toBe(false);
  });
});

describe("o aviso é alcançável e oferece saída", () => {
  it("/dashboard renderiza o aviso em vez de redirecionar", () => {
    // Redirecionar era o que prendia. A rota tem de mostrar, não desviar.
    const rota = APP.slice(APP.indexOf('path="/dashboard"'));
    const proxima = rota.indexOf('path="', 20);
    const bloco = rota.slice(0, proxima > 0 ? proxima : rota.length);
    expect(bloco).toContain("bloqueadoPorSaldo(user)");
    expect(bloco).toContain("<AvisoSemSaldo");
  });

  it("a verificação de saldo vem ANTES da de cadastro", () => {
    // Invertida, `onboardingRequired` capturaria os dois casos e o aviso nunca
    // apareceria — que é exatamente o estado anterior.
    const rota = APP.slice(APP.indexOf('path="/dashboard"'));
    expect(rota.indexOf("bloqueadoPorSaldo(user)")).toBeLessThan(
      rota.indexOf("onboardingRequired(user)"),
    );
  });

  it("o aviso nomeia a causa, e são três distintas", () => {
    expect(AVISO).toContain("Suas sessões acabaram");
    expect(AVISO).toContain("Há cobrança pendente de acerto");
    expect(AVISO).toContain("O período de avaliação terminou");
  });

  it("o aviso oferece caminho de saída, e não só explicação", () => {
    expect(AVISO).toContain('to="/access/register"');
    expect(AVISO).toContain("suporte@froid.com.br");
  });

  it("o administrador ganha o caminho de volta que não existia", () => {
    expect(AVISO).toContain('to="/admin"');
    expect(AVISO).toContain("admin &&");
  });

  it("diz o que continua funcionando, para não parecer perda de dados", () => {
    expect(AVISO).toContain("continuam acessíveis");
  });
});
