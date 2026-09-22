import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { IPMLineChart } from "../components/indicators/IPMLineChart";
import MapaZonalFroid from "../components/charts/MapaZonalFroid";
it("preserva lacunas e valores recebidos sem suavizar", () => {
 const html=renderToStaticMarkup(<IPMLineChart data={[]} current={60} elapsedSeconds={4}
 samples={[{second:0,value:40},{second:1,value:60},{second:2,value:null},{second:4,value:60}]} />);
 const path=html.match(/<path d="([^"]+)"[^>]*stroke="#22f58b"/)?.[1];
 expect(path).toBeDefined();
 expect(path?.match(/M/g)).toHaveLength(2);
 expect(path?.match(/L/g)).toHaveLength(1);
 expect(path).not.toContain("C ");
 expect(html).toContain("-4s");
});
it("nao apresenta ultimo ponto nem qualidade como leitura atual", () => {
 const html=renderToStaticMarkup(<IPMLineChart data={[50,51]} current={null}/>);
 expect(html).toContain("Sem leitura atual");
 expect(html).not.toContain("<circle");
 expect(html).not.toContain("Excelente");
});
it("IDM ausente nao desenha neutralidade medida", () => {
 const html=renderToStaticMarkup(<MapaZonalFroid zones={[]} />);
 expect(html).toContain("Sem apura");
 expect(html).not.toContain("<circle");
});
