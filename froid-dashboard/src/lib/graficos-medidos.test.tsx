import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";

// Os dois tracos do IPM sao ancorados por `data-linha`, e nao pela cor: em
// 22/09/2026 a ponte tracejada entrou usando o mesmo verde da linha medida — e
// correto, e a mesma serie — e este teste, que casava por `stroke="#22f58b"`,
// passou a ler o caminho errado e falhou. Cor e cosmetico; papel e contrato.
const caminho = (html: string, papel: string) =>
  html.match(new RegExp(`<path[^>]*data-linha="${papel}"[^>]*d="([^"]+)"`))?.[1]
  ?? html.match(new RegExp(`<path[^>]*d="([^"]+)"[^>]*data-linha="${papel}"`))?.[1];

const AMOSTRAS = [
  { second: 0, value: 40 },
  { second: 1, value: 60 },
  { second: 2, value: null },
  { second: 4, value: 60 },
];

it("preserva lacunas e valores recebidos sem suavizar", () => {
  const html = renderToStaticMarkup(
    <IPMLineChart data={[]} current={60} elapsedSeconds={4} samples={AMOSTRAS} />,
  );
  const medida = caminho(html, "medida");
  expect(medida).toBeDefined();
  // Dois `M` e um `L`: o segundo 4 NAO e ligado ao segundo 1 por cima do
  // buraco. E esta e a garantia — desenhar por cima da lacuna afirmaria uma
  // medida que ninguem tomou.
  expect(medida?.match(/M/g)).toHaveLength(2);
  expect(medida?.match(/L/g)).toHaveLength(1);
  expect(medida).not.toContain("C ");
  expect(html).toContain("-4s");
});

it("a ponte atravessa a lacuna, e se declara tracejada", () => {
  const html = renderToStaticMarkup(
    <IPMLineChart data={[]} current={60} elapsedSeconds={4} samples={AMOSTRAS} />,
  );
  const ponte = caminho(html, "ponte");
  expect(ponte).toBeDefined();
  // A ponte liga os tres pontos MEDIDOS em sequencia: um `M` e dois `L`. Ela
  // existe para o profissional ler a trajetoria de relance (pedido de
  // 22/09/2026) e nao acrescenta ponto nenhum — so liga os que foram medidos.
  expect(ponte?.match(/M/g)).toHaveLength(1);
  expect(ponte?.match(/L/g)).toHaveLength(2);
  // Tracejada, e dito por escrito na tela. Traco cheio sobre o buraco seria a
  // mentira que a linha medida evita; tracejado sem legenda seria a mesma
  // mentira, so que silenciosa.
  expect(html).toMatch(/data-linha="ponte"[^>]*stroke-dasharray|stroke-dasharray[^>]*data-linha="ponte"/);
  expect(html).toContain("sem apura");
});

it("um ponto medido entre silencios continua visivel", () => {
  // Fala em rajada curta: um unico segundo medido, sem vizinho contiguo. Sem o
  // disco proprio o SVG fica em branco com medida dentro dele.
  const html = renderToStaticMarkup(
    <IPMLineChart
      data={[]}
      current={55}
      elapsedSeconds={6}
      samples={[
        { second: 0, value: 50 },
        { second: 1, value: null },
        { second: 3, value: 55 },
        { second: 4, value: null },
        { second: 6, value: 52 },
      ]}
    />,
  );
  expect(html).toContain("<circle");
});

it("nao apresenta ultimo ponto nem qualidade como leitura atual", () => {
  const html = renderToStaticMarkup(<IPMLineChart data={[50, 51]} current={null} />);
  expect(html).toContain("Sem leitura atual");
  expect(html).not.toContain("<circle");
  expect(html).not.toContain("Excelente");
});

it("IDM ausente nao desenha neutralidade medida", () => {
  const html = renderToStaticMarkup(<MapaZonalFroid zones={[]} />);
  expect(html).toContain("Sem apura");
  expect(html).not.toContain("<circle");
});
