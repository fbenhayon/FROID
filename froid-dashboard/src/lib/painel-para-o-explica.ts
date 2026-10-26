import type { MetricSnapshot } from "./session-report";
import { findSummaryForCut, type ResumoDoCorte } from "./resumo-do-corte";

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

/**
 * Um corte no vocabulário do glossário, com o tema e o resumo daquele trecho.
 *
 * POR QUE EXISTE. Em 15/10/2026, na sessão froid-mv85lqul447x, o profissional
 * pediu "o valor das palavras por minuto por corte e os percentuais de
 * variação". O relatório mandava os oito cortes inteiros, com doze zonas cada
 * um, dentro de um JSON de 105 mil caracteres — e o servidor guardava os
 * primeiros cinco mil. O corte caía dentro da linha de base; os cortes nunca
 * chegavam, e o FROID Explica respondia "não há dados de cortes específicos"
 * sobre oito cortes impressos na mesma tela.
 *
 * Aqui cada corte vira UMA linha: janela, amostras, tema, resumo e os mesmos
 * 33 rótulos da tabela, formatados como a tela os formata. Oito cortes cabem
 * em quatro mil caracteres, e o servidor os escreve numa seção própria do
 * prompt, fora do JSON truncável.
 *
 * Tema e resumo são CONTEÚDO (inferidos do que foi dito); as métricas são
 * MEDIDAS. `null` significa que não há resumo casado com o corte, nunca "".
 * `amostras` nulo significa contagem não registrada, nunca zero amostras.
 */
export interface CorteParaOExplica {
  corte: string;
  inicio_s: number;
  fim_s: number;
  duracao_s: number;
  amostras: number | null;
  tema: string | null;
  resumo: string | null;
  metricas: Record<string, string>;
}

export function corteParaOExplica(
  snapshot: MetricSnapshot,
  resumo?: ResumoDoCorte,
): CorteParaOExplica {
  const inicio = Number.isFinite(snapshot.startSecond) ? snapshot.startSecond : 0;
  const fim = Number.isFinite(snapshot.endSecond) ? snapshot.endSecond : inicio;
  const tema = String(resumo?.theme || "").trim();
  const texto = String(resumo?.summary || "").trim();
  return {
    corte: snapshot.label || `${Math.floor(inicio / 60)}-${Math.ceil(fim / 60)}min`,
    inicio_s: inicio,
    fim_s: fim,
    duracao_s: Math.max(0, fim - inicio),
    amostras: Number.isFinite(snapshot.sampleCount) ? snapshot.sampleCount : null,
    tema: tema || null,
    resumo: texto || null,
    metricas: Object.fromEntries(metricasParaOExplica(snapshot)),
  };
}

/**
 * A linha de base e os cortes, prontos para o contexto do FROID Explica.
 *
 * `janela` diz de que sessão são os cortes ("cortes desta sessao" no
 * relatório; "cortes da ultima sessao deste paciente" na ficha), pela mesma
 * razão de `contextoDaTabela`: a mesma tabela sob outro recorte é outro número.
 * Sem cortes, nenhuma chave é criada — ausência não vira lista vazia com cara
 * de "a sessão não teve cortes".
 */
export function contextoDosCortes(
  baseline: MetricSnapshot | null | undefined,
  cortes: MetricSnapshot[] | null | undefined,
  resumos: ResumoDoCorte[] | null | undefined,
  janela: string,
): Record<string, unknown> {
  const saida: Record<string, unknown> = {};
  if (baseline) {
    saida.panel_baseline = {
      janela: `${baseline.startSecond}-${baseline.endSecond} s`,
      amostras: Number.isFinite(baseline.sampleCount) ? baseline.sampleCount : null,
      metricas: Object.fromEntries(metricasParaOExplica(baseline)),
    };
  }
  const listaDeResumos = Array.isArray(resumos) ? resumos : [];
  const lista = (Array.isArray(cortes) ? cortes : []).map((corte) =>
    corteParaOExplica(corte, findSummaryForCut(corte, listaDeResumos)),
  );
  if (lista.length) {
    saida.panel_cuts = lista;
    saida.panel_cuts_window = janela;
  }
  return saida;
}

/**
 * O trecho FINAL de uma transcrição que cabe em `limite` caracteres, cortado
 * em linhas inteiras, e quantas linhas ficaram de fora.
 *
 * Até 20/10/2026 o corte era por caractere depois do carimbo: a primeira linha
 * do trecho saía sem [mm:ss] enquanto o contexto afirmava que todas têm
 * (padrão 2.4). Uma linha maior que o limite sozinha fica inteira: cortar
 * dentro dela recriaria o defeito.
 */
export function recorteFinalDaTranscricao(
  texto: string,
  limite: number,
): { texto: string; linhasOmitidas: number } {
  const linhas = String(texto || "").split("\n");
  if (linhas.length > 1 && linhas[linhas.length - 1] === "") linhas.pop();
  if (texto.length <= limite) return { texto, linhasOmitidas: 0 };
  const mantidas: string[] = [];
  let tamanho = 0;
  for (let i = linhas.length - 1; i >= 0; i -= 1) {
    const custo = linhas[i].length + (mantidas.length ? 1 : 0);
    if (mantidas.length > 0 && tamanho + custo > limite) break;
    mantidas.unshift(linhas[i]);
    tamanho += custo;
  }
  return { texto: mantidas.join("\n"), linhasOmitidas: linhas.length - mantidas.length };
}

/** mm:ss de um instante em segundos. */
function mmss(segundos: number): string {
  const total = Math.max(0, Math.floor(segundos));
  const minutos = Math.floor(total / 60);
  const resto = total % 60;
  return `${String(minutos).padStart(2, "0")}:${String(resto).padStart(2, "0")}`;
}

/**
 * A transcrição com o instante [mm:ss] abrindo cada linha, quando ele existe.
 *
 * O FROID não grava áudio; "reouça o trecho" nunca foi uma instrução
 * executável. O que existe é a transcrição, e desde a Fase 1 do Data-FROID
 * cada linha dela tem o segundo em que foi dita (`transcriptLineSeconds`,
 * 1:1 com as linhas). Com o instante na frente, "releia de 12:30 a 14:00"
 * passa a apontar para um lugar real.
 *
 * Sem a lista de segundos, ou com tamanho diferente do de linhas, nada é
 * inferido: as linhas saem sem instante e o contexto declara isso. A única
 * tolerância é a quebra de linha final, que não é uma linha.
 */
export function transcricaoParaOExplica(
  transcript: string,
  segundosPorLinha?: number[] | null,
): { session_transcript: string; transcript_timestamps: string } {
  const texto = String(transcript || "");
  const linhas = texto.split("\n");
  if (linhas.length > 1 && linhas[linhas.length - 1] === "") {
    linhas.pop();
  }
  const segundos = Array.isArray(segundosPorLinha) ? segundosPorLinha : [];
  const alinhado =
    linhas.length > 0 &&
    segundos.length === linhas.length &&
    segundos.every((s) => Number.isFinite(s));
  if (!alinhado) {
    return {
      session_transcript: texto,
      transcript_timestamps:
        "nao registrados neste relatorio: as linhas nao tem instante; aponte trechos pelo conteudo, nao por minuto",
    };
  }
  return {
    session_transcript: linhas
      .map((linha, i) => `[${mmss(segundos[i])}] ${linha}`)
      .join("\n"),
    transcript_timestamps:
      "cada linha abre com [mm:ss], o instante da sessao em que foi dita",
  };
}
