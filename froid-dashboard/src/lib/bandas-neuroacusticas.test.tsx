import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { SpectralBandsChart } from "../components/indicators/SpectralBandsChart";
import type { AcousticBiomarkers } from "./froid-engine";

const render = (values: Record<string, unknown> | null) => renderToStaticMarkup(
  <SpectralBandsChart audioMeta={values as (AcousticBiomarkers & Record<string, unknown>) | null} />,
);

it("declara ausência sem inventar barras, índice ou duração", () => {
  const html = render(null);
  expect(html).toContain("Sem Capacidade de Apuração");
  expect(html).toContain("não informada");
  expect(html).not.toContain('role="meter"');
  expect(html).not.toContain("1000");
});

it("preserva zero medido e distingue as bandas ausentes", () => {
  const html = render({ spectral_delta_0_4hz: 0, spectral_band_index: 0 });
  expect(html.match(/role="meter"/g)).toHaveLength(1);
  expect(html).toContain('aria-valuenow="0"');
  expect(html).toContain("width:0%");
  expect(html).toContain("sem apuração");
  expect(html).not.toContain("nenhuma banda foi recebida");
});

it("mantém escala fixa mesmo quando a maior banda muda", () => {
  for (const theta of [0.3, 0.8]) {
    const html = render({ spectral_delta_0_4hz: 0.2, spectral_theta_4_8hz: theta });
    expect(html).toContain("width:20%");
    expect(html).toContain('aria-valuenow="20"');
    expect(html).toContain("0–100%");
    expect(html).toContain("Modulações mais lentas");
  }
});

it("não converte valores inválidos em medidas", () => {
  const html = render({ spectral_delta_0_4hz: NaN, spectral_theta_4_8hz: Infinity, spectral_band_index: null });
  expect(html).not.toContain('role="meter"');
  expect(html).toContain("Sem Capacidade de Apuração");
});
