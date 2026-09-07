import type { MetricSnapshot } from "./session-report";

/**
 * A tabela de métricas no vocabulário que o FROID Explica entende.
 *
 * POR QUE ISTO EXISTE. Em 07/09/2026 o profissional perguntou, lendo um
 * relatório de sessão encerrada, "qual a utilidade desse marcador MFCC7". A
 * resposta abriu com "O valor do MFCC7 nesta sessão não foi enviado pelo
 * painel" — verdade, e inútil: o número estava na tela dele, três centímetros
 * acima da caixa de pergunta.
 *
 * A causa: só o `LiveSession` passava `getLiveContext` ao `AIInsights`. As
 * telas de relatório e de paciente montam a mesma tabela, a partir do mesmo
 * `MetricSnapshot`, e mandavam ao Explica tudo menos ela. É o padrão 2.1 de
 * novo — a peça existe, está correta, e nada a consome.
 *
 * POR QUE UM MÓDULO E NÃO UMA CÓPIA. Cada tela escreve o rótulo do seu jeito:
 * `TOM` na sessão ao vivo, `Tom` no relatório; `JITTER` contra `Jitter idx.`;
 * `DELTA` contra `Delta 0.5-4Hz`. O glossário do servidor casa por rótulo, e
 * um terceiro dialeto faria a busca falhar em silêncio, devolvendo de novo
 * "não foi enviado" sobre um número presente. Aqui os rótulos são os
 * CANÔNICOS — os mesmos da tabela do `LiveSession`, que é o que o servidor
 * conhece —, e as tabelas visíveis de cada tela continuam como estão.
 *
 * `test_explica_clinico_glossario` confronta esta lista com a que o
 * `LiveSession` renderiza: rótulo novo num lado sem o outro quebra o teste.
 */

/** Mesma regra do painel: ausência vira "--", nunca zero. */
function fmt(value: unknown, digits: number): string {
  if (value === null || value === undefined || value === "") return "--";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

/**
 * Pares [rótulo canônico, valor como texto] de um snapshot.
 *
 * Não inclui `CORTE`: a janela em análise é conceito da sessão ao vivo, e num
 * relatório fechado ela seria a sessão inteira — dizer "CORTE" ali seria um
 * rótulo prometendo o que não entrega.
 */
export function metricasParaOExplica(
  snapshot: MetricSnapshot | null | undefined,
): Array<[string, string]> {
  if (!snapshot) return [];
  return [
    ["IPM", fmt(snapshot.ipmAvg, 1)],
    ["IDM", fmt(snapshot.idmAvg, 2)],
    ["ZONAS", snapshot.dominantZone ? `Zona ${snapshot.dominantZone}` : "--"],
    ["TOM", snapshot.emotionalTone || "--"],
    ["P/MIN", fmt(snapshot.wordsPerMinute, 1)],
    ["DISSO.", fmt(snapshot.dissonanceCount, 0)],
    ["MFCC7", fmt(snapshot.mfcc7, 3)],
    ["MFCC9", fmt(snapshot.mfcc9, 3)],
    ["DMFCC7", fmt(snapshot.mfcc7Delta, 4)],
    ["DMFCC9", fmt(snapshot.mfcc9Delta, 4)],
    ["DDMFCC7", fmt(snapshot.mfcc7DeltaDelta, 4)],
    ["DDMFCC9", fmt(snapshot.mfcc9DeltaDelta, 4)],
    ["F0 MED.", fmt(snapshot.f0Mean, 2)],
    ["ZCR", fmt(snapshot.zcr, 3)],
    ["JITTER", fmt(snapshot.jitter, 3)],
    ["SHIMMER", fmt(snapshot.shimmer, 3)],
    ["DELTA", fmt(snapshot.spectralDelta0_4, 3)],
    ["THETA", fmt(snapshot.spectralTheta4_8, 3)],
    ["ALPHA", fmt(snapshot.spectralAlpha8_12, 3)],
    ["BETA", fmt(snapshot.spectralBeta12_30, 3)],
    ["GAMA", fmt(snapshot.spectralGamma30_80, 3)],
    ["IND. ESPECTRAL", fmt(snapshot.spectralBandIndex, 3)],
    ["SUB-H 5-12", fmt(snapshot.subharmonic5_12, 3)],
    ["SUB-H 12-20", fmt(snapshot.subharmonic12_20, 3)],
    ["SUB-H 20-40", fmt(snapshot.subharmonic20_40, 3)],
    ["VOCAL 85-165", fmt(snapshot.vocalBasal85_165, 3)],
    ["DNA INFRA", fmt(snapshot.dnaInfrasoundNuclear, 3)],
    ["DNA LIMBICO", fmt(snapshot.dnaLimbicModulation, 3)],
    ["DNA VOCAL", fmt(snapshot.dnaVocalBasalTension, 3)],
    ["DNA FLOOD", fmt(snapshot.dnaAutonomicFlooding, 3)],
    ["DNA SHUTDOWN", fmt(snapshot.dnaDissociativeShutdown, 3)],
    ["DNA NEURO", fmt(snapshot.dnaNeurogenicResonance, 3)],
    ["DNA SOMATO", fmt(snapshot.dnaSomatoaffectiveDissonance, 3)],
  ];
}

/**
 * O objeto pronto para entrar no contexto do FROID Explica.
 *
 * `janela` diz DE QUE recorte são os números — média da sessão, um corte de
 * dez minutos, a linha de base. Sem isso o assistente falaria de "esta sessão"
 * sobre a média de um corte, e o profissional não teria como perceber.
 */
export function contextoDaTabela(
  snapshot: MetricSnapshot | null | undefined,
  janela: string,
): Record<string, unknown> {
  const metricas = metricasParaOExplica(snapshot);
  if (!metricas.length) return {};
  return {
    panel_metrics: Object.fromEntries(metricas),
    panel_metrics_window: janela,
  };
}
