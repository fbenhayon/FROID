/**
 * Cadência da fala RELATIVA à referência do próprio paciente — só a fala dele.
 *
 * Por que relativa, e não por limites fixos de palavras por minuto: o que a
 * literatura acompanha é a VARIAÇÃO dentro da mesma pessoa — a fala desacelera
 * quando a depressão piora (Yamamoto et al., PLOS ONE 2020, r = −0,378 com a
 * HAMD-17). Limites absolutos iguais para todos não têm validação para um
 * indivíduo: a velocidade basal varia muito entre pessoas saudáveis (de 111 a
 * 291 palavras por minuto em conversa, Yuan, Liberman e Cieri 2006).
 *
 * Decisões do dono, 11/11/2026:
 *  - a medida é feita SÓ sobre a fala do paciente, na referência e em cada
 *    intervalo (antes, a CADÊNCIA usava as palavras da janela inteira, e um
 *    corte em que o profissional falava mais baixava a cadência sem o
 *    paciente desacelerar);
 *  - as faixas absolutas da literatura (< 50 "afasia", < 100 "lentificação",
 *    ≥ 190 "aceleração") SAÍRAM do painel: a verificação das fontes mostrou
 *    que o 190 não tem fonte, o 100 é média de grupo tratada como corte e o 50
 *    é citação de segunda mão; e os números dos estudos (outra língua, outra
 *    tarefa, outra forma de contar) não são comparáveis aos do FROID. A
 *    literatura fica como CONTEXTO citado no site e no Explica, nunca como
 *    limite;
 *  - a referência dos 60 s iniciais é a referência DESTA SESSÃO, não o
 *    "normal" da pessoa: se o paciente entra nervoso ou deprimido, ela já nasce
 *    alterada. A cadência mostra reação dentro da sessão, não o estado em que
 *    ele chegou. A referência do histórico do paciente é a próxima etapa.
 *
 * Os cortes de 15% e 30% são escolha de produto, não valores validados — a
 * literatura verificada não traz corte de variação para um indivíduo. Ficam
 * aqui, num lugar só, até que o Data-FROID tenha volume para medir a variação
 * comum entre sessões.
 */

import {
  palavrasPorMinutoNaFalaDoPaciente,
  type SegmentoTranscrito,
} from "./medidas-do-corte";

export const CORTES_CADENCIA = {
  /** A partir daqui a fala está acelerada ou lentificada. */
  moderado: 0.15,
  /** A partir daqui, muito acelerada ou muito lentificada. */
  acentuado: 0.3,
} as const;

/** Janela da referência desta sessão: os 60 s iniciais (a calibração). */
export const SEGUNDOS_DA_REFERENCIA = 60;

export type FaixaCadencia =
  | "muito_acelerada"
  | "acelerada"
  | "na_referencia"
  | "lentificada"
  | "muito_lentificada";

export const ROTULO_FAIXA: Record<FaixaCadencia, string> = {
  muito_acelerada: "muito acelerada",
  acelerada: "acelerada",
  na_referencia: "na referência",
  lentificada: "lentificada",
  muito_lentificada: "muito lentificada",
};

export const RESSALVA_CADENCIA =
  "Variação da velocidade da fala do paciente — só a fala dele — em relação " +
  "aos 60 segundos iniciais desta sessão. Mostra reação dentro da sessão, não " +
  "o estado em que o paciente chegou: se ele entrou nervoso ou deprimido, a " +
  "referência já nasce alterada. Os limites de 15% e 30% são escolha do " +
  "produto; a literatura descreve diferenças entre grupos, não cortes para um " +
  "indivíduo. A leitura clínica é do profissional.";

export interface LeituraCadencia {
  /** Fração com sinal: -0,32 = 32% abaixo da referência. */
  variacao: number;
  faixa: FaixaCadencia;
  rotulo: string;
}

