import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { IPMLineChart } from "../components/indicators/IPMLineChart";

/**
 * A PISCADA: o tique calado apagava a tela e a silaba seguinte a reacendia.
 *
 * O motor publica um tique por segundo e declara `apuracao_disponivel: false`
 * em toda janela sem voz vozeada — que `froid_core.py` descreve como "metade de
 * qualquer consulta". O painel usava esse instante como porteiro de TODOS os
 * paineis derivados, entao cada segundo de silencio do paciente esvaziava
 * zonas, IPM, coerencia e alertas, e a primeira silaba os trazia de volta por
 * um segundo. No modo `1min` o estrago era maior: o instante derrubava
 * justamente o agregado que a janela clinica existe para segurar parado.
 *
 * `estado-da-captura.ts` ja tinha corrigido o mesmo defeito no alarme, com a
 * mesma regra — silencio clinico e dado, nao ausencia de sinal. Estes testes
 * prendem a regra tambem na apresentacao, nos dois lados: ela RETEM dentro do
 * horizonte e volta a declarar ausencia depois dele.
 *
 * Selecao por AST/nome, nunca por numero de linha.
 */
const fonte = readFileSync(join(__dirname, "../pages/LiveSession.tsx"), "utf8");
const arvore = ts.createSourceFile(
  "LiveSession.tsx",
  fonte,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);

/** Acha a declaracao pelo nome em QUALQUER profundidade: estas vivem dentro do
 *  componente de sete mil linhas, nao no topo do modulo. */
function declaracaoProfunda(nome: string): string {
  let achado: string | null = null;
  const visitar = (no: ts.Node) => {
    if (achado !== null) return;
    const bate = ts.isFunctionDeclaration(no)
      ? no.name?.text === nome
      : ts.isVariableStatement(no) &&
        no.declarationList.declarations.some((d) => d.name.getText(arvore) === nome);
    if (bate) {
      achado = no.getText(arvore);
      return;
    }
    no.forEachChild(visitar);
  };
  visitar(arvore);
  if (achado === null) throw new Error(`Declaração ausente: ${nome}`);
  return achado;
}

