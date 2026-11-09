/**
 * Cadência da fala RELATIVA à referência do próprio paciente.
 *
 * Por que relativa, e não por limites fixos de palavras por minuto: o que a
 * literatura valida é a VARIAÇÃO dentro da mesma pessoa. Em pacientes
 * acompanhados ao longo do tratamento, a fala desacelera quando os sintomas
 * pioram e volta quando melhoram (Yamamoto et al., PLOS ONE 2020, contra a
 * HAMD-17; Mundt et al., Biological Psychiatry 2012). Limites absolutos iguais
 * para todos não têm essa validação: a velocidade basal varia de pessoa para
 * pessoa, e a própria calibração do FROID existe para não usar régua
 * universal.
 *
 * O que este indicador NÃO faz, por decisão do dono em 09/11/2026: não
 * classifica pânico, mania nem depressão. As faixas descrevem a velocidade
 * em relação à referência, nada mais. A leitura clínica é do profissional.
 *
 * Os cortes de 15% e 30% são escolha de produto, não valores validados — a
 * literatura consultada não traz corte por pessoa. Ficam aqui, num lugar só,
 * para que mudar seja uma linha.
 */

export const CORTES_CADENCIA = {
  /** A partir daqui a fala está acelerada ou lentificada. */
  moderado: 0.15,
  /** A partir daqui, muito acelerada ou muito lentificada. */
  acentuado: 0.3,
} as const;

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
  "Variação da velocidade de fala em relação à referência deste paciente. " +
  "A associação entre mudança de cadência e sintomas é observada em nível de " +
  "grupo na literatura; não constitui classificação deste paciente. " +
  "A leitura clínica é do profissional.";

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

/** "−32% vs. referência · lentificada", ou null sem apuração. */
export function formatarCadencia(leitura: LeituraCadencia | null): string | null {
  if (!leitura) return null;
  const pct = Math.round(leitura.variacao * 100);
  const sinal = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sinal}${Math.abs(pct)}% vs. referência · ${leitura.rotulo}`;
}
