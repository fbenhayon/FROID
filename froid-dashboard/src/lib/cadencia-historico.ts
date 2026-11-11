/**
 * Referência de cadência pelo HISTÓRICO do próprio paciente.
 *
 * Decisão do dono, 11/11/2026. A referência dos 60 s iniciais é da sessão: se
 * o paciente entra nervoso ou deprimido, ela já nasce alterada, e a cadência
 * mostra reação dentro da sessão, não o estado em que ele chegou. Para o
 * estado, a régua é o próprio paciente ao longo do tempo: a MEDIANA das
 * palavras por minuto na fala dele nas sessões anteriores. É também o que a
 * literatura acompanha — a mesma pessoa, com a fala desacelerando quando a
 * depressão piora (Yamamoto et al., PLOS ONE 2020).
 *
 * A indicação é uma referência do tempo e do número de sessões realizadas: ela
 * se apura e se refina a cada sessão nova. Por isso o número de sessões e o
 * período vão sempre junto do valor — com uma sessão só, a mediana é aquela
 * sessão, e quem lê precisa saber disso. Nenhum mínimo é imposto: um corte
 * escolhido sem medida seria chute; o n à vista deixa o julgamento com o
 * profissional.
 *
 * Mediana, não média: uma sessão atípica (um dia de crise, uma transcrição
 * ruim) não arrasta a referência. Sessões sem fala do paciente apurada não
 * entram — ausência não vira zero.
 */

import { lerCadencia, segmentosDoRelatorio, type LeituraCadencia } from "./cadencia";
import { palavrasPorMinutoNaFalaDoPaciente } from "./medidas-do-corte";
import {
  getReportPatient,
  patientGroupKey,
  type PatientIdentity,
  type SessionReportRecord,
} from "./session-report";

export interface ReferenciaDoHistorico {
  /** Mediana das palavras por minuto na fala do paciente, ou null sem sessão. */
  mediana: number | null;
  /** Sessões anteriores com fala do paciente apurada. */
  sessoes: number;
  /** Data (ISO) da sessão mais antiga e da mais recente que entraram. */
  desde: string | null;
  ate: string | null;
}

/** Palavras por minuto na fala do paciente na sessão inteira, pela
 *  transcrição gravada com o instante de cada linha. Null sem apuração. */
export function falaDaSessao(report: SessionReportRecord): number | null {
  const segmentos = segmentosDoRelatorio(report.transcript, report.transcriptLineSeconds);
  if (!segmentos) return null;
  return palavrasPorMinutoNaFalaDoPaciente(segmentos, 0, Number.MAX_SAFE_INTEGER);
}

function chave(paciente: PatientIdentity | null | undefined): string {
  if (!paciente) return "";
  return patientGroupKey(paciente, "");
}

function mediana(valores: number[]): number | null {
  if (!valores.length) return null;
  const v = [...valores].sort((a, b) => a - b);
  const meio = Math.floor(v.length / 2);
  const m = v.length % 2 ? v[meio] : (v[meio - 1] + v[meio]) / 2;
  return Math.round(m * 10) / 10;
}

/**
 * Mediana das sessões ANTERIORES do mesmo paciente. `antesDe` limita às
 * sessões criadas antes daquela data (no relatório, a data da própria sessão);
 * `excluirSessao` tira a sessão em curso.
 */
export function referenciaDoHistorico(
  reports: SessionReportRecord[],
  paciente: PatientIdentity | null | undefined,
  opcoes: { antesDe?: string | null; excluirSessao?: string | null } = {},
): ReferenciaDoHistorico {
  const alvo = chave(paciente);
  const vazio: ReferenciaDoHistorico = { mediana: null, sessoes: 0, desde: null, ate: null };
  if (!alvo) return vazio;
  const limite = opcoes.antesDe ? new Date(opcoes.antesDe).getTime() : null;
  const vistos = new Set<string>();
  const medidas: Array<{ valor: number; quando: string }> = [];
  for (const r of Array.isArray(reports) ? reports : []) {
    if (!r || !r.sessionId || vistos.has(r.sessionId)) continue;
    vistos.add(r.sessionId);
    if (opcoes.excluirSessao && r.sessionId === opcoes.excluirSessao) continue;
    if (chave(getReportPatient(r)) !== alvo) continue;
    const quando = r.createdAt || "";
    if (limite !== null && !(new Date(quando).getTime() < limite)) continue;
    const valor = falaDaSessao(r);
    if (valor === null) continue;
    medidas.push({ valor, quando });
  }
  if (!medidas.length) return vazio;
  const datas = medidas.map((m) => m.quando).filter(Boolean).sort();
  return {
    mediana: mediana(medidas.map((m) => m.valor)),
    sessoes: medidas.length,
    desde: datas[0] || null,
    ate: datas[datas.length - 1] || null,
  };
}

/** Cadência de um valor contra a referência do histórico. */
export function lerContraHistorico(
  atual: number | null,
  historico: ReferenciaDoHistorico,
): LeituraCadencia | null {
  return lerCadencia(atual, historico.mediana);
}

function data(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("pt-BR");
}

/**
 * "−20% vs. mediana de 5 sessões anteriores (12/09/2026 a 04/11/2026) · lentificada",
 * ou a declaração de que ainda não há histórico.
 */
export function formatarHistorico(atual: number | null, historico: ReferenciaDoHistorico): string {
  if (!historico.sessoes || historico.mediana === null) {
    return "Sem histórico ainda: é a primeira sessão deste paciente com fala apurada. A referência começa a se formar a partir desta.";
  }
  const sessoes = historico.sessoes === 1 ? "1 sessão anterior" : `${historico.sessoes} sessões anteriores`;
  const periodo =
    historico.sessoes > 1 && historico.desde && historico.ate
      ? ` (${data(historico.desde)} a ${data(historico.ate)})`
      : historico.ate
        ? ` (${data(historico.ate)})`
        : "";
  const base = `${Math.round(historico.mediana)} p/min, mediana de ${sessoes}${periodo}`;
  const leitura = lerContraHistorico(atual, historico);
  if (!leitura) return `Referência do histórico: ${base}. Falta fala do paciente nesta sessão para comparar.`;
  const pct = Math.round(leitura.variacao * 100);
  const sinal = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sinal}${Math.abs(pct)}% vs. histórico · ${leitura.rotulo} (referência: ${base})`;
}

export const RESSALVA_HISTORICO =
  "Referência pelo histórico deste paciente: mediana das palavras por minuto na " +
  "fala dele nas sessões anteriores. É uma indicação que se apura e se refina a " +
  "cada sessão realizada — com poucas sessões, ela ainda é frágil, e o número de " +
  "sessões fica à vista para isso. Os limites de 15% e 30% são escolha do produto. " +
  "A leitura clínica é do profissional.";
