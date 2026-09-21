import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DiagnosticoAcustico } from "../components/indicators/DiagnosticoAcustico";

// Exercita as funções reais do componente sem iniciar câmera, roteador ou
// WebSockets durante o teste. Seleção por AST/nome, nunca por número de linha.
const fonte = readFileSync(join(__dirname, "../pages/LiveSession.tsx"), "utf8");
const arvore = ts.createSourceFile("LiveSession.tsx", fonte, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
function executar(codigo: string, dependencias: Record<string, unknown> = {}) {
  const js = ts.transpileModule(codigo, { compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 } }).outputText;
  return new Function(...Object.keys(dependencias), js)(...Object.values(dependencias));
}
function declaracao(nome: string) {
  const no = arvore.statements.find((s) =>
    ts.isFunctionDeclaration(s) ? s.name?.text === nome
      : ts.isVariableStatement(s) && s.declarationList.declarations.some((d) => d.name.getText(arvore) === nome));
  if (!no) throw new Error(`Declaração ausente: ${nome}`);
  return no.getText(arvore);
}
const { reducer, createInitialState } = executar(
  `${declaracao("reducer")}\n${declaracao("createInitialState")}\nreturn {reducer,createInitialState};`,
  { IPM_HISTORY_LIMIT: 1200 },
);
const Aviso = executar(`${declaracao("AvisoDeApuracao")}\nreturn AvisoDeApuracao;`, { React, DiagnosticoAcustico });
const leitura = { session_id: "sessao-teste", timestamp_ms: 100, ipm_score: 42,
  perception_zones: [], realtime_alerts: [], apuracao_disponivel: true,
  audio_meta: { voice_features_source: "real_pcm" } };

describe("o painel invalida medidas quando perde a leitura atual", () => {
  it.each(["WS_CLOSE", "SEM_LEITURA"])("%s limpa medidas e conserva histórico", (type) => {
    const historico = [42];
    const anterior = { ...createInitialState(), connected: true, payload: leitura,
      aggregated: { ipm: 42 }, localIpm: 42, ipmHistory: historico };
    const proximo = reducer(anterior, { type });
    expect(proximo.payload).toBeNull();
    expect(proximo.aggregated).toBeNull();
    expect(proximo.localIpm).toBeNull();
    expect(proximo.ipmHistory).toBe(historico);
    const reaberto = reducer(proximo, { type: "WS_OPEN" });
    expect(reaberto.connected).toBe(true);
    expect(reaberto.payload).toBeNull();
    expect(reaberto.aggregated).toBeNull();
    expect(reducer(reaberto, { type: "AGGREGATE", agg: { ipm: 42 } }).aggregated).toBeNull();
    expect(reducer(reaberto, { type: "PAYLOAD", data: leitura }).payload).toBe(leitura);
  });
});

function ligarHandlers() {
  const atrib: string[] = [];
  function visitar(no: ts.Node, naAnalise = false) {
    const dentro = naAnalise || (ts.isCallExpression(no) && no.expression.getText(arvore) === "useEffect"
      && no.getText(arvore).includes("/ws/fusion/"));
    if (dentro && ts.isBinaryExpression(no) && ["socket.onmessage", "socket.onclose"].includes(no.left.getText(arvore))) {
      atrib.push(no.getText(arvore));
    }
    no.forEachChild((filho) => visitar(filho, dentro));
  }
  visitar(arvore);
  expect(atrib).toHaveLength(2);
  const socket: any = {};
  const contexto = {
    socket, cancelled: false, wsRef: { current: socket }, sessionId: "sessao-teste",
    wsLastMessageAtRef: { current: 0 }, elapsedSecondsRef: { current: 10 },
    patientTrackUsable: vi.fn(() => true), attributedSpeakerRef: { current: null },
    directLocalMetricsActiveRef: { current: false }, firstPatientMetricSecondRef: { current: null },
    sessionSamplesRef: { current: [] }, frameBuffer: { current: [leitura] },
    dispatch: vi.fn(), setLiveTranscription: vi.fn(), console: { error: vi.fn() },
    deveReconectarAnalise: () => true, motivoDaRecusaDeSinalizacao: () => "Recusado",
    setRecusaDaAnalise: vi.fn(), scheduleConnect: vi.fn(), attempt: 0,
  };
  executar(atrib.join(";\n"), contexto);
  return contexto;
}