function numero(valor: unknown): number | null {
  if (valor === null || valor === undefined || valor === "") return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

/**
 * Nulo quando falta a medida atual ou a referência — ausência de apuração se
 * declara, não vira "na referência". Uma medida atual de zero é medida e vale;
 * referência zero ou negativa não permite variação relativa.
 */
export function lerCadencia(atual: unknown, referencia: unknown): LeituraCadencia | null {
  const a = numero(atual);
  const r = numero(referencia);
  if (a === null || r === null || r <= 0 || a < 0) return null;
  const variacao = (a - r) / r;
  const intensidade = Math.abs(variacao);
  let faixa: FaixaCadencia;
  if (intensidade < CORTES_CADENCIA.moderado) faixa = "na_referencia";
  else if (variacao > 0) faixa = intensidade >= CORTES_CADENCIA.acentuado ? "muito_acelerada" : "acelerada";
  else faixa = intensidade >= CORTES_CADENCIA.acentuado ? "muito_lentificada" : "lentificada";
  return { variacao, faixa, rotulo: ROTULO_FAIXA[faixa] };
}

const PREFIXO_DO_PACIENTE = /^\s*(PC|PAC)\s*-\s*/i;

/** Quantas palavras o paciente disse no intervalo — para a referência mostrar
 *  de quanta fala ela saiu. Poucas palavras, referência frágil: o número fica à
 *  vista em vez de um corte escolhido sem medida. */
export function palavrasDoPacienteNoIntervalo(
  segmentos: SegmentoTranscrito[],
  segundoInicial: number,
  segundoFinal: number,
): number {
  return (Array.isArray(segmentos) ? segmentos : [])
    .filter(
      (s) =>
        s &&
        s.elapsedSeconds >= segundoInicial &&
        s.elapsedSeconds < segundoFinal &&
        PREFIXO_DO_PACIENTE.test(String(s.text || "")),
    )
    .map((s) => String(s.text || "").replace(PREFIXO_DO_PACIENTE, ""))
    .join(" ")
    .split(/\s+/)
    .filter(Boolean).length;
}

export interface CadenciaNaFala {
  /** Palavras por minuto na fala do paciente nos 60 s iniciais. */
  referencia: number | null;
  /** Palavras do paciente que formaram a referência. */
  palavrasNaReferencia: number;
  /** Palavras por minuto na fala do paciente no intervalo pedido. */
  atual: number | null;
  leitura: LeituraCadencia | null;
}

/** Cadência do intervalo [inicio, fim) contra os 60 s iniciais, as duas
 *  medidas só na fala do paciente. */
export function cadenciaNaFalaDoPaciente(
  segmentos: SegmentoTranscrito[],
  segundoInicial: number,
  segundoFinal: number,
): CadenciaNaFala {
  const referencia = palavrasPorMinutoNaFalaDoPaciente(segmentos, 0, SEGUNDOS_DA_REFERENCIA);
  const atual = palavrasPorMinutoNaFalaDoPaciente(segmentos, segundoInicial, segundoFinal);
  return {
    referencia,
    palavrasNaReferencia: palavrasDoPacienteNoIntervalo(segmentos, 0, SEGUNDOS_DA_REFERENCIA),
    atual,
    leitura: lerCadencia(atual, referencia),
  };
}

/**
 * Segmentos da transcrição gravada num relatório: cada linha com o segundo em
 * que foi dita (`transcriptLineSeconds`, 1:1). Mesma regra de alinhamento do
 * contexto do Explica: sem a lista, ou com tamanho diferente, nada é inferido
 * e o resultado é nulo — a cadência do relatório sai "sem apuração".
 */
export function segmentosDoRelatorio(
  transcript: unknown,
  segundosPorLinha?: number[] | null,
): SegmentoTranscrito[] | null {
  const linhas = String(transcript || "").split("\n");
  if (linhas.length > 1 && linhas[linhas.length - 1] === "") linhas.pop();
  const segundos = Array.isArray(segundosPorLinha) ? segundosPorLinha : [];
  if (!linhas.length || segundos.length !== linhas.length || !segundos.every((s) => Number.isFinite(s))) {
    return null;
  }
  return linhas.map((text, i) => ({ text, elapsedSeconds: segundos[i] }));
}

/** "−32% vs. 60 s iniciais desta sessão · lentificada", ou null sem apuração. */
export function formatarCadencia(leitura: LeituraCadencia | null): string | null {
  if (!leitura) return null;
  const pct = Math.round(leitura.variacao * 100);
  const sinal = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sinal}${Math.abs(pct)}% vs. 60 s iniciais desta sessão · ${leitura.rotulo}`;
}

/** "112 p/min (referência: 128 p/min em 41 palavras)", ou null sem apuração. */
export function formatarFalaDoPaciente(c: CadenciaNaFala): string | null {
  if (c.atual === null) return null;
  const atual = `${Math.round(c.atual)} p/min`;
  if (c.referencia === null) return `${atual} (sem referência: o paciente não falou nos 60 s iniciais)`;
  return `${atual} (referência: ${Math.round(c.referencia)} p/min em ${c.palavrasNaReferencia} palavras)`;
}
