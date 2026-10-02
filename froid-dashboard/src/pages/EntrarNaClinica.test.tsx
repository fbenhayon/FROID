/** Tela de resgate de convite de equipe: cada erro do backend vira uma frase
 *  que diz o proximo passo, e o formulario abre com o codigo do link ja no
 *  campo. Sem DOM: render estatico, como o resto da suite do painel. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import {
  EntrarNaClinicaPage,
  mensagemDoErro,
  situacaoDoConvite,
} from "./EntrarNaClinica";

it("situacaoDoConvite distingue os quatro estados diante da conta logada", () => {
  const base = {
    clinic_name: "Clinica X",
    invited_email: "convidado@x.com",
    roles: ["professional"],
    status: "pending",
    expired: false,
  };
  expect(situacaoDoConvite("convidado@x.com", null)).toBe("sem_detalhes");
  expect(situacaoDoConvite("convidado@x.com", { ...base, expired: true })).toBe("indisponivel");
  expect(situacaoDoConvite("convidado@x.com", { ...base, status: "accepted" })).toBe("indisponivel");
  expect(situacaoDoConvite("outro@x.com", base)).toBe("email_divergente");
  // Casa a identidade ignorando caixa/espaco; o backend tambem normaliza.
  expect(situacaoDoConvite("  Convidado@X.com ", base)).toBe("pronto");
});

it("cada codigo de erro vira a orientacao certa, distinta uma da outra", () => {
  const porOutroEmail = mensagemDoErro(403, "convite destinado a outro email");
  const limite = mensagemDoErro(409, "limite de profissionais do plano atingido");
  const inativo = mensagemDoErro(402, "plano FROID inativo");
  const invalido = mensagemDoErro(404, "convite inválido ou expirado");

  expect(porOutroEmail).toContain("outro e-mail");
  expect(limite).toContain("limite de profissionais");
  expect(inativo).toContain("inativo");
  expect(invalido.toLowerCase()).toContain("expirado");

  // Nenhuma mensagem pode colidir com outra: o convidado precisa saber QUAL
  // dos quatro problemas e o dele.
  const todas = [porOutroEmail, limite, inativo, invalido];
  expect(new Set(todas).size).toBe(4);
});

it("erro sem codigo conhecido usa o detalhe do servidor e nunca fica vazio", () => {
  expect(mensagemDoErro(500, "erro interno")).toBe("erro interno");
  expect(mensagemDoErro(500, "")).not.toHaveLength(0);
});

it("o formulario abre com o codigo que veio no link", () => {
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={["/entrar-clinica?token=CODIGO-DO-LINK"]}>
      <EntrarNaClinicaPage />
    </MemoryRouter>,
  );
  expect(html).toContain("Entrar numa clínica");
  expect(html).toContain("Código de convite");
  expect(html).toContain("CODIGO-DO-LINK");
});