function executar(codigo: string, dependencias: Record<string, unknown>) {
  const js = ts.transpileModule(codigo, {
    compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  return new Function(...Object.keys(dependencias), js)(...Object.values(dependencias));
}

const NOMES = [
  "horizonteDeRetencaoSegundos",
  "idadeDaApuracao",
  "apuracaoRetida",
  "semApuracaoNaJanela",
  "displayZones",
  "displayIpm",
  "coerenciaMedida",
  "displayCoherence",
] as const;

const zonaMedida = { zone: 3, deviation_score: 0.42 };
const tiqueMedido = {
  session_id: "sessao-teste",
  timestamp_ms: 100,
  ipm_score: 57,
  coherence_status: "COERENTE",
  perception_zones: [zonaMedida],
  realtime_alerts: [],
  apuracao_disponivel: true,
  audio_meta: { voice_features_source: "real_pcm" },
};

/** Roda o portao real do painel com o estado pedido. */
function portao(opcoes: {
  /** Segundos decorridos desde a apuracao retida. */
  idade: number | null;
  clinico?: boolean;
  minutos?: number;
  conectado?: boolean;
  zonasDoAgregado?: unknown[] | null;
  coerenciaDoAgregado?: string | null;
}) {
  const {
    idade,
    clinico = false,
    minutos = clinico ? 1 : 0,
    conectado = true,
    zonasDoAgregado = null,
    coerenciaDoAgregado = null,
  } = opcoes;
  const elapsedSeconds = 600;
  const state = {
    connected: conectado,
    elapsedSeconds,
    localIpm: null,
    lastMeasured:
      idade === null
        ? null
        : { payload: tiqueMedido, atSecond: elapsedSeconds - idade },
  };
  return executar(
    `${NOMES.map(declaracaoProfunda).join("\n")}\nreturn {${NOMES.join(",")}};`,
    {
      state,
      clinicalPresentationActive: clinico,
      clinicalWindowMinutes: minutos,
      CLINICAL_MICRO_WINDOW_SECONDS: 60,
      PATIENT_AUDIO_GRACE_MS: 20_000,
      presentationAgg:
        zonasDoAgregado || coerenciaDoAgregado
          ? {
              zones: zonasDoAgregado || [],
              ipm: 55,
              coherence: coerenciaDoAgregado || undefined,
            }
          : null,
    },
  );
}

describe("silêncio do paciente não apaga a última apuração", () => {
  it("tique calado conserva zonas e IPM dentro da tolerância de 20s", () => {
    const r = portao({ idade: 5 });
    expect(r.semApuracaoNaJanela).toBe(false);
    expect(r.displayZones).toEqual([zonaMedida]);
    expect(r.displayIpm).toBe(57);
  });

  it("passado o horizonte, a tela volta a declarar ausência", () => {
    const r = portao({ idade: 21 });
    expect(r.semApuracaoNaJanela).toBe(true);
    expect(r.displayZones).toEqual([]);
    expect(r.displayIpm).toBeNull();
  });

  it("a janela clínica de 1min retém pelos 60s que ela promete", () => {
    expect(portao({ idade: 45, clinico: true, minutos: 1 }).semApuracaoNaJanela).toBe(false);
    expect(portao({ idade: 61, clinico: true, minutos: 1 }).semApuracaoNaJanela).toBe(true);
  });

  it("o horizonte acompanha a janela escolhida, não um valor fixo", () => {
    expect(portao({ idade: 45, clinico: false }).horizonteDeRetencaoSegundos).toBe(20);
    expect(portao({ idade: 45, clinico: true, minutos: 1 }).horizonteDeRetencaoSegundos).toBe(60);
    expect(portao({ idade: 45, clinico: true, minutos: 5 }).horizonteDeRetencaoSegundos).toBe(300);
  });

  it("socket caído não retém nada: não é silêncio do paciente", () => {
    const r = portao({ idade: 1, conectado: false });
    expect(r.apuracaoRetida).toBeNull();
    expect(r.displayZones).toEqual([]);
  });

  it("sem nenhuma medida na sessão, não há o que reter", () => {
    const r = portao({ idade: null });
    expect(r.idadeDaApuracao).toBeNull();
    expect(r.semApuracaoNaJanela).toBe(true);
  });

  it('"SEM_APURACAO" do agregado não apaga o painel: cai na última medida', () => {
    // O RiskChart lê essa string como ausência. Vinda do agregado de 3s ela
    // apagava o gráfico de risco enquanto as zonas ao lado seguiam na tela.
    const r = portao({ idade: 5, coerenciaDoAgregado: "SEM_APURACAO" });
    expect(r.displayCoherence).toBe("COERENTE");
    expect(r.displayZones).toEqual([zonaMedida]);
  });

  it("coerência medida no agregado continua prevalecendo", () => {
    expect(portao({ idade: 5, coerenciaDoAgregado: "DISSONANTE" }).displayCoherence).toBe(
      "DISSONANTE",
    );
  });

  it("sem apuração na janela, a coerência é vazia — nunca NEUTRO", () => {
    expect(portao({ idade: 21 }).displayCoherence).toBe("");
  });

  it("no modo clínico o agregado da janela continua tendo precedência", () => {
    const outras = [{ zone: 7, deviation_score: -0.2 }];
    const r = portao({ idade: 5, clinico: true, minutos: 1, zonasDoAgregado: outras });
    expect(r.displayZones).toEqual(outras);
  });
});

describe("o reducer guarda a última medida e o segundo em que ela foi tomada", () => {
  const { reducer, createInitialState } = executar(
    `${declaracaoProfunda("reducer")}\n${declaracaoProfunda("createInitialState")}\nreturn {reducer,createInitialState};`,
    { IPM_HISTORY_LIMIT: 1200 },
  );
  const tiqueCalado = {
    session_id: "sessao-teste",
    timestamp_ms: 200,
    ipm_score: null,
    perception_zones: [],
    realtime_alerts: [],
    apuracao_disponivel: false,
    motivo_sem_apuracao: "janela sem voz vozeada",
  };
  const vivo = () => ({ ...createInitialState(), connected: true, phase: "LIVE", elapsedSeconds: 30 });

  it("tique medido grava payload e segundo", () => {
    const r = reducer(vivo(), { type: "PAYLOAD", data: tiqueMedido });
    expect(r.lastMeasured).toEqual({ payload: tiqueMedido, atSecond: 30 });
  });

  it("tique calado NÃO derruba a última medida — só a deixa envelhecer", () => {
    const medido = reducer(vivo(), { type: "PAYLOAD", data: tiqueMedido });
    const calado = reducer({ ...medido, elapsedSeconds: 33 }, { type: "PAYLOAD", data: tiqueCalado });
    expect(calado.payload).toBe(tiqueCalado);
    expect(calado.lastMeasured).toEqual({ payload: tiqueMedido, atSecond: 30 });
    // E o histórico do IPM segue sem o tique calado: zero não é medida.
    expect(calado.ipmHistory).toEqual([57]);
  });

  it("perder a leitura limpa a retenção: socket caído não é paciente calado", () => {
    const medido = reducer(vivo(), { type: "PAYLOAD", data: tiqueMedido });
    expect(reducer(medido, { type: "WS_CLOSE" }).lastMeasured).toBeNull();
    expect(reducer(medido, { type: "SEM_LEITURA" }).lastMeasured).toBeNull();
  });
});

describe("um ponto medido sozinho continua visível", () => {
  // `M x,y` apenas move a caneta. Uma rajada curta de fala entre silêncios
  // produzia exatamente esse caminho: o SVG saía em branco com pontos medidos
  // dentro dele.
  it("desenha disco para a medida sem vizinho contíguo", () => {
    const html = renderToStaticMarkup(
      <IPMLineChart
        data={[]}
        current={null}
        elapsedSeconds={10}
        samples={[
          { second: 2, value: 55 },
          { second: 6, value: 61 },
        ]}
      />,
    );
    expect(html.match(/<circle/g)).toHaveLength(2);
  });

  it("linha contínua não vira disco: só o ponto isolado ganha marca", () => {
    const html = renderToStaticMarkup(
      <IPMLineChart
        data={[]}
        current={null}
        elapsedSeconds={10}
        samples={[
          { second: 0, value: 50 },
          { second: 1, value: 52 },
          { second: 2, value: 54 },
          { second: 8, value: 60 },
        ]}
      />,
    );
    expect(html.match(/<circle/g)).toHaveLength(1);
  });

  it("nenhuma medida, nenhum disco", () => {
    const html = renderToStaticMarkup(
      <IPMLineChart data={[]} current={null} elapsedSeconds={10} samples={[{ second: 3, value: null }]} />,
    );
    expect(html).not.toContain("<circle");
    expect(html).toContain("Aguardando serie temporal");
  });
});
