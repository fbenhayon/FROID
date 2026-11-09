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
 * As cinco faixas de CADÊNCIA descrevem só a velocidade em relação à
 * referência do próprio paciente. A indicação da situação descrita na
 * literatura vive à parte, em `zonaDaLiteratura`, sobre a medida na fala do
 * paciente (determinação do dono, 09/11/2026). A leitura clínica é do
 * profissional.
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

/**
 * Faixas de referência da LITERATURA para palavras por minuto NA FALA do
 * paciente (medidas-do-corte: palavrasPorMinutoNaFalaDoPaciente).
 *
 * Determinação do dono, 09/11/2026: o profissional vê, durante a sessão, a
 * indicação da situação descrita na literatura para a faixa em que a fala
 * está. É referência de grupo citada, não diagnóstico do paciente — o
 * contrato assinado diz que o FROID não diagnostica, e a leitura é do
 * profissional.
 *
 * Fontes (tabela enviada pelo dono em 09/11/2026):
 *  - Yamamoto et al., PLOS ONE 2020: depressão maior fala mais devagar que
 *    controles; r = −0,378 com HAMD-17 (VERIFICADO no artigo).
 *  - Cohen et al., Schizophrenia Research 2014 (meta-análise) e Frontiers in
 *    Psychiatry 2024: alogia/afeto plano ~97,8 PPM; pressão de fala > 190 PPM.
 *  - Estudos de fluência em afasia (NIH/PMC 2024): não fluente < 50 PPM.
 *  - Yuan, Liberman e Cieri: conversação adulta 150–190 PPM.
 *  O par "~96,0 vs. ~134,9 PPM" do TDM veio na tabela do dono atribuído a
 *  JMIR Mental Health 2024, mas NÃO foi localizado no artigo (Wadle et al.)
 *  nem em Yamamoto 2020; por isso o corte de 100 PPM é apresentado como da
 *  compilação, sem citar esse par.
 */
export type ZonaLiteratura = "afasia_nao_fluente" | "lentificacao" | "referencia" | "aceleracao";

export const CORTES_LITERATURA = { afasia: 50, lentificacao: 100, aceleracao: 190 } as const;

export const ROTULO_ZONA_LITERATURA: Record<ZonaLiteratura, string> = {
  afasia_nao_fluente: "< 50 · faixa descrita na afasia não fluente",
  lentificacao: "< 100 · lentificação descrita em retardo psicomotor depressivo e alogia",
  referencia: "100–189 · faixa conversacional",
  aceleracao: "≥ 190 · aceleração descrita em pressão de fala e mania",
};

export function zonaDaLiteratura(ppmNaFala: unknown): ZonaLiteratura | null {
  const n = numero(ppmNaFala);
  if (n === null || n <= 0) return null;
  if (n < CORTES_LITERATURA.afasia) return "afasia_nao_fluente";
  if (n < CORTES_LITERATURA.lentificacao) return "lentificacao";
  if (n < CORTES_LITERATURA.aceleracao) return "referencia";
  return "aceleracao";
}

/** "92 · < 100 · lentificação descrita em …", ou null sem apuração. */
export function formatarPpmNaFala(ppmNaFala: unknown): string | null {
  const zona = zonaDaLiteratura(ppmNaFala);
  if (!zona) return null;
  return `${Math.round(Number(ppmNaFala))} · ${ROTULO_ZONA_LITERATURA[zona]}`;
}

/** "−32% vs. referência · lentificada", ou null sem apuração. */
export function formatarCadencia(leitura: LeituraCadencia | null): string | null {
  if (!leitura) return null;
  const pct = Math.round(leitura.variacao * 100);
  const sinal = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sinal}${Math.abs(pct)}% vs. referência · ${leitura.rotulo}`;
}
