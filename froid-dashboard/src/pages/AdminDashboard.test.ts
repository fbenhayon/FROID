import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { pendenciaDoAdministrador } from "./AdminDashboard";

/**
 * O painel de administracao nao pode ter o "Sair" como unica saida.
 *
 * Historico do defeito, em duas camadas. Primeiro o botao "Dashboard" levava a
 * uma tela que devolvia a pessoa para ca — beco silencioso: clicava, a URL
 * mudava, nada acontecia. A correcao escondeu o botao quando ele nao levaria a
 * lugar nenhum, o que era honesto e produziu um beco PIOR: sobrou um botao so
 * na tela, e era o de encerrar a sessao. Num dia de atendimento, a unica saida
 * do painel administrativo era deslogar.
 *
 * Botao escondido nao informa. Dizer o que falta e oferecer a porta que
 * resolve informa.
 */

const PAGINA = readFileSync(join(__dirname, "AdminDashboard.tsx"), "utf-8");
const PAGINA_CORRIDA = PAGINA.replace(/\s+/g, " ");

function usuario(acesso: Record<string, unknown>) {
  return { access_status: { admin: true, ...acesso } } as never;
}

describe("por que o painel clínico não está alcançável", () => {
  it("não acusa pendência quando não há onboarding pendente", () => {
    expect(pendenciaDoAdministrador(usuario({ onboarding_required: false }))).toBeNull();
  });

  it("aponta a escolha de produto quando não há cadastro", () => {
    const p = pendenciaDoAdministrador(
      usuario({ onboarding_required: true, has_profile: false }),
    );
    expect(p?.destino).toBe("/access/produto");
  });

  it("aponta o plano quando falta plano", () => {
    const p = pendenciaDoAdministrador(
      usuario({ onboarding_required: true, has_profile: true, selected_plan: "" }),
    );
    expect(p?.destino).toBe("/access/register");
    expect(p?.motivo).toMatch(/plano de sess/i);
  });

  it("aponta o saldo quando há plano mas não há sessões", () => {
    const p = pendenciaDoAdministrador(
      usuario({
        onboarding_required: true,
        has_profile: true,
        selected_plan: "pro_10",
        remaining_sessions: 0,
      }),
    );
    expect(p?.motivo).toMatch(/saldo/i);
  });

  it("não oferece botão quando a pendência é aprovação — não há o que clicar", () => {
    // Oferecer uma porta que não resolve é pior que não oferecer: manda a
    // pessoa procurar solução onde não há.
    const p = pendenciaDoAdministrador(
      usuario({ onboarding_required: true, manual_approval_pending: true }),
    );
    expect(p?.rotulo).toBe("");
  });

  it("sempre devolve um motivo legível quando há pendência", () => {
    const p = pendenciaDoAdministrador(usuario({ onboarding_required: true, has_profile: true, selected_plan: "x", remaining_sessions: 5 }));
    expect(p?.motivo).toBeTruthy();
  });
});

describe("a tela nunca fica só com o Sair", () => {
  it("oferece o NR-1, que não depende do onboarding clínico", () => {
    // A empresa NR-1 do administrador não passa pelo onboarding clínico, então
    // esta porta continua aberta mesmo quando a outra não está.
    expect(PAGINA).toContain('nav("/nr1")');
  });

  it("quando o Dashboard não leva a lugar nenhum, oferece a porta que resolve", () => {
    expect(PAGINA).toContain("pendencia?.rotulo &&");
    expect(PAGINA).toContain("nav(pendencia.destino)");
  });

  it("explica na tela, e não só no title do botão", () => {
    expect(PAGINA_CORRIDA).toMatch(/painel de atendimento n[aã]o est[aá] acess[ií]vel/i);
  });

  it("separa administrar a plataforma de atender pacientes", () => {
    // É a confusão que criou o problema: as duas coisas foram amarradas, e
    // quem administra ficou preso ao onboarding de quem atende.
    expect(PAGINA_CORRIDA).toMatch(/uma n[aã]o depende da outra/i);
  });
});
