/** Tela de resgate de convite de equipe: cada erro do backend vira uma frase
 *  que diz o proximo passo, e o formulario abre com o codigo do link ja no
 *  campo. Sem DOM: render estatico, como o resto da suite do painel. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { EntrarNaClinicaPage, mensagemDoErro } from "./EntrarNaClinica";

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