describe("mensagens do canal de análise não mantêm leitura obsoleta", () => {
  it("socket substituído não publica dados nem fecha a conexão nova", () => {
    const c = ligarHandlers();
    c.wsRef.current = {};
    c.socket.onmessage({ data: JSON.stringify(leitura) });
    c.socket.onclose({ code: 1006 });
    expect(c.dispatch).not.toHaveBeenCalled();
    expect(c.scheduleConnect).not.toHaveBeenCalled();
    expect(c.wsLastMessageAtRef.current).toBe(0);
  });
  it.each(["{", "{}", JSON.stringify({ ...leitura, session_id: "outra" })])("mensagem inválida %s limpa leitura sem renovar watchdog", (data) => {
    const c = ligarHandlers();
    c.socket.onmessage({ data });
    expect(c.dispatch).toHaveBeenCalledWith({ type: "SEM_LEITURA" });
    expect(c.frameBuffer.current).toEqual([]);
    expect(c.wsLastMessageAtRef.current).toBe(0);
    expect(c.sessionSamplesRef.current).toEqual([]);
  });
  it("trilha recusada não mantém medidas da trilha anterior", () => {
    const c = ligarHandlers();
    c.patientTrackUsable.mockReturnValue(false);
    c.socket.onmessage({ data: JSON.stringify(leitura) });
    expect(c.dispatch).toHaveBeenCalledWith({ type: "SEM_LEITURA" });
    expect(c.frameBuffer.current).toEqual([]);
    expect(c.sessionSamplesRef.current).toEqual([]);
  });
  it("a próxima leitura válida volta a alimentar painel e registro", () => {
    const c = ligarHandlers();
    c.socket.onmessage({ data: JSON.stringify(leitura) });
    expect(c.dispatch).toHaveBeenCalledWith({ type: "PAYLOAD", data: leitura });
    expect(c.wsLastMessageAtRef.current).toBeGreaterThan(0);
    expect(c.sessionSamplesRef.current).toEqual([{ elapsedSeconds: 10, payload: leitura }]);
  });
  it("queda do canal limpa os frames aguardando agregação", () => {
    const c = ligarHandlers();
    c.socket.onclose({ code: 1006 });
    expect(c.frameBuffer.current).toEqual([]);
    expect(c.dispatch).toHaveBeenCalledWith({ type: "WS_CLOSE" });
  });
});

const avisoBase = { semFace: false, semVoz: false, silencioProlongado: false,
  presencialSemCamera: false, causaNoPaciente: "", recusaDaAnalise: "", aguardandoAnalise: "",
  diagnosticoAcustico: null, onReligarAnalise: () => {} };
describe("o aviso informa o que foi medido e não inventa a causa", () => {
  it("ausência de vozeamento não afirma sinal fraco nem 60 segundos medidos", () => {
    const html = renderToStaticMarkup(<Aviso {...avisoBase} silencioProlongado />);
    expect(html).toContain("Áudio recebido, mas sem voz reconhecida");
    expect(html).not.toContain("sinal está fraco");
    expect(html).not.toContain("60 segundos");
    expect(html).toContain("não informou o diagnóstico");
  });
  it("desconexão tem prioridade sobre o último relato de silêncio", () => {
    const html = renderToStaticMarkup(<Aviso {...avisoBase} silencioProlongado aguardandoAnalise="Reconectando." />);
    expect(html).toContain("Sem leitura atual");
    expect(html).not.toContain("Áudio recebido");
  });
  it("erro reportado pelo paciente aparece mesmo antes do próximo tick", () => {
    const html = renderToStaticMarkup(<Aviso {...avisoBase} causaNoPaciente="Falha de rede" />);
    expect(html).toContain("Falha de rede");
    expect(html).toContain("Sem capacidade de apuração");
  });
  it("diagnóstico distingue zero medido de dado ausente", () => {
    const html = renderToStaticMarkup(<DiagnosticoAcustico diagnostico={{
      estado: "sem_vozeamento", rms: 0, loudness_dbfs: null, f0_voiced_ratio: 0,
      sample_rate_hz: 48000, captura_cliente: { mesmo_dispositivo: true, audio_bruto: false },
    }} />);
    expect(html).toContain("0.00000");
    expect(html).toContain("0.0%");
    expect(html).toContain("48000 Hz");
    expect(html).toContain("não registrado");
    expect(html).not.toContain("NaN");
  });
});
